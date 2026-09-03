# notebooks/

**[`supply_chain_graph_engineering.ipynb`](supply_chain_graph_engineering.ipynb)** is the
notebook, and it is the centre of this repository. 10 parts, 41 sections, 113 cells,
committed with the outputs and all 14 figures from the full run (8 ecosystems, 82.8M
edges), so it reads completely on GitHub without running anything. Every section is
theory, then code, then an honest reading of the result, negatives included.

## Reading it

Open it on GitHub or in Jupyter. The committed outputs are from the full run, so the
numbers you see are the real ones (4.46M packages, 82.8M resolved edges).

## Running it yourself

```bash
pip install -e ".[notebook]"
python -m ipykernel install --user --name scgraph
python scripts/acquire_smoke.py          # ~3 min, needs network, no large download
jupyter lab notebooks/supply_chain_graph_engineering.ipynb
```

The first code cell walks up to the repo root (it looks for `pyproject.toml`), changes
into it, and imports `scgraph`, so the notebook works from wherever you open it.

The setup cell defines `SMOKE_TEST` (default `True`) and `ECOSYSTEMS`. On the smoke
profile it runs on a laptop in a few minutes and produces the same figures at a smaller
scale. Setting `SMOKE_TEST = False` switches to the full corpus, which needs
`data/parquet/` and `data/graph/` (see [`../data/README.md`](../data/README.md)) and, for
the model-layer sections, a CUDA GPU. The full-run sequence is in
[`../docs/reproducing.md`](../docs/reproducing.md).

## Editing it

Edit the notebook directly in Jupyter. When you commit, the `notebook-has-outputs`
pre-commit hook checks that the outputs and figures are still there, so re-run the
notebook after a change rather than committing a stripped copy. For a release the
committed notebook should carry full-run outputs, which means executing it on a VM with
the full corpus.
