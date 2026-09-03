"""Data acquisition.

Two regimes, chosen by SMOKE_TEST:

  SMOKE  — real data at a size that fits a laptop with 17 GB free.
           * OSV per-ecosystem `all.zip`  (npm/PyPI/Maven/crates.io/Go) — a few tens of MB
           * a resolved dependency graph BFS'd from a seed set via the deps.dev API
             (no key, real resolved versions, real transitive edges)

  FULL   — the whole ecosystem, on a machine with the disk for it.
           * Libraries.io Open Data (Zenodo) — projects/versions/dependencies CSVs
           * OSV `all.zip` (all ecosystems)
           * GitHub Advisory Database (git clone) for CWE
           This module only wires SMOKE; the FULL loaders are in acquire_full and
           follow the same table contract.

Table contract (parquet, written by parse.py):
  packages(pkg_id, ecosystem, name)
  versions(ver_id, pkg_id, version, published_at, is_default)
  deps(ver_id, dep_pkg_id, requirement, scope)                 -- declared
  resolved(ver_id, res_ver_id, depth)                          -- traversable graph
  advisories(adv_id, aliases, summary, severity, withdrawn, published, cwe)
  affected(adv_id, ecosystem, name, entry_json)                -- raw OSV affected[] entry
"""

from __future__ import annotations

import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

OSV_BUCKET = "https://osv-vulnerabilities.storage.googleapis.com"
OSV_ECO = {
    "npm": "npm",
    "pypi": "PyPI",
    "maven": "Maven",
    "cargo": "crates.io",
    "go": "Go",
    "rubygems": "RubyGems",
    "packagist": "Packagist",
    "nuget": "NuGet",
}

DEPSDEV = "https://api.deps.dev/v3"
DEPSDEV_SYS = {"npm": "npm", "pypi": "pypi", "maven": "maven", "cargo": "cargo", "go": "go"}

SEEDS = {
    "npm": [
        "react",
        "express",
        "lodash",
        "axios",
        "webpack",
        "chalk",
        "debug",
        "next",
        "vue",
        "typescript",
        "eslint",
        "jest",
        "moment",
        "commander",
        "left-pad",
        "minimist",
        "node-fetch",
        "ws",
        "socket.io",
        "vite",
    ],
    "pypi": [
        "requests",
        "flask",
        "django",
        "numpy",
        "pandas",
        "urllib3",
        "jinja2",
        "pyyaml",
        "cryptography",
        "pillow",
        "setuptools",
        "boto3",
        "click",
        "fastapi",
        "sqlalchemy",
        "certifi",
        "werkzeug",
        "aiohttp",
    ],
    "maven": [
        "org.apache.logging.log4j:log4j-core",
        "com.fasterxml.jackson.core:jackson-databind",
        "org.springframework:spring-core",
        "com.google.guava:guava",
        "org.apache.commons:commons-text",
        "org.slf4j:slf4j-api",
        "junit:junit",
        "org.yaml:snakeyaml",
    ],
    "cargo": [
        "serde",
        "tokio",
        "clap",
        "regex",
        "rand",
        "syn",
        "log",
        "reqwest",
        "hyper",
        "openssl",
    ],
    "go": [
        "github.com/gin-gonic/gin",
        "github.com/gorilla/websocket",
        "golang.org/x/crypto",
        "github.com/sirupsen/logrus",
        "github.com/stretchr/testify",
    ],
}


def _get(url: str, timeout=60, tries=4):
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    assert last is not None  # tries >= 1, so a failed attempt set it before we fell through
    raise last


def fetch_osv(ecosystems, dest: str) -> dict:
    """Download per-ecosystem OSV `all.zip` and keep it AS a zip (one file write,
    not thousands). Returns {ecosystem: n_records}. Read later with iter_osv_records."""
    out = {}
    Path(dest).mkdir(parents=True, exist_ok=True)
    for eco in ecosystems:
        oe = OSV_ECO[eco]
        zp = Path(dest) / f"{eco}.zip"
        if zp.exists() and zp.stat().st_size > 1000:
            with zipfile.ZipFile(zp) as z:
                out[eco] = sum(1 for n in z.namelist() if n.endswith(".json"))
            print(f"[osv] {eco:6} cached: {out[eco]} records ({zp.stat().st_size / 1e6:.1f} MB)")
            continue
        url = f"{OSV_BUCKET}/{oe}/all.zip"
        print(f"[osv] {eco:6} downloading {url}")
        blob = _get(url, timeout=240)
        zp.write_bytes(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            n = sum(1 for name in z.namelist() if name.endswith(".json"))
        out[eco] = n
        print(f"[osv] {eco:6} {n} records ({len(blob) / 1e6:.1f} MB)")
    return out


def iter_osv_records(dest: str, ecosystem: str):
    """Yield parsed OSV JSON records from the saved per-ecosystem zip."""
    zp = Path(dest) / f"{ecosystem}.zip"
    if not zp.exists():
        return
    with zipfile.ZipFile(zp) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                try:
                    yield json.loads(z.read(name))
                except Exception:
                    continue


def _resolved_deps(system: str, name: str, version: str):
    url = (
        f"{DEPSDEV}/systems/{system}/packages/{urllib.parse.quote(name, safe='')}"
        f"/versions/{urllib.parse.quote(version, safe='')}:dependencies"
    )
    try:
        return json.loads(_get(url))
    except Exception:
        return None


def _pkg_versions(system: str, name: str):
    url = f"{DEPSDEV}/systems/{system}/packages/{urllib.parse.quote(name, safe='')}"
    try:
        return json.loads(_get(url))
    except Exception:
        return None


import urllib.parse  # noqa: E402  (kept near use)


def fetch_depsdev_sample(ecosystems, dest: str, max_packages=3000, seeds=None, sleep=0.05) -> dict:
    """BFS the resolved dependency graph from a seed set. Writes one JSONL file per
    ecosystem: each line is {package, version, published, licenses, advisories,
    resolved:[{from,to,requirement,relation}], nodes:[...]}. Returns counts."""
    seeds = seeds or SEEDS
    Path(dest).mkdir(parents=True, exist_ok=True)
    counts = {}
    for eco in ecosystems:
        system = DEPSDEV_SYS[eco]
        outp = Path(dest) / f"{eco}.jsonl"
        if outp.exists() and outp.stat().st_size > 0:
            counts[eco] = sum(1 for _ in outp.open())
            print(f"[deps.dev] {eco:6} cached: {counts[eco]} version-nodes")
            continue
        seen_pkg: set[str] = set()
        queue = list(seeds.get(eco, []))
        n_written = 0
        with outp.open("w", encoding="utf-8") as fh:
            while queue and len(seen_pkg) < max_packages:
                name = queue.pop(0)
                if name in seen_pkg:
                    continue
                seen_pkg.add(name)
                meta = _pkg_versions(system, name)
                if not meta:
                    continue
                vers = [v["versionKey"]["version"] for v in meta.get("versions", [])]
                default = next(
                    (
                        v["versionKey"]["version"]
                        for v in meta.get("versions", [])
                        if v.get("isDefault")
                    ),
                    vers[-1] if vers else None,
                )
                if not default:
                    continue
                dg = _resolved_deps(system, name, default)
                edges, nodes = [], []
                if dg:
                    idx = {i: n["versionKey"] for i, n in enumerate(dg.get("nodes", []))}
                    for i, n in enumerate(dg.get("nodes", [])):
                        vk = n["versionKey"]
                        nodes.append(
                            {
                                "name": vk["name"],
                                "version": vk["version"],
                                "relation": n.get("relation"),
                            }
                        )
                        if i > 0 and vk["name"] not in seen_pkg and len(seen_pkg) < max_packages:
                            queue.append(vk["name"])
                    for e in dg.get("edges", []):
                        f, t = idx.get(e["fromNode"]), idx.get(e["toNode"])
                        if f and t:
                            edges.append(
                                {
                                    "from": [f["name"], f["version"]],
                                    "to": [t["name"], t["version"]],
                                    "requirement": e.get("requirement", ""),
                                }
                            )
                rec = {
                    "ecosystem": eco,
                    "package": name,
                    "version": default,
                    "versions": vers[:400],
                    "nodes": nodes,
                    "resolved": edges,
                }
                fh.write(json.dumps(rec) + "\n")
                n_written += 1
                if n_written % 100 == 0:
                    print(f"[deps.dev] {eco:6} {n_written} nodes, {len(queue)} queued")
                time.sleep(sleep)
        counts[eco] = n_written
        print(f"[deps.dev] {eco:6} {n_written} version-nodes written")
    return counts


if __name__ == "__main__":
    import sys

    dest = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(Path(__file__).resolve().parent.parent / "data" / "raw")
    )
    ecos = ["npm", "pypi"]
    print("== OSV ==")
    print(fetch_osv(ecos, f"{dest}/osv"))
    print("== deps.dev sample ==")
    print(fetch_depsdev_sample(ecos, f"{dest}/depsdev", max_packages=800))
