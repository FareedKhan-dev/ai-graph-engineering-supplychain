"""Agent Coordination (survey S4.3) - built so it can be MEASURED against a one-pass
pipeline, which is the survey's actual open question.

  CapabilityGraph  typed edges agent -> {ecosystem it handles, tool it holds,
                   measured reliability per task class}. Routing is a graph query.
  Team             fan-out per (manifest x package) -> fan-in to one report.
                   PatchProposer and BuildVerifier are SEPARATE nodes on purpose:
                   the survey's confirmation-bias failure ("the agent that writes
                   the patch grades the patch") is designed out, not prompted away.
  CommGraph        every message an agent sends another is an edge; the notebook
                   renders it and measures which edges carried decisive information.

In SMOKE the "model" calls are deterministic stand-ins (a real 14B judge slots in when
a GPU is available). The point of the smoke run is the CONTROL FLOW and the MEASUREMENT
HARNESS, not the model quality.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .ladder import AlertLadder
from .paths import ExposurePath, exposure_paths
from .remediate import greedy_fix

# ---------------------------------------------------------------- capability graph
CAPABILITIES = {
    "Resolver.npm": {"ecosystems": {"npm"}, "task": "resolve", "reliability": 0.98},
    "Resolver.pypi": {"ecosystems": {"pypi"}, "task": "resolve", "reliability": 0.95},
    "Resolver.maven": {"ecosystems": {"maven"}, "task": "resolve", "reliability": 0.93},
    "Resolver.cargo": {"ecosystems": {"cargo"}, "task": "resolve", "reliability": 0.97},
    "Resolver.go": {"ecosystems": {"go"}, "task": "resolve", "reliability": 0.90},
    "AdvisoryMatcher": {"ecosystems": {"*"}, "task": "match", "reliability": 0.99},
    "Reach.JS": {"ecosystems": {"npm"}, "task": "reach", "reliability": 0.70},
    "Reach.PY": {"ecosystems": {"pypi"}, "task": "reach", "reliability": 0.62},
    "Reach.JVM": {"ecosystems": {"maven"}, "task": "reach", "reliability": 0.80},
    "LicenseAuditor": {"ecosystems": {"*"}, "task": "license", "reliability": 1.00},
    "PatchProposer": {"ecosystems": {"*"}, "task": "patch", "reliability": 0.85},
    "BuildVerifier": {"ecosystems": {"*"}, "task": "verify", "reliability": 0.92},
    "Escalator": {"ecosystems": {"*"}, "task": "escalate", "reliability": 1.00},
}


class CapabilityGraph:
    def __init__(self, caps=CAPABILITIES):
        self.caps = caps

    def route(self, task: str, ecosystem: str):
        best = None
        for name, c in self.caps.items():
            if c["task"] != task:
                continue
            serves = "*" in c["ecosystems"] or ecosystem in c["ecosystems"]
            if serves and (best is None or c["reliability"] > self.caps[best]["reliability"]):
                best = name
        return best


# ---------------------------------------------------------------- comms graph
@dataclass
class CommGraph:
    edges: list = field(default_factory=list)  # (src, dst, kind, payload_size, decisive)

    def send(self, src, dst, kind, payload, decisive=False):
        self.edges.append((src, dst, kind, len(str(payload)), decisive))

    def summary(self):
        from collections import Counter

        k = Counter(e[2] for e in self.edges)
        dec = sum(1 for e in self.edges if e[4])
        return {"messages": len(self.edges), "by_kind": dict(k), "decisive": dec}


# ---------------------------------------------------------------- the coordinated run
@dataclass
class AuditResult:
    manifest: str
    alerts: list
    suppressed: list
    remediation: object
    comm: CommGraph
    seconds: float
    mode: str


def _reachability_stub(store, path):
    """Deterministic stand-in: 'reachable' if the terminal is a DIRECT dep (depth<=1)
    or CVSS>=9, 'unreachable' if it is a deep dev-ish leaf, else 'undetermined'.
    With a GPU this is a static call-graph query plus a judge call."""
    if path.depth <= 1 or path.severity >= 9.0:
        return "reachable"
    if path.depth >= 4 and path.severity < 5.0:
        return "unreachable"
    return "undetermined"


def run_one_pass(store, root_vid, grounder=None, min_severity=0.0):
    """The baseline: ground -> traverse -> gate -> remediate. No feedback edge."""
    t = time.time()
    comm = CommGraph()
    paths = list(exposure_paths(store, root_vid, 12, 200))
    live = [p for p in paths if not p.withdrawn]
    lad = AlertLadder(store, min_severity=min_severity)
    by_adv: dict[str, list[ExposurePath]] = {}
    for p in live:
        by_adv.setdefault(p.advisory, []).append(p)
    alerts: list[tuple[str, str, ExposurePath]] = []
    supp: list[tuple[str, str, ExposurePath]] = []
    for adv, ps in by_adv.items():
        v = lad.evaluate([{"via": "t"}], ps)
        (alerts if v.alert else supp).append((adv, v.reason, ps[0]))
    rem = greedy_fix(store, root_vid, [p for a, _, p in alerts])
    pid = int(store.ver_pkg[root_vid])
    return AuditResult(
        f"{store.pkg_eco[pid]}/{store.pkg_name[pid]}@{store.ver_str[root_vid]}",
        alerts,
        supp,
        rem,
        comm,
        time.time() - t,
        "one_pass",
    )


def run_coordinated(store, root_vid, capgraph=None, min_severity=0.0):
    """The team: same pipeline, but ReachabilityAnalyst gates PatchProposer
    (only patch what is on a live path), BuildVerifier can bounce a patch back
    (REFINE), and Escalator handles the unfixable. Every hand-off is a comm edge."""
    t = time.time()
    cg = capgraph or CapabilityGraph()
    comm = CommGraph()
    pid = int(store.ver_pkg[root_vid])
    eco = str(store.pkg_eco[pid])

    resolver = cg.route("resolve", eco)
    comm.send("Orchestrator", resolver, "task", "resolve tree")
    paths = [p for p in exposure_paths(store, root_vid, 12, 200) if not p.withdrawn]
    comm.send(resolver, "AdvisoryMatcher", "resolved-tree", paths)

    by_adv: dict[str, list[ExposurePath]] = {}
    for p in paths:
        by_adv.setdefault(p.advisory, []).append(p)
    comm.send(
        "AdvisoryMatcher",
        "Reach." + {"npm": "JS", "pypi": "PY", "maven": "JVM"}.get(eco, "JS"),
        "matched-advisories",
        by_adv,
    )

    reach = {a: _reachability_stub(store, ps[0]) for a, ps in by_adv.items()}
    on_path = [a for a, r in reach.items() if r != "unreachable"]
    comm.send(
        "Reach",
        "PatchProposer",
        f"{len(on_path)}/{len(by_adv)} on a live path",
        on_path,
        decisive=(len(on_path) < len(by_adv)),
    )

    lad = AlertLadder(store, min_severity=min_severity)
    alerts, supp = [], []
    for adv, ps in by_adv.items():
        v = lad.evaluate([{"via": "t"}], ps, reachability=reach)
        if v.alert and adv in on_path:
            alerts.append((adv, "exposed", ps[0]))
        else:
            supp.append((adv, reach.get(adv, "?") if adv not in on_path else v.reason, ps[0]))

    rem = greedy_fix(store, root_vid, [p for a, _, p in alerts])
    # BuildVerifier: a major bump has a 40% chance of "breaking the build" -> REFINE
    import random

    rng = random.Random(int(store.ver_pkg[root_vid]))
    broken = [pk for pk, (fr, to, major) in rem.bumps.items() if major and rng.random() < 0.4]
    if broken:
        comm.send(
            "BuildVerifier",
            "PatchProposer",
            f"{len(broken)} bumps break the build",
            broken,
            decisive=True,
        )
        rem2 = greedy_fix(store, root_vid, [p for a, _, p in alerts], allow_major=False)
        rem = rem2
    if rem.unfixable:
        comm.send("PatchProposer", "Escalator", f"{len(rem.unfixable)} unfixable", rem.unfixable)

    return AuditResult(
        f"{store.pkg_eco[pid]}/{store.pkg_name[pid]}@{store.ver_str[root_vid]}",
        alerts,
        supp,
        rem,
        comm,
        time.time() - t,
        "coordinated",
    )


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    roots = [v for v in range(S.N) if S.ver_default[v] and len(S.dependents(v)) == 0][:200]
    op_a = co_a = op_fix = co_fix = 0
    for r in roots:
        a = run_one_pass(S, r)
        b = run_coordinated(S, r)
        op_a += len(a.alerts)
        co_a += len(b.alerts)
        op_fix += a.remediation.cleared
        co_fix += b.remediation.cleared
    print(f"one-pass    : {op_a} alerts, {op_fix} advisories cleared by remediation")
    print(
        f"coordinated : {co_a} alerts, {co_fix} advisories cleared "
        f"(reachability gate suppresses the unreachable; verifier bounces breaking majors)"
    )
