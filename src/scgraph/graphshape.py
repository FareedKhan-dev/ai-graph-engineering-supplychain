"""What KIND of graph is the dependency graph? (the network-science layer)

Every function operates on a CSR pair (indptr, indices) so it scales from the SMOKE
sample to a 100M-node package graph unchanged. The point, for a reader learning graph
engineering: the *structure* of the graph dictates which algorithms are affordable and
which questions are even answerable.

  degree_stats        in/out degree; heavy-tailed? -> power-law MLE + KS test
  kcore               coreness of every node by O(E) bucket-peeling
  components          weak / strong connected components (SCC == dependency cycles)
  dag_depth           longest path (only defined if the graph is a DAG) + level sizes
  sample_distances    BFS from K sampled sources -> effective diameter, path-length CDF
"""

from __future__ import annotations

import numpy as np


def _deg(indptr):
    return np.diff(np.asarray(indptr)).astype(np.int64)


def degree_stats(indptr_out, indptr_in):
    dout, din = _deg(indptr_out), _deg(indptr_in)
    return {
        "n": len(dout),
        "out": _summary(dout),
        "in": _summary(din),
        "out_powerlaw": powerlaw_mle(din),  # in-degree = "how many depend on me"
    }


def _summary(d):
    d = d[d >= 0]
    return {
        "mean": float(d.mean()),
        "median": float(np.median(d)),
        "p90": float(np.percentile(d, 90)),
        "p99": float(np.percentile(d, 99)),
        "max": int(d.max()),
        "zero_frac": float((d == 0).mean()),
    }


def powerlaw_mle(deg, xmin=2):
    """Clauset-Shalizi-Newman MLE for a discrete power law P(k) ~ k^-alpha, k>=xmin,
    plus a crude KS distance to the fitted CDF. Not a full goodness-of-fit test, but
    enough to say 'heavy-tailed, alpha ~ 2.x' the way network-science papers do."""
    x = np.asarray(deg, float)
    x = x[x >= xmin]
    if len(x) < 50:
        return {"alpha": None, "xmin": xmin, "n_tail": len(x), "ks": None}
    alpha = 1 + len(x) / np.sum(np.log(x / (xmin - 0.5)))
    # KS vs fitted
    xs = np.sort(x)
    cdf_emp = np.arange(1, len(xs) + 1) / len(xs)
    # discrete power-law CDF approx via Hurwitz zeta ratio (normalised on observed support)
    ks_grid = np.unique(xs)
    w = ks_grid.astype(float) ** (-alpha)
    cdf_fit_grid = np.cumsum(w) / w.sum()
    cdf_fit = np.interp(xs, ks_grid, cdf_fit_grid)
    ks = float(np.max(np.abs(cdf_emp - cdf_fit)))
    return {
        "alpha": round(float(alpha), 3),
        "xmin": xmin,
        "n_tail": len(x),
        "ks": round(ks, 3),
    }


def powerlaw_gof(deg, xmin=2, n_boot=250, seed=0):
    """Clauset-Shalizi-Newman goodness-of-fit: bootstrapped p-value for the hypothesis
    that the degree tail (>= xmin) is power-law. p = fraction of synthetic power-law
    datasets (same alpha, same n) whose KS distance to their own fit >= the observed
    KS. p >= 0.1 -> plausible; p < 0.1 -> reject. The KS number alone can't do this."""
    rng = np.random.default_rng(seed)
    d = np.asarray(deg, float)
    d = d[d >= 1]
    tail = d[d >= xmin]
    if len(tail) < 50:
        return {"alpha": None, "p_value": None, "n_boot": 0, "verdict": "too few tail points"}

    from scipy.special import zeta  # Hurwitz zeta

    def _fit(x):
        x = x[x >= xmin]
        return (1 + len(x) / np.sum(np.log(x / (xmin - 0.5)))) if len(x) >= 50 else None

    def _ks(x, alpha):
        # exact discrete power-law CDF: P(X<=k) = 1 - zeta(alpha,k+1)/zeta(alpha,xmin)
        xs = np.sort(x[x >= xmin])
        if len(xs) < 2:
            return 1.0
        norm = zeta(alpha, float(xmin))
        vals = np.unique(xs)
        cdf_fit_at = 1.0 - zeta(alpha, vals + 1) / norm
        fit = np.interp(xs, vals, cdf_fit_at)
        emp = np.searchsorted(xs, xs, side="right") / len(xs)  # empirical CDF S(x)
        return float(np.max(np.abs(emp - fit)))

    alpha = _fit(d)
    ks_obs = _ks(d, alpha)
    n = len(tail)
    ge = 0
    for _ in range(n_boot):
        u = rng.random(n)
        syn = np.floor((xmin - 0.5) * (1 - u) ** (-1 / (alpha - 1)) + 0.5)
        syn = syn[np.isfinite(syn) & (syn >= xmin)]
        a2 = _fit(syn)
        if a2 is not None and _ks(syn, a2) >= ks_obs:
            ge += 1
    p = ge / n_boot
    return {
        "alpha": round(float(alpha), 3),
        "xmin": xmin,
        "n_tail": int(n),
        "ks_observed": round(ks_obs, 4),
        "p_value": round(p, 3),
        "n_boot": n_boot,
        "verdict": (
            "power law not rejected (p>=0.1)"
            if p >= 0.1
            else "power law REJECTED (p<0.1); lognormal / cutoff more likely"
        ),
    }


def kcore(indptr, indices, n=None):
    """Coreness of every node (undirected). Batagelj-Zaversnik O(E) bucket peeling.
    Above ~1M nodes the pure-Python peel is slow; use igraph's C implementation if
    it is importable (same result, ~100x faster)."""
    indptr = np.asarray(indptr)
    indices = np.asarray(indices)
    n = n or len(indptr) - 1
    if n > 1_000_000:
        try:
            import igraph as _ig

            src = np.repeat(np.arange(n, dtype=np.int64), np.diff(indptr))
            E = np.stack([src, np.asarray(indices, np.int64)], 1)
            g = _ig.Graph(n=int(n), edges=E, directed=False)
            return np.asarray(g.coreness(mode="all"), np.int64)
        except Exception as e:
            print(f"[kcore] igraph fast-path unavailable ({e}); pure-Python peel")
    # symmetrise degree
    deg = _deg(indptr).copy()
    inc = np.bincount(indices, minlength=n)
    deg = deg + inc  # rough undirected degree
    core = np.zeros(n, np.int64)
    order = np.argsort(deg, kind="stable")
    pos = np.empty(n, np.int64)
    pos[order] = np.arange(n)
    d = deg.copy()
    bins = np.bincount(d, minlength=(d.max() + 2) if len(d) else 2)
    start = np.zeros(len(bins), np.int64)
    np.cumsum(bins[:-1], out=start[1:])
    vert = order.copy()
    binstart = start.copy()
    for i in range(n):
        v = vert[i]
        core[v] = d[v]
        for u in _neigh(indptr, indices, v):
            if d[u] > d[v]:
                du, pu = d[u], pos[u]
                pw = binstart[du]
                w = vert[pw]
                if u != w:
                    pos[u], pos[w] = pw, pu
                    vert[pu], vert[pw] = w, u
                binstart[du] += 1
                d[u] -= 1
    return core


def _neigh(indptr, indices, v):
    return indices[indptr[v] : indptr[v + 1]]


def components(n, indptr, indices, strong=False):
    """Wraps scipy.sparse.csgraph. strong=True -> SCCs; an SCC of size>1 is a
    dependency cycle (impossible in a RESOLVED graph, common in DECLARED npm)."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    indptr = np.asarray(indptr)
    indices = np.asarray(indices)
    A = csr_matrix((np.ones(len(indices), np.int8), indices, indptr), shape=(n, n))
    k, lab = connected_components(A, directed=strong, connection="strong" if strong else "weak")
    sizes = np.bincount(lab)
    return {
        "n_components": int(k),
        "largest": int(sizes.max()),
        "largest_frac": float(sizes.max() / n),
        "n_nontrivial": int((sizes > 1).sum()),
        "singletons": int((sizes == 1).sum()),
        "cycle_members": int(sizes[sizes > 1].sum()) if strong else None,
    }


def dag_depth(n, indptr, indices):
    """Longest path length per node via topological DP. Assumes a DAG (call
    components(strong=True) first; if SCCs exist this is on the condensation)."""
    indptr = np.asarray(indptr)
    indices = np.asarray(indices)
    indeg = np.bincount(indices, minlength=n)
    from collections import deque

    q = deque(np.where(indeg == 0)[0].tolist())
    depth = np.zeros(n, np.int64)
    seen = 0
    while q:
        v = q.popleft()
        seen += 1
        for u in indices[indptr[v] : indptr[v + 1]]:
            if depth[v] + 1 > depth[u]:
                depth[u] = depth[v] + 1
            indeg[u] -= 1
            if indeg[u] == 0:
                q.append(int(u))
    lvl = np.bincount(depth)
    return {
        "is_dag": seen == n,
        "max_depth": int(depth.max()),
        "level_sizes": lvl.tolist(),
        "mean_depth": float(depth.mean()),
    }


def sample_distances(n, indptr, indices, k=200, seed=0):
    """BFS from k random sources; return the path-length histogram + effective
    diameter (90th percentile). Exact diameter is O(VE) - infeasible at scale.
    Uses scipy.csgraph (C BFS) when available; falls back to a Python deque."""
    rng = np.random.default_rng(seed)
    indptr = np.asarray(indptr)
    indices = np.asarray(indices)
    src = rng.choice(n, size=min(k, n), replace=False)
    hist = np.zeros(64, np.int64)
    try:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import shortest_path

        A = csr_matrix((np.ones(len(indices), np.int8), indices, indptr), shape=(n, n))
        # a full (k x n) distance matrix is k*n*8 bytes - chunk the sources so it stays small
        chunk = max(1, min(len(src), 24_000_000 // max(n, 1) + 1))
        for i in range(0, len(src), chunk):
            D = shortest_path(A, method="D", unweighted=True, indices=src[i : i + chunk])
            d = D[np.isfinite(D) & (D > 0)].astype(np.int64)
            hist += np.bincount(np.minimum(d, 63), minlength=64)
            del D
    except Exception:
        from collections import deque

        for s in src:
            dist = np.full(n, -1, np.int32)
            dist[s] = 0
            q = deque([int(s)])
            while q:
                v = q.popleft()
                for u in indices[indptr[v] : indptr[v + 1]]:
                    if dist[u] < 0:
                        dist[u] = dist[v] + 1
                        if dist[u] < 64:
                            hist[dist[u]] += 1
                        q.append(int(u))
    tot = int(hist.sum())
    cdf = np.cumsum(hist) / max(tot, 1)
    eff = int(np.searchsorted(cdf, 0.9))
    return {
        "reachable_pairs": tot,
        "hist": hist[:20].tolist(),
        "effective_diameter_p90": eff,
        "mean_path": float((np.arange(64) * hist).sum() / max(tot, 1)),
    }


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    P = len(S.pkg_name)
    print("package-graph degree stats:")
    ds = degree_stats(S.pkgdep_indptr, S.pkgrev_indptr)
    print(
        f"  n={ds['n']:,}  in-degree: mean {ds['in']['mean']:.1f} max {ds['in']['max']}"
        f"  power-law alpha={ds['out_powerlaw']['alpha']} (KS {ds['out_powerlaw']['ks']})"
    )
    print("SCC (cycles):", components(P, S.pkgdep_indptr, S.pkgdep_indices, strong=True))
    print("DAG depth   :", dag_depth(P, S.pkgdep_indptr, S.pkgdep_indices))
