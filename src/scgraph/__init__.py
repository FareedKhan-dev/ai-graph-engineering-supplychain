"""scgraph: graph engineering for software supply-chain impact analysis.

A fully local, zero-LLM-to-build pipeline over the open-source dependency graph. It
answers "are we exposed to CVE-X, through which dependency path, and what is the safe
fix?" and abstains wherever it cannot justify an alert with a resolvable path.

The package is organised in layers:

    Data          acquire, acquire_full, parse, osv        native edges, no model
    Graph store   kgstore                                  CSR memmap graph + bitsets
    Structure     graphshape, centrality, systemic,        degree law, k-core, cycles,
                  community, temporal                       articulation points, PageRank
    Grounding     ground, paths, ladder                     text to purl, exposure BFS,
                                                            the 7-gate alert ladder
    Remediation   remediate, report, whatif                 ILP patch set, SBOM, diff
    Model layer   embed, reach, gnn, judge                  optional, needs a GPU
    System        agents, runstate                          coordination, run graph

Heavy optional dependencies (torch, transformers, sentence-transformers) are imported
lazily by embed, gnn, judge and reach. Importing scgraph itself pulls only numpy,
pyarrow, scipy and the standard library.
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = [
    "AlertLadder",
    "Grounder",
    "KGStore",
    "__version__",
    "affected",
    "audit_manifest",
    "band",
    "base_score",
    "blast_radius",
    "build_graph",
    "compare",
    "exposure_paths",
    "exposure_report",
    "greedy_fix",
    "ilp_fix",
    "resolve",
    "satisfies",
    "sort_versions",
    "to_cyclonedx",
    "to_markdown",
]

from .cvss import band, base_score
from .ground import Grounder
from .kgstore import KGStore
from .kgstore import build as build_graph
from .ladder import AlertLadder, audit_manifest
from .paths import blast_radius, exposure_paths
from .remediate import greedy_fix, ilp_fix
from .report import exposure_report, to_cyclonedx, to_markdown
from .resolve import resolve, satisfies
from .versions import affected, compare, sort_versions
