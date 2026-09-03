"""Deterministic grounding: free-text question -> graph entry points.

The first place a hallucination could enter, so no model is allowed near it
(notebook §6). "the log4j thing" must not be handed to a model that will guess
between log4j, log4j-core, log4j-api, org.apache.logging.log4j:log4j-core, and the
EOL org.apache.log4j:log4j (v1, different CVEs entirely).

Resolution order, longest-match-first, first hit wins:
  1. explicit purl               pkg:npm/lodash@4.17.20
  2. explicit advisory id        CVE-2021-44228 / GHSA-jfh8-c2jp-5v3q  -> its affected packages
  3. known-incident alias        "log4shell", "spring4shell", "xz backdoor"
  4. exact package name          "lodash", "org.apache.logging.log4j:log4j-core"
  5. normalised name             "log 4 j core" -> log4j-core   (guarded against English words)
A dense fallback (embedding lay phrases) is added in a later section and measured on
the SYSTEM margin, not component precision (notebook §17).
"""

from __future__ import annotations

import itertools
import re

import numpy as np

_PURL = re.compile(r"pkg:(?P<type>[a-zA-Z]+)/(?P<ns>[^/@]+/)?(?P<name>[^@]+)(?:@(?P<ver>.+))?")
_ADV = re.compile(
    r"\b(CVE-\d{4}-\d{3,7}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|"
    r"RUSTSEC-\d{4}-\d{4}|PYSEC-\d{4}-\d+|GO-\d{4}-\d+)\b",
    re.I,
)
_PURL_ECO = {
    "npm": "npm",
    "pypi": "pypi",
    "maven": "maven",
    "cargo": "cargo",
    "golang": "go",
    "go": "go",
    "gem": "rubygems",
    "composer": "packagist",
}

INCIDENTS = {
    "log4shell": [("maven", "org.apache.logging.log4j:log4j-core")],
    "log4j": [("maven", "org.apache.logging.log4j:log4j-core")],
    "spring4shell": [
        ("maven", "org.springframework:spring-core"),
        ("maven", "org.springframework:spring-beans"),
    ],
    "spring4shell rce": [("maven", "org.springframework:spring-core")],
    "text4shell": [("maven", "org.apache.commons:commons-text")],
    "xz backdoor": [("cargo", "xz2"), ("pypi", "xz")],
    "left pad": [("npm", "left-pad")],
    "shai hulud": [("npm", "chalk"), ("npm", "debug")],
    "event stream": [("npm", "event-stream")],
    "colors js": [("npm", "colors")],
    "ua parser": [("npm", "ua-parser-js")],
    "prototype pollution": [("npm", "lodash"), ("npm", "minimist")],
}

_COMMON = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "our",
    "we",
    "my",
    "in",
    "to",
    "of",
    "and",
    "or",
    "for",
    "vulnerable",
    "affected",
    "exposed",
    "exposure",
    "risk",
    "issue",
    "problem",
    "bug",
    "attack",
    "thing",
    "does",
    "do",
    "have",
    "has",
    "any",
    "which",
    "what",
    "package",
    "library",
    "dependency",
    "version",
    "code",
    "app",
    "application",
    "service",
    "system",
    "server",
    "client",
    "module",
    "current",
    "latest",
    "security",
    "advisory",
    "cve",
    "patch",
    "fix",
    "update",
}

_NORM = re.compile(r"[^a-z0-9.:+/@_-]+")


def normalise(s: str) -> str:
    return _NORM.sub(" ", (s or "").lower()).strip()


class Grounder:
    def __init__(self, store, incident_aliases=None):
        self.s = store
        self.incidents = dict(INCIDENTS)
        if incident_aliases:
            self.incidents.update(incident_aliases)
        # Index ONLY real packages: >=1 concrete version in the corpus. Malware
        # advisories name tens of thousands of removed packages ("@x/backdoor",
        # "@y/lodash"); a substring match against those is pure noise.
        P = len(store.pkg_name)
        nver = np.bincount(np.asarray(store.ver_pkg, np.int64), minlength=P)[:P]
        real_pids = np.where(nver > 0)[0]
        eco_a = np.asarray(store.pkg_eco)
        name_a = np.asarray(store.pkg_name)
        self.exact: dict[str, list[tuple[str, str]]] = {}
        self.squashed: dict[str, list[tuple[str, str]]] = {}
        self._real_index_size = len(real_pids)
        for pid in real_pids.tolist():
            eco, name = str(eco_a[pid]), str(name_a[pid])
            forms = {name.lower()}
            if ":" in name:  # maven  group:artifact -> also "artifact"
                forms.add(name.split(":", 1)[1].lower())
            if "/" in name:  # go / scoped npm -> also last segment
                forms.add(name.rsplit("/", 1)[1].lower())
            for f in forms:
                self.exact.setdefault(f, []).append((eco, name))
                sq = re.sub(r"[^a-z0-9]", "", f)
                if len(sq) >= 4:
                    self.squashed.setdefault(sq, []).append((eco, name))
        # reverse index: advisory id / alias -> {(eco, name)}  (built once).
        # Only the versions that actually carry an advisory edge (aff_indptr jump) -
        # on the FULL corpus that is ~1% of 26M versions.
        self._adv_pkgs: dict[str, set[tuple[str, str]]] = {}
        canon = np.asarray(store.adv_canon)
        oid = np.asarray(store.adv_id)
        _aip = np.asarray(store.aff_indptr)
        hot = np.where(np.diff(_aip) > 0)[0]
        for vid in hot.tolist():
            adl = store.advisories_of(vid)
            if len(adl) == 0:
                continue
            pid = int(store.ver_pkg[vid])
            ent = (str(store.pkg_eco[pid]), str(store.pkg_name[pid]))
            for a in adl:
                a = int(a)
                keys = {str(oid[a]).upper(), str(canon[a]).upper()}
                keys.update(
                    x.upper() for x in getattr(store, "adv_aliases", {}).get(str(oid[a]), [])
                )
                for k in keys:
                    self._adv_pkgs.setdefault(k, set()).add(ent)

    def ground(self, question: str, max_terms=8):
        q = question or ""
        out, seen = [], set()

        # 1. explicit purl
        for m in _PURL.finditer(q):
            eco = _PURL_ECO.get(m["type"].lower())
            if not eco:
                continue
            name = (m["ns"] or "") + m["name"]
            name = name.rstrip("/")
            key = (eco, name)
            if key not in seen:
                seen.add(key)
                out.append(
                    {
                        "ecosystem": eco,
                        "name": name,
                        "surface": m.group(0),
                        "via": "purl",
                        "version": m["ver"],
                    }
                )

        # 2. explicit advisory id -> its affected packages
        for m in _ADV.finditer(q):
            aid = m.group(0).upper()
            for eco, name in self._packages_for_advisory(aid):
                key = (eco, name)
                if key not in seen:
                    seen.add(key)
                    out.append(
                        {
                            "ecosystem": eco,
                            "name": name,
                            "surface": aid,
                            "via": "advisory",
                            "advisory": aid,
                        }
                    )

        nq = normalise(q)

        # 3. known incident aliases (longest first)
        for alias in sorted(self.incidents, key=len, reverse=True):
            if alias in nq:
                for eco, name in self.incidents[alias]:
                    if self.s.pkg_id(eco, name) < 0:
                        continue
                    key = (eco, name)
                    if key not in seen:
                        seen.add(key)
                        out.append(
                            {"ecosystem": eco, "name": name, "surface": alias, "via": "incident"}
                        )

        # 4/5. exact + squashed package names among the tokens / token n-grams
        toks = [t for t in nq.split() if t not in _COMMON]
        grams = (
            toks
            + [f"{a} {b}" for a, b in itertools.pairwise(toks)]
            + [f"{a}/{b}" for a, b in itertools.pairwise(toks)]
            + [f"{a}:{b}" for a, b in itertools.pairwise(toks)]
        )
        for g in sorted(set(grams), key=len, reverse=True):
            for tbl, via in ((self.exact, "name"), (self.squashed, "name-squashed")):
                key_g = g if via == "name" else re.sub(r"[^a-z0-9]", "", g)
                for eco, name in tbl.get(key_g, []):
                    key = (eco, name)
                    if key in seen or len(key_g) < 3:
                        continue
                    if via == "name-squashed" and " " not in g and g in _COMMON:
                        continue
                    seen.add(key)
                    out.append({"ecosystem": eco, "name": name, "surface": g, "via": via})
        return out[:max_terms]

    def _packages_for_advisory(self, aid):
        return sorted(self._adv_pkgs.get(aid.upper(), ()))
