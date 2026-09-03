# results/

The committed evidence from the full run (2026-09-02) on the 8-ecosystem corpus:
4,460,049 packages, 21,415,461 versions, 82,807,953 resolved edges, 285,698 advisories.

Everything here is small and version-controlled so the complete result can be read
without acquiring any data. The numbers are reproduced by
[`scripts/run_pipeline.py`](../scripts/run_pipeline.py) plus
[`scripts/run_evaluation.py`](../scripts/run_evaluation.py); see
[`docs/reproducing.md`](../docs/reproducing.md).

## Layout

| path | what |
|---|---|
| `run_manifest.json` | the canonical headline numbers: graph scale, decision measurement, shape, systemic risk, ablation, remediation, coordination, and the `eval_addons` block |
| `scorecard.json` | one line per checked claim, with the method and the result |
| `figures/` | 15 rendered figures (PNG); every figure named in `run_manifest.json` is here |
| `metrics/` | the per-section result JSON files (see the table below) |
| `reports/` | `exposure_report.md` (the headline deliverable) plus 10 worked exposure reports |
| `sbom/` | `portfolio.sbom.cdx.json` plus the 10 per-report CycloneDX SBOMs |

## metrics/

| file | contents |
|---|---|
| `graph_shape.json` | degree distribution, power-law alpha, cycles, DAG depth, diameter |
| `powerlaw_gof.json` | Clauset bootstrapped goodness-of-fit: alpha 1.957, p = 0.0, power law rejected |
| `systemic.json`, `criticality.json` | reverse-PageRank Gini, articulation points, bridges, centrality disagreement |
| `community.json` | label-propagation communities, modularity Q |
| `graph_growth.json`, `temporal.json` | densification exponent, attachment kernel, snapshot series |
| `decision.json` | the resolved-tree depth histogram and path-retention measurement |
| `semantic_relevance.json` | real-vs-control AUROC for advisory-text embeddings |
| `gnn.json` | GraphSAGE vs tabular, bootstrap AP-delta CI |
| `instrument_check.json` | the advisory-text severity check, blind vs oracle |
| `whatif_portfolio.json` | remediation as a graph edit: advisories introduced, net-worse manifests |
| `resolver_fidelity.json` | our resolver vs deps.dev, per ecosystem, in-snapshot |
| `vs_osvscanner.json`, `vs_osvscanner_big.json` | agreement with osv-scanner (10 and 150 lockfiles) |
| `ablation.json` | do the advanced graph signals change a decision (three surfaces) |
| `timing.json`, `scaling.json`, `perf_summary.json` | build/load/query latency, throughput, per-algorithm wall-clock, scaling curve |
| `exp_ablation.json`, `exp_coordination.json`, `exp_reachability.json`, `exp_remediation.json` | the notebook's in-line experiment outputs |
| `org_ledger.json`, `costs.json` | the multi-repo ledger and the run cost accounting |

## Updating

Fresh runs write to `data/out/`, not here, so a re-run never clobbers these reference
files. To update the reference after inspecting a run, copy the changed files across and
regenerate `docs/results.md` in the same commit.
