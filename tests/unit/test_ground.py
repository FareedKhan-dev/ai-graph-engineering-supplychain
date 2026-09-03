"""Deterministic grounding: free text to a package identifier, or nothing."""

from __future__ import annotations

from scgraph.ground import Grounder
from scgraph.kgstore import KGStore


def test_cve_id_grounds_via_the_advisory(tiny_graph: KGStore) -> None:
    hits = Grounder(tiny_graph).ground("are we exposed to CVE-2021-44228?")
    assert any(h["name"] == "org.apache.logging.log4j:log4j-core" for h in hits)
    assert all(h["via"] == "advisory" for h in hits)


def test_incident_nickname_grounds(tiny_graph: KGStore) -> None:
    hits = Grounder(tiny_graph).ground("the log4shell thing")
    assert any(h["name"] == "org.apache.logging.log4j:log4j-core" for h in hits)


def test_bare_package_name_grounds(tiny_graph: KGStore) -> None:
    hits = Grounder(tiny_graph).ground("is left-pad affected")
    assert any(h["name"] == "left-pad" and h["ecosystem"] == "npm" for h in hits)


def test_nonsense_grounds_to_nothing(tiny_graph: KGStore) -> None:
    assert Grounder(tiny_graph).ground("wingardium leviosa broomstick") == []


def test_grounding_is_deterministic(tiny_graph: KGStore) -> None:
    g = Grounder(tiny_graph)
    assert g.ground("CVE-2021-44228") == g.ground("CVE-2021-44228")
