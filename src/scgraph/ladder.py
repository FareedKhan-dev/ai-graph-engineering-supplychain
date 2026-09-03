"""The alert ladder (notebook §8, "the refusal ladder").

Six gates. All but the last are pure graph predicates, evaluated before any model
is invoked. A refusal here is not a model choosing to be cautious; it is an empty
result set from a deterministic query. The point of the whole design: turn
"npm audit says 47 things" into a short list whose every entry carries a path, and
an explicit refusal for everything that cannot be justified.

  gate 1  nothing grounded            question named no package we index
  gate 2  package not in the tree     grounded, but no exposure path exists
  gate 3  no version in an affected range   (subsumed: no path terminal is affected)
  gate 4  affected only via a non-installable version   (yanked / unpublished)
  gate 5  every path runs through a WITHDRAWN advisory
  gate 6  as-of-date: advisory published AFTER the version we ship  (the notebook's
          `as_of` gate — "was this knowable when we shipped v2.3?")
  gate 7  (later section) reachability: present but the vulnerable symbol is not on
          a live call path -> ANNOTATE, do not alert
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Verdict:
    alert: bool
    reason: str
    n_paths_total: int = 0
    n_paths_usable: int = 0
    detail: str = ""
    paths: list = field(default_factory=list)


class AlertLadder:
    def __init__(self, store, as_of=None, min_severity=0.0, alert_on_unreachable=False):
        self.s = store
        self.as_of = as_of  # "YYYY-MM-DD" or None
        self.min_severity = min_severity
        self.alert_on_unreachable = alert_on_unreachable

    def evaluate(self, groundings, paths, reachability=None):
        s = self.s
        if not groundings:
            return Verdict(
                False,
                "not_grounded",
                detail="nothing in the question resolves to a package or advisory we index",
            )
        if not paths:
            return Verdict(
                False,
                "no_exposure_path",
                detail="grounded, but no resolved dependency path reaches an affected version",
            )

        # gate 4: drop paths whose terminal version is yanked / not installable
        usable = [p for p in paths if _installable(s, p.hops[-1])]
        if not usable:
            return Verdict(
                False,
                "only_noninstallable_evidence",
                len(paths),
                0,
                "affected only via a yanked or unpublished version",
                paths,
            )

        # gate 5: every remaining path is a withdrawn advisory
        live = [p for p in usable if not p.withdrawn]
        if not live:
            return Verdict(
                False,
                "only_withdrawn_advisories",
                len(paths),
                0,
                "every affected path runs through a withdrawn advisory",
                paths,
            )

        # gate 6: as-of date — advisory not knowable when the shipped version was published
        if self.as_of is not None:
            knowable = [p for p in live if p.published and p.published[:10] <= self.as_of]
            if not knowable:
                return Verdict(
                    False,
                    "not_knowable_as_of_date",
                    len(paths),
                    0,
                    f"no supporting advisory was published on or before {self.as_of}",
                    paths,
                )
            live = knowable

        # severity floor
        sev = [p for p in live if p.severity >= self.min_severity or p.severity == 0.0]
        if not sev:
            return Verdict(
                False,
                "below_severity_floor",
                len(paths),
                len(live),
                f"all matched advisories below CVSS {self.min_severity}",
                paths,
            )
        live = sev

        # gate 7: reachability annotation (optional gate)
        if reachability is not None and not self.alert_on_unreachable:
            reachable = [
                p for p in live if reachability.get(p.advisory, "undetermined") != "unreachable"
            ]
            if not reachable:
                return Verdict(
                    False,
                    "present_but_unreachable",
                    len(paths),
                    0,
                    "affected versions present, but the vulnerable symbol is "
                    "not on a live call path (annotate for review)",
                    paths,
                )
            live = reachable

        live.sort(key=lambda p: (-p.severity, p.depth))
        return Verdict(True, "exposed", len(paths), len(live), "", live)


def _installable(store, vid):
    # smoke proxy: a version present in our snapshot with a non-empty string.
    # FULL run replaces this with the registry `yanked` / `deprecated` flag.
    return bool(str(store.ver_str[vid]))


def audit_manifest(store, ladder, grounder, root_vid, max_depth=12, max_paths=200):
    """One manifest -> a full exposure report. Every advisory that touches the tree
    is classified: exposed (with path) / withdrawn / not-knowable / etc."""
    from .paths import ExposurePath, exposure_paths

    all_paths = exposure_paths(store, root_vid, max_depth, max_paths)
    by_adv: dict[str, list[ExposurePath]] = {}
    for p in all_paths:
        by_adv.setdefault(p.advisory, []).append(p)
    report = []
    for adv, ps in by_adv.items():
        v = ladder.evaluate([{"via": "tree"}], ps)
        report.append(
            {
                "advisory": adv,
                "verdict": v.reason,
                "alert": v.alert,
                "n_paths": len(ps),
                "min_depth": min(p.depth for p in ps),
                "severity": max(p.severity for p in ps),
                "example_path": ps[0].render(store),
            }
        )
    report.sort(key=lambda r: (not r["alert"], -r["severity"]))
    return report
