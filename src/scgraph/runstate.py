"""Runtime State Management (survey S4.4) - the versioned run graph.

RunGraph      append-only event log + a per-(manifest,package) status with
              provenance. A proposed bump is a TENTATIVE write; BuildVerifier
              COMMITS it. This is the proposal->validate->commit boundary the
              survey (and PatchBoard / MemTX) argue for.
bisect_build  "the build went red after bumping {A,B,C,...}; which single bump is
              decisive?" - binary search over the bump set, re-checking a (mocked)
              build predicate. O(log n) build runs instead of n. This is
              git-bisect moved from the file diff to the dependency-graph diff.
recover       given the decisive bump: retract it / try the next-safe version /
              pin with a recorded exception. Every step is a recovery boundary.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

STATUS = (
    "clean",
    "affected_reachable",
    "affected_unreachable",
    "affected_unknown",
    "patched",
    "yanked_blocked",
    "license_violation",
    "escalated",
)


@dataclass
class RunGraph:
    run_id: str
    events: list = field(default_factory=list)  # append-only
    status: dict = field(default_factory=dict)  # pkg -> (status, provenance)
    tentative: dict = field(default_factory=dict)  # pkg -> (from,to) not yet committed

    def record(self, kind, **payload):
        self.events.append({"t": round(time.time(), 3), "kind": kind, **payload})

    def set_status(self, pkg, st, why):
        assert st in STATUS, st
        self.status[pkg] = (st, why)
        self.record("status", pkg=pkg, status=st, why=why)

    def propose(self, pkg, frm, to, why):
        self.tentative[pkg] = (frm, to)
        self.record("propose", pkg=pkg, frm=frm, to=to, why=why)

    def commit(self, pkg, build_id):
        frm, to = self.tentative.pop(pkg)
        self.set_status(pkg, "patched", f"build {build_id}: {frm} -> {to}")
        self.record("commit", pkg=pkg, frm=frm, to=to, build=build_id)

    def rollback(self, pkg, reason):
        if pkg in self.tentative:
            frm, to = self.tentative.pop(pkg)
            self.record("rollback", pkg=pkg, frm=frm, to=to, reason=reason)

    def snapshot(self):
        return {
            "run_id": self.run_id,
            "events": len(self.events),
            "committed": sum(1 for s, _ in self.status.values() if s == "patched"),
            "tentative": len(self.tentative),
            "status_counts": _counts(s for s, _ in self.status.values()),
        }


def _counts(it):
    from collections import Counter

    return dict(Counter(it))


def bisect_build(bump_set, build_ok, rg: RunGraph | None = None):
    """bump_set: dict pkg -> (from, to). build_ok(applied_dict) -> bool.
    Returns the culprit bumps: those whose removal, holding the rest, makes the build
    pass. Leave-one-out over the bump set (O(n) build runs). If no single removal
    fixes it, delta-debug down to a minimal failing subset (an *interaction*).
    This is git-bisect moved from the file diff to the dependency-graph diff -
    possible only because the run graph kept both the pre- and post-bump resolution.
    """
    items = dict(bump_set)
    if build_ok(items):
        return {}
    culprits = {}
    for pk in list(items):
        without = {k: v for k, v in items.items() if k != pk}
        if build_ok(without):
            culprits[pk] = items[pk]
            if rg:
                rg.record("bisect_culprit", pkg=pk, frm=items[pk][0], to=items[pk][1])
    if culprits:
        return culprits
    # no single bump is solely responsible -> minimal failing subset (ddmin, n=2..)
    from itertools import combinations

    for k in range(2, len(items) + 1):
        for combo in combinations(items, k):
            if not build_ok({c: items[c] for c in combo}):
                sub = {c: items[c] for c in combo}
                if rg:
                    rg.record("bisect_interaction", pkgs=list(combo))
                return sub
    return dict(items)


def recover(store, culprits, alerts_by_pkg, rg: RunGraph):
    """For each culprit bump: try the next clean non-major version; else pin with a
    recorded exception; else escalate."""

    from .remediate import _clean_versions

    out = []
    for pk, (frm, to) in culprits.items():
        eco, name = pk.split("/", 1)
        pid = store.pkg_id(eco, name)
        # find current vid
        cur_vid = next((v for v in store.versions_of(pid) if str(store.ver_str[v]) == frm), -1)
        if cur_vid < 0:
            rg.set_status(pk, "escalated", "current version not in graph")
            out.append((pk, "escalate"))
            continue
        cands = _clean_versions(store, pid, cur_vid)
        alt = next(((v) for vid, v, newer, major in cands if newer and not major), None)
        if alt and alt != to:
            rg.propose(pk, frm, alt, "recovery: next clean non-major after build break")
            out.append((pk, f"retry -> {alt}"))
        else:
            rg.set_status(
                pk, "escalated", f"only fix is {to} which breaks the build; pin + exception"
            )
            out.append((pk, "pin+exception"))
    return out


if __name__ == "__main__":
    rg = RunGraph("demo")
    bumps = {
        "a": ("1.0.0", "1.2.0"),
        "b": ("2.0.0", "3.0.0"),
        "c": ("0.4.0", "0.4.9"),
        "d": ("5.1.0", "6.0.0"),
    }

    # pretend "b" is the culprit: build fails iff b is bumped
    def build_ok(applied):
        return applied.get("b", ("2.0.0", "2.0.0"))[1] != "3.0.0"

    culprit = bisect_build(bumps, build_ok, rg)
    print("bisect found culprit:", culprit)
    print("run graph:", json.dumps(rg.snapshot(), indent=2))
