"""Remediation: the minimal safe bump, prerelease avoidance, the unfixable case."""

from __future__ import annotations

from scgraph.kgstore import KGStore
from scgraph.paths import exposure_paths
from scgraph.remediate import _is_prerelease, greedy_fix, ilp_fix


def test_greedy_fix_bumps_to_the_first_patched_version(tiny_graph: KGStore) -> None:
    rem = greedy_fix(tiny_graph, 0, exposure_paths(tiny_graph, 0, 12, 50))
    assert rem.cleared == 1
    assert rem.unfixable == []
    key = "maven/org.apache.logging.log4j:log4j-core"
    assert key in rem.bumps
    from_v, to_v, is_major = rem.bumps[key]
    assert from_v == "2.12.1"
    assert to_v == "2.17.0"
    assert is_major is False


def test_ilp_fix_agrees_with_greedy_on_the_single_advisory_case(tiny_graph: KGStore) -> None:
    paths = exposure_paths(tiny_graph, 0, 12, 50)
    ilp = ilp_fix(tiny_graph, 0, paths)
    assert ilp.cleared == 1
    assert "maven/org.apache.logging.log4j:log4j-core" in ilp.bumps


def test_clean_manifest_needs_no_remediation(tiny_graph: KGStore) -> None:
    lib_safe = tiny_graph.pkg_id("npm", "lib-safe")
    root = tiny_graph.default_version(lib_safe)
    rem = greedy_fix(tiny_graph, root, exposure_paths(tiny_graph, root, 12, 50))
    assert rem.bumps == {}
    assert rem.cleared == 0


class TestIsPrerelease:
    def test_positive(self) -> None:
        for v in ("2.0.0-rc1", "1.0.0-alpha", "3.1.0-beta.2", "1.0.0-SNAPSHOT", "2.0.0.dev3"):
            assert _is_prerelease(v) is True

    def test_negative(self) -> None:
        for v in ("2.17.0", "1.0.0", "10.2.3", "2020.4.5.1"):
            assert _is_prerelease(v) is False
