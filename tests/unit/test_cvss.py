"""CVSS v3.x / v4.0 base-score arithmetic and severity banding."""

from __future__ import annotations

import pytest

from scgraph.cvss import band, base_score, score_v3, score_v4

LOG4SHELL_V3 = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"


class TestScoreV3:
    def test_log4shell_is_ten(self) -> None:
        assert score_v3(LOG4SHELL_V3) == pytest.approx(10.0)

    def test_low_severity_vector(self) -> None:
        s = score_v3("CVSS:3.1/AV:N/AC:H/PR:L/UI:N/S:U/C:L/I:N/A:N")
        assert 2.5 <= s <= 4.5

    def test_no_impact_is_zero(self) -> None:
        assert score_v3("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N") == 0.0

    def test_malformed_vector_is_zero_not_exception(self) -> None:
        assert score_v3("CVSS:3.1/garbage") == 0.0

    def test_score_never_exceeds_ten(self) -> None:
        assert score_v3(LOG4SHELL_V3) <= 10.0


class TestScoreV4:
    def test_v4_vector_approximated_from_shared_metrics(self) -> None:
        s = score_v4("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")
        assert 8.0 <= s <= 10.0


class TestBaseScore:
    def test_reads_the_vector_string_from_an_osv_severity_list(self) -> None:
        assert base_score([{"type": "CVSS_V3", "score": LOG4SHELL_V3}]) == pytest.approx(10.0)

    def test_accepts_a_bare_number(self) -> None:
        assert base_score([{"type": "CVSS_V3", "score": "7.5"}]) == 7.5

    def test_takes_the_maximum_across_entries(self) -> None:
        entries = [
            {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N"},
            {"type": "CVSS_V3", "score": LOG4SHELL_V3},
        ]
        assert base_score(entries) == pytest.approx(10.0)

    def test_empty_or_none_is_zero(self) -> None:
        assert base_score([]) == 0.0
        assert base_score(None) == 0.0


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "none"),
        (2.0, "low"),
        (5.5, "medium"),
        (7.8, "high"),
        (9.8, "critical"),
        (10.0, "critical"),
    ],
)
def test_band(score: float, expected: str) -> None:
    assert band(score) == expected
