#!/usr/bin/env python3
"""Acquire the full corpus: Libraries.io Open Data plus the OSV feed plus GHSA.

    python scripts/acquire_full.py --dest data          # or a large scratch mount

This downloads about 25 GB and expands it to about 100 GB of CSV, so run it on a
machine with the disk for it, not a laptop. The download is resumable, uses aria2c and
pigz when they are on PATH, and the archive is checked against a pinned md5. See
docs/reproducing.md for the full sequence.

If you only want to reproduce the published results, prefer:

    python scripts/fetch_artifacts.py --set full

which pulls the already-parsed 550 MB parquet tables from the GitHub Release and skips
this step entirely.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scgraph.acquire import fetch_osv
from scgraph.acquire_full import OSV_ECOSYSTEMS, fetch_ghsa, fetch_libraries_io, locate_csvs


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--dest", type=Path, default=Path("data"), help="scratch root (needs ~130 GB free)"
    )
    p.add_argument("--skip-libraries-io", action="store_true")
    p.add_argument("--skip-ghsa", action="store_true")
    a = p.parse_args()

    raw = a.dest / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    print("== OSV (8 ecosystems) ==")
    print("records:", fetch_osv(OSV_ECOSYSTEMS, str(raw / "osv")))

    if not a.skip_ghsa:
        print("\n== GitHub Advisory Database ==")
        try:
            fetch_ghsa(str(raw))
        except Exception as e:
            print("ghsa clone failed (non-fatal):", e)

    if not a.skip_libraries_io:
        print("\n== Libraries.io Open Data v1.6.0 ==")
        fetch_libraries_io(str(a.dest), verify=True)

    csvs = locate_csvs(str(a.dest))
    print("\nCSV shards:", {k: (len(v) if isinstance(v, list) else 1) for k, v in csvs.items()})
    print("next: python scripts/run_pipeline.py --profile full")


if __name__ == "__main__":
    main()
