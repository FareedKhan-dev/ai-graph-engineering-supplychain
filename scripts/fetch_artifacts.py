#!/usr/bin/env python3
"""Download the large reproducibility artifacts from the project's GitHub Release.

    python scripts/fetch_artifacts.py --set full      # parquet tables + embeddings (~670 MB)
    python scripts/fetch_artifacts.py --set blogpack  # per-package arrays for plotting (~135 MB)
    python scripts/fetch_artifacts.py --list

Git stays lean: the committed tree has all code, both notebooks, and every figure and
metric, but not the parsed corpus. This script fills that gap. The release tag defaults
to the value of scgraph.__version__.

Assets are extracted in place: "full" unpacks to data/parquet/ and data/emb/, "blogpack"
to blogpack/. Each asset is checked against the sha256 recorded in ARTIFACTS below once
the real release exists (fill these in when cutting the release).
"""

from __future__ import annotations

import argparse
import hashlib
import tarfile
import urllib.request
from pathlib import Path

import scgraph

REPO = "OWNER/REPO"  # set to the real slug when the repo is created

# asset name -> (sha256 or None, extract-destination relative to repo root)
ARTIFACTS: dict[str, dict[str, tuple[str | None, str]]] = {
    "full": {
        "parquet-full.tar.gz": (None, "."),
        "embeddings.tar.gz": (None, "."),
    },
    "blogpack": {
        "blogpack.tar.gz": (None, "."),
    },
}


def _release_base(tag: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{tag}"


def _sha256(p: Path, buf: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        while chunk := fh.read(buf):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET {url}")
    with urllib.request.urlopen(url) as r, dest.open("wb") as fh:
        total = int(r.headers.get("Content-Length", 0))
        read = 0
        while chunk := r.read(1 << 20):
            fh.write(chunk)
            read += len(chunk)
            if total:
                print(f"\r  {read / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    print()


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--set", choices=sorted(ARTIFACTS), help="which artifact set to fetch")
    p.add_argument(
        "--tag", default=f"v{scgraph.__version__}", help="release tag (default: v<version>)"
    )
    p.add_argument("--list", action="store_true", help="list the artifact sets and exit")
    p.add_argument("--keep-archives", action="store_true")
    a = p.parse_args()

    if a.list or not a.set:
        for name, assets in ARTIFACTS.items():
            print(f"{name}:")
            for asset, (_, dest) in assets.items():
                print(f"    {asset}  ->  {dest}")
        if not a.set:
            return

    root = Path(__file__).resolve().parent.parent
    base = _release_base(a.tag)
    for asset, (want_sha, dest) in ARTIFACTS[a.set].items():
        archive = root / asset
        _download(f"{base}/{asset}", archive)
        if want_sha:
            got = _sha256(archive)
            if got != want_sha:
                raise SystemExit(f"sha256 mismatch for {asset}: {got} != {want_sha}")
            print("  sha256 ok")
        print(f"  extracting -> {dest}")
        with tarfile.open(archive) as tf:
            tf.extractall(root / dest, filter="data")
        if not a.keep_archives:
            archive.unlink()

    print(f"\ndone. artifact set {a.set!r} is in place.")
    if a.set == "full":
        print("next: make graph  (rebuild the CSR store, ~2.3 min)")


if __name__ == "__main__":
    main()
