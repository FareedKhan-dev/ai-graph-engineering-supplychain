"""Shared paths for the evaluation modules.

Fresh runs write to `data/out/` so they never clobber the committed reference copies in
`results/`. To update the reference, copy the files across after inspecting a run.
Override the data root with SCGRAPH_DATA_DIR, or the output dir with SCGRAPH_METRICS_DIR.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("SCGRAPH_DATA_DIR", ROOT / "data"))
PARQUET = DATA / "parquet"
GRAPH = DATA / "graph"
OUT = Path(os.environ.get("SCGRAPH_METRICS_DIR", DATA / "out"))
FIGURES = Path(os.environ.get("SCGRAPH_FIGURES_DIR", DATA / "out" / "figures"))

OUT.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)
