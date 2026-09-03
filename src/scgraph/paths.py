"""Exposure path finding — the notebook §7/§8 "what connects the question's concepts"
transplanted to "what path connects this repo to this advisory".

Given a root version (the app / a manifest's resolved tree root) and the graph, find
every path  root -> v1 -> ... -> vk  where vk is affected by some advisory. The path
IS the deliverable; it is what the on-call engineer acts on.

Two evidence classes, both fully provenanced:
  DIRECT     the root's own resolved tree contains an affected version at depth 1
  TRANSITIVE an affected version sits deeper in the resolved tree; the path names
             every hop, each hop a RESOLVES_TO edge that a real resolver produced
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class ExposurePath:
    advisory: str  # canonical id
    osv_id: str
    severity: float
    withdrawn: bool
    hops: list  # [ver_id, ...] root .. affected terminal
    depth: int
    terminal_pkg: str  # "ecosystem/name@version"
    published: str

    def render(self, store):
        names = []
        for vid in self.hops:
            pid = int(store.ver_pkg[vid])
            names.append(f"{store.pkg_name[pid]}@{store.ver_str[vid]}")
        chain = " -> ".join(names)
        flag = "  !! WITHDRAWN" if self.withdrawn else ""
        return f"[{self.advisory}  cvss={self.severity:.1f}] {chain}{flag}"


def exposure_paths(store, root_vid: int, max_depth=12, max_paths=200, min_severity=0.0):
    """BFS the resolved tree from root_vid; every time a node is affected, emit the
    path. Deduplicate by (advisory, terminal). Ranked shallow-first, then severity."""
    out: list[ExposurePath] = []
    seen_terminal = set()
    q = deque([(root_vid, [root_vid])])
    visited = {root_vid}
    while q and len(out) < max_paths * 4:
        vid, path = q.popleft()
        if len(path) - 1 > max_depth:
            continue
        for aid in store.advisories_of(vid):
            aid = int(aid)
            if store.adv_sev[aid] < min_severity and not store.adv_withdrawn[aid]:
                pass
            key = (aid, vid)
            if key in seen_terminal:
                continue
            seen_terminal.add(key)
            pid = int(store.ver_pkg[vid])
            out.append(
                ExposurePath(
                    advisory=str(store.adv_canon[aid]),
                    osv_id=str(store.adv_id[aid]),
                    severity=float(store.adv_sev[aid]),
                    withdrawn=bool(store.adv_withdrawn[aid]),
                    hops=list(path),
                    depth=len(path) - 1,
                    terminal_pkg=f"{store.pkg_eco[pid]}/{store.pkg_name[pid]}@{store.ver_str[vid]}",
                    published=str(store.adv_published[aid]),
                )
            )
        for nxt in store.resolves_to(vid):
            nxt = int(nxt)
            if nxt not in visited:
                visited.add(nxt)
                q.append((nxt, [*path, nxt]))
    out.sort(key=lambda p: (p.depth, -p.severity))
    return out[:max_paths]


def blast_radius(store, pkg_id: int, max_up=5, node_budget=400_000):
    """Reverse: every root version whose resolved tree reaches any version of pkg_id.
    'If I have to yank/patch this package, who is affected?' — one reverse-CSR walk,
    bounded by `max_up` hops and `node_budget` visited nodes (a hub like `lodash` has
    millions of transitive dependents; the count past a few hundred k is not actionable
    and the exact figure is reported as '>= budget')."""
    targets = set(store.versions_of(pkg_id))
    hit_roots = set()
    q = deque((t, 0) for t in targets)
    seen = set(targets)
    truncated = False
    while q:
        vid, up = q.popleft()
        if up > max_up:
            continue
        if len(seen) > node_budget:
            truncated = True
            break
        deps = store.dependents(vid)
        if len(deps) == 0 and store.ver_default[vid]:
            hit_roots.add(vid)
        for d in deps:
            d = int(d)
            if d not in seen:
                seen.add(d)
                if store.ver_default[d]:
                    hit_roots.add(d)
                q.append((d, up + 1))
    out = sorted(hit_roots)
    if truncated:
        out.append(-1)  # sentinel: caller reports ">= len-1"
    return out
