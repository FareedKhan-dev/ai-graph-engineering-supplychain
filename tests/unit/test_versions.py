"""Version ordering and OSV affected-range evaluation, per ecosystem."""

from __future__ import annotations

import pytest

from scgraph.versions import affected, compare, fixed_versions, in_osv_range, sort_versions

LOG4SHELL = {
    "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "2.0-beta9"}, {"fixed": "2.15.0"}]}]
}


class TestCompare:
    @pytest.mark.parametrize(
        ("a", "b", "eco", "sign"),
        [
            ("1.2.0", "1.10.0", "npm", -1),
            ("1.2.0", "1.10.0", "pypi", -1),
            ("2.14.1", "2.15.0", "npm", -1),
            ("1.0.0", "1.0.0", "npm", 0),
            ("2.0.0", "1.9.9", "npm", 1),
            ("1.4.2", "1.4.10", "pypi", -1),
        ],
    )
    def test_numeric_ordering(self, a: str, b: str, eco: str, sign: int) -> None:
        assert _sign(compare(a, b, eco)) == sign

    def test_release_beats_prerelease_semver(self) -> None:
        assert compare("1.0.0", "1.0.0-rc1", "npm") > 0
        assert compare("1.0.0-alpha", "1.0.0-beta", "npm") < 0

    def test_release_beats_snapshot_maven(self) -> None:
        assert compare("1.0", "1.0-SNAPSHOT", "maven") > 0

    def test_unknown_ecosystem_falls_back_to_semver(self) -> None:
        assert compare("1.2.0", "1.10.0", "not-a-real-ecosystem") < 0

    def test_garbage_input_does_not_raise(self) -> None:
        # compare swallows parse errors and still returns an int
        assert isinstance(compare("", "???", "npm"), int)


def test_sort_versions_is_stable_and_correct() -> None:
    assert sort_versions(["1.10.0", "1.2.0", "1.1.0", "1.2.0"], "npm") == [
        "1.1.0",
        "1.2.0",
        "1.2.0",
        "1.10.0",
    ]


class TestOsvRange:
    def test_introduced_fixed_interval(self) -> None:
        events = [{"introduced": "2.0.0"}, {"fixed": "2.15.0"}]
        assert in_osv_range("2.14.1", events, "maven") is True
        assert in_osv_range("2.15.0", events, "maven") is False
        assert in_osv_range("1.9.9", events, "maven") is False

    def test_introduced_zero_means_from_the_beginning(self) -> None:
        events = [{"introduced": "0"}, {"fixed": "1.3.0"}]
        assert in_osv_range("0.0.1", events, "npm") is True
        assert in_osv_range("1.3.0", events, "npm") is False

    def test_last_affected_is_inclusive(self) -> None:
        events = [{"introduced": "1.0.0"}, {"last_affected": "1.5.0"}]
        assert in_osv_range("1.5.0", events, "npm") is True
        assert in_osv_range("1.5.1", events, "npm") is False

    def test_open_ended_interval(self) -> None:
        assert in_osv_range("9.9.9", [{"introduced": "1.0.0"}], "npm") is True


class TestAffected:
    def test_range_based_entry(self) -> None:
        assert affected("2.14.1", LOG4SHELL, "maven") is True
        assert affected("2.15.0", LOG4SHELL, "maven") is False

    def test_explicit_versions_list_wins(self) -> None:
        entry = {"versions": ["1.0.0", "1.0.1"], "ranges": [{"events": [{"introduced": "0"}]}]}
        assert affected("1.0.1", entry, "npm") is True
        assert affected("2.0.0", entry, "npm") is False

    def test_git_ranges_are_ignored(self) -> None:
        entry = {"ranges": [{"type": "GIT", "events": [{"introduced": "0"}]}]}
        assert affected("1.0.0", entry, "npm") is False

    def test_fixed_versions_extraction(self) -> None:
        assert fixed_versions(LOG4SHELL) == ["2.15.0"]


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)
