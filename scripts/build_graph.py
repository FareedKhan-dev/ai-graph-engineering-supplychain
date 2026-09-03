#!/usr/bin/env python3
"""Build the CSR memmap graph store from the parsed parquet edge tables.

    python scripts/build_graph.py                         # data/parquet -> data/graph
    python scripts/build_graph.py --parquet PQ --graph GD

This is deterministic: the same parquet always produces the same store. On the full
corpus it takes about 2.3 minutes and the store is about 2 GB. The store holds the
version graph, the package-level graph, and the per-advisory affected-version bitsets,
all as memory-mapped numpy arrays.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scgraph import build_graph
from scgraph.kgstore import KGStore


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--parquet", type=Path, default=Path("data/parquet"))
    p.add_argument("--graph", type=Path, default=Path("data/graph"))
    a = p.parse_args()

    if not (a.parquet / "packages.parquet").exists():
        raise SystemExit(
            f"no parquet tables under {a.parquet}. Run scripts/run_pipeline.py first, "
            "or scripts/fetch_artifacts.py --set full for the full corpus."
        )

    t0 = time.time()
    stats = build_graph(str(a.parquet), str(a.graph))
    print(json.dumps(stats, indent=2))

    store = KGStore(str(a.graph))
    print(
        f"\nloaded: {store.N:,} versions, {len(store.pkg_name):,} packages, "
        f"{len(store.res_indices):,} resolved edges, {len(store.aff_ids):,} affected entries"
    )
    print(f"build + load in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
