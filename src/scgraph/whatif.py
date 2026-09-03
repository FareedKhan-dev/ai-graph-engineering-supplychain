"""Differential graph analysis: a remediation is a graph edit; evaluate it by re-running
the graph queries on both sides of the edit.

A proposed fix (bump package P from v_old to v_new) rewires every RESOLVES_TO edge that
pointed at a P-version. That edit can:

  * clear advisories  (the intent)
  * ADD advisories    (v_new is itself in some affected range - the "the upgrade fixed
                       CVE-A and introduced CVE-B" failure, invisible to a tool that only
                       checks the package you asked about)
  * change the shape  (v_new has different dependencies -> new transitive subtree, new
                       depth, new terminals)
  * ripple            every OTHER manifest whose resolved tree also contains P now has a
                       pending re-resolution; we count them (the blast radius of the FIX)

`diff_manifest`  applies the bump set to ONE manifest's resolved tree in memory and
                 returns before/after {exposure paths, total severity, max depth,
                 advisories added, advisories removed}.

`fix_ripple`     |{roots whose tree contains P}| - how many teams this fix touches if it
                 lands in the shared lockfile.

`ecosystem_delta` optional: recompute reverse-PageRank / blast-radius head with P's
                 in-edges repointed, to show whether the fix moves systemic risk.

No graph rebuild: the edit is applied as an overlay (a dict of redirected edges) that
`_resolves_to_ov` consults, so a what-if is O(affected subtree), not O(V).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


def _versions_affected(store, vid):
    return {
        str(store.adv_canon[int(a)])
        for a in store.advisories_of(vid)
        if not store.adv_withdrawn[int(a)]
    }


@dataclass
class ManifestDiff:
    manifest: str
    bumps: dict  # "eco/name" -> (from, to)
    before_advisories: set = field(default_factory=set)
    after_advisories: set = field(default_factory=set)
    before_severity: float = 0.0
    after_severity: float = 0.0
    before_depth: int = 0
    after_depth: int = 0
    resolve_failures: list = field(default_factory=list)

    @property
    def cleared(self):
        return sorted(self.before_advisories - self.after_advisories)

    @property
    def introduced(self):
        return sorted(self.after_advisories - self.before_advisories)

    def summary(self):
        return (
            f"{self.manifest}: -{len(self.cleared)} advisories, "
            f"+{len(self.introduced)} introduced, "
            f"severity {self.before_severity:.1f}->{self.after_severity:.1f}, "
            f"depth {self.before_depth}->{self.after_depth}"
            + (
                f", {len(self.resolve_failures)} unresolvable bumps"
                if self.resolve_failures
                else ""
            )
        )


def _walk(store, root_vid, redirect, max_depth=14):
    """BFS the resolved tree, honouring `redirect` (vid -> replacement vid) applied to
    edge targets. Returns (advisory_canon -> best_severity, max_depth_seen)."""
    adv: dict[str, float] = {}
    seen = {root_vid}
    q = deque([(root_vid, 0)])
    maxd = 0
    while q:
        vid, d = q.popleft()
        maxd = max(maxd, d)
        for a in store.advisories_of(vid):
            a = int(a)
            if store.adv_withdrawn[a]:
                continue
            c = str(store.adv_canon[a])
            adv[c] = max(adv.get(c, 0.0), float(store.adv_sev[a]))
        if d >= max_depth:
            continue
        for nxt in store.resolves_to(vid):
            nxt = int(redirect.get(int(nxt), int(nxt)))
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, d + 1))
    return adv, maxd


def _pick_new_vid(store, pid, to_version):
    for vid in store.versions_of(pid):
        if str(store.ver_str[vid]) == to_version:
            return vid
    return -1


def diff_manifest(store, root_vid, bumps, max_depth=14):
    """bumps: {"eco/name": (from_version, to_version)}  (as produced by remediate.*).
    Builds the redirect overlay and walks the tree before/after."""
    pid0 = int(store.ver_pkg[root_vid])
    root_key = f"{store.pkg_eco[pid0]}/{store.pkg_name[pid0]}"
    md = ManifestDiff(manifest=f"{root_key}@{store.ver_str[root_vid]}", bumps=dict(bumps))
    redirect = {}
    after_root = root_vid
    for key, (_frm, to) in bumps.items():
        eco, name = key.split("/", 1)
        pid = store.pkg_id(eco, name)
        if pid < 0:
            md.resolve_failures.append((key, "package not in graph"))
            continue
        new_vid = _pick_new_vid(store, pid, to)
        if new_vid < 0:
            md.resolve_failures.append((key, f"version {to} not in graph"))
            continue
        if key == root_key:  # bumping the manifest package itself
            after_root = int(new_vid)
            continue
        for old_vid in store.versions_of(pid):
            redirect[int(old_vid)] = int(new_vid)

    before, bd = _walk(store, root_vid, {}, max_depth)
    after, ad = _walk(store, after_root, redirect, max_depth)
    md.before_advisories, md.after_advisories = set(before), set(after)
    md.before_severity = round(sum(before.values()), 1)
    md.after_severity = round(sum(after.values()), 1)
    md.before_depth, md.after_depth = bd, ad
    return md


def fix_ripple(store, pkg_key, roots=None, max_up=6):
    """How many manifest roots have `pkg_key` somewhere in their resolved tree - i.e.
    how many teams a change to this package's pinned version forces to re-resolve."""
    eco, name = pkg_key.split("/", 1)
    pid = store.pkg_id(eco, name)
    if pid < 0:
        return {"package": pkg_key, "reachable_roots": 0}
    from .paths import blast_radius

    hit = blast_radius(store, pid, max_up=max_up)
    truncated = hit and hit[-1] == -1
    if truncated:
        hit = hit[:-1]
    seen, names = set(), []
    for v in hit:
        rp = int(store.ver_pkg[v])
        nm = f"{store.pkg_eco[rp]}/{store.pkg_name[rp]}"
        if nm not in seen:
            seen.add(nm)
            names.append(nm)
    return {
        "package": pkg_key,
        "reachable_roots": (f">={len(seen)}" if truncated else len(seen)),
        "sample": names[:8],
    }


def portfolio_delta(store, remediations, max_depth=14):
    """Apply each Remediation's bumps to its own manifest, aggregate the before/after.
    `remediations` = iterable of (root_vid, bumps_dict)."""
    tot: dict[str, Any] = {
        "manifests": 0,
        "cleared": 0,
        "introduced": 0,
        "sev_before": 0.0,
        "sev_after": 0.0,
        "net_worse": 0,
        "no_change": 0,
    }
    worse = []
    for root_vid, bumps in remediations:
        if not bumps:
            continue
        d = diff_manifest(store, root_vid, bumps, max_depth)
        tot["manifests"] += 1
        tot["cleared"] += len(d.cleared)
        tot["introduced"] += len(d.introduced)
        tot["sev_before"] += d.before_severity
        tot["sev_after"] += d.after_severity
        if d.introduced and len(d.introduced) >= len(d.cleared):
            tot["net_worse"] += 1
            worse.append(d.summary())
        if not d.cleared and not d.introduced:
            tot["no_change"] += 1
    tot["sev_before"] = round(tot["sev_before"], 1)
    tot["sev_after"] = round(tot["sev_after"], 1)
    tot["worse_examples"] = worse[:8]
    return tot


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore
    from .paths import exposure_paths
    from .remediate import greedy_fix

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    roots = [v for v in range(S.N) if S.ver_default[v] and len(S.dependents(v)) == 0]
    rems = []
    for r in roots:
        ps = [p for p in exposure_paths(S, r, 12, 120) if not p.withdrawn]
        if not ps:
            continue
        rem = greedy_fix(S, r, ps)
        if rem.bumps:
            rems.append((r, {k: (v[0], v[1]) for k, v in rem.bumps.items()}))
    print(f"{len(rems)} manifests with a proposed fix")
    for r, b in rems[:6]:
        print("  " + diff_manifest(S, r, b).summary())
    pd = portfolio_delta(S, rems)
    print(
        "\nportfolio:",
        {
            k: pd[k]
            for k in ("manifests", "cleared", "introduced", "sev_before", "sev_after", "net_worse")
        },
    )
    if rems:
        k0 = next(iter(rems[0][1]))
        print("ripple of", k0, "->", fix_ripple(S, k0))
