"""End-to-end checks.

`test_committed_results_are_consistent` is fast and always runs: it guards against the
committed `results/` drifting out of agreement with itself.

`test_smoke_pipeline` actually acquires the smoke corpus from the live OSV and deps.dev
APIs and runs parse -> materialise -> build. It is marked `slow` and `network` and is
deselected by the default `pytest` invocation; run it with `-m network`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_committed_results_are_consistent(repo_root: Path) -> None:
    metrics = repo_root / "results" / "metrics"
    manifest = json.loads((repo_root / "results" / "run_manifest.json").read_text(encoding="utf-8"))

    graph = manifest["graph"]
    assert graph["package_nodes"] > 4_000_000
    assert graph["version_nodes"] > 20_000_000
    assert graph["resolves_edges"] > 80_000_000

    # the scorecard's power-law verdict must match the goodness-of-fit metric
    gof = json.loads((metrics / "powerlaw_gof.json").read_text(encoding="utf-8"))
    assert gof["in_degree"]["p_value"] == 0.0
    assert "REJECT" in gof["in_degree"]["verdict"].upper()

    # every figure named in the manifest is committed
    figures = repo_root / "results" / "figures"
    for fig in manifest.get("figures", []):
        assert (figures / fig).exists(), f"missing committed figure: {fig}"


def test_every_metric_file_is_valid_json(repo_root: Path) -> None:
    for p in (repo_root / "results" / "metrics").glob("*.json"):
        json.loads(p.read_text(encoding="utf-8"))


def test_exposure_report_names_a_path(repo_root: Path) -> None:
    report = (repo_root / "results" / "reports" / "exposure_report.md").read_text(encoding="utf-8")
    assert "->" in report or "→" in report


@pytest.mark.slow
@pytest.mark.network
def test_smoke_pipeline(tmp_path: Path, repo_root: Path) -> None:
    raw = tmp_path / "raw"
    env_scripts = repo_root / "scripts"

    subprocess.run(
        [
            sys.executable,
            str(env_scripts / "acquire_smoke.py"),
            "--dest",
            str(raw),
            "--ecosystems",
            "npm",
            "pypi",
        ],
        check=True,
        cwd=repo_root,
    )
    assert (raw / "osv").is_dir()
    assert (raw / "depsdev" / "npm.jsonl").exists()

    from scgraph import build_graph
    from scgraph.kgstore import KGStore
    from scgraph.osv import materialise
    from scgraph.parse import build_tables

    pq = tmp_path / "parquet"
    build_tables(str(raw), str(pq), ["npm", "pypi"], smoke=True)
    materialise(str(pq))
    build_graph(str(pq), str(tmp_path / "graph"))

    store = KGStore(str(tmp_path / "graph"))
    assert store.N > 100
    assert len(store.aff_ids) > 0
