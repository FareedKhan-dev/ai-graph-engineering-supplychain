#!/usr/bin/env python3
"""Run the graph-construction pipeline end to end: parse -> materialise -> build.

    python scripts/run_pipeline.py --profile smoke
    python scripts/run_pipeline.py --profile full          # all 8 ecosystems

Stages:
  1. parse       raw acquisitions -> parquet edge tables (packages, versions, resolved,
                 advisories, affected, aliases)
  2. materialise OSV affected ranges -> affected_versions.parquet + alias union-find
  3. build       parquet -> CSR memmap graph store

The smoke profile parses the deps.dev sample from scripts/acquire_smoke.py. The full
profile parses the Libraries.io corpus and expects scripts/acquire_full.py to have run
(or scripts/fetch_artifacts.py --set full to have provided the parquet directly, in
which case stage 1 is skipped).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

SMOKE_ECOSYSTEMS = ["npm", "pypi", "maven", "cargo", "go"]
FULL_ECOSYSTEMS = ["npm", "pypi", "maven", "cargo", "go", "rubygems", "packagist", "nuget"]


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--profile", choices=["smoke", "full"], default="smoke")
    p.add_argument("--raw", type=Path, default=Path("data/raw"))
    p.add_argument("--parquet", type=Path, default=Path("data/parquet"))
    p.add_argument("--graph", type=Path, default=Path("data/graph"))
    p.add_argument("--ecosystems", nargs="+", default=None)
    p.add_argument("--skip-parse", action="store_true", help="parquet already present (fetched)")
    a = p.parse_args()

    ecosystems = a.ecosystems or (SMOKE_ECOSYSTEMS if a.profile == "smoke" else FULL_ECOSYSTEMS)
    a.parquet.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if a.skip_parse or (a.profile == "full" and (a.parquet / "packages.parquet").exists()):
        print("== stage 1: parse (skipped, parquet present) ==")
    elif a.profile == "smoke":
        from scgraph.parse import build_tables

        print("== stage 1: parse (smoke) ==")
        print(
            json.dumps(build_tables(str(a.raw), str(a.parquet), ecosystems, smoke=True), indent=2)
        )
    else:
        from scgraph.acquire_full import build_full_tables, locate_csvs

        print("== stage 1: parse (full, Libraries.io) ==")
        csvs = locate_csvs(str(a.raw.parent))
        print(json.dumps(build_full_tables(csvs, str(a.parquet), ecosystems, str(a.raw)), indent=2))

    from scgraph.osv import materialise

    print("\n== stage 2: materialise OSV affected ranges ==")
    print(json.dumps(materialise(str(a.parquet)), indent=2))

    from scgraph import build_graph

    print("\n== stage 3: build CSR graph store ==")
    print(json.dumps(build_graph(str(a.parquet), str(a.graph)), indent=2))

    print(f"\npipeline complete in {(time.time() - t0) / 60:.1f} min -> {a.graph}")
    print("next: open notebooks/supply_chain_graph_engineering.ipynb, or scripts/run_evaluation.py")


if __name__ == "__main__":
    main()
