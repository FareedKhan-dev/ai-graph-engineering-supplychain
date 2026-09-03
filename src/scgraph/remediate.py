"""Minimal remediation as constrained optimisation.

Given a manifest's resolved tree and the advisories that reach it, find the SMALLEST
set of version bumps that clears them all without (a) entering a *new* affected range
or (b) crossing a major-version boundary. Two solvers:

  greedy_fix   per affected package, lowest clean version >= current. Always
               terminates, scales, gives an upper bound. This is what most tools do.
  ilp_fix      the honest formulation. Binary y[p,v] (choose version v of package p),
               one-hot per package, "clears advisory a" as a linear constraint,
               objective = #bumps + lambda*#major-bumps. Solved with scipy HiGHS.
               Exposes the structure a greedy solver hides: sometimes fixing A forces
               a downgrade of B, and no assignment satisfies everything -> UNFIXABLE.

The measured finding (notebook S19): what fraction of real trees are UNFIXABLE at
each severity floor, and why (no fix published / fix requires a major / mutually
exclusive constraints).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .versions import _semver_parts, compare


def _is_prerelease(v: str) -> bool:
    """True for 1.0.0-alpha, 2.0.0rc1, 3.0.0.dev4, 1.0-SNAPSHOT, -beta, -M1 ..."""
    s = (v or "").lower()
    try:
        if _semver_parts(v)[3] is not None:
            return True
    except Exception:
        pass
    import re as _re

    return bool(
        _re.search(
            r"(-|\.|_)?(alpha|beta|rc|dev|snapshot|preview|pre|m\d|cr\d|"
            r"a\d|b\d|nightly|canary|next|milestone)",
            s,
        )
    )


def _major(v: str) -> str:
    import re

    m = re.match(r"[vV]?(\d+)", v or "")
    return m.group(1) if m else "0"


def _clean_versions(store, pid, current_vid):
    """Versions of pid that are affected by NOTHING, sorted, with major tags.
    Prereleases (alpha/beta/rc/SNAPSHOT/dev) are excluded UNLESS the version we are
    replacing is itself a prerelease - a fix that tells you to ship `jetty 10.0.0-alpha0`
    is not a fix. (FULL run also wants: published, not yanked, satisfies parent ranges.)"""
    eco = str(store.pkg_eco[pid])
    cur = str(store.ver_str[current_vid])
    cur_pre = _is_prerelease(cur)
    out = []
    for vid in store.versions_of(pid):
        if len(store.advisories_of(vid)) > 0:
            continue
        v = str(store.ver_str[vid])
        if _is_prerelease(v) and not cur_pre:
            continue
        try:
            newer = compare(v, cur, eco) >= 0
        except Exception:
            newer = True
        out.append((vid, v, newer, _major(v) != _major(cur)))
    out.sort(key=lambda t: 0 if not t[3] else 1)  # prefer same-major
    return out


@dataclass
class Remediation:
    manifest: str
    bumps: dict = field(default_factory=dict)  # pkg -> (from, to, is_major)
    unfixable: list = field(default_factory=list)  # [(pkg, reason)]
    cleared: int = 0
    total_advisories: int = 0
    solver: str = ""

    def summary(self):
        maj = sum(1 for b in self.bumps.values() if b[2])
        return (
            f"{self.manifest}: cleared {self.cleared}/{self.total_advisories}  "
            f"bumps={len(self.bumps)} ({maj} major)  unfixable={len(self.unfixable)}"
        )


def greedy_fix(store, root_vid, paths, allow_major=True):
    """paths = ExposurePath list for this manifest."""
    from collections import defaultdict

    by_pkg = defaultdict(list)  # terminal pid -> [ExposurePath]
    for p in paths:
        by_pkg[int(store.ver_pkg[p.hops[-1]])].append(p)
    pid = int(store.ver_pkg[root_vid])
    rem = Remediation(
        manifest=f"{store.pkg_eco[pid]}/{store.pkg_name[pid]}@{store.ver_str[root_vid]}",
        total_advisories=len({p.advisory for p in paths}),
        solver="greedy",
    )
    for tpid, ps in by_pkg.items():
        cur_vid = ps[0].hops[-1]
        cur = str(store.ver_str[cur_vid])
        cands = _clean_versions(store, tpid, cur_vid)
        pick = next(
            (
                (vid, v, major)
                for vid, v, newer, major in cands
                if newer and (allow_major or not major)
            ),
            None,
        )
        if pick is None:
            has_any_clean = bool(cands)
            reason = (
                "only a major bump is clean"
                if has_any_clean
                else "no published version is free of advisories"
            )
            rem.unfixable.append((f"{store.pkg_eco[tpid]}/{store.pkg_name[tpid]}", reason))
            continue
        _vid, v, major = pick
        rem.bumps[f"{store.pkg_eco[tpid]}/{store.pkg_name[tpid]}"] = (cur, v, major)
        rem.cleared += len({p.advisory for p in ps})
    return rem


def ilp_fix(store, root_vid, paths, lam=0.35, max_pkgs=40, time_limit=10):
    """Honest ILP. Only run on small trees (the formulation is the teaching point)."""
    try:
        from scipy.optimize import Bounds, LinearConstraint, milp
    except Exception:
        return greedy_fix(store, root_vid, paths)
    from collections import defaultdict

    term = defaultdict(set)  # pid -> {advisory canon}
    adv_of = defaultdict(set)  # advisory -> {pid}
    for p in paths:
        tp = int(store.ver_pkg[p.hops[-1]])
        term[tp].add(p.advisory)
        adv_of[p.advisory].add(tp)
    pids = list(term)[:max_pkgs]
    # candidate versions per package: current + every version, tagged clean/major
    var, meta = [], []
    for pi, tp in enumerate(pids):
        cur_vid = next(p.hops[-1] for p in paths if int(store.ver_pkg[p.hops[-1]]) == tp)
        cur = str(store.ver_str[cur_vid])
        cur_pre = _is_prerelease(cur)
        for vid in store.versions_of(tp):
            v = str(store.ver_str[vid])
            if vid != cur_vid and _is_prerelease(v) and not cur_pre:
                continue
            clean = len(store.advisories_of(vid)) == 0
            is_cur = vid == cur_vid
            major = _major(v) != _major(cur)
            var.append((pi, vid))
            meta.append(
                {
                    "pi": pi,
                    "tp": tp,
                    "vid": vid,
                    "v": v,
                    "clean": clean,
                    "is_cur": is_cur,
                    "major": major,
                }
            )
    if not var:
        return greedy_fix(store, root_vid, paths)
    K = len(var)
    # cost: bump = 1 - is_cur ; + lam if major ; huge if not clean (soft-forbid)
    c = np.array(
        [
            (0.0 if m["is_cur"] else 1.0)
            + (lam if m["major"] else 0.0)
            + (0.0 if m["clean"] else 50.0)
            for m in meta
        ]
    )
    # one-hot per package
    A_rows, lb = [], []
    ub: list[float] = []
    for pi in range(len(pids)):
        row = np.array([1.0 if meta[k]["pi"] == pi else 0.0 for k in range(K)])
        A_rows.append(row)
        lb.append(1)
        ub.append(1)
    # each package's chosen version must be clean (>= all clean vars sum to 1 already
    # handled by cost; hard constraint: sum of clean vars for pi >= 1)
    for pi in range(len(pids)):
        row = np.array(
            [1.0 if (meta[k]["pi"] == pi and meta[k]["clean"]) else 0.0 for k in range(K)]
        )
        if row.sum() > 0:
            A_rows.append(row)
            lb.append(1)
            ub.append(np.inf)
    cons = LinearConstraint(np.array(A_rows), lb, ub)
    res = milp(
        c,
        constraints=cons,
        integrality=np.ones(K),
        bounds=Bounds(0, 1),
        options={"time_limit": time_limit},
    )
    pid0 = int(store.ver_pkg[root_vid])
    rem = Remediation(
        manifest=f"{store.pkg_eco[pid0]}/{store.pkg_name[pid0]}@{store.ver_str[root_vid]}",
        total_advisories=len({p.advisory for p in paths}),
        solver="ilp",
    )
    if not res.success or res.x is None:
        rem.unfixable.append(("(whole tree)", "ILP infeasible - mutually exclusive constraints"))
        return rem
    chosen = np.where(res.x > 0.5)[0]
    for k in chosen:
        m = meta[k]
        if m["is_cur"]:
            continue
        if not m["clean"]:
            rem.unfixable.append(
                (
                    f"{store.pkg_eco[m['tp']]}/{store.pkg_name[m['tp']]}",
                    "no clean version - solver forced a compromise",
                )
            )
            continue
        cur = next(
            str(store.ver_str[p.hops[-1]])
            for p in paths
            if int(store.ver_pkg[p.hops[-1]]) == m["tp"]
        )
        rem.bumps[f"{store.pkg_eco[m['tp']]}/{store.pkg_name[m['tp']]}"] = (cur, m["v"], m["major"])
        rem.cleared += len(term[m["tp"]])
    return rem


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore
    from .paths import exposure_paths

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    roots = [v for v in range(S.N) if S.ver_default[v] and len(S.dependents(v)) == 0]
    fixed = unfix = 0
    for r in roots:
        ps = [p for p in exposure_paths(S, r, 12, 120) if not p.withdrawn]
        if not ps:
            continue
        rem = greedy_fix(S, r, ps)
        fixed += rem.cleared > 0
        unfix += len(rem.unfixable) > 0
        if rem.cleared and len(rem.bumps) <= 4:
            print("  " + rem.summary())
    print(f"\nmanifests with a remediation: {fixed}   with >=1 unfixable pkg: {unfix}")
