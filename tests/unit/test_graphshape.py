"""Structural statistics: degree, k-core, components, and the power-law GoF test."""

from __future__ import annotations

import numpy as np

from scgraph import graphshape as gsh
from scgraph.kgstore import KGStore


def test_degree_stats_on_the_package_graph(tiny_graph: KGStore) -> None:
    stats = gsh.degree_stats(tiny_graph.pkgdep_indptr, tiny_graph.pkgrev_indptr)
    assert stats["n"] == 6
    assert stats["in"]["max"] == 2  # log4j-core is depended on by framework and cli-tool


def test_kcore_is_zero_for_a_forest(tiny_graph: KGStore) -> None:
    core = gsh.kcore(tiny_graph.pkgdep_indptr, tiny_graph.pkgdep_indices)
    assert core.max() <= 1  # the tiny dependency graph is a tree, no dense core


def test_components_counts_the_connected_pieces(tiny_graph: KGStore) -> None:
    n = len(tiny_graph.pkg_name)
    comp = gsh.components(n, tiny_graph.pkgdep_indptr, tiny_graph.pkgdep_indices)
    # {app, web-framework, log4j-core, cli-tool} connected; lib-safe and left-pad isolated
    assert comp["n_components"] == 3
    assert comp["largest"] == 4
    assert comp["singletons"] == 2


class TestPowerLawGof:
    def test_true_power_law_is_not_rejected(self) -> None:
        rng = np.random.default_rng(0)
        # sample from a discrete power law with alpha ~ 2.5
        u = rng.random(20_000)
        deg = np.floor((1.5) * (1 - u) ** (-1 / 1.5)).astype(int)
        out = gsh.powerlaw_gof(deg, xmin=2, n_boot=100, seed=0)
        assert out["p_value"] >= 0.1

    def test_poisson_is_rejected(self) -> None:
        rng = np.random.default_rng(0)
        deg = rng.poisson(5, size=20_000)
        out = gsh.powerlaw_gof(deg, xmin=2, n_boot=100, seed=0)
        assert out["p_value"] < 0.1
