"""Exposure-path traversal and reverse blast radius."""

from __future__ import annotations

from scgraph.kgstore import KGStore
from scgraph.paths import blast_radius, exposure_paths


def test_finds_the_transitive_exposure(tiny_graph: KGStore) -> None:
    paths = exposure_paths(tiny_graph, 0, max_depth=12, max_paths=50)  # app@1.0.0
    assert len(paths) == 1
    p = paths[0]
    assert p.depth == 2
    assert not p.withdrawn
    rendered = p.render(tiny_graph)
    assert "com.example:app@1.0.0" in rendered
    assert "log4j-core@2.12.1" in rendered
    assert "CVE-2021-44228" in rendered


def test_clean_root_has_no_paths(tiny_graph: KGStore) -> None:
    lib_safe = tiny_graph.pkg_id("npm", "lib-safe")
    root = tiny_graph.default_version(lib_safe)
    assert exposure_paths(tiny_graph, root, max_depth=12, max_paths=50) == []


def test_patched_consumer_has_no_paths(tiny_graph: KGStore) -> None:
    cli = tiny_graph.pkg_id("maven", "com.example:cli-tool")
    root = tiny_graph.default_version(cli)  # -> log4j-core@2.17.0, patched
    assert exposure_paths(tiny_graph, root, max_depth=12, max_paths=50) == []


def test_max_depth_prunes(tiny_graph: KGStore) -> None:
    assert exposure_paths(tiny_graph, 0, max_depth=1, max_paths=50) == []


def test_blast_radius_lists_reachable_root_versions(tiny_graph: KGStore) -> None:
    log4j = tiny_graph.pkg_id("maven", "org.apache.logging.log4j:log4j-core")
    # blast_radius returns root *version* ids whose resolved tree reaches the package
    reached_pkgs = {int(tiny_graph.ver_pkg[v]) for v in blast_radius(tiny_graph, log4j, max_up=5)}
    for name in ("com.example:app", "com.example:web-framework", "com.example:cli-tool"):
        assert tiny_graph.pkg_id("maven", name) in reached_pkgs
