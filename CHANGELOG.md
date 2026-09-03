# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-02

First public release. The pipeline was built and validated end to end on the full
open-source dependency graph (8 ecosystems: 4,460,049 packages, 21,415,461 versions,
82,807,953 resolved edges, 285,698 advisories).

### Added

- **Engine (`src/scgraph/`, 25 modules)** across seven layers: data acquisition and
  parsing, the CSR memmap graph store, structural analysis (degree law, k-core, cycles,
  articulation points, reverse PageRank, densification, community detection, temporal
  trajectories), deterministic grounding and exposure-path traversal, the seven-gate alert
  ladder, remediation as an integer linear program, cited reporting with a CycloneDX SBOM,
  an optional GPU model layer (embeddings, reachability prior, GraphSAGE, an advisory-text
  severity check), and a system-intelligence layer (capability graph, coordinated run,
  versioned run graph with dependency-graph bisect).
- **Notebook** `notebooks/supply_chain_graph_engineering.ipynb`: 10 parts, 41 sections,
  113 cells, teaching-grade (theory, then code, then an honest reading of the result),
  committed with every output and all 14 figures from the full run.
- **Evaluation suite** (`scripts/run_evaluation.py`): query latency and throughput, a
  Clauset bootstrapped power-law goodness-of-fit test, resolver fidelity against deps.dev,
  a feature ablation across three decision surfaces, and a 150-lockfile comparison against
  `osv-scanner`.
- **Committed results** (`results/`): 15 figures, ~25 metric JSON files, 11 worked exposure
  reports, and the portfolio SBOM.
- **CLIs** (`scripts/`): acquire (smoke and full), run the pipeline, build the graph,
  run the evaluation suite, fetch release artifacts, execute the notebook. The full run
  on a GPU box is a documented sequence of these, not a separate orchestration layer.
- Tooling: `pyproject.toml` with ruff, mypy, pytest and coverage configuration; a
  `Makefile`; pre-commit hooks; GitHub Actions for CI and a nightly smoke-profile notebook
  execution.

### Known limitations

- Three metrics are partly tautological or lexical and are labelled as such in
  `docs/evaluation.md` and notebook section S28: the "100% path retention" figure (real
  parse retention is 96.64%), the ablation-monotonicity consistency check, and the semantic
  relevance AUROC (partly text overlap).
- The model layer requires a CUDA GPU. The full parquet corpus and embeddings are
  distributed as GitHub Release assets rather than committed to git.

[1.0.0]: https://github.com/FareedKhan-dev/ai-graph-engineering-supplychain/releases/tag/v1.0.0
