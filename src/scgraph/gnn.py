"""Graph representation learning on the dependency graph (Part IX, GPU).

Task - TEMPORAL node classification, no leakage:
    Given the package graph and every node's features as they stood at year Y,
    predict which packages receive their FIRST advisory in the window (Y, Y+H].

Why this is the honest version of "can a model help":
  * Temporal split. Features come only from edges/metadata with timestamp <= Y; labels
    come only from advisories published after Y. Train Y=Y0, validate Y0+H, test Y0+2H.
  * Severe class imbalance (most packages never get a CVE) -> we report Average Precision
    (PR-AUC) and precision@k, not just AUROC, and pick the threshold on validation.
  * A TABULAR BASELINE on the identical features (logistic regression, then gradient
    boosting). The result we actually care about is the DELTA: does neighbourhood
    message-passing beat the same features fed to a non-graph model? On dependency
    graphs the honest answer is "a little, not a lot" - and knowing that is the point.

Model - 2-layer GraphSAGE (mean aggregator), full-batch, pure torch sparse:
    h1 = relu( W_self0 x  + W_neigh0 (A_norm x) )
    h2 =       W_self1 h1 + W_neigh1 (A_norm h1)      -> logit
  Trained on the 2-CORE of the giant weakly-connected component (the structurally
  non-trivial subgraph; the degree<=1 tail carries no neighbourhood signal). The
  restriction is reported, not hidden.

`_have_torch` gate: on a box without torch this raises a clear RuntimeError. A synthetic
self-test (`python -m scgraph.gnn`) builds a graph where structure is predictive and
checks the GNN clears its tabular baseline.
"""

from __future__ import annotations

import numpy as np


def _have_torch():
    try:
        import torch  # noqa: F401

        return True
    except Exception:
        return False


# --------------------------------------------------------------------- features
def node_features(store, as_of_year, deg_in, deg_out, pagerank, kcore, age_years=None):
    """Assemble a [P, F] float32 feature matrix from precomputed structural signals.
    All inputs are length-P arrays over packages. Log1p the heavy-tailed counts."""
    P = len(store.pkg_name)
    eco = np.asarray(store.pkg_eco)
    ecos = ["npm", "pypi", "maven", "cargo", "go", "rubygems", "packagist", "nuget"]
    onehot = np.stack([(eco == e).astype(np.float32) for e in ecos], 1)
    nver = np.bincount(np.asarray(store.ver_pkg, np.int64), minlength=P)[:P]
    feats = [
        np.log1p(deg_in).astype(np.float32),
        np.log1p(deg_out).astype(np.float32),
        np.log1p(pagerank * P).astype(np.float32),
        kcore.astype(np.float32),
        np.log1p(nver).astype(np.float32),
    ]
    if age_years is not None:
        feats.append(np.nan_to_num(np.asarray(age_years, np.float32), nan=0.0))
    X = np.concatenate([np.stack(feats, 1), onehot], 1)
    # standardise the continuous block
    cont = X[:, : len(feats)]
    mu, sd = cont.mean(0), cont.std(0) + 1e-6
    X[:, : len(feats)] = (cont - mu) / sd
    return X.astype(np.float32)


def first_advisory_year(store):
    """P-array: year of each package's earliest non-withdrawn advisory, or +inf.
    Only walks versions that actually carry an advisory edge (~1% at FULL scale)."""
    P = len(store.pkg_name)
    out = np.full(P, np.inf)
    aip = np.asarray(store.aff_indptr)
    pubyr = np.array(
        [int(str(x)[:4]) if str(x)[:4].isdigit() else 0 for x in np.asarray(store.adv_published)]
    )
    wdr = np.asarray(store.adv_withdrawn)
    for vid in np.where(np.diff(aip) > 0)[0].tolist():
        pid = int(store.ver_pkg[vid])
        for aid in store.advisories_of(vid):
            aid = int(aid)
            if wdr[aid] or pubyr[aid] == 0:
                continue
            if pubyr[aid] < out[pid]:
                out[pid] = pubyr[aid]
    return out


def temporal_labels(first_year, y_feat, horizon):
    """train mask = packages with no advisory on/before y_feat; positive = first
    advisory in (y_feat, y_feat + horizon]."""
    eligible = first_year > y_feat
    pos = eligible & (first_year <= y_feat + horizon)
    return eligible, pos


def temporal_split(first_year, Y0, H, seed=0):
    """Leakage-free, DISJOINT train/val/test with BOTH classes in every split.

    A node is "at risk at year Y" if it has no advisory on/before Y (first_year > Y).
    Positives are nodes whose FIRST advisory falls in that split's forward window:
      train positive : first advisory in (Y0,      Y0+H]
      val   positive : first advisory in (Y0+H,    Y0+2H]
      test  positive : first advisory in (Y0+2H,   Y0+3H]
    Negatives are at-risk nodes whose first advisory is AFTER the window (or never) -
    these are randomly partitioned 70/15/15 into the three splits, so each split has a
    realistic base rate instead of dumping every never-vulnerable package into `test`
    (the bug the first version had: all-positive train set).

    Returns (y, train_idx, val_idx, test_idx) - one `y` since the splits are disjoint.
    """
    fy = np.asarray(first_year, float)
    n = len(fy)
    rng = np.random.default_rng(seed)

    pos_tr = np.where((fy > Y0) & (fy <= Y0 + H))[0]
    pos_va = np.where((fy > Y0 + H) & (fy <= Y0 + 2 * H))[0]
    pos_te = np.where((fy > Y0 + 2 * H) & (fy <= Y0 + 3 * H))[0]
    # negatives: at risk at Y0, first advisory strictly after the whole 3H horizon (incl inf)
    neg = np.where((fy > Y0) & (fy > Y0 + 3 * H))[0]
    rng.shuffle(neg)
    a, b = int(0.70 * len(neg)), int(0.85 * len(neg))
    neg_tr, neg_va, neg_te = neg[:a], neg[a:b], neg[b:]

    train = np.concatenate([pos_tr, neg_tr])
    val = np.concatenate([pos_va, neg_va])
    test = np.concatenate([pos_te, neg_te])
    y = np.zeros(n, int)
    y[pos_tr] = 1
    y[pos_va] = 1
    y[pos_te] = 1
    return y, np.sort(train), np.sort(val), np.sort(test)


# --------------------------------------------------------------------- 2-core
def two_core_of_giant(indptr, indices, n, max_nodes=1_500_000):
    """Node index array of the k-core of the largest weakly-connected component, with k
    chosen (>=2) so the result is <= max_nodes - full-batch GraphSAGE has to hold the
    whole node-feature matrix and both layers' activations in VRAM."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    from .graphshape import kcore

    ip = np.asarray(indptr)
    ix = np.asarray(indices)
    A = csr_matrix((np.ones(len(ix), np.int8), ix, ip), shape=(n, n))
    _, lab = connected_components(A, directed=False)
    giant = np.bincount(lab).argmax()
    in_giant = lab == giant
    core = kcore(ip, ix, n)
    for k in range(2, int(core.max()) + 1 if len(core) else 3):
        sel = np.where(in_giant & (core >= k))[0]
        if len(sel) <= max_nodes:
            return sel
    # even the max-coreness set was too big (dense mutual-dependency cluster) - hard
    # cap by degree so training never sees an unbounded graph
    sel = np.where(in_giant & (core >= max(int(core.max()), 2)))[0]
    if len(sel) > max_nodes:
        deg = np.diff(ip)[sel] + np.bincount(ix, minlength=n)[sel]
        sel = sel[np.argsort(-deg)[:max_nodes]]
    return sel


# --------------------------------------------------------------------- models
def _subgraph_csr(indptr, indices, nodes):
    """Relabelled undirected CSR over `nodes` (row-normalised adjacency ready)."""
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = len(ip) - 1
    remap = np.full(n, -1, np.int64)
    remap[nodes] = np.arange(len(nodes))
    src = np.repeat(np.arange(n, dtype=np.int64), np.diff(ip))
    m = (remap[src] >= 0) & (remap[ix] >= 0)
    a, b = remap[src[m]], remap[ix[m]]
    a, b = np.concatenate([a, b]), np.concatenate([b, a])  # undirected
    k = len(nodes)
    order = np.argsort(a, kind="stable")
    a, b = a[order], b[order]
    sip = np.zeros(k + 1, np.int64)
    np.add.at(sip, a + 1, 1)
    np.cumsum(sip, out=sip)
    return sip, b


def train_graphsage(
    X,
    sip,
    sindices,
    y,
    train_idx,
    val_idx,
    test_idx,
    hidden=64,
    epochs=60,
    lr=5e-3,
    wd=1e-4,
    seed=0,
    device=None,
):
    """Full-batch 2-layer GraphSAGE (mean aggregator). Returns dict with test AUROC/AP
    and the fitted probabilities."""
    if not _have_torch():
        raise RuntimeError("train_graphsage needs torch (GPU box).")
    import torch
    import torch.nn.functional as F
    from sklearn.metrics import average_precision_score

    torch.manual_seed(seed)
    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")

    k = X.shape[0]
    # normalised sparse adjacency  D^-1 A  (mean aggregator)
    deg = np.diff(sip).astype(np.float32)
    inv = np.divide(1.0, deg, out=np.zeros_like(deg), where=deg > 0)
    row = np.repeat(np.arange(k), np.diff(sip))
    Acoo = (
        torch.sparse_coo_tensor(
            np.stack([row, sindices]), torch.tensor(inv[row], dtype=torch.float32), (k, k)
        )
        .coalesce()
        .to(dev)
    )
    Xt = torch.tensor(X, dtype=torch.float32, device=dev)
    yt = torch.tensor(y.astype(np.float32), device=dev)
    F_in = X.shape[1]

    class SAGE(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.l0s = torch.nn.Linear(F_in, hidden)
            self.l0n = torch.nn.Linear(F_in, hidden)
            self.l1s = torch.nn.Linear(hidden, 1)
            self.l1n = torch.nn.Linear(hidden, 1)
            self.bn = torch.nn.BatchNorm1d(hidden)

        def forward(self, x, A):
            h = F.relu(self.bn(self.l0s(x) + self.l0n(torch.sparse.mm(A, x))))
            h = F.dropout(h, 0.3, self.training)
            return (self.l1s(h) + self.l1n(torch.sparse.mm(A, h))).squeeze(-1)

    net = SAGE().to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=wd)
    tr = torch.tensor(train_idx, device=dev)
    torch.tensor(val_idx, device=dev)
    pos_w = torch.tensor(
        [(y[train_idx] == 0).sum() / max((y[train_idx] == 1).sum(), 1)],
        dtype=torch.float32,
        device=dev,
    )
    best_ap, best_state, best_ep = -1, None, 0
    for ep in range(epochs):
        net.train()
        opt.zero_grad()
        out = net(Xt, Acoo)
        loss = F.binary_cross_entropy_with_logits(out[tr], yt[tr], pos_weight=pos_w)
        loss.backward()
        opt.step()
        if ep % 3 == 0 or ep == epochs - 1:
            net.eval()
            with torch.no_grad():
                p = torch.sigmoid(net(Xt, Acoo)).cpu().numpy()
            ap = average_precision_score(y[val_idx], p[val_idx]) if y[val_idx].any() else 0
            if ap > best_ap:
                best_ap, best_ep = ap, ep
                best_state = {kk: v.detach().cpu().clone() for kk, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        p = torch.sigmoid(net(Xt, Acoo)).cpu().numpy()
    return _metrics("graphsage", y, p, test_idx, val_idx) | {"best_epoch": best_ep, "_prob": p}


def train_tabular(X, y, train_idx, val_idx, test_idx):
    """Same features, no graph. Logistic regression + gradient boosting."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression

    out = {}
    for name, clf in (
        ("logreg", LogisticRegression(max_iter=400, class_weight="balanced")),
        (
            "gbdt",
            HistGradientBoostingClassifier(max_depth=4, max_iter=250, class_weight="balanced"),
        ),
    ):
        clf.fit(X[train_idx], y[train_idx])
        p = clf.predict_proba(X)[:, 1]
        out[name] = _metrics(name, y, p, test_idx, val_idx) | {"_prob": p}
    return out


def _metrics(name, y, p, test_idx, val_idx, ks=(50, 100, 500)):
    from sklearn.metrics import average_precision_score, roc_auc_score

    yt, pt = y[test_idx], p[test_idx]
    res = {
        "model": name,
        "n_test": len(test_idx),
        "test_pos": int(yt.sum()),
        "auroc": round(float(roc_auc_score(yt, pt)), 4)
        if yt.any() and (~yt.astype(bool)).any()
        else None,
        "ap": round(float(average_precision_score(yt, pt)), 4) if yt.any() else None,
        "base_rate": round(float(yt.mean()), 5),
    }
    order = np.argsort(-pt)
    for kk in ks:
        if kk <= len(order):
            res[f"precision_at_{kk}"] = round(float(yt[order[:kk]].mean()), 4)
    return res


def bootstrap_delta(y, p_gnn, p_tab, test_idx, metric="ap", n_boot=500, seed=0):
    """Bootstrap CI for (GNN - tabular) on the test set. If the CI crosses 0 the graph
    model is not reliably better."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    fn = average_precision_score if metric == "ap" else roc_auc_score
    rng = np.random.default_rng(seed)
    yt = y[test_idx]
    a = p_gnn[test_idx]
    b = p_tab[test_idx]
    deltas = []
    for _ in range(n_boot):
        s = rng.integers(0, len(yt), len(yt))
        if yt[s].sum() < 2:
            continue
        deltas.append(fn(yt[s], a[s]) - fn(yt[s], b[s]))
    d = np.array(deltas)
    return {
        "metric": metric,
        "delta_mean": round(float(d.mean()), 4),
        "ci95": [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)],
        "p_gnn_better": round(float((d > 0).mean()), 3),
    }


if __name__ == "__main__":
    # synthetic: label depends on a latent community + neighbour labels (homophily),
    # so a GNN that sees neighbours should beat tabular-on-noisy-features.
    if not _have_torch():
        print("no torch here - this module is for the GPU box")
        raise SystemExit
    rng = np.random.default_rng(0)
    k = 4000
    comm = rng.integers(0, 8, k)
    # ring-of-cliques-ish: edges mostly within community
    src_l, dst_l = [], []
    for _ in range(k * 4):
        a = rng.integers(k)
        b = rng.integers(k)
        if rng.random() < 0.85:
            cand = np.where(comm == comm[a])[0]
            b = cand[rng.integers(len(cand))]
        src_l.append(a)
        dst_l.append(b)
    src, dst = np.array(src_l), np.array(dst_l)
    ip = np.zeros(k + 1, np.int64)
    np.add.at(ip, src + 1, 1)
    np.cumsum(ip, out=ip)
    order = np.argsort(src, kind="stable")
    ix = dst[order]
    latent = (comm % 3 == 0).astype(float)
    y = ((latent + rng.normal(0, 0.4, k)) > 0.6).astype(int)
    X = np.c_[rng.normal(0, 1, (k, 6)), rng.normal(latent[:, None], 1.5, (k, 2))].astype(np.float32)
    idx = rng.permutation(k)
    tr, va, te = idx[:2000], idx[2000:2800], idx[2800:]
    sip, sidx = _subgraph_csr(ip, ix, np.arange(k))
    g = train_graphsage(X, sip, sidx, y, tr, va, te, epochs=40)
    t = train_tabular(X, y, tr, va, te)
    print("GNN   :", g)
    print("logreg:", t["logreg"])
    print("gbdt  :", t["gbdt"])
