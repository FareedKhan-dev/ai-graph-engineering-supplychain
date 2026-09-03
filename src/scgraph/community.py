"""Community structure of the package graph: does the dependency network break into
coherent sub-ecosystems, and where are the seams?

  label_propagation   Raghavan-Albert-Kumara near-linear community detection. Each node
                      adopts the label most common among its neighbours; iterate to a
                      fixed point. O(E) per sweep, a handful of sweeps. Asynchronous
                      updates + a random tie-break + a seeded permutation so it is
                      deterministic given `seed`.

  modularity          Newman-Girvan Q of a labelling: the fraction of edges inside
                      communities minus the expected fraction under a degree-preserving
                      null model. Q > ~0.3 means real structure; Q ~ 0 means the
                      partition is no better than random.

  bridge_edges        edges whose endpoints are in different communities - the
                      integration points between sub-ecosystems (a vulnerability here
                      crosses a community boundary).

  ecosystem_purity    for each community, the entropy / dominant-ecosystem share of its
                      members - are communities just "npm" vs "pypi", or do they cut
                      across (a "web framework" community spanning several ecosystems)?

For a reader: community detection is the unsupervised counterpart to the k-core /
centrality analysis - instead of "how central", it asks "which neighbourhood", and the
modularity number tells you whether that question even has an answer for this graph.
"""

from __future__ import annotations

import contextlib

import numpy as np


def _undirected(indptr, indices, n):
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    src = np.repeat(np.arange(n, dtype=np.int64), np.diff(ip))
    a = np.concatenate([src, ix])
    b = np.concatenate([ix, src])
    uip = np.zeros(n + 1, np.int64)
    np.add.at(uip, a + 1, 1)
    np.cumsum(uip, out=uip)
    order = np.argsort(a, kind="stable")
    return uip, b[order].astype(np.int64)


def label_propagation(indptr, indices, n=None, max_sweeps=25, seed=0, min_component=1, big=400_000):
    """Return an int label per node (a community id) + the sweep count. Isolated nodes
    keep singleton labels. Deterministic given seed. Above `big` nodes, use igraph's C
    implementation of the same algorithm (Raghavan-Albert-Kumara LPA); the pure-Python
    sweep loop below is the teaching reference and is only fast at SMOKE scale."""
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = n or len(ip) - 1

    if n > big:
        try:
            import igraph as _ig

            src = np.repeat(np.arange(n, dtype=np.int64), np.diff(ip))
            g = _ig.Graph(n=int(n), edges=np.stack([src, ix], 1), directed=False)
            g.simplify()
            with contextlib.suppress(Exception):
                _ig.set_random_number_generator(None)
            import random as _r

            _r.seed(seed)
            vc = g.community_label_propagation()
            lab = np.asarray(vc.membership, np.int64)
            _, lab = np.unique(lab, return_inverse=True)
            return lab.astype(np.int64), -1  # -1 sweeps = igraph LPA
        except Exception as e:
            print(f"[community] igraph LPA unavailable ({e}); pure-Python sweeps")

    uip, uix = _undirected(ip, ix, n)
    deg = np.diff(uip)
    label = np.arange(n, dtype=np.int64)
    rng = np.random.default_rng(seed)
    active = np.where(deg >= min_component)[0]
    sweep = 0
    for sweep in range(1, max_sweeps + 1):  # noqa: B007 - value is the sweep count, used below
        rng.shuffle(active)
        changed = 0
        for v in active:
            a, b = uip[v], uip[v + 1]
            if b == a:
                continue
            nb = uix[a:b]
            lab = label[nb]
            # most frequent neighbour label, random tie-break
            u, c = np.unique(lab, return_counts=True)
            best = u[c == c.max()]
            newl = best[0] if len(best) == 1 else best[rng.integers(len(best))]
            if newl != label[v]:
                label[v] = newl
                changed += 1
        if changed == 0:
            break
    # compactify labels
    _, label = np.unique(label, return_inverse=True)
    return label.astype(np.int64), sweep


def modularity(indptr, indices, label, n=None):
    """Newman-Girvan Q on the undirected graph. Q = sum_c (e_cc - a_c^2) where e_cc is
    the fraction of edge-endpoints inside community c and a_c the fraction touching it."""
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = n or len(ip) - 1
    uip, uix = _undirected(ip, ix, n)
    m2 = len(uix)  # 2|E|
    if m2 == 0:
        return 0.0
    src = np.repeat(np.arange(n, dtype=np.int64), np.diff(uip))
    ls, ld = label[src], label[uix]
    intra = np.bincount(ls[ls == ld], minlength=label.max() + 1)
    deg = np.diff(uip)
    a_c = np.bincount(label, weights=deg, minlength=label.max() + 1) / m2
    e_cc = intra / m2
    return float((e_cc - a_c**2).sum())


def community_report(store, label, sweeps=None, topk=12):
    """Summarise: #communities, size distribution, modularity, ecosystem purity of the
    biggest, and the cross-community edge fraction."""
    P = len(store.pkg_name)
    sizes = np.bincount(label)
    order = np.argsort(-sizes)
    eco = np.asarray(store.pkg_eco)
    Q = modularity(store.pkgdep_indptr, store.pkgdep_indices, label, P)
    src = np.repeat(np.arange(P, dtype=np.int64), np.diff(np.asarray(store.pkgdep_indptr)))
    dst = np.asarray(store.pkgdep_indices, np.int64)
    cross = float((label[src] != label[dst]).mean()) if len(dst) else 0.0
    comms = []
    for c in order[:topk]:
        if sizes[c] < 3:
            break
        members = np.where(label == c)[0]
        ec = eco[members]
        u, cnt = np.unique(ec, return_counts=True)
        dom = u[cnt.argmax()]
        comms.append(
            {
                "id": int(c),
                "size": int(sizes[c]),
                "dominant_ecosystem": str(dom),
                "purity": round(float(cnt.max() / cnt.sum()), 3),
                "sample": [str(store.pkg_name[m]) for m in members[:6]],
            }
        )
    return {
        "n_communities": int((sizes >= 3).sum()),
        "largest": int(sizes.max()),
        "modularity": round(Q, 4),
        "cross_community_edge_frac": round(cross, 4),
        "sweeps": sweeps,
        "communities": comms,
    }


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    P = len(S.pkg_name)
    lab, sw = label_propagation(S.pkgdep_indptr, S.pkgdep_indices, P, seed=1)
    rep = community_report(S, lab, sweeps=sw)
    print(
        f"communities (>=3): {rep['n_communities']:,}   largest {rep['largest']:,}   "
        f"Q={rep['modularity']}   cross-edges {rep['cross_community_edge_frac'] * 100:.1f}%   "
        f"({sw} sweeps)"
    )
    for c in rep["communities"][:8]:
        print(
            f"  #{c['id']:<5} n={c['size']:<5} {c['dominant_ecosystem']:<9} "
            f"purity={c['purity']}  {c['sample'][:4]}"
        )
