"""The deliverable: a manifest -> a cited exposure report + a minimal remediation plan
+ a CycloneDX SBOM with per-component exposure annotations.

Everything here is DETERMINISTIC - the graph decides what is exposed, what the path is,
and what the safe bump is. With a GPU a judge model adds prose (the "why this matters"
paragraph, the migration note), fact-checked against the path set - it never adds or
removes a finding.
"""

from __future__ import annotations

import datetime
import json

from .cvss import band
from .ladder import AlertLadder
from .paths import ExposurePath, exposure_paths
from .remediate import greedy_fix


def exposure_report(
    store, root_vid, grounder=None, as_of=None, min_severity=0.0, reachability=None
):
    pid = int(store.ver_pkg[root_vid])
    manifest = f"{store.pkg_eco[pid]}/{store.pkg_name[pid]}@{store.ver_str[root_vid]}"
    paths = list(exposure_paths(store, root_vid, 12, 400))
    lad = AlertLadder(store, as_of=as_of, min_severity=min_severity)

    by_adv: dict[str, list[ExposurePath]] = {}
    for p in paths:
        by_adv.setdefault(p.advisory, []).append(p)

    alerted: list[dict] = []
    suppressed: list[dict] = []
    for adv, ps in by_adv.items():
        v = lad.evaluate([{"via": "tree"}], ps, reachability=reachability)
        best = min(ps, key=lambda x: (x.depth, -x.severity))
        row = {
            "advisory": adv,
            "osv_id": best.osv_id,
            "severity": round(best.severity, 1),
            "band": band(best.severity),
            "depth": best.depth,
            "path": best.render(store),
            "terminal": best.terminal_pkg,
            "published": best.published,
            "reason": v.reason,
        }
        (alerted if v.alert else suppressed).append(row)

    rem = greedy_fix(
        store,
        root_vid,
        [p for adv, ps in by_adv.items() for p in ps if adv in {a["advisory"] for a in alerted}],
    )

    alerted.sort(key=lambda r: (-r["severity"], r["depth"]))
    return {
        "manifest": manifest,
        "generated": datetime.date.today().isoformat(),
        "as_of": as_of,
        "alerted": alerted,
        "suppressed": suppressed,
        "remediation": {
            "bumps": rem.bumps,
            "unfixable": rem.unfixable,
            "cleared": rem.cleared,
            "total": len(alerted),
        },
    }


def to_markdown(rep, max_show=12) -> str:
    L = [
        f"# Supply-chain exposure - `{rep['manifest']}`",
        f"_generated {rep['generated']}"
        + (f" - as-of {rep['as_of']}" if rep["as_of"] else "")
        + "_",
        "",
    ]
    a, s = rep["alerted"], rep["suppressed"]
    L += [
        f"**{len(a)} exposures** need action - {len(s)} findings suppressed (with reason) - "
        f"an `npm audit`-style tool would show all {len(a) + len(s)}.",
        "",
    ]
    if a:
        direct = [r for r in a if r["depth"] == 0]
        trans = [r for r in a if r["depth"] > 0]
        if direct:
            _n = len(direct)
            L += [
                f"## Direct exposures ({_n}) - a vulnerable version is a direct dependency",
                "",
            ]
            for r in direct[:max_show]:
                head = f"{r['band'].upper()} ({r['severity']})"
                L.append(f"- **{r['advisory']}**  {head}  -  `{r['terminal']}`")
            if len(direct) > max_show:
                L.append(f"- _... and {len(direct) - max_show} more direct_")
            L.append("")
        if trans:
            L += ["## Transitive exposures (each carries the path that proves it)", ""]
            for r in trans[:max_show]:
                head = f"{r['band'].upper()} ({r['severity']})  -  depth {r['depth']}"
                L += [f"### {r['advisory']}  -  {head}", "```", r["path"], "```", ""]
    rm = rep["remediation"]
    if rm["bumps"] or rm["unfixable"]:
        L += ["## Minimal remediation", ""]
        for pk, (frm, to, major) in rm["bumps"].items():
            tag = "  **(MAJOR — review breaking changes)**" if major else ""
            L.append(f"- `{pk}`  {frm} → **{to}**{tag}")
        for pk, why in rm["unfixable"]:
            L.append(f"- `{pk}`  ⚠️ **no safe fix**: {why}")
        L += [
            "",
            f"_{rm['cleared']}/{rm['total']} exposures cleared by {len(rm['bumps'])} bump(s)._",
            "",
        ]
    if s:
        L += [
            "## Suppressed (present in the tree, not actioned)",
            "",
            "| finding | why not an alert |",
            "|---|---|",
        ]
        for r in s[:40]:
            L.append(f"| {r['advisory']} ({r['band']}) | `{r['reason']}` |")
    return "\n".join(L).replace("—", "-").replace("·", "-")


def resolved_requirements(store, root_vid, ecosystem, max_nodes=4000) -> str:
    """Serialise a resolved dependency tree as a lockfile osv-scanner can read:
      pypi -> requirements.txt  (name==version, one per line)
      npm  -> package-lock.json (lockfileVersion 3, flat `packages` map)
    Used only for the S26 head-to-head; not part of the alerting path."""
    from collections import deque

    pins: dict[str, str] = {}
    q = deque([root_vid])
    seen = {root_vid}
    while q and len(pins) < max_nodes:
        v = q.popleft()
        p = int(store.ver_pkg[v])
        pins[str(store.pkg_name[p])] = str(store.ver_str[v])
        for n in store.resolves_to(v):
            n = int(n)
            if n not in seen:
                seen.add(n)
                q.append(n)
    if ecosystem == "pypi":
        return "\n".join(f"{k}=={v}" for k, v in sorted(pins.items()) if v) + "\n"
    if ecosystem == "npm":
        pkgs = {"": {"name": "generated", "version": "0.0.0"}}
        for k, v in pins.items():
            if v:
                pkgs[f"node_modules/{k}"] = {"version": v}
        return json.dumps(
            {
                "name": "generated",
                "version": "0.0.0",
                "lockfileVersion": 3,
                "requires": True,
                "packages": pkgs,
            }
        )
    return ""


def to_cyclonedx(store, root_vid, rep) -> dict:
    """A minimal CycloneDX 1.5 SBOM with a `vulnerabilities` section pointing at the
    exposure paths. Real tools consume this."""
    from collections import deque

    pid = int(store.ver_pkg[root_vid])
    comps, seen = [], {root_vid}
    q = deque([root_vid])
    while q:
        v = q.popleft()
        p = int(store.ver_pkg[v])
        comps.append(
            {
                "type": "library",
                "name": str(store.pkg_name[p]),
                "version": str(store.ver_str[v]),
                "purl": f"pkg:{store.pkg_eco[p]}/{store.pkg_name[p]}@{store.ver_str[v]}",
            }
        )
        for n in store.resolves_to(v):
            n = int(n)
            if n not in seen:
                seen.add(n)
                q.append(n)
    vulns = [
        {
            "id": r["advisory"],
            "source": {"name": "OSV"},
            "ratings": [{"score": r["severity"], "severity": r["band"], "method": "CVSSv3"}],
            "affects": [{"ref": r["terminal"]}],
            "description": f"exposure path: {r['path']}",
        }
        for r in rep["alerted"]
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": rep["generated"],
            "component": {
                "type": "application",
                "name": str(store.pkg_name[pid]),
                "version": str(store.ver_str[root_vid]),
            },
        },
        "components": comps,
        "vulnerabilities": vulns,
    }


if __name__ == "__main__":
    from pathlib import Path

    from .kgstore import KGStore

    S = KGStore(str(Path(__file__).resolve().parent.parent / "data" / "graph"))
    roots = [v for v in range(S.N) if S.ver_default[v] and len(S.dependents(v)) == 0]
    scored = sorted(((len(exposure_paths(S, r, 12, 60)), r) for r in roots), reverse=True)
    rep = exposure_report(S, scored[0][1])
    print(to_markdown(rep)[:2000])
