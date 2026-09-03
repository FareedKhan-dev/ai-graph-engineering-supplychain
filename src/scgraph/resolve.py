"""Version-range resolution: declared range -> concrete published version.

Needed only for the FULL corpus (Libraries.io `dependencies.csv`), where a row is
`(project, version, dep_name, requirement, kind, resolved_version?)`. When
`resolved_version` is populated (it often is) we use it like a lockfile pin; otherwise
we resolve the `requirement` string against the dep's published version list.

Range grammars supported (the common subset that covers ~99% of real manifests):
  npm / cargo / packagist  node-semver: ^ ~ >= <= > < = , || x/*  and `a - b` hyphen ranges
  pypi                     PEP 440 via packaging.specifiers (exact, no reimplementation)
  maven                    `[a,b)` `(,b]` `[a,]` interval notation + soft `a`
  go                       exact (`go.mod` requirements are already concrete) / semver >=

Policy: pick the HIGHEST published version that satisfies, preferring non-prerelease;
this matches npm/cargo default install behaviour and deps.dev's resolver closely
enough for a bulk graph (the notebook S4 scores the gap against deps.dev + lockfiles).
"""

from __future__ import annotations

import re
from typing import Any

from .versions import _semver_parts, compare, sort_versions

SpecifierSet: Any
try:
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version as _PyVer
except Exception:  # pragma: no cover
    SpecifierSet = None

_OP = re.compile(r"\s*(\^|~>|~|>=|<=|>|<|=|==)?\s*([0-9][^\s,|]*)")
_HYPHEN = re.compile(r"^\s*([0-9][^\s]*)\s+-\s+([0-9][^\s]*)\s*$")


def _bump_caret(v: str) -> str:
    M, m, p, _ = _semver_parts(v)
    if M > 0:
        return f"{M + 1}.0.0"
    if m > 0:
        return f"0.{m + 1}.0"
    return f"0.0.{p + 1}"


def _bump_tilde(v: str) -> str:
    M, m, _p, _ = _semver_parts(v)
    return f"{M}.{m + 1}.0" if re.match(r"^\D*\d+\.\d+", v) else f"{M + 1}.0.0"


def _semver_ok(version: str, clause: str, eco: str) -> bool:
    clause = clause.strip()
    if not clause or clause in ("*", "x", "latest"):
        return True
    h = _HYPHEN.match(clause)
    if h:
        return compare(version, h.group(1), eco) >= 0 and compare(version, h.group(2), eco) <= 0
    # split on whitespace-joined AND clauses
    for atom in clause.split():
        m = _OP.match(atom)
        if not m:
            continue
        op, ref = m.group(1) or "=", m.group(2)
        ref_x = ref.replace(".x", ".0").replace(".*", ".0")
        if op == "^":
            if not (
                compare(version, ref_x, eco) >= 0 and compare(version, _bump_caret(ref_x), eco) < 0
            ):
                return False
        elif op in ("~", "~>"):
            if not (
                compare(version, ref_x, eco) >= 0 and compare(version, _bump_tilde(ref_x), eco) < 0
            ):
                return False
        elif op == ">=":
            if compare(version, ref_x, eco) < 0:
                return False
        elif op == "<=":
            if compare(version, ref_x, eco) > 0:
                return False
        elif op == ">":
            if compare(version, ref_x, eco) <= 0:
                return False
        elif op == "<":
            if compare(version, ref_x, eco) >= 0:
                return False
        else:  # = / ==
            if op == "=" and ("x" in ref or "*" in ref):
                pre = ref.split("x")[0].split("*")[0].rstrip(".")
                if not version.startswith(pre):
                    return False
            elif compare(version, ref_x, eco) != 0:
                return False
    return True


def _maven_ok(version: str, clause: str) -> bool:
    clause = clause.strip()
    m = re.match(r"^([\[(])\s*([^,\]\)]*)\s*,\s*([^,\]\)]*)\s*([\]\)])$", clause)
    if not m:
        return compare(version, clause, "maven") >= 0 if clause else True
    lo_inc, lo, hi, hi_inc = m.groups()
    if lo:
        c = compare(version, lo, "maven")
        if c < 0 or (c == 0 and lo_inc == "("):
            return False
    if hi:
        c = compare(version, hi, "maven")
        if c > 0 or (c == 0 and hi_inc == ")"):
            return False
    return True


def satisfies(version: str, requirement: str, ecosystem: str) -> bool:
    req = (requirement or "").strip()
    eco = (ecosystem or "").lower()
    if not req or req in ("*", "latest", "any"):
        return True
    if "||" in req:
        return any(satisfies(version, part, ecosystem) for part in req.split("||"))
    if eco in ("pypi", "pip") and SpecifierSet is not None:
        try:
            return _PyVer(version) in SpecifierSet(req, prereleases=True)
        except Exception:
            return True
    if eco == "maven":
        # Maven: `,` separates lo/hi INSIDE an interval; `],[` or `),(` separate
        # multiple intervals (a version satisfying ANY interval is a match).
        parts = re.split(r"(?<=[\])])\s*,\s*(?=[\[(])", req)
        return any(_maven_ok(version, p) for p in parts)
    return _semver_ok(version, req, eco or "npm")


def resolve(requirement: str, available, ecosystem: str, allow_prerelease=False):
    """Highest published version satisfying `requirement`. `available` = version strings.
    Returns None if nothing satisfies (a dangling stub - counted in S3)."""
    if not available:
        return None
    ok = [v for v in available if satisfies(v, requirement, ecosystem)]
    if not ok:
        return None
    if not allow_prerelease:
        stable = [v for v in ok if _semver_parts(v)[3] is None]
        ok = stable or ok
    return sort_versions(ok, ecosystem)[-1]


if __name__ == "__main__":
    T = [
        ("1.2.5", "^1.2.0", "npm", True),
        ("2.0.0", "^1.2.0", "npm", False),
        ("1.2.9", "~1.2.3", "npm", True),
        ("1.3.0", "~1.2.3", "npm", False),
        ("4.17.21", ">=4.17.15 <5.0.0", "npm", True),
        ("1.4.2", ">=1.0,<2.0", "pypi", True),
        ("2.1", ">=1.0,<2.0", "pypi", False),
        ("1.5.0", "[1.0,2.0)", "maven", True),
        ("2.0", "[1.0,2.0)", "maven", False),
        ("2.14.1", "*", "npm", True),
    ]
    for v, r, e, want in T:
        got = satisfies(v, r, e)
        print(f"  satisfies({v!r}, {r!r}, {e}) = {got}   {'OK' if got == want else 'FAIL'}")
    print(
        "  resolve('^1.2.0', [1.1.0,1.2.3,1.4.0,2.0.0], npm) ->",
        resolve("^1.2.0", ["1.1.0", "1.2.3", "1.4.0", "2.0.0"], "npm"),
    )
