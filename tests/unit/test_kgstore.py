"""The CSR graph store: build determinism, adjacency, and lookups."""

from __future__ import annotations

from scgraph import build_graph
from scgraph.kgstore import KGStore


def test_dimensions(tiny_graph: KGStore) -> None:
    assert tiny_graph.N == 9  # versions
    assert len(tiny_graph.pkg_name) == 6
    assert len(tiny_graph.res_indices) == 3
    assert len(tiny_graph.aff_ids) == 2


def test_forward_and_reverse_adjacency_agree(tiny_graph: KGStore) -> None:
    # app@1.0.0 (ver 0) resolves to web-framework@2.1.0 (ver 1)
    assert 1 in list(tiny_graph.resolves_to(0))
    # and web-framework@2.1.0 has app@1.0.0 as a dependent
    assert 0 in list(tiny_graph.dependents(1))


def test_package_level_graph(tiny_graph: KGStore) -> None:
    log4j = tiny_graph.pkg_id("maven", "org.apache.logging.log4j:log4j-core")
    framework = tiny_graph.pkg_id("maven", "com.example:web-framework")
    assert log4j >= 0 and framework >= 0
    assert log4j in list(tiny_graph.pkg_deps(framework))
    assert framework in list(tiny_graph.pkg_dependents(log4j))


def test_pkg_id_missing_returns_negative(tiny_graph: KGStore) -> None:
    assert tiny_graph.pkg_id("npm", "does-not-exist") < 0


def test_advisories_of_the_vulnerable_version(tiny_graph: KGStore) -> None:
    # log4j-core@2.12.1 is ver 3, affected by SEC-1
    assert len(list(tiny_graph.advisories_of(3))) == 1
    # log4j-core@2.17.0 is ver 4, patched
    assert len(list(tiny_graph.advisories_of(4))) == 0


def test_build_is_deterministic(tiny_corpus, tmp_path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    stats_a = build_graph(str(tiny_corpus), str(a))
    stats_b = build_graph(str(tiny_corpus), str(b))
    assert stats_a == stats_b
    for name in ("res_indptr", "res_indices", "aff_adv_ids", "ver_pkg"):
        assert (a / f"{name}.npy").read_bytes() == (b / f"{name}.npy").read_bytes()
