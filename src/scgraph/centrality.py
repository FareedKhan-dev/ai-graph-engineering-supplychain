"""Structural criticality: which packages are load-bearing in the *topological* sense,
not just the PageRank sense.

`systemic.py` answers "influence" with reverse-PageRank (a spectral / random-walk
notion). This module answers the sharper question with classical graph theory:

  articulation_points   nodes whose removal increases the number of connected
                        components - the true single points of failure. Hopcroft-Tarjan,
                        O(V+E), iterative (no recursion - the graph is too deep for
                        Python's stack). Computed on the UNDIRECTED package graph.

  bridges               edges whose removal disconnects. A bridge dependency is one
                        with no alternative path - the ecosystem has no redundancy there.

  betweenness_sampled   fraction of shortest paths through each node. Exact Brandes is
                        O(VE) - 10^15 ops on the full graph, infeasible. We sample K
                        source BFS pivots; the Riondato-Kornaropoulos bound says
                        K >= (c/eps^2)(floor(log2(VD-2)) + 1 + ln(1/delta)) pivots give a
                        uniform eps-approximation of every node's betweenness w.p. 1-delta
                        (VD = vertex diameter). We report the bound and the sample used.

  harmonic_centrality   sum of 1/d(v,u) over reachable u, from the same BFS pivots -
                        a closeness variant that is well-defined on disconnected graphs.

For a reader: articulation points and bridges are the "no redundancy" finding; sampled
betweenness is the "on the most dependency paths" finding; they identify different
packages than PageRank does, and the notebook shows the rank correlation (Spearman)
between all four - moderate, not high, which is the point: no single centrality is
"the" centrality.
"""

from __future__ import annotations

import numpy as np


def _undirected_csr(indptr, indices, n):
    """Symmetrise a directed CSR into an undirected one (dedup parallel edges)."""
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    src = np.repeat(np.arange(n, dtype=np.int64), np.diff(ip))
    a = np.concatenate([src, ix])
    b = np.concatenate([ix, src])
    key = a * np.int64(n) + b
    order = np.argsort(key, kind="stable")
    a, b = a[order], b[order]
    keep = np.ones(len(a), bool)
    if len(a) > 1:
        dup = (a[1:] == a[:-1]) & (b[1:] == b[:-1])
        keep[1:] = ~dup
    a, b = a[keep], b[keep]
    uip = np.zeros(n + 1, np.int64)
    np.add.at(uip, a + 1, 1)
    np.cumsum(uip, out=uip)
    return uip, b.astype(np.int64)


def articulation_points_and_bridges(indptr, indices, n=None, max_nodes=6_000_000):
    """Hopcroft-Tarjan on the undirected graph. Returns
    (is_articulation: bool[n], bridges: list[(u,v)], n_components_forest).
    Uses igraph's C implementation above ~500k nodes (same definition, ~100x faster);
    else an iterative (recursion-free) pure-Python DFS."""
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = n or len(ip) - 1

    if n > 500_000:
        try:
            import igraph as _ig
            from scipy.sparse import csr_matrix
            from scipy.sparse.csgraph import connected_components

            src = np.repeat(np.arange(n, dtype=np.int64), np.diff(ip))
            g = _ig.Graph(n=int(n), edges=np.stack([src, ix], 1), directed=False)
            g.simplify()
            is_art = np.zeros(n, bool)
            is_art[np.asarray(g.articulation_points(), np.int64)] = True
            ig_bridges = [tuple(map(int, g.es[eid].tuple)) for eid in g.bridges()]
            A = csr_matrix((np.ones(len(ix), np.int8), ix, ip), shape=(n, n))
            ncomp, _ = connected_components(A, directed=False)
            return is_art, ig_bridges, int(ncomp)
        except Exception as e:
            print(f"[articulation] igraph fast-path unavailable ({e}); pure-Python DFS")

    uip, uix = _undirected_csr(ip, ix, n)

    disc = np.full(n, -1, np.int64)
    low = np.zeros(n, np.int64)
    parent = np.full(n, -1, np.int64)
    is_art = np.zeros(n, bool)
    bridges: list[tuple[int, int]] = []
    timer = 0
    ncomp = 0

    # iterative DFS with an explicit stack of (node, neighbour-cursor)
    it = uip[:-1].copy()  # per-node cursor into uix
    stack = np.empty(n, np.int64)

    for s in range(n):
        if disc[s] != -1:
            continue
        ncomp += 1
        sp = 0
        stack[sp] = s
        disc[s] = low[s] = timer
        timer += 1
        root_children = 0
        while sp >= 0:
            v = stack[sp]
            if it[v] < uip[v + 1]:
                w = uix[it[v]]
                it[v] += 1
                if disc[w] == -1:
                    parent[w] = v
                    disc[w] = low[w] = timer
                    timer += 1
                    sp += 1
                    stack[sp] = w
                    if v == s:
                        root_children += 1
                elif w != parent[v]:
                    if disc[w] < low[v]:
                        low[v] = disc[w]
            else:
                sp -= 1
                if sp >= 0:
                    p = stack[sp]
                    if low[v] < low[p]:
                        low[p] = low[v]
                    if parent[p] != -1 and low[v] >= disc[p]:
                        is_art[p] = True
                    if low[v] > disc[p]:
                        bridges.append((int(p), int(v)))
        if root_children >= 2:
            is_art[s] = True
    return is_art, bridges, ncomp


def betweenness_sampled(
    indptr,
    indices,
    n=None,
    k=400,
    seed=0,
    directed=True,
    cutoff=0,
    pivot_pool=None,
    return_harmonic=True,
):
    """Brandes accumulation from `k` sampled source pivots (RK estimator).
    betweenness[v] ~= (n / k) * sum_pivots delta_pivot(v), normalised to [0,1] by the
    max possible (n-1)(n-2). Unweighted graph -> BFS, not Dijkstra.

      cutoff      if > 0, BFS stops past this many hops. Paths longer than ~8 hops in a
                  dependency graph contribute negligible betweenness mass and cost the
                  most; the notebook reports the truncation.
      pivot_pool  restrict pivots to this node array (e.g. the 2-core, or the largest
                  weakly-connected component) - exact-on-the-spine, which is where the
                  betweenness mass lives anyway.
    """
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = n or len(ip) - 1
    if not directed:
        ip, ix = _undirected_csr(ip, ix, n)
    rng = np.random.default_rng(seed)
    pool = np.arange(n) if pivot_pool is None else np.asarray(pivot_pool, np.int64)
    k = min(k, len(pool))
    pivots = rng.choice(pool, size=k, replace=False)

    bc = np.zeros(n, np.float64)
    harm = np.zeros(n, np.float64)
    reach = np.zeros(n, np.int64)

    for s in pivots:
        s = int(s)
        dist = np.full(n, -1, np.int64)
        sigma = np.zeros(n, np.float64)
        dist[s] = 0
        sigma[s] = 1.0
        order = [s]
        head = 0
        preds: dict[int, list[int]] = {}
        while head < len(order):
            v = order[head]
            head += 1
            if cutoff and dist[v] >= cutoff:
                continue
            dv = dist[v] + 1
            sv = sigma[v]
            for w in ix[ip[v] : ip[v + 1]]:
                w = int(w)
                if dist[w] == -1:
                    dist[w] = dv
                    order.append(w)
                    sigma[w] += sv
                    preds.setdefault(w, []).append(v)
                elif dist[w] == dv:
                    sigma[w] += sv
                    preds.setdefault(w, []).append(v)
        m = dist > 0
        harm[s] += (1.0 / dist[m]).sum()
        reach[s] += int(m.sum())
        delta = np.zeros(n, np.float64)
        for w in reversed(order):
            dw = delta[w]
            sw = sigma[w]
            for v in preds.get(w, ()):
                delta[v] += (sigma[v] / sw) * (1.0 + dw)
            if w != s:
                bc[w] += dw

    scale = n / max(k, 1)
    denom = (n - 1) * (n - 2) if n > 2 else 1
    out = {
        "betweenness": bc * scale / denom,
        "pivots": int(k),
        "cutoff": int(cutoff),
        "rk_bound": _rk_bound(n, int(np.max(reach) if len(reach) else 0)),
    }
    if return_harmonic:
        out["harmonic_pivot"] = harm
        out["harmonic_pivot_mask"] = np.isin(np.arange(n), pivots)
    return out


def _rk_bound(n, vd, eps=0.05, delta=0.1, c=0.5):
    """Riondato-Kornaropoulos pivot count for a uniform eps-approx of betweenness."""
    vd = max(vd, 3)
    import math

    return math.ceil((c / eps**2) * (math.floor(math.log2(vd - 2)) + 1 + math.log(1.0 / delta)))


def _run_with_timeout(fn, seconds):
    """Run `fn` with a wall-clock budget (SIGALRM - Unix only; a no-op timeout on
    platforms without it, which just means the caller's own except-block is the
    only safety net there)."""
    import signal

    if not hasattr(signal, "SIGALRM"):
        return fn()

    def _handler(signum, frame):
        raise TimeoutError(f"exceeded {seconds}s budget")

    old = signal.signal(signal.SIGALRM, _handler)
    # signal.alarm is POSIX-only (guarded by the hasattr check above). The
    # attr-defined ignore is needed on Windows, where it is absent; unused-ignore
    # keeps mypy quiet on Linux, where it is present.
    signal.alarm(int(seconds))  # type: ignore[attr-defined, unused-ignore]
    try:
        return fn()
    finally:
        signal.alarm(0)  # type: ignore[attr-defined, unused-ignore]
        signal.signal(signal.SIGALRM, old)


def betweenness_core(
    indptr,
    indices,
    n=None,
    cutoff=4,
    max_core_nodes=40_000,
    sample_k=150,
    seed=0,
    time_budget_s=150,
):
    """Betweenness restricted to a HARD-CAPPED subgraph of the structural heart.

    Two independent ways this used to blow up, both closed here:
      1. k-core peeling does not guarantee a small node count - if coreness stays high
         across a huge, densely-interlinked cluster (real in tooling-heavy ecosystems),
         "the k=kmax core" can itself be far larger than the cap.
      2. Even a "bounded" pure-Python sampled Brandes is not actually bounded if the
         subgraph is dense enough that a `cutoff`-hop BFS reaches most of it - cost is
         pivots * (nodes reached), not pivots * cutoff.

    Fix: peel to the highest k with node count <= max_core_nodes; if NO k gets under the
    cap (even k=kmax), forcibly truncate to the top `max_core_nodes` nodes by degree
    within the max-coreness set - a hard ceiling regardless of graph structure. Prefer
    igraph's C `betweenness(cutoff)` (handles a dense 60k-node subgraph in seconds to
    low minutes); the pure-Python sampler is the last-resort fallback, capped much
    smaller (a Python BFS re-touching most of a dense graph per pivot has no cheap
    escape hatch the way a single C pass does).
    """
    from .graphshape import kcore

    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = n or len(ip) - 1
    core = kcore(ip, ix, n)
    out = np.zeros(n, np.float64)
    kmax = int(core.max()) if len(core) else 0
    chosen_k, truncated = 2, False
    for kk in range(2, max(kmax, 2) + 1):
        if int((core >= kk).sum()) <= max_core_nodes:
            chosen_k = kk
            break
    else:
        chosen_k = max(kmax, 2)
    nodes = np.where(core >= chosen_k)[0]
    if len(nodes) > max_core_nodes:  # hard ceiling: even k=kmax was too big
        deg = np.diff(np.asarray(indptr))[nodes] + np.bincount(ix, minlength=n)[nodes]
        nodes = nodes[np.argsort(-deg)[:max_core_nodes]]
        truncated = True
    if len(nodes) < 3:
        return {
            "betweenness": out,
            "n_core": len(nodes),
            "core_k": chosen_k,
            "method": "empty",
        }
    sip, sidx = _subgraph_csr(ip, ix, nodes)
    denom = (len(nodes) - 1) * (len(nodes) - 2) / 2 if len(nodes) > 2 else 1
    tag = f"{chosen_k}-core" + (", degree-truncated" if truncated else "")

    try:
        import igraph as _ig

        src = np.repeat(np.arange(len(nodes), dtype=np.int64), np.diff(sip))
        g = _ig.Graph(n=len(nodes), edges=np.stack([src, sidx], 1), directed=False)
        g.simplify()
        bc = np.asarray(
            _run_with_timeout(lambda: g.betweenness(cutoff=cutoff), time_budget_s), np.float64
        )
        out[nodes] = bc / denom
        return {
            "betweenness": out,
            "n_core": len(nodes),
            "core_k": chosen_k,
            "method": f"igraph betweenness (cutoff={cutoff}), {tag}",
            "cutoff": cutoff,
        }
    except Exception as e:
        # last resort: much smaller cap, few pivots, short cutoff - must terminate fast
        cap2 = min(len(nodes), 8_000)
        if cap2 < len(nodes):
            deg2 = np.diff(sip)
            keep = np.argsort(-deg2)[:cap2]
            sip, sidx = _subgraph_csr(sip, sidx, keep)
            nodes = nodes[keep]
        r = betweenness_sampled(
            sip,
            sidx,
            len(nodes),
            k=min(sample_k, 60),
            seed=seed,
            cutoff=min(cutoff, 3),
            directed=False,
        )
        out[nodes] = r["betweenness"]
        return {
            "betweenness": out,
            "n_core": len(nodes),
            "core_k": chosen_k,
            "method": f"sampled Brandes, {r['pivots']} pivots, {tag} ({e})",
            "rk_bound": r["rk_bound"],
            "cutoff": min(cutoff, 3),
        }


# back-compat alias
betweenness_2core = betweenness_core


def _subgraph_csr(indptr, indices, nodes):
    """Undirected relabelled CSR over `nodes` (helper shared with gnn)."""
    ip = np.asarray(indptr, np.int64)
    ix = np.asarray(indices, np.int64)
    n = len(ip) - 1
    remap = np.full(n, -1, np.int64)
    remap[nodes] = np.arange(len(nodes))
    src = np.repeat(np.arange(n, dtype=np.int64), np.diff(ip))
    m = (remap[src] >= 0) & (remap[ix] >= 0)
    a, b = remap[src[m]], remap[ix[m]]
    a, b = np.concatenate([a, b]), np.concatenate([b, a])
    k = len(nodes)
    order = np.argsort(a, kind="stable")
    a, b = a[order], b[order]
    sip = np.zeros(k + 1, np.int64)
    np.add.at(sip, a + 1, 1)
    np.cumsum(sip, out=sip)
    return sip, b.astype(np.int64)


def spearman(a, b):
    """Rank correlation between two centrality vectors (no scipy dependency)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    ra_c = ra - ra.mean()
    rb_c = rb - rb.mean()
    d = np.sqrt((ra_c**2).sum() * (rb_c**2).sum())
    return float((ra_c * rb_c).sum() / d) if d else 0.0


if __name__ == "__main__":
    from pathlib import Path

    from . import systemic as sysm
    from .kgstore import KGStore

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    P = len(S.pkg_name)
    art, br, nc = articulation_points_and_bridges(S.pkgdep_indptr, S.pkgdep_indices, P)
    print(f"packages: {P:,}   forest components: {nc:,}")
    print(f"articulation points: {int(art.sum()):,}  ({100 * art.mean():.2f}%)")
    print(f"bridges: {len(br):,}")
    top = np.argsort(-art.astype(int) * (np.diff(np.asarray(S.pkgrev_indptr)) + 1))[:10]
    print("  sample articulation packages (by dependents):")
    for i in top:
        if art[i]:
            print(f"    {S.pkg_eco[i]}/{S.pkg_name[i]}  dependents={len(S.pkg_dependents(i))}")
    bw = betweenness_sampled(S.pkgdep_indptr, S.pkgdep_indices, P, k=min(300, P), seed=1)
    print(f"\nsampled betweenness: {bw['pivots']} pivots (RK bound suggests {bw['rk_bound']})")
    pr = sysm.pagerank_rev(S.pkgrev_indptr, S.pkgrev_indices, P)
    print(f"Spearman(betweenness, reverse-PageRank) = {spearman(bw['betweenness'], pr):.3f}")
    print("  -> no single centrality is 'the' centrality")
