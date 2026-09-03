"""The seven-gate alert ladder: an alert requires a justified path, and the
as-of-date gate only alerts on advisories that were knowable at the time."""

from __future__ import annotations

from scgraph.ground import Grounder
from scgraph.kgstore import KGStore
from scgraph.ladder import AlertLadder, audit_manifest


def _audit(store: KGStore, root: int, as_of: str | None = None):
    return audit_manifest(store, AlertLadder(store, as_of=as_of), Grounder(store), root, 12, 50)


def test_exposed_manifest_alerts_with_a_path(tiny_graph: KGStore) -> None:
    report = _audit(tiny_graph, 0)  # app@1.0.0
    assert len(report) == 1
    row = report[0]
    assert row["alert"] is True
    assert row["verdict"] == "exposed"
    assert row["advisory"] == "CVE-2021-44228"
    assert row["severity"] == 10.0
    assert row["min_depth"] == 2
    assert "log4j-core@2.12.1" in row["example_path"]


def test_clean_manifest_produces_no_alerts(tiny_graph: KGStore) -> None:
    lib_safe = tiny_graph.pkg_id("npm", "lib-safe")
    assert _audit(tiny_graph, tiny_graph.default_version(lib_safe)) == []


def test_patched_manifest_produces_no_alerts(tiny_graph: KGStore) -> None:
    cli = tiny_graph.pkg_id("maven", "com.example:cli-tool")
    assert _audit(tiny_graph, tiny_graph.default_version(cli)) == []


def test_as_of_gate_suppresses_advisories_from_the_future(tiny_graph: KGStore) -> None:
    # CVE-2021-44228 was published 2021-12-10.
    before = _audit(tiny_graph, 0, as_of="2019-01-01")
    after = _audit(tiny_graph, 0, as_of="2026-01-01")
    assert sum(r["alert"] for r in before) == 0
    assert sum(r["alert"] for r in after) == 1
