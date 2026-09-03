# Contributing to scgraph

Thank you for your interest. This document covers the development setup, the quality
gate, and the conventions this codebase follows.

## Development setup

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,notebook]"
pre-commit install
```

`make setup` does all of the above. On Windows without GNU make, run the commands
directly, using `.venv\Scripts\` in place of `.venv/bin/`:

| task | command |
|---|---|
| lint | `ruff check . && ruff format --check . && mypy src/scgraph` |
| auto-fix | `ruff check --fix . && ruff format .` |
| test | `pytest -m "not network"` |
| coverage | `pytest -m "not network" --cov=scgraph --cov-report=term-missing` |
| notebook | edit it in Jupyter, then `python scripts/_run_notebook.py notebooks/supply_chain_graph_engineering.ipynb scgraph 1500` to repopulate outputs |

## The quality gate

Every pull request must pass, and CI enforces all of it:

1. **`ruff check`** with the rule set in `pyproject.toml`. The evaluation scripts under
   `scripts/evaluation/` are held to a lighter standard (they are single-shot
   reproduction scripts, not library code).
2. **`ruff format --check`**. Run `ruff format .` before committing; the pre-commit hook
   does this automatically.
3. **`mypy src/scgraph`** with no errors. The numeric kernels lean on numpy dynamism, so
   full strictness is not required, but new code should carry annotations on its public
   functions.
4. **`pytest -m "not network"`**. New behavior needs a test. The graph-dependent tests
   use the `tiny_graph` fixture in `tests/conftest.py`, which builds a real CSR store
   from a six-package synthetic corpus by running the actual pipeline.

## Conventions

- **Zero LLM calls to build the graph.** Every edge must trace to a published field: a
  manifest range, a lockfile pin, an OSV affected range. Language models are confined to
  the model layer (`embed`, `reach`, `gnn`, `judge`) and every model output is measured
  against independent ground truth. A contribution that introduces a model call into the
  graph-construction path will not be merged.
- **Every alert carries a path.** The alerting code must not emit a finding it cannot
  justify with a resolvable dependency path. When reachability is unverified, the system
  abstains; it does not guess.
- **Report negatives.** If a method does not help, say so in the notebook and the docs.
  Three metrics are currently labelled as partly tautological or lexical in
  `docs/evaluation.md`; that honesty is a feature, keep it.
- **Prose style in docs and comments:** full words rather than contractions, and no em
  dashes. Use a hyphen, a comma, or parentheses.
- **Result numbers** live in `results/run_manifest.json` and `results/scorecard.json`. If
  a change moves a headline number, regenerate the affected `results/` files and update
  `docs/results.md` in the same pull request.

## Commit and pull request

- Branch from `main`. Keep pull requests focused.
- Write a clear description: what changed, why, and how it was verified.
- Update `CHANGELOG.md` under an `## [Unreleased]` heading for anything user-visible.

## Adding an ecosystem

The resolver (`resolve.py`), version ordering (`versions.py`), and the Libraries.io
platform map (`acquire_full.py`) all need an entry. Add unit tests for the new
ecosystem's version comparison and range satisfaction. See `docs/methodology.md`.

## Reporting security issues

Do not open a public issue. See [`SECURITY.md`](SECURITY.md).
