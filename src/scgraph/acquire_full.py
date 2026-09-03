"""Full-corpus acquisition (run it on a machine with the disk a laptop does not have).

Same table contract as acquire.py / parse.py; swaps the deps.dev BFS sample for the
Libraries.io Open Data dump and keeps OSV live.

Libraries.io Open Data (Zenodo, CC-BY-SA): one big archive of CSVs -
  projects-1.6.0-*.csv          name, platform, language, repository, latest release, ...
  versions-1.6.0-*.csv          project, number, published_at
  dependencies-1.6.0-*.csv      project, version, dependency name, requirement, kind,
                                optional, dependency platform
  repository_dependencies-*.csv (manifest-level, not used here)
The 2020 v1.6 record is fully documented; the 2025 release has the same schema, larger.
Pin the DOI + sha256 in RELEASE below before running so the download is checkable.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# --- PINNED release (Libraries.io Open Data, Zenodo record 3626071, DOI
#     10.5281/zenodo.3626071 - v1.6.0 2020-01-12, the final published version).
#     CC-BY-SA-4.0. 24.9 GB tar.gz -> ~100 GB of CSV: 34 package managers,
#     ~4.2M projects, ~26M versions, ~105M dependency rows. This is the graph. --------
RELEASE: dict[str, Any] = {
    "doi": "10.5281/zenodo.3626071",
    "doi_url": "https://zenodo.org/records/3626071",
    "files": {
        # filename: (direct_url, md5, size_bytes)
        "libraries-1.6.0-2020-01-12.tar.gz": (
            "https://zenodo.org/records/3626071/files/libraries-1.6.0-2020-01-12.tar.gz",
            "4f2275284b86827751bb31ce74238b15",
            24_890_021_718,
        ),
    },
}
OSV_ECOSYSTEMS = ["npm", "pypi", "maven", "cargo", "go", "rubygems", "packagist", "nuget"]


def _md5(p, buf=1 << 20):
    h = hashlib.md5()
    with Path(p).open("rb") as fh:
        while chunk := fh.read(buf):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, out: Path) -> None:
    """Resumable download. Uses aria2c (16 connections) when available, else curl -C -."""
    if shutil.which("aria2c"):
        subprocess.run(
            [
                "aria2c",
                "-x16",
                "-s16",
                "-k",
                "20M",
                "-c",
                "--file-allocation=none",
                "-d",
                str(out.parent),
                "-o",
                out.name,
                url,
            ],
            check=True,
        )
    else:
        subprocess.run(
            ["curl", "-fL", "--retry", "8", "--retry-delay", "5", "-C", "-", "-o", str(out), url],
            check=True,
        )


def _extract(archive: Path, into: Path) -> None:
    """Extract a .tar.gz. Uses pigz (parallel gunzip) when available."""
    if shutil.which("pigz"):
        subprocess.run(
            ["tar", "--use-compress-program=pigz", "-xf", str(archive), "-C", str(into)], check=True
        )
    else:
        subprocess.run(["tar", "xzf", str(archive), "-C", str(into)], check=True)


def fetch_libraries_io(dest: str, verify=True):
    """Download + verify + extract the pinned Libraries.io tar.gz into
    `dest/librariesio`. ~25 GB in, ~100 GB out - run this where the disk is (a large
    scratch mount, not a laptop). Resumable; uses aria2c and pigz when present."""
    d = Path(dest) / "librariesio"
    d.mkdir(parents=True, exist_ok=True)
    for name, (url, want_md5, want_size) in RELEASE["files"].items():
        p = d / name
        if not p.exists() or p.stat().st_size != want_size:
            print(f"[libio] downloading {name}  ({want_size / 1e9:.1f} GB)")
            _download(url, p)
        sz = p.stat().st_size
        print(f"[libio] {name}  size={sz / 1e9:.2f} GB  (want {want_size / 1e9:.2f})")
        if want_size and sz != want_size:
            raise SystemExit(f"size mismatch for {name}: {sz} != {want_size}")
        if verify and want_md5:
            got = _md5(p)
            print(f"[libio] md5={got}  (want {want_md5})")
            if got != want_md5:
                raise SystemExit(f"md5 mismatch for {name}: {got} != {want_md5}")
        marker = d / (name + ".extracted")
        if not marker.exists():
            print(f"[libio] extracting {name} (this takes 15-30 min, ~100 GB) ...")
            _extract(p, d)
            marker.write_text("ok")
    csvs = sorted(str(x) for x in d.rglob("*.csv"))
    print(f"[libio] {len(csvs)} CSV files:")
    for c in csvs:
        print(f"        {Path(c).name}  {Path(c).stat().st_size / 1e9:.2f} GB")
    return {Path(c).stem.split("-")[0]: c for c in csvs}


def fetch_ghsa(dest: str):
    d = Path(dest) / "ghsa"
    if not (d / ".git").exists():
        print("[ghsa] git clone github/advisory-database (shallow)")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/github/advisory-database", str(d)],
            check=True,
        )
    else:
        subprocess.run(["git", "-C", str(d), "pull", "--ff-only"], check=False)
    n = sum(1 for _ in (d / "advisories").rglob("*.json"))
    print(f"[ghsa] {n} advisory json files")
    return str(d / "advisories")


LIBIO_PLATFORM = {
    "npm": "npm",
    "pypi": "pypi",
    "maven": "maven",
    "cargo": "cargo",
    "go": "go",
    "rubygems": "rubygems",
    "packagist": "packagist",
    "nuget": "nuget",
}
_PLAT_LC = {v: k for k, v in LIBIO_PLATFORM.items()}


csv.field_size_limit(1 << 24)  # Libraries.io has some very long dependency-requirement cells


def _csv_rows(paths, want_cols, progress_every=5_000_000, tag=""):
    """Stream selected columns from one or more CSV shards. Uses csv.reader + a
    column-index map (not DictReader - ~3x faster over 10^8 rows)."""
    seen = 0
    for p in paths if isinstance(paths, (list, tuple)) else [paths]:
        with Path(p).open(encoding="utf-8", newline="") as fh:
            r = csv.reader(fh)
            header = next(r, None)
            if not header:
                continue
            idx = {c: i for i, c in enumerate(header)}
            keep = {c: idx[c] for c in want_cols if c in idx}
            hi = max(keep.values()) if keep else 0
            for rec in r:
                if len(rec) <= hi:
                    continue
                seen += 1
                if progress_every and seen % progress_every == 0:
                    print(
                        f"        [{tag or Path(p).stem.split('-')[0]}] {seen:,} rows", flush=True
                    )
                yield {c: rec[i] for c, i in keep.items()}


def build_full_tables(
    csvs: dict,
    pq_dir: str,
    ecosystems,
    raw_dir: str,
    runtime_kinds=("runtime", "normal", "", "compile", "provided"),
    log=print,
):
    """Libraries.io CSVs -> the EXACT parquet contract that parse.build_tables emits.
    `csvs` maps 'projects'/'versions'/'dependencies' -> path (or list of shard paths).
    OSV layer read from raw_dir/osv (identical to parse.py).

    Memory: holds the interners (pkg ~4M, ver ~26M), the per-package sorted version
    lists, and the resolved-edge set. ~20-30 GB peak on the full v1.6 dump - fits a
    64 GB box. Resolution is memoised by (dst_pid, requirement, ecosystem): the ~50M
    runtime dep rows collapse to a few M distinct (package, range) resolves.
    """
    import json as _json
    import time as _time
    from pathlib import Path

    import numpy as _np
    import pyarrow as pa
    import pyarrow.parquet as pq

    from .acquire import iter_osv_records
    from .parse import Interner, _cvss_score
    from .resolve import resolve
    from .versions import sort_versions

    keep_plat = {LIBIO_PLATFORM[e] for e in ecosystems if e in LIBIO_PLATFORM}
    PQ = Path(pq_dir)
    PQ.mkdir(parents=True, exist_ok=True)
    pkg, ver = Interner(), Interner()
    ver_pub: dict[int, str] = {}
    pkg_latest: dict[int, str] = {}
    pkg_versions: dict[int, list[str]] = {}
    t0 = _time.time()

    log("[full] pass 1/3  projects ...")
    for row in _csv_rows(
        csvs["projects"], {"Platform", "Name", "Latest Release Number"}, tag="projects"
    ):
        plat = row["Platform"].strip().lower()
        if plat not in keep_plat:
            continue
        pid = pkg((_PLAT_LC.get(plat, plat), row["Name"]))
        if row.get("Latest Release Number"):
            pkg_latest[pid] = row["Latest Release Number"].strip()
    log(f"[full]   {len(pkg):,} packages  ({_time.time() - t0:.0f}s)")

    log("[full] pass 2/3  versions ...")
    for row in _csv_rows(
        csvs["versions"],
        {"Platform", "Project Name", "Number", "Published Timestamp"},
        tag="versions",
    ):
        plat = row["Platform"].strip().lower()
        if plat not in keep_plat:
            continue
        pid = pkg((_PLAT_LC.get(plat, plat), row["Project Name"]))
        num = row["Number"].strip()
        vid = ver((pid, num))
        ver_pub[vid] = (row.get("Published Timestamp") or "")[:10]
        pkg_versions.setdefault(pid, []).append(num)
    log(f"[full]   {len(ver):,} versions  ({_time.time() - t0:.0f}s)")

    # sort each package's version list once (resolver wants ordered candidates)
    for pid, lst in pkg_versions.items():
        if len(lst) > 1:
            pkg_versions[pid] = sort_versions(lst, pkg.keys[pid][0])

    log("[full] pass 3/3  dependencies (resolving ranges -> versions) ...")
    resolved_src, resolved_dst = [], []
    n_dep = n_res = n_dangling = 0
    rcache: dict[tuple, str | None] = {}  # (dst_pid, req, deco) -> chosen str|None
    for row in _csv_rows(
        csvs["dependencies"],
        {
            "Platform",
            "Project Name",
            "Version Number",
            "Dependency Name",
            "Dependency Platform",
            "Dependency Kind",
            "Dependency Requirements",
            "Optional Dependency",
        },
        tag="deps",
    ):
        plat = row["Platform"].strip().lower()
        if plat not in keep_plat:
            continue
        if (row.get("Dependency Kind") or "").strip().lower() not in runtime_kinds:
            continue
        if (row.get("Optional Dependency") or "").strip().lower() == "true":
            continue
        eco = _PLAT_LC.get(plat, plat)
        deco = _PLAT_LC.get((row.get("Dependency Platform") or plat).strip().lower(), eco)
        src_pid = pkg._m.get((eco, row["Project Name"]))
        dst_pid = pkg._m.get((deco, row["Dependency Name"]))
        if src_pid is None or dst_pid is None:
            continue
        src_vid = ver._m.get((src_pid, row["Version Number"].strip()))
        if src_vid is None:
            continue
        n_dep += 1
        req = (row.get("Dependency Requirements") or "*").strip()
        ck = (dst_pid, req, deco)
        chosen = rcache.get(ck, 0)
        if chosen == 0:
            chosen = resolve(req, pkg_versions.get(dst_pid, []), deco)
            rcache[ck] = chosen
        if chosen is None:
            n_dangling += 1
            continue
        resolved_src.append(src_vid)
        resolved_dst.append(ver((dst_pid, chosen)))
        n_res += 1
    log(
        f"[full]   {n_dep:,} runtime deps  {n_res:,} resolved  {n_dangling:,} dangling  "
        f"({len(rcache):,} distinct resolves cached)  ({_time.time() - t0:.0f}s)"
    )

    # dedup resolved edges via numpy
    re = (
        _np.stack([_np.asarray(resolved_src, _np.int64), _np.asarray(resolved_dst, _np.int64)], 1)
        if resolved_src
        else _np.zeros((0, 2), _np.int64)
    )
    if len(re):
        re = _np.unique(re, axis=0)
    log(f"[full]   {len(re):,} distinct resolved edges")

    ver_default = _np.zeros(len(ver), bool)
    for pid, latest in pkg_latest.items():
        vid = ver._m.get((pid, latest))
        if vid is not None:
            ver_default[vid] = True

    adv, adv_meta = Interner(), {}
    aff_a, aff_p, aff_j, aff_seen, alias_pairs = [], [], [], set(), set()
    ECO_MAP = {
        "npm": "npm",
        "PyPI": "pypi",
        "Maven": "maven",
        "crates.io": "cargo",
        "Go": "go",
        "RubyGems": "rubygems",
        "Packagist": "packagist",
        "NuGet": "nuget",
    }
    for e in ecosystems:
        for rec in iter_osv_records(f"{raw_dir}/osv", e):
            aid = adv(rec["id"])
            if aid not in adv_meta:
                al = rec.get("aliases", [])
                adv_meta[aid] = {
                    "osv_id": rec["id"],
                    "canon_id": next((a for a in al if a.startswith("CVE-")), rec["id"]),
                    "summary": (rec.get("summary") or "")[:400],
                    "severity": _cvss_score(rec.get("severity")),
                    "withdrawn": bool(rec.get("withdrawn")),
                    "published": rec.get("published") or "",
                }
                for a in al:
                    alias_pairs.add((rec["id"], a))
            for ent in rec.get("affected", []):
                nm = (ent.get("package") or {}).get("name")
                if not nm:
                    continue
                pe = ECO_MAP.get((ent["package"].get("ecosystem") or ""), e)
                dst = pkg((pe, nm))
                ej = _json.dumps(ent, sort_keys=True)
                if (aid, dst, hash(ej)) in aff_seen:
                    continue
                aff_seen.add((aid, dst, hash(ej)))
                aff_a.append(aid)
                aff_p.append(dst)
                aff_j.append(ej)

    A = len(adv_meta)
    log(f"[full]   {A:,} advisories  {len(aff_a):,} affected entries  ({_time.time() - t0:.0f}s)")
    vkeys = ver.keys
    for name, t in {
        "packages": pa.table(
            {
                "pkg_id": pa.array(range(len(pkg)), pa.int32()),
                "ecosystem": [k[0] for k in pkg.keys],
                "name": [k[1] for k in pkg.keys],
            }
        ),
        "versions": pa.table(
            {
                "ver_id": pa.array(range(len(ver)), pa.int32()),
                "pkg_id": pa.array([k[0] for k in vkeys], pa.int32()),
                "version": [k[1] for k in vkeys],
                "is_default": pa.array(ver_default, pa.bool_()),
                "published": [ver_pub.get(i, "") for i in range(len(ver))],
            }
        ),
        "resolved": pa.table(
            {"ver_id": pa.array(re[:, 0], pa.int32()), "res_ver_id": pa.array(re[:, 1], pa.int32())}
        ),
        "advisories": pa.table(
            {
                "adv_id": pa.array(range(A), pa.int32()),
                "osv_id": [adv_meta[i]["osv_id"] for i in range(A)],
                "canon_id": [adv_meta[i]["canon_id"] for i in range(A)],
                "summary": [adv_meta[i]["summary"] for i in range(A)],
                "severity": pa.array([adv_meta[i]["severity"] for i in range(A)], pa.float32()),
                "withdrawn": [adv_meta[i]["withdrawn"] for i in range(A)],
                "published": [adv_meta[i]["published"] for i in range(A)],
            }
        ),
        "affected": pa.table(
            {
                "adv_id": pa.array(aff_a, pa.int32()),
                "pkg_id": pa.array(aff_p, pa.int32()),
                "entry_json": aff_j,
            }
        ),
        "aliases": pa.table(
            {"osv_id": [a for a, _ in alias_pairs], "alias": [b for _, b in alias_pairs]}
        ),
    }.items():
        pq.write_table(t, PQ / f"{name}.parquet")
        log(f"[full]   wrote {name}.parquet")
    stats = {
        "packages": len(pkg),
        "versions": len(ver),
        "declared_deps": n_dep,
        "resolutions": n_res,
        "resolved_edges": len(re),
        "dangling_unresolvable": n_dangling,
        "resolution_retention_pct": round(100 * n_res / max(n_dep, 1), 2),
        "distinct_resolves": len(rcache),
        "advisories": A,
        "affected_entries": len(aff_a),
        "wall_seconds": round(_time.time() - t0, 1),
    }
    (PQ / "_parse_stats.json").write_text(_json.dumps(stats, indent=2))
    return stats


def locate_csvs(raw_dir: str) -> dict:
    """Find the projects / versions / dependencies CSV shards under raw_dir/librariesio.

    Libraries.io v1.6 ships sibling files with wider schemas
    (`projects_with_repository_fields-*.csv`, `repository_dependencies-*.csv`) - match
    ONLY the base table name so we don't ingest a project twice or confuse
    repository_dependencies for dependencies."""
    import re
    from pathlib import Path

    d = Path(raw_dir) / "librariesio"
    out = {}
    for key in ("projects", "versions", "dependencies"):
        rx = re.compile(rf"^{key}-[\d.]+-\d{{4}}-\d\d-\d\d\.csv$")
        hits = sorted(str(p) for p in d.rglob("*.csv") if rx.match(p.name))
        if not hits:  # fall back to a looser match
            hits = sorted(str(p) for p in d.rglob(f"{key}-*.csv"))
        if hits:
            out[key] = hits if len(hits) > 1 else hits[0]
    return out


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else "/mnt/data/raw"
    print("== GHSA ==")
    fetch_ghsa(raw)
    print("== Libraries.io ==")
    fetch_libraries_io(raw)
    csvs = locate_csvs(raw)
    shards = {k: (len(v) if isinstance(v, list) else 1) for k, v in csvs.items()}
    print(f"\nCSV shards found: {shards}")
    print(
        "Then: build_full_tables(csvs, PQ, ECOSYSTEMS, raw) -> notebook runs with SMOKE_TEST=False."
    )
