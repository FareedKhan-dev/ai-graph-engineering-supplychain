# scgraph documentation

This directory documents `scgraph`, a fully local, zero-LLM-to-build pipeline over the
open-source dependency graph that answers "are we exposed to CVE-X, through which
dependency path, and what is the safe fix?" and abstains wherever it cannot justify an
alert with a resolvable path.

## Pages

| page | what it covers |
|---|---|
| [architecture.md](architecture.md) | the end-to-end pipeline: the seven layers, the CSR memmap graph store, version resolution, the seven-gate alert ladder, exposure paths, remediation as optimisation, the system-intelligence layer, and a data-flow diagram |
| [methodology.md](methodology.md) | every graph and statistical method used, each with what it computes, how it is computed here, the literature reference, and the full-run result |
| [data-sources.md](data-sources.md) | each input corpus: what it provides, exact version and DOI, license, how `scgraph` ingests it, provenance caveats, and the parsed table row counts |
| [results.md](results.md) | the full-run findings read in context: graph scale and shape, criticality, systemic risk, evolution, remediation, the model layer, external validation, and performance |
| [evaluation.md](evaluation.md) | the five evaluation modules and a candid "known limitations and caveats" section, including the three partly-tautological metrics |
| [reproducing.md](reproducing.md) | three tiers of reproduction: read-only, a laptop smoke run, and the full run on a GPU box |
| [glossary.md](glossary.md) | definitions of the terms a reader will hit: articulation point, betweenness, CSR, CVSS, k-core, PURL, SBOM, VEX, and the rest |

## Start here

- **If you are evaluating the approach:** read [results.md](results.md) for the findings,
  then [evaluation.md](evaluation.md) for how each number is checked and where it is weak.
- **If you want to run it:** read [reproducing.md](reproducing.md). The read-only tier
  needs nothing but this repository; the smoke tier runs on a laptop in about three
  minutes.
- **If you are reading the code:** read [architecture.md](architecture.md) for how the 25
  modules fit together, then [methodology.md](methodology.md) for the theory behind each
  structural analysis.

## Conventions

Every quantitative claim on these pages is reproduced in
[`../results/run_manifest.json`](../results/run_manifest.json) and
[`../results/scorecard.json`](../results/scorecard.json). Figures are the committed
figures under [`figures/`](figures); the same images live in `../results/figures/`. The
pipeline is modelled on the survey *Graph Engineering in the Era of LLM Agents*
(arXiv:2608.21156v2).
