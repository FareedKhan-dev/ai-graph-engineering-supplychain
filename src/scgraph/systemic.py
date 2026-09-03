"""Systemic risk: which packages, if compromised, expose the most of the ecosystem?

This is the xz-utils question asked at scale. Three lenses, all on the package graph:

  pagerank_rev     reverse PageRank on the "is depended on by" graph -> influence.
                   Power iteration = repeated sparse mat-vec; ~20 iters; O(E) each.
  blast_radius     for each package, |{roots that transitively depend on it}| via a
                   reverse-BFS frontier over all packages at once (vectorised).
  compromise_sim   counterfactual: mark package X malicious, propagate "exposed" along
                   reverse edges, count reachable application packages. The honest
                   upper bound on a single-maintainer compromise.

For a reader: exact betweenness is O(VE) and infeasible here; reverse PageRank +
reachable-set size are the affordable proxies for "load-bearing", and they agree on
the head of the distribution (checked in the notebook).
"""

from __future__ import annotations

import numpy as np


def pagerank_rev(indptr_rev, indices_rev, n=None, damping=0.85, iters=40, tol=1e-9):
    """PageRank on the REVERSED graph (edge u->v means 'v is depended on by u'),
    so mass flows toward widely-depended-on infrastructure."""
    indptr = np.asarray(indptr_rev, np.int64)
    indices = np.asarray(indices_rev, np.int64)
    n = n or len(indptr) - 1
    outdeg = np.diff(indptr)
    dangling = outdeg == 0
    r = np.full(n, 1.0 / n)
    # CSR row = source; scatter-add contributions to targets
    src = np.repeat(np.arange(n), outdeg)
    for _ in range(iters):
        contrib = np.zeros(n)
        share = np.where(dangling, 0.0, r / np.maximum(outdeg, 1))
        np.add.at(contrib, indices, share[src])
        leaked = r[dangling].sum()
        r_new = (1 - damping) / n + damping * (contrib + leaked / n)
        if np.abs(r_new - r).sum() < tol:
            r = r_new
            break
        r = r_new
    return r / r.sum()


def blast_radius(indptr_fwd, indices_fwd, roots, n=None):
    """|{roots whose forward dependency closure contains p}| for every package p.
    `roots` = application package ids. Forward CSR: p -> its dependencies. One BFS
    per root; each marks every package it can reach and increments its counter.
    Uses scipy.csgraph (C BFS) when available - the pure-Python deque version is
    O(R * E_reachable) and too slow past ~1M nodes."""
    indptr = np.asarray(indptr_fwd, np.int64)
    indices = np.asarray(indices_fwd, np.int64)
    n = n or len(indptr) - 1
    radius = np.zeros(n, np.int64)
    try:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import breadth_first_order

        A = csr_matrix((np.ones(len(indices), np.int8), indices, indptr), shape=(n, n))
        for a in roots:
            order = breadth_first_order(A, int(a), directed=True, return_predecessors=False)
            radius[np.asarray(order)] += 1
        return radius
    except Exception:
        from collections import deque

        for a in roots:
            seen = np.zeros(n, bool)
            seen[a] = True
            q = deque([int(a)])
            while q:
                v = q.popleft()
                for u in indices[indptr[v] : indptr[v + 1]]:
                    if not seen[u]:
                        seen[u] = True
                        q.append(int(u))
            radius[seen] += 1
        return radius


def compromise_sim(indptr_rev, indices_rev, victim, roots_mask, n=None):
    """Mark `victim` compromised; propagate along reverse edges (dependents);
    return the set of reached packages and the count that are applications."""
    from collections import deque

    indptr = np.asarray(indptr_rev, np.int64)
    indices = np.asarray(indices_rev, np.int64)
    n = n or len(indptr) - 1
    seen = np.zeros(n, bool)
    seen[victim] = True
    q = deque([int(victim)])
    while q:
        v = q.popleft()
        for u in indices[indptr[v] : indptr[v + 1]]:
            if not seen[u]:
                seen[u] = True
                q.append(int(u))
    np.where(seen)[0]
    return {
        "reached": int(seen.sum()),
        "reached_apps": int((seen & roots_mask).sum()),
        "reached_frac": float(seen.mean()),
    }


def gini(x):
    x = np.sort(np.asarray(x, float))
    if x.sum() == 0:
        return 0.0
    idx = np.arange(1, len(x) + 1)
    return float((2 * np.sum(idx * x) / (len(x) * x.sum())) - (len(x) + 1) / len(x))


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    P = len(S.pkg_name)
    pr = pagerank_rev(S.pkgrev_indptr, S.pkgrev_indices, P)
    top = np.argsort(-pr)[:15]
    print("top packages by reverse-PageRank (systemic influence):")
    for i in top:
        print(
            f"  {pr[i]:.5f}  {S.pkg_eco[i]}/{S.pkg_name[i]}  "
            f"(dependents={len(S.pkg_dependents(i))})"
        )
    print(f"\nPageRank Gini: {gini(pr):.3f}  (1.0 = all mass on one package)")
