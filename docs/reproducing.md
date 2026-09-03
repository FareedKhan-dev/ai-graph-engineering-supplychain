# Reproducing this

Three tiers, from "read the committed evidence" to "rebuild the graph from the Zenodo
dump". Pick the one that matches how much you need to verify.

| tier | what you get | time | disk | GPU |
|---|---|---|---|---|
| 1. read-only | every figure, every metric, the notebook with its full-run outputs, the exposure reports and SBOMs | none | none (this repo) | no |
| 2. smoke | the full pipeline on a real but small corpus, end to end on a laptop | about 3 minutes | under 1 GB | no |
| 3a. full, from artifacts | the full-scale CPU pipeline (structure, grounding, ladder, remediation) | about 10 minutes | about 3 GB | no |
| 3b. full, model layer | the embeddings, GraphSAGE and judge on top of 3a | about 6 hours | about 25 GB | yes |
| 3c. full, from the Zenodo dump | the parsed Parquet rebuilt from Libraries.io v1.6.0 | about 2 hours build, plus download | about 150 GB | no |

Python 3.11 or newer is required.

---

## Tier 1: read-only

Everything needed to check the claims is committed:

- [`../results/run_manifest.json`](../results/run_manifest.json) and
  [`../results/scorecard.json`](../results/scorecard.json): the headline numbers.
- [`../results/metrics/`](../results/metrics): about 25 metric JSON files, one per
  experiment.
- [`../results/figures/`](../results/figures): 15 figures. The same images (minus the
  spine-check figure) are in [`figures/`](figures) for use in these docs.
- [`../results/reports/`](../results/reports): 11 worked exposure reports, each with the
  paths that prove every finding.
- [`../results/sbom/`](../results/sbom): per-report CycloneDX SBOMs and the portfolio SBOM.
- [`../notebooks/supply_chain_graph_engineering.ipynb`](../notebooks/supply_chain_graph_engineering.ipynb):
  the notebook, committed with every output and all 14 figures from the full run inline.

Read [results.md](results.md) alongside the notebook. No install, no data, no network.

---

## Tier 2: smoke (laptop, about 3 minutes)

A real run on a small corpus: the complete live OSV advisory feed for five ecosystems
plus a curated resolved dependency graph fetched from the deps.dev API (about 50 seed
packages per ecosystem plus known-vulnerable version pins, so Log4Shell and the lodash
prototype-pollution line actually appear). No large download; outbound HTTPS only.

```bash
git clone https://github.com/FareedKhan-dev/ai-graph-engineering-supplychain.git
cd ai-graph-engineering-supplychain
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 1. acquire the smoke corpus (live OSV + deps.dev, ~3 min)
python scripts/acquire_smoke.py

# 2. run the pipeline end to end: parse -> materialise OSV -> build the CSR store
python scripts/run_pipeline.py --profile smoke
```

Or run it through the notebook, which self-bootstraps to the repository root:

```bash
pip install -e ".[notebook]"
jupyter lab notebooks/supply_chain_graph_engineering.ipynb
```

The equivalent `make` shortcuts are `make smoke` (acquire plus pipeline) and
`make notebook` (regenerate and execute on the smoke profile).

The notebook's behaviour is controlled by one parameter cell (papermill-style) at the
top: `SMOKE_TEST` (default `True`), `DATA_DIR` (default `./data`), `ECOSYSTEMS`, the model
names, and the traversal knobs `MAX_DEPTH` and `MAX_PATHS`. Setting `SMOKE_TEST = False`
switches to the full profile and expects the full Parquet to be present (tier 3a).

**What the smoke run produces**, under `data/`:

| path | contents |
|---|---|
| `data/raw/osv/*.zip` | the OSV `all.zip` per ecosystem, kept as zips |
| `data/raw/depsdev/*.jsonl` | the deps.dev resolved-graph sample |
| `data/parquet/` | the columnar edge tables |
| `data/graph/*.npy` | the CSR memmap store |
| `data/out/` | `run_manifest.json`, `exposure_report.md`, `sbom.cdx.json`, `figures/*.png`, and one JSON per experiment |

What the smoke tier does **not** give you: the network-science numbers are computed on a
graph of roughly 68,000 version nodes, so the power-law exponent, modularity and
densification figures are smoke-scale, not the full-run values. The GPU sections skip
with a clear message. The pipeline's structure and every code path are exercised, and the
smoke corpus is real data (the live OSV feed and real deps.dev resolutions), not
synthetic.

---

## Tier 3: full run

### 3a. The CPU pipeline, from published artifacts

The full run needs the parsed Parquet tables, about 550 MB. You do **not** need the 25 GB
Zenodo download for this: `scripts/fetch_artifacts.py` pulls the already-parsed tables
(and the embeddings) from the GitHub Release.

```bash
python scripts/fetch_artifacts.py --set full     # parquet tables + embeddings
python scripts/build_graph.py                    # rebuild the ~2 GB CSR store (~2.3 min)
python scripts/run_pipeline.py --profile full --skip-parse
```

`make graph` is the shorthand for the `build_graph.py` step. After this you can run the
notebook with `SMOKE_TEST=False`; the CPU sections reproduce directly, and the GPU
sections load the cached results that came down with `--set full`.

Which notebook parts run where:

| notebook part | needs |
|---|---|
| I data thesis, II graph shape, III grounding and traversal | CPU only |
| IV model layer (S15 embeddings, S16 semantic relevance, S17 reachability) | GPU (or cached) |
| V remediation, VI system intelligence | CPU only |
| VII representation learning (S24b GraphSAGE) | GPU (or cached) |
| VIII honest evaluation (S25 judge) | GPU for S25 (or cached), rest CPU |
| IX figures, X performance and scaling | CPU only |

Approximate CPU-section runtimes on the full graph
([`costs.json`](../results/metrics/costs.json),
[`timing.json`](../results/metrics/timing.json)): CSR build about 2.3 minutes, KGStore
load 13 seconds, reverse PageRank 4 seconds, articulation points 8 seconds, label
propagation about 3.5 minutes, sampled betweenness about 3 minutes. The full executed
notebook ran in about 16 minutes.

### 3b. The model layer, on a GPU box

The embeddings, the temporal GraphSAGE and the judge instrument check need a CUDA GPU
with about 40 GB of VRAM. Any GPU rental or your own workstation works; the published run
used a single L40 (48 GB) on Ubuntu 24.04 with CUDA 12.8.

Driver and framework pinning matters. Install PyTorch from the index that matches your
driver first (the scripts assume CUDA 12.8):

```bash
pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
pip install -e ".[gpu,fast]"
```

The cu13 wheels import but report `cuda.is_available() == False` silently on a 12.8
driver; Transformers is sufficient at these volumes, vLLM is not needed.

The whole pipeline on a GPU box:

```bash
# on the box: git clone, cd in, then
sudo apt-get install -y python3.12-venv pigz aria2      # aria2 and pigz speed up the download
python -m venv .venv && . .venv/bin/activate
pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
pip install -e ".[gpu,fast,notebook]"
python -m ipykernel install --user --name scgraph

python scripts/acquire_full.py --dest data              # ~25 GB in, ~100 GB out, resumable
python scripts/run_pipeline.py --profile full           # parse, materialise, build (~90 min)

# edit notebooks/supply_chain_graph_engineering.ipynb: set SMOKE_TEST = False, then
python scripts/_run_notebook.py notebooks/supply_chain_graph_engineering.ipynb scgraph 36000 --allow-errors
python scripts/run_evaluation.py --all
```

Run it under `nohup ... &` or `tmux` if the box is remote. Every stage is idempotent, so
a re-run resumes rather than repeating. Provisioning and teardown of the box are your
provider's concern; the repository does not automate them. The embedding stage is the
expensive one: several hours for the package corpus
([`costs.json`](../results/metrics/costs.json) estimates about 5 hours on an L40-class
card). The GraphSAGE and judge stages are minutes.

### 3c. Rebuild the Parquet from the Zenodo dump

For full reproduction from the primary source, on a machine with the disk for it (a GPU
GPU box or a workstation with about 150 GB free, not a laptop):

```bash
python scripts/acquire_full.py --dest /path/with/150GB
python scripts/run_pipeline.py --profile full
```

`acquire_full.py` downloads the pinned Libraries.io Open Data v1.6.0 tarball (Zenodo
record 3626071, `libraries-1.6.0-2020-01-12.tar.gz`, 24,890,021,718 bytes, MD5
`4f2275284b86827751bb31ce74238b15`), verifies the size and MD5, and extracts it to
roughly 100 GB of CSV. It also fetches the live OSV feed for all eight ecosystems and
shallow-clones the GitHub Advisory Database. The download is resumable and uses
`aria2c` and `pigz` automatically when they are on PATH. The MD5 check alone takes about
3 minutes; extraction is 10 to 25 minutes.

`run_pipeline.py --profile full` then runs `build_full_tables` (Libraries.io CSV to
Parquet), `osv.materialise`, and `build_graph`. On a 28-core machine the full build
(parse, materialise, CSR) takes roughly 90 minutes and produces the same Parquet tables
that `--set full` would have downloaded.

---

## Verifying you reproduced it

Compare your regenerated `data/out/run_manifest.json` (or `results/run_manifest.json` if
you overwrote it) against the committed [`../results/run_manifest.json`](../results/run_manifest.json).
The graph block (`version_nodes`, `package_nodes`, `advisories`, `resolves_edges`) should
match exactly for a full run from the same Zenodo dump and a fresh OSV feed close in time.
The advisory count will drift as OSV publishes new records; everything derived purely from
Libraries.io is deterministic.

Every stage is idempotent and checkpointed, so an interrupted run resumes from the last
completed stage rather than starting over.

---

## Common issues

| symptom | cause and fix |
|---|---|
| GPU sections skip with "no CUDA" | expected on a CPU box; the notebook loads cached GPU results if `--set full` was fetched |
| `igraph` import error on the structure sections | install the `fast` extra: `pip install -e ".[fast]"` |
| `cuda.is_available()` is `False` after installing torch | wrong CUDA index; reinstall torch from the `cu128` index that matches your driver |
| resolver disagreement with deps.dev looks high | expected: the corpus is a 2020 snapshot; see [evaluation.md](evaluation.md) section 3 |
| MD5 mismatch on the Zenodo tarball | the download was truncated; `acquire_full.py` resumes it, or delete and refetch |

See [architecture.md](architecture.md) for what each stage does and
[data-sources.md](data-sources.md) for exactly what is downloaded.
