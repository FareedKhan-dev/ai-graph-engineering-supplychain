"""CVSS v3.x / v4.0 vector -> base score.

OSV stores `severity: [{type: "CVSS_V3", score: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]`
i.e. the vector string, not the number. The base-score formula is fully specified
(FIRST CVSS v3.1 spec §7.1); it is arithmetic, no model. v4.0 base scoring is a
lookup table — we approximate it from the v3-equivalent metrics, and mark it.
"""

from __future__ import annotations

import math

_V3 = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20},
    "AC": {"L": 0.77, "H": 0.44},
    "PR": {"N": 0.85, "L": 0.62, "H": 0.27},  # unchanged-scope values
    "PR_C": {"N": 0.85, "L": 0.68, "H": 0.50},  # changed-scope
    "UI": {"N": 0.85, "R": 0.62},
    "C": {"H": 0.56, "L": 0.22, "N": 0.0},
    "I": {"H": 0.56, "L": 0.22, "N": 0.0},
    "A": {"H": 0.56, "L": 0.22, "N": 0.0},
}


def _roundup(x: float) -> float:
    return math.ceil(x * 10) / 10


def score_v3(vector: str) -> float:
    m = dict(p.split(":", 1) for p in vector.split("/") if ":" in p)
    try:
        scope_changed = m.get("S") == "C"
        isc_base = 1 - (1 - _V3["C"][m["C"]]) * (1 - _V3["I"][m["I"]]) * (1 - _V3["A"][m["A"]])
        if scope_changed:
            impact = 7.52 * (isc_base - 0.029) - 3.25 * (isc_base - 0.02) ** 15
        else:
            impact = 6.42 * isc_base
        pr = _V3["PR_C"][m["PR"]] if scope_changed else _V3["PR"][m["PR"]]
        expl = 8.22 * _V3["AV"][m["AV"]] * _V3["AC"][m["AC"]] * pr * _V3["UI"][m["UI"]]
        if impact <= 0:
            return 0.0
        if scope_changed:
            return min(_roundup(1.08 * (impact + expl)), 10.0)
        return min(_roundup(impact + expl), 10.0)
    except (KeyError, ZeroDivisionError):
        return 0.0


def score_v4(vector: str) -> float:
    """Coarse v4 approximation: reuse the v3 formula on the shared base metrics
    (AV/AC/PR/UI/VC->C/VI->I/VA->A). Flagged as approximate by the caller."""
    v = vector.replace("VC:", "C:").replace("VI:", "I:").replace("VA:", "A:")
    m = dict(p.split(":", 1) for p in v.split("/") if ":" in p)
    keep: dict[str, str] = {k: m[k] for k in ("AV", "AC", "PR", "UI", "C", "I", "A") if k in m}
    keep.setdefault("S", "U")
    return score_v3("/".join(f"{k}:{val}" for k, val in keep.items()))


def base_score(severity_list) -> float:
    """OSV `severity` list -> best base score."""
    best = 0.0
    for s in severity_list or []:
        raw = str(s.get("score", "")).strip()
        s.get("type", "")
        if not raw:
            continue
        try:  # sometimes it's already a number
            best = max(best, min(float(raw), 10.0))
            continue
        except ValueError:
            pass
        if raw.startswith("CVSS:4"):
            best = max(best, score_v4(raw))
        elif raw.startswith("CVSS:3") or "AV:" in raw:
            best = max(best, score_v3(raw))
    return round(best, 1)


def band(score: float) -> str:
    return (
        "none"
        if score == 0
        else "low"
        if score < 4
        else "medium"
        if score < 7
        else "high"
        if score < 9
        else "critical"
    )


if __name__ == "__main__":
    log4shell = [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"}]
    s = base_score(log4shell)
    assert 9.5 <= s <= 10.0, s  # Log4Shell is 10.0
    med = base_score([{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:H/PR:L/UI:N/S:U/C:L/I:N/A:N"}])
    assert 2.5 <= med <= 4.5, med
    print(f"cvss.py OK  (log4shell={s}, band={band(s)})")
