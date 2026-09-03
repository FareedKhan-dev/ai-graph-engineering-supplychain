"""Reachability (Part IV S17): is the vulnerable code actually on a call path?

Two layers:

  reachability_prior   CPU, no model. A calibrated prior from graph structure alone:
                       dependency KIND (runtime vs dev/optional), DEPTH, whether the
                       affected package is a DIRECT dep of the root, and whether OSV
                       names a specific vulnerable symbol. This already suppresses the
                       obvious noise (a ReDoS advisory on a build-only formatter).

  call_graph_reachability  GPU/tools. Static call-graph extraction from the repo's
                       entrypoints to the vulnerable symbol - jelly / js-callgraph
                       (JS), PyCG (Python), java-callgraph / OPAL (JVM). Returns a
                       three-way verdict. Interface defined here; the extractor binary
                       is invoked in S17 on a box that carries the tools. `undetermined`
                       is honest, not a failure - dynamic dispatch / reflection / DI
                       make it common.

Ground truth: OpenSSF / OSV VEX 'not affected' statements + advisories with a named
vulnerable function.  The notebook reports precision/recall PER ECOSYSTEM and refuses
to pool them (S18 - reachability does not transfer across analysers).
"""

from __future__ import annotations

REACHABLE, UNREACHABLE, UNDETERMINED = "reachable", "unreachable", "undetermined"


_SYM_HINT = ("function", "method", "() ", "call to", "vulnerable symbol", "api endpoint")


def _osv_has_symbol(store, advisory_canon):
    """Does the advisory name a specific vulnerable function/symbol? (Go advisories
    almost always do via `ecosystem_specific.imports`; others sometimes in details.)
    O(1) via the store's canon->idx map; smoke approximates from the summary text."""
    idx = getattr(store, "canon_to_idx", {}).get(advisory_canon)
    if idx is None:
        return False
    return any(k in str(store.adv_summary[idx]).lower() for k in _SYM_HINT)


def reachability_prior(store, path, dep_kind="runtime"):
    """A prior in {reachable, unreachable, undetermined} from structure alone.
    Deliberately conservative: only says `unreachable` when the evidence is strong."""
    if dep_kind in ("dev", "test", "development", "optional"):
        return UNREACHABLE  # not shipped
    if path.depth <= 1:
        return REACHABLE  # direct dep, in your import graph
    if path.severity >= 9.0:
        return REACHABLE  # critical -> assume worst until proven
    if path.depth >= 5 and path.severity < 5.0 and not _osv_has_symbol(store, path.advisory):
        return UNREACHABLE  # deep, low-sev, no named symbol
    return UNDETERMINED


def reachability_map(store, paths, dep_kinds=None):
    dk = dep_kinds or {}
    out: dict[str, str] = {}
    for p in paths:
        cur = out.get(p.advisory)
        v = reachability_prior(store, p, dk.get(p.advisory, "runtime"))
        # most-severe verdict across paths for the same advisory
        rank = {REACHABLE: 2, UNDETERMINED: 1, UNREACHABLE: 0}
        if cur is None or rank[v] > rank[cur]:
            out[p.advisory] = v
    return out


# ---------------------------------------------------------------- GPU / tools layer
_EXTRACTOR = {
    "npm": ["jelly", "--tokens", "--callgraph"],  # tsjs jelly
    "pypi": ["pycg", "--package"],
    "maven": ["java", "-jar", "java-callgraph.jar"],
}


def call_graph_reachability(repo_dir, ecosystem, vulnerable_symbol, entrypoints=None):
    """Run the ecosystem's static call-graph tool; return (verdict, evidence).
    Stub on any box without the tool installed; provide the extractors on PATH to use it."""
    import shutil

    tool = _EXTRACTOR.get(ecosystem, [None])[0]
    if tool is None or shutil.which(tool) is None:
        return UNDETERMINED, {"reason": f"{tool or ecosystem} call-graph tool not on PATH"}
    # ... invoke tool, parse the graph, BFS from entrypoints to vulnerable_symbol ...
    raise NotImplementedError(
        "invoke the extractor, load its JSON call graph, BFS entrypoints -> symbol. "
        "See docs/architecture.md (the reachability gate)."
    )


def risk_coverage(verdicts, is_real):
    """For the `undetermined` bucket: if we treat undetermined as 'alert', what is the
    coverage / control-leak trade? Returns points for the curve."""
    import numpy as np

    v = np.asarray(verdicts, object)
    real = np.asarray(is_real, bool)
    out = []
    for policy in ("reachable_only", "reachable+undetermined", "all"):
        if policy == "reachable_only":
            keep = v == REACHABLE
        elif policy == "reachable+undetermined":
            keep = v != UNREACHABLE
        else:
            keep = np.ones(len(v), bool)
        cov = float((keep & real).sum() / max(real.sum(), 1))
        leak = float((keep & ~real).sum() / max((~real).sum(), 1))
        out.append({"policy": policy, "coverage": cov, "control_leak": leak})
    return out


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore
    from .paths import exposure_paths

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    roots = [v for v in range(S.N) if S.ver_default[v] and len(S.dependents(v)) == 0]
    from collections import Counter

    verdicts: Counter[str] = Counter()
    for r in roots[:300]:
        for p in exposure_paths(S, r, 12, 60):
            verdicts[reachability_prior(S, p)] += 1
    print("reachability prior over exposure paths (structure only, no model):")
    for k, n in verdicts.most_common():
        print(f"  {k:<14} {n}")
