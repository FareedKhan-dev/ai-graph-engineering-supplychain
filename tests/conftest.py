"""Shared fixtures.

`tiny_graph` builds a small but real CSR store by writing a handful of parquet tables
and running the actual `materialise` + `build_graph` pipeline on them, so the
graph-dependent tests exercise the same code path as a full run.

The synthetic corpus models the canonical exposure:

    app@1.0.0  ->  web-framework@2.1.0  ->  logging-core@2.12.1   (affected by SEC-1)
    cli-tool@3.0.0  ->  logging-core@2.17.0                       (patched, not affected)
    lib-safe@1.0.0                                                (no dependencies, clean)
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scgraph import build_graph
from scgraph.kgstore import KGStore
from scgraph.osv import materialise

# ---- packages -------------------------------------------------------------------
_PACKAGES = [
    (0, "maven", "com.example:app"),
    (1, "maven", "com.example:web-framework"),
    (2, "maven", "org.apache.logging.log4j:log4j-core"),
    (3, "maven", "com.example:cli-tool"),
    (4, "npm", "lib-safe"),
    (5, "npm", "left-pad"),
]

# ---- versions: (ver_id, pkg_id, version, is_default) ----------------------------
_VERSIONS = [
    (0, 0, "1.0.0", True),
    (1, 1, "2.1.0", True),
    (2, 1, "2.0.0", False),
    (3, 2, "2.12.1", False),  # vulnerable
    (4, 2, "2.17.0", True),  # patched
    (5, 3, "3.0.0", True),
    (6, 4, "1.0.0", True),
    (7, 5, "1.3.0", True),
    (8, 5, "1.1.0", False),
]

# ---- resolved edges: (ver_id -> res_ver_id) ------------------------------------
_RESOLVED = [
    (0, 1),  # app@1.0.0        -> web-framework@2.1.0
    (1, 3),  # web-framework@2.1.0 -> log4j-core@2.12.1  (vulnerable path)
    (5, 4),  # cli-tool@3.0.0   -> log4j-core@2.17.0     (patched)
]

# ---- advisories: (adv_id, osv_id, canon_id, summary, severity, withdrawn, published)
_ADVISORIES = [
    (
        0,
        "SEC-1",
        "CVE-2021-44228",
        "Remote code execution in logging-core",
        10.0,
        False,
        "2021-12-10",
    ),
    (1, "SEC-2", "CVE-2018-0000", "Prototype pollution in left-pad", 7.5, False, "2018-06-01"),
]

# ---- affected: (adv_id, pkg_id, entry_json) -----------------------------------
_AFFECTED = [
    (
        0,
        2,
        json.dumps(
            {
                "ranges": [
                    {"type": "ECOSYSTEM", "events": [{"introduced": "2.0.0"}, {"fixed": "2.15.0"}]}
                ]
            }
        ),
    ),
    (
        1,
        5,
        json.dumps(
            {"ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "1.3.0"}]}]}
        ),
    ),
]

_ALIASES = [("SEC-1", "CVE-2021-44228"), ("SEC-2", "CVE-2018-0000")]


def _write_corpus(pq_dir: Path) -> None:
    pq_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table(
            {
                "pkg_id": pa.array([p[0] for p in _PACKAGES], pa.int32()),
                "ecosystem": [p[1] for p in _PACKAGES],
                "name": [p[2] for p in _PACKAGES],
            }
        ),
        pq_dir / "packages.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "ver_id": pa.array([v[0] for v in _VERSIONS], pa.int32()),
                "pkg_id": pa.array([v[1] for v in _VERSIONS], pa.int32()),
                "version": [v[2] for v in _VERSIONS],
                "is_default": [v[3] for v in _VERSIONS],
            }
        ),
        pq_dir / "versions.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "ver_id": pa.array([r[0] for r in _RESOLVED], pa.int32()),
                "res_ver_id": pa.array([r[1] for r in _RESOLVED], pa.int32()),
            }
        ),
        pq_dir / "resolved.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "adv_id": pa.array([a[0] for a in _ADVISORIES], pa.int32()),
                "osv_id": [a[1] for a in _ADVISORIES],
                "canon_id": [a[2] for a in _ADVISORIES],
                "summary": [a[3] for a in _ADVISORIES],
                "severity": pa.array([a[4] for a in _ADVISORIES], pa.float32()),
                "withdrawn": [a[5] for a in _ADVISORIES],
                "published": [a[6] for a in _ADVISORIES],
            }
        ),
        pq_dir / "advisories.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "adv_id": pa.array([a[0] for a in _AFFECTED], pa.int32()),
                "pkg_id": pa.array([a[1] for a in _AFFECTED], pa.int32()),
                "entry_json": [a[2] for a in _AFFECTED],
            }
        ),
        pq_dir / "affected.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "osv_id": [a[0] for a in _ALIASES],
                "alias": [a[1] for a in _ALIASES],
            }
        ),
        pq_dir / "aliases.parquet",
    )


@pytest.fixture(scope="session")
def tiny_corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Directory holding the parsed parquet tables for the synthetic corpus."""
    pq_dir = tmp_path_factory.mktemp("corpus") / "parquet"
    _write_corpus(pq_dir)
    materialise(str(pq_dir))
    return pq_dir


@pytest.fixture(scope="session")
def tiny_graph(tiny_corpus: Path) -> KGStore:
    """A loaded KGStore built from the synthetic corpus."""
    graph_dir = tiny_corpus.parent / "graph"
    build_graph(str(tiny_corpus), str(graph_dir))
    return KGStore(str(graph_dir))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
