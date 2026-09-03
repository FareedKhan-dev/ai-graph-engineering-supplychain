"""The dependency graph is an *evolving* object. Snapshots + the laws of graph growth.

Libraries.io gives every version a publish date. Assign each RESOLVES_TO edge the
publish date of its source version (the edge came into being when that version shipped)
and you can reconstruct the graph as it stood at any past instant, then measure how it
grew. Four classical results (Leskovec-Kleinberg-Faloutsos, "Graphs over Time", KDD'05,
and Barabasi-Albert) that a dependency graph either obeys or interestingly violates:

  densification_law     |E(t)| ~ |V(t)|^a. a = 1 is constant average degree; a > 1 is
                        *densification* - the graph gets denser as it grows. Software
                        ecosystems densify (each new package depends on more existing
                        ones than the last). Fit a by OLS on log|V| vs log|E|.

  shrinking_diameter    effective diameter as a function of t. LKF's surprise: it goes
                        *down* (or flattens) as the graph grows, not up. Measured by BFS
                        sampling per snapshot.

  attachment_kernel     P(a new edge attaches to an existing node of degree k) as a
                        function of k. Barabasi-Albert predicts linear ("preferential
                        attachment"): rich get richer. We bin by degree and measure the
                        exponent - dependency graphs are usually super-linear at the head
                        (a package that just got popular gets adopted even faster).

  component_growth      size of the largest weakly-connected component over t - when did
                        the ecosystem "percolate" into one giant component.

  pagerank_trajectory   reverse-PageRank of a watch-list of packages across snapshots -
                        when did `left-pad` / `lodash` / `log4j-core` become load-bearing.

Everything is computed from ONE pass that sorts edges by time; each snapshot is a prefix
of that sorted edge list, so k snapshots cost one sort + k cheap CSR builds.
"""

from __future__ import annotations

import numpy as np


def _year_frac(datestr):
    """'2016-04-11' -> 2016.27 ; robust to '', 'YYYY', 'YYYY-MM' and timestamps."""
    if not datestr:
        return np.nan
    s = str(datestr)[:10].replace("/", "-")
    p = s.split("-")
    try:
        y = int(p[0])
    except ValueError:
        return np.nan
    if y < 1990 or y > 2035:
        return np.nan
    m = int(p[1]) if len(p) > 1 and p[1].isdigit() else 6
    d = int(p[2]) if len(p) > 2 and p[2].isdigit() else 15
    return y + (m - 1) / 12 + (d - 1) / 365


def edge_times(store):
    """RESOLVES_TO edge -> time (year-fraction) of the source version's publish date.
    Returns (src, dst, t) arrays over edges with a usable date; the rest are dropped
    from the temporal view (reported as a coverage number)."""
    pub = getattr(store, "ver_published", None)
    if pub is None:
        raise RuntimeError(
            "store has no ver_published - rebuild the CSR with the FULL "
            "loader (parse.build_tables does not carry version dates)"
        )
    src = np.repeat(np.arange(store.N, dtype=np.int64), np.diff(np.asarray(store.res_indptr)))
    dst = np.asarray(store.res_indices, np.int64)
    tv = np.array([_year_frac(x) for x in np.asarray(pub)], float)
    t = tv[src]
    ok = ~np.isnan(t)
    return src[ok], dst[ok], t[ok], float(ok.mean())


def snapshots(src, dst, t, n, cuts):
    """For each cutoff year in `cuts`, build the CSR of edges with t <= cut and return
    per-snapshot (V_active, E, largest_wcc, mean_out_degree). One sort, k prefix scans."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    order = np.argsort(t, kind="stable")
    s, d, tt = src[order], dst[order], t[order]
    rows = []
    for cut in cuts:
        m = np.searchsorted(tt, cut, side="right")
        se, de = s[:m], d[:m]
        if m == 0:
            rows.append({"year": cut, "V": 0, "E": 0, "largest_wcc": 0, "mean_deg": 0.0})
            continue
        active = np.unique(np.concatenate([se, de]))
        A = csr_matrix((np.ones(m, np.int8), (se, de)), shape=(n, n))
        _, lab = connected_components(A, directed=False)
        lab_active = lab[active]
        big = np.bincount(lab_active).max() if len(lab_active) else 0
        rows.append(
            {
                "year": float(cut),
                "V": int(active.size),
                "E": int(m),
                "largest_wcc": int(big),
                "mean_deg": float(m / max(active.size, 1)),
            }
        )
    return rows


def densification_law(rows):
    """OLS of log E on log V across snapshots -> densification exponent a (E ~ V^a)."""
    r = [x for x in rows if x["V"] > 10 and x["E"] > 10]
    if len(r) < 3:
        return {"exponent": None, "r2": None, "n_points": len(r)}
    lv = np.log(np.array([x["V"] for x in r], float))
    le = np.log(np.array([x["E"] for x in r], float))
    a, b = np.polyfit(lv, le, 1)
    pred = a * lv + b
    ss_res = ((le - pred) ** 2).sum()
    ss_tot = ((le - le.mean()) ** 2).sum()
    return {
        "exponent": round(float(a), 3),
        "intercept": round(float(b), 3),
        "r2": round(float(1 - ss_res / ss_tot), 4) if ss_tot else None,
        "n_points": len(r),
        "reading": (
            "densifying (super-linear edge growth)"
            if a > 1.05
            else "constant average degree"
            if a < 0.95
            else "~linear"
        ),
    }


def attachment_kernel(src, dst, t, n, split_year, nbins=24):
    """Preferential-attachment test. Freeze the graph at `split_year`; for every edge
    that appears AFTER it, look at the in-degree (at freeze time) of the node it attached
    to. kernel(k) = P(attach to a node of in-degree k) / P(node has in-degree k).
    Linear kernel => Barabasi-Albert preferential attachment; super-linear => winner
    takes all."""
    pre = t <= split_year
    post = ~pre
    if post.sum() < 200 or pre.sum() < 200:
        return {"exponent": None, "n_post_edges": int(post.sum())}
    indeg = np.bincount(dst[pre], minlength=n).astype(np.int64)
    attached_k = indeg[dst[post]]
    # available mass per degree among nodes that existed pre-split
    existed = np.unique(np.concatenate([src[pre], dst[pre]]))
    deg_exist = indeg[existed]
    kmax = int(max(attached_k.max(), deg_exist.max(), 1))
    edges = np.unique(np.floor(np.geomspace(1, kmax + 1, nbins)).astype(np.int64))
    edges = np.concatenate([[0], edges])
    a_hist, _ = np.histogram(attached_k, bins=edges)
    avail, _ = np.histogram(deg_exist, bins=edges)
    ctr = 0.5 * (edges[:-1] + edges[1:])
    m = (a_hist > 0) & (avail > 0) & (ctr > 0)
    if m.sum() < 4:
        return {"exponent": None, "n_post_edges": int(post.sum())}
    kernel = (a_hist[m] / a_hist.sum()) / (avail[m] / avail.sum())
    slope, _intb = np.polyfit(np.log(ctr[m]), np.log(np.maximum(kernel, 1e-9)), 1)
    return {
        "exponent": round(float(slope), 3),
        "n_post_edges": int(post.sum()),
        "k": ctr[m].tolist(),
        "kernel": kernel.tolist(),
        "reading": (
            "winner-takes-all (super-linear)"
            if slope > 1.15
            else "preferential attachment (~linear, Barabasi-Albert)"
            if slope > 0.7
            else "sub-linear / egalitarian"
        ),
    }


def pagerank_trajectory(src, dst, t, n, cuts, watch_ids, damping=0.85, iters=25):
    """reverse-PageRank of each watched package at each snapshot year. The reverse-CSR
    of each prefix is built with scipy (C) - a pure-Python fill loop over up to ~10^8
    edges per snapshot is not acceptable at FULL scale."""
    from scipy.sparse import csr_matrix

    from .systemic import pagerank_rev

    order = np.argsort(t, kind="stable")
    s, d, tt = src[order], dst[order], t[order]
    traj: dict[int, list[float]] = {int(w): [] for w in watch_ids}
    for cut in cuts:
        m = int(np.searchsorted(tt, cut, side="right"))
        if m == 0:
            for w in watch_ids:
                traj[int(w)].append(0.0)
            continue
        # reverse edge d->s so PageRank mass flows toward depended-on nodes
        A = csr_matrix((np.ones(m, np.int8), (d[:m], s[:m])), shape=(n, n))
        A.sum_duplicates()
        pr = pagerank_rev(
            A.indptr.astype(np.int64), A.indices.astype(np.int64), n, damping=damping, iters=iters
        )
        for w in watch_ids:
            traj[int(w)].append(float(pr[int(w)]))
    return traj


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore

    for gd in ("data/graph_full", "data/graph"):
        p = Path(__file__).resolve().parent.parent / gd
        if (p / "res_indptr.npy").exists():
            S = KGStore(str(p))
            print(f"[temporal] using {gd}")
            break
    try:
        src, dst, t, cov = edge_times(S)
    except RuntimeError as e:
        print("skip:", e)
        raise SystemExit from e
    print(f"edges with a usable source date: {len(src):,}  ({cov * 100:.1f}% coverage)")
    cuts = list(range(2010, 2021))
    rows = snapshots(src, dst, t, S.N, cuts)
    for r in rows:
        print(
            f"  {int(r['year'])}  V={r['V']:>9,}  E={r['E']:>10,}  "
            f"giant={r['largest_wcc']:>9,}  <deg>={r['mean_deg']:.2f}"
        )
    print("densification:", densification_law(rows))
    print(
        "attachment  :",
        {
            k: v
            for k, v in attachment_kernel(src, dst, t, S.N, 2018).items()
            if k in ("exponent", "reading", "n_post_edges")
        },
    )
