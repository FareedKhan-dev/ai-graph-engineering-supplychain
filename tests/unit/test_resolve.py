"""Declared-range to concrete-version resolution, per ecosystem."""

from __future__ import annotations

import pytest

from scgraph.resolve import resolve, satisfies


class TestSatisfiesNpm:
    @pytest.mark.parametrize(
        ("version", "requirement", "expected"),
        [
            ("1.2.5", "^1.2.0", True),
            ("2.0.0", "^1.2.0", False),
            ("1.2.9", "~1.2.3", True),
            ("1.3.0", "~1.2.3", False),
            ("4.17.21", ">=4.17.15 <5.0.0", True),
            ("5.0.0", ">=4.17.15 <5.0.0", False),
            ("2.14.1", "*", True),
            ("1.0.0", "1.0.0 || 2.0.0", True),
            ("2.0.0", "1.0.0 || 2.0.0", True),
            ("1.5.0", "1.0.0 || 2.0.0", False),
        ],
    )
    def test(self, version: str, requirement: str, expected: bool) -> None:
        assert satisfies(version, requirement, "npm") is expected


class TestSatisfiesOtherEcosystems:
    @pytest.mark.parametrize(
        ("version", "requirement", "eco", "expected"),
        [
            ("1.4.2", ">=1.0,<2.0", "pypi", True),
            ("2.1", ">=1.0,<2.0", "pypi", False),
            ("1.5.0", "[1.0,2.0)", "maven", True),
            ("2.0", "[1.0,2.0)", "maven", False),
            ("1.0.0", "", "npm", True),
            ("1.0.0", "latest", "npm", True),
        ],
    )
    def test(self, version: str, requirement: str, eco: str, expected: bool) -> None:
        assert satisfies(version, requirement, eco) is expected


class TestResolve:
    def test_picks_highest_satisfying_stable_version(self) -> None:
        assert resolve("^1.2.0", ["1.1.0", "1.2.3", "1.4.0", "2.0.0"], "npm") == "1.4.0"

    def test_returns_none_when_nothing_satisfies(self) -> None:
        assert resolve("^3.0.0", ["1.0.0", "2.0.0"], "npm") is None

    def test_returns_none_for_empty_availability(self) -> None:
        assert resolve("*", [], "npm") is None

    def test_prereleases_excluded_by_default(self) -> None:
        assert resolve("*", ["1.0.0", "2.0.0-rc1"], "npm") == "1.0.0"

    def test_prereleases_included_on_request(self) -> None:
        assert resolve("*", ["1.0.0", "2.0.0-rc1"], "npm", allow_prerelease=True) == "2.0.0-rc1"

    def test_falls_back_to_prerelease_when_it_is_the_only_match(self) -> None:
        # a wildcard matches the prerelease, and with no stable option it is returned
        assert resolve("*", ["2.0.0-rc1"], "npm") == "2.0.0-rc1"
