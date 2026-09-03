#!/usr/bin/env python3
"""Acquire the smoke corpus: the real OSV advisory feed plus a small, curated
resolved-dependency sample from the deps.dev API.

    python scripts/acquire_smoke.py                # writes into ./data/raw
    python scripts/acquire_smoke.py --dest data/raw --ecosystems npm pypi

The sample is about 50 seed packages per ecosystem at their default version, plus a
set of explicit known-vulnerable version pins so the smoke graph actually contains the
incidents everyone remembers (Log4Shell, the lodash prototype-pollution line, and so
on). It takes roughly three minutes and needs only outbound HTTPS, no login. This is
enough to run the notebook end to end on the smoke profile.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from scgraph.acquire import fetch_osv

_UA = "scgraph-smoke/1.0 (+https://github.com/OWNER/REPO)"
_DD = "https://api.deps.dev/v3"

# Seed packages chosen to have real advisories somewhere in their resolved trees.
SEEDS: dict[str, list[str]] = {
    "npm": [
        "react",
        "react-dom",
        "express",
        "lodash",
        "axios",
        "webpack",
        "chalk",
        "debug",
        "next",
        "vue",
        "eslint",
        "jest",
        "moment",
        "commander",
        "minimist",
        "node-fetch",
        "ws",
        "socket.io",
        "vite",
        "postcss",
        "request",
        "handlebars",
        "marked",
        "serialize-javascript",
        "y18n",
        "ejs",
        "async",
        "js-yaml",
        "tar",
        "glob-parent",
        "ansi-regex",
        "json5",
        "semver",
        "qs",
        "tough-cookie",
        "underscore",
        "shelljs",
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
        "lxml",
        "paramiko",
        "twisted",
        "tornado",
        "scrapy",
        "celery",
        "redis",
        "gunicorn",
        "httpx",
        "starlette",
        "pydantic",
        "wheel",
    ],
    "maven": [
        "org.apache.logging.log4j:log4j-core",
        "com.fasterxml.jackson.core:jackson-databind",
        "org.springframework:spring-core",
        "org.springframework:spring-web",
        "com.google.guava:guava",
        "org.apache.commons:commons-text",
        "org.apache.commons:commons-collections4",
        "org.yaml:snakeyaml",
        "org.apache.struts:struts2-core",
        "org.apache.tomcat.embed:tomcat-embed-core",
        "com.h2database:h2",
        "org.springframework.boot:spring-boot-starter-web",
        "io.netty:netty-all",
        "org.apache.httpcomponents:httpclient",
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
        "smallvec",
        "time",
        "chrono",
        "tungstenite",
        "rustls",
        "h2",
        "libsqlite3-sys",
        "tokio-util",
        "crossbeam-utils",
    ],
    "go": [
        "github.com/gin-gonic/gin",
        "github.com/gorilla/websocket",
        "golang.org/x/crypto",
        "github.com/sirupsen/logrus",
        "github.com/stretchr/testify",
        "golang.org/x/net",
        "golang.org/x/text",
        "github.com/prometheus/client_golang",
        "github.com/hashicorp/consul",
        "github.com/dgrijalva/jwt-go",
        "github.com/go-yaml/yaml",
    ],
}

# Explicit vulnerable pins so the smoke corpus contains real exposures.
VULN_PINS: dict[str, list[tuple[str, str]]] = {
    "npm": [
        ("lodash", "4.17.15"),
        ("minimist", "1.2.0"),
        ("handlebars", "4.0.11"),
        ("y18n", "4.0.0"),
        ("ansi-regex", "3.0.0"),
        ("json5", "2.1.0"),
        ("node-fetch", "2.6.0"),
        ("tar", "4.4.10"),
        ("glob-parent", "5.1.1"),
        ("serialize-javascript", "3.0.0"),
        ("ejs", "3.1.6"),
        ("qs", "6.5.2"),
        ("tough-cookie", "2.4.3"),
        ("ws", "7.4.5"),
        ("async", "2.6.3"),
        ("axios", "0.21.0"),
        ("moment", "2.29.1"),
        ("marked", "0.7.0"),
        ("semver", "5.7.1"),
        ("debug", "3.1.0"),
    ],
    "pypi": [
        ("requests", "2.19.1"),
        ("urllib3", "1.24.1"),
        ("jinja2", "2.10"),
        ("pyyaml", "5.1"),
        ("pillow", "8.1.0"),
        ("cryptography", "3.2"),
        ("werkzeug", "0.15.2"),
        ("flask", "0.12.2"),
        ("django", "2.2.0"),
        ("aiohttp", "3.7.3"),
        ("lxml", "4.6.2"),
        ("paramiko", "2.4.1"),
        ("certifi", "2020.4.5.1"),
    ],
    "maven": [
        ("org.apache.logging.log4j:log4j-core", "2.14.1"),
        ("com.fasterxml.jackson.core:jackson-databind", "2.9.9"),
        ("org.springframework:spring-core", "5.3.14"),
        ("org.springframework:spring-web", "5.3.14"),
        ("com.google.guava:guava", "24.1.1-jre"),
        ("org.apache.commons:commons-text", "1.9"),
        ("org.yaml:snakeyaml", "1.29"),
        ("org.apache.struts:struts2-core", "2.5.20"),
        ("com.h2database:h2", "1.4.199"),
    ],
    "cargo": [
        ("time", "0.2.23"),
        ("smallvec", "1.6.0"),
        ("openssl", "0.10.32"),
        ("hyper", "0.14.9"),
        ("tokio", "1.8.0"),
        ("h2", "0.3.1"),
        ("chrono", "0.4.19"),
    ],
    "go": [
        ("github.com/dgrijalva/jwt-go", "3.2.0+incompatible"),
        ("golang.org/x/crypto", "0.0.0-20200220183623-bac4c82f6975"),
        ("golang.org/x/net", "0.0.0-20210226172049-e18ecbb05110"),
        ("github.com/gin-gonic/gin", "1.6.3"),
    ],
}


def _get(url: str, tries: int = 4) -> dict | None:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(1.0 + i)
    return None


def _quote(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def fetch_depsdev_sample(ecosystems: list[str], dest: Path) -> dict[str, int]:
    """Curated resolved-graph sample: seeds at default version plus vulnerable pins."""
    dest.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for eco in ecosystems:
        if eco not in SEEDS:
            continue
        out = dest / f"{eco}.jsonl"
        jobs = [(nm, None) for nm in SEEDS[eco]] + [(nm, v) for nm, v in VULN_PINS.get(eco, [])]
        n = 0
        with out.open("w", encoding="utf-8") as fh:
            for name, pin in jobs:
                meta = _get(f"{_DD}/systems/{eco}/packages/{_quote(name)}")
                if not meta:
                    print(f"  miss {eco}/{name}")
                    continue
                versions = [
                    v["versionKey"]["version"]
                    for v in meta.get("versions", [])
                    if not v["versionKey"]["version"].startswith("0.0.0-")
                ]
                default = pin or next(
                    (
                        v["versionKey"]["version"]
                        for v in meta.get("versions", [])
                        if v.get("isDefault")
                    ),
                    versions[-1] if versions else None,
                )
                if not default:
                    continue
                dg = _get(
                    f"{_DD}/systems/{eco}/packages/{_quote(name)}"
                    f"/versions/{_quote(default)}:dependencies"
                )
                nodes: list[dict] = []
                edges: list[dict] = []
                if dg:
                    idx = {i: nd["versionKey"] for i, nd in enumerate(dg.get("nodes", []))}
                    for nd in dg.get("nodes", []):
                        vk = nd["versionKey"]
                        nodes.append(
                            {
                                "name": vk["name"],
                                "version": vk["version"],
                                "relation": nd.get("relation"),
                            }
                        )
                    for e in dg.get("edges", []):
                        src, dst = idx.get(e["fromNode"]), idx.get(e["toNode"])
                        if src and dst:
                            edges.append(
                                {
                                    "from": [src["name"], src["version"]],
                                    "to": [dst["name"], dst["version"]],
                                    "requirement": e.get("requirement", ""),
                                }
                            )
                fh.write(
                    json.dumps(
                        {
                            "ecosystem": eco,
                            "package": name,
                            "version": default,
                            "versions": versions[:250],
                            "nodes": nodes,
                            "resolved": edges,
                        }
                    )
                    + "\n"
                )
                n += 1
        counts[eco] = n
        mentions = sum(
            len(json.loads(line)["nodes"])
            for line in out.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        print(f"{eco:6} {n} seeds, {mentions} node-mentions")
    return counts


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--dest", type=Path, default=Path("data/raw"))
    p.add_argument(
        "--ecosystems",
        nargs="+",
        default=["npm", "pypi", "maven", "cargo", "go"],
        help="which ecosystems to sample (OSV is always fetched for all five)",
    )
    a = p.parse_args()

    t0 = time.time()
    print("== OSV advisory feed ==")
    print("records:", fetch_osv(["npm", "pypi", "maven", "cargo", "go"], str(a.dest / "osv")))
    print("\n== deps.dev resolved-graph sample ==")
    fetch_depsdev_sample(a.ecosystems, a.dest / "depsdev")
    print(f"\nsmoke corpus ready in {time.time() - t0:.0f}s -> {a.dest}")
    print("next: python scripts/run_pipeline.py --profile smoke")


if __name__ == "__main__":
    main()
