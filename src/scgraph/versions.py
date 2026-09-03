"""Per-ecosystem version comparison + OSV affected-range evaluation.

The load-bearing operation for the whole pipeline is: *given an OSV `affected` entry
and a concrete resolved version, is that version affected?* OSV encodes ranges as a
sorted list of `events` (`introduced` / `fixed` / `last_affected`) plus, often, an
explicit `versions` list. When the explicit list is present it is unambiguous and we
use it. Otherwise we walk the events, which needs a correct per-ecosystem ordering.

We deliberately do NOT parse declared-dependency ranges (`^1.2.0` in package.json)
here: the traversable graph is built from *resolved* versions (deps.dev / lockfiles),
so range parsing is only needed for OSV events, and OSV events are (almost always)
exact versions, not ranges. That removes node-semver range parsing from the hot path.
"""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Any

_PyVer: Any
_PyInvalid: type[BaseException]
try:  # PyPI ordering is a solved problem — use it
    from packaging.version import InvalidVersion as _PyInvalid
    from packaging.version import Version as _PyVer
except Exception:  # pragma: no cover
    _PyVer = None
    _PyInvalid = Exception

_SEMVER_RE = re.compile(
    r"^[vV]?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?"
)


def _semver_parts(v: str):
    """(major, minor, patch, prerelease-tuple-or-None). Tolerant of go +incompatible
    and pseudo-versions; falls back to a loose numeric split."""
    v = (v or "").strip()
    v = v.split("+incompatible", 1)[0]
    m = _SEMVER_RE.match(v)
    if m:
        pre = m.group("pre")
        pre_ids = tuple(pre.split(".")) if pre else None
        return (int(m["major"]), int(m["minor"]), int(m["patch"]), pre_ids)
    nums = re.findall(r"\d+", v)
    nums = [int(x) for x in nums[:3]] + [0, 0, 0]
    return (nums[0], nums[1], nums[2], None)


def _cmp_pre(a_pre, b_pre) -> int:
    """SemVer 2.0.0 §11: no prerelease outranks a prerelease; otherwise compare
    identifiers, numeric < numeric numerically, else lexically, longer wins on tie."""
    if a_pre is None and b_pre is None:
        return 0
    if a_pre is None:
        return 1
    if b_pre is None:
        return -1
    for x, y in zip(a_pre, b_pre):
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            d = int(x) - int(y)
            if d:
                return (d > 0) - (d < 0)
        elif xn != yn:
            return -1 if xn else 1
        elif x != y:
            return (x > y) - (x < y)
    return (len(a_pre) > len(b_pre)) - (len(a_pre) < len(b_pre))


def _cmp_semver(a: str, b: str) -> int:
    am, an, ap, apre = _semver_parts(a)
    bm, bn, bp, bpre = _semver_parts(b)
    for x, y in ((am, bm), (an, bn), (ap, bp)):
        if x != y:
            return (x > y) - (x < y)
    return _cmp_pre(apre, bpre)


_MAVEN_QUALIFIERS = {
    "alpha": -6,
    "beta": -5,
    "milestone": -4,
    "rc": -3,
    "cr": -3,
    "snapshot": -2,
    "": -1,
    "final": 0,
    "ga": 0,
    "release": 0,
    "sp": 1,
}


def _maven_tokens(v: str):
    v = (v or "").strip().lower()
    out: list[int | str] = []
    buf, is_num = "", None
    for ch in v:
        if ch in ".-":
            if buf:
                out.append(int(buf) if is_num else buf)
            buf, is_num = "", None
            continue
        d = ch.isdigit()
        if is_num is not None and d != is_num and buf:
            out.append(int(buf) if is_num else buf)
            buf = ""
        buf += ch
        is_num = d
    if buf:
        out.append(int(buf) if is_num else buf)
    return out


def _cmp_maven(a: str, b: str) -> int:
    ta, tb = _maven_tokens(a), _maven_tokens(b)
    for i in range(max(len(ta), len(tb))):
        xa = ta[i] if i < len(ta) else 0
        xb = tb[i] if i < len(tb) else 0
        if isinstance(xa, str):
            xa = _MAVEN_QUALIFIERS.get(xa, xa)
        if isinstance(xb, str):
            xb = _MAVEN_QUALIFIERS.get(xb, xb)
        if isinstance(xa, str) and isinstance(xb, int):
            return -1
        if isinstance(xa, int) and isinstance(xb, str):
            return 1
        if xa != xb:
            return (xa > xb) - (xa < xb)
    return 0


def _cmp_pep440(a: str, b: str) -> int:
    if _PyVer is None:
        return _cmp_semver(a, b)
    try:
        pa, pb = _PyVer(a), _PyVer(b)
    except _PyInvalid:
        return _cmp_semver(a, b)
    return (pa > pb) - (pa < pb)


_CMP = {
    "npm": _cmp_semver,
    "cargo": _cmp_semver,
    "crates.io": _cmp_semver,
    "go": _cmp_semver,
    "rubygems": _cmp_semver,
    "packagist": _cmp_semver,
    "nuget": _cmp_semver,
    "pypi": _cmp_pep440,
    "pip": _cmp_pep440,
    "maven": _cmp_maven,
}


def compare(a: str, b: str, ecosystem: str = "npm") -> int:
    """-1 / 0 / 1 for a<b / a==b / a>b under the ecosystem's version ordering."""
    fn = _CMP.get((ecosystem or "").lower(), _cmp_semver)
    try:
        return fn(a, b)
    except Exception:
        return _cmp_semver(a, b)


def sort_versions(versions, ecosystem: str = "npm"):
    def _cmp(x: str, y: str) -> int:
        return compare(x, y, ecosystem)

    return sorted(versions, key=cmp_to_key(_cmp))


def in_osv_range(version: str, events: list, ecosystem: str = "npm") -> bool:
    """Walk a single OSV `ranges[].events` list (already list of {key:val} dicts).
    A version is affected iff it lies in an [introduced, fixed) or [introduced,
    last_affected] interval opened by the walk."""
    intervals, cur = [], None
    ev = []
    for e in events:
        for k, val in e.items():
            ev.append((k, val))
    # OSV spec: events are sorted; "0" introduced means "from the beginning"
    for k, val in ev:
        if k == "introduced":
            cur = val
        elif k == "fixed":
            intervals.append((cur, val, False))
            cur = None
        elif k == "last_affected":
            intervals.append((cur, val, True))
            cur = None
    if cur is not None:
        intervals.append((cur, None, False))
    for lo, hi, inclusive in intervals:
        ge_lo = lo in (None, "0") or compare(version, lo, ecosystem) >= 0
        if not ge_lo:
            continue
        if hi is None:
            return True
        c = compare(version, hi, ecosystem)
        if (c <= 0) if inclusive else (c < 0):
            return True
    return False


def affected(version: str, osv_affected_entry: dict, ecosystem: str = "npm") -> bool:
    """Top-level: is `version` affected by one OSV `affected` entry?
    Prefer the explicit `versions` list; else evaluate every `ranges` block."""
    exact = osv_affected_entry.get("versions")
    if exact:
        return version in set(exact)
    for rng in osv_affected_entry.get("ranges", []):
        if rng.get("type") == "GIT":
            continue
        if in_osv_range(version, rng.get("events", []), ecosystem):
            return True
    return False


def fixed_versions(osv_affected_entry: dict) -> list:
    out = []
    for rng in osv_affected_entry.get("ranges", []):
        for e in rng.get("events", []):
            if "fixed" in e:
                out.append(e["fixed"])
    return out


if __name__ == "__main__":  # quick self-check
    assert compare("2.14.1", "2.15.0", "npm") < 0
    assert compare("1.0.0", "1.0.0-rc1", "npm") > 0  # release > prerelease
    assert compare("1.4.2", "1.4.10", "pypi") < 0
    assert compare("1.0", "1.0-SNAPSHOT", "maven") > 0  # release > snapshot
    log4shell = {
        "ranges": [
            {"type": "ECOSYSTEM", "events": [{"introduced": "2.0-beta9"}, {"fixed": "2.15.0"}]}
        ]
    }
    assert affected("2.14.1", log4shell, "maven") is True
    assert affected("2.15.0", log4shell, "maven") is False
    assert affected("2.17.1", log4shell, "maven") is False
    print("versions.py self-check OK")
