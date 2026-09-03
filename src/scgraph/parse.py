"""Normalise raw acquisitions into the columnar edge tables (the step GraphRAG pays
$33k of LLM calls for — here it is field extraction, 0 models).

Tables (parquet, under PQ):
  packages(pkg_id:int32, ecosystem:str, name:str)              node table
  versions(ver_id:int32, pkg_id:int32, version:str, is_default:bool)
  resolved(ver_id:int32, res_ver_id:int32)                     traversable edges
  advisories(adv_id:int32, osv_id:str, canon_id:str, summary:str,
             severity:float32, withdrawn:bool, published:str)
  affected(adv_id:int32, pkg_id:int32, entry_json:str)         raw OSV affected entry
  affected_versions(adv_id:int32, ver_id:int32)                materialised (osv.py)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .acquire import iter_osv_records
from .cvss import base_score as _cvss_score


class Interner:
    def __init__(self):
        self._m = {}
        self.keys = []

    def __call__(self, key):
        i = self._m.get(key)
        if i is None:
            i = len(self.keys)
            self._m[key] = i
            self.keys.append(key)
        return i

    def __len__(self):
        return len(self.keys)


def build_tables(raw_dir: str, pq_dir: str, ecosystems, smoke=True) -> dict:
    raw, PQ = Path(raw_dir), Path(pq_dir)
    PQ.mkdir(parents=True, exist_ok=True)

    pkg = Interner()  # (ecosystem, name) -> pkg_id
    ver = Interner()  # (pkg_id, version) -> ver_id
    ver_default = {}
    resolved_edges = set()

    # ---- 1. package / version / resolved graph, from the deps.dev sample ----
    dd = raw / "depsdev"
    n_nodes = 0
    for eco in ecosystems:
        p = dd / f"{eco}.jsonl"
        if not p.exists():
            continue
        for line in p.open(encoding="utf-8"):
            rec = json.loads(line)
            e = rec["ecosystem"]
            root_pid = pkg((e, rec["package"]))
            for v in rec.get("versions", []):
                ver((root_pid, v))
            rid = ver((root_pid, rec["version"]))
            ver_default[rid] = True
            for nd in rec.get("nodes", []):
                pid = pkg((e, nd["name"]))
                ver((pid, nd["version"]))
                n_nodes += 1
            for ed in rec.get("resolved", []):
                (fn, fv), (tn, tv) = ed["from"], ed["to"]
                fvid = ver((pkg((e, fn)), fv))
                tvid = ver((pkg((e, tn)), tv))
                resolved_edges.add((fvid, tvid))

    # ---- 2. advisories + affected entries, from OSV ----
    # An OSV record can appear in several ecosystem zips; intern by id and keep ONE
    # row per unique advisory, emitted at position == adv_id (kgstore indexes by it).
    adv = Interner()
    adv_meta = {}  # aid -> dict
    aff_rows: dict[str, list[Any]] = {"adv_id": [], "pkg_id": [], "entry_json": []}
    aff_seen = set()  # (aid, pid, ent_hash) dedup
    alias_pairs = set()
    ECO_MAP = {
        "npm": "npm",
        "PyPI": "pypi",
        "Maven": "maven",
        "crates.io": "cargo",
        "Go": "go",
        "pypi": "pypi",
    }
    for eco in ecosystems:
        for rec in iter_osv_records(str(raw / "osv"), eco):
            aid = adv(rec["id"])
            if aid not in adv_meta:
                aliases = rec.get("aliases", [])
                canon = next((a for a in aliases if a.startswith("CVE-")), rec["id"])
                adv_meta[aid] = {
                    "osv_id": rec["id"],
                    "canon_id": canon,
                    "summary": (rec.get("summary") or "")[:400],
                    "severity": _cvss_score(rec.get("severity")),
                    "withdrawn": bool(rec.get("withdrawn")),
                    "published": rec.get("published") or "",
                }
                for a in aliases:
                    alias_pairs.add((rec["id"], a))
            for ent in rec.get("affected", []):
                pk = ent.get("package") or {}
                nm = pk.get("name")
                if not nm:
                    continue
                # tag the package with the entry's OWN ecosystem, not the zip's
                pe = ECO_MAP.get(pk.get("ecosystem", ""), eco)
                pid = pkg((pe, nm))
                ent_json = json.dumps(ent, sort_keys=True)
                key = (aid, pid, hash(ent_json))
                if key in aff_seen:
                    continue
                aff_seen.add(key)
                aff_rows["adv_id"].append(aid)
                aff_rows["pkg_id"].append(pid)
                aff_rows["entry_json"].append(ent_json)

    # ---- 3. emit ----
    pk_tbl = pa.table(
        {
            "pkg_id": pa.array(range(len(pkg)), pa.int32()),
            "ecosystem": [k[0] for k in pkg.keys],
            "name": [k[1] for k in pkg.keys],
        }
    )
    v_tbl = pa.table(
        {
            "ver_id": pa.array(range(len(ver)), pa.int32()),
            "pkg_id": pa.array([k[0] for k in ver.keys], pa.int32()),
            "version": [k[1] for k in ver.keys],
            "is_default": [ver_default.get(i, False) for i in range(len(ver))],
        }
    )
    re_tbl = pa.table(
        {
            "ver_id": pa.array([a for a, _ in resolved_edges], pa.int32()),
            "res_ver_id": pa.array([b for _, b in resolved_edges], pa.int32()),
        }
    )
    A = len(adv_meta)
    adv_tbl = pa.table(
        {
            "adv_id": pa.array(range(A), pa.int32()),
            "osv_id": [adv_meta[i]["osv_id"] for i in range(A)],
            "canon_id": [adv_meta[i]["canon_id"] for i in range(A)],
            "summary": [adv_meta[i]["summary"] for i in range(A)],
            "severity": pa.array([adv_meta[i]["severity"] for i in range(A)], pa.float32()),
            "withdrawn": [adv_meta[i]["withdrawn"] for i in range(A)],
            "published": [adv_meta[i]["published"] for i in range(A)],
        }
    )
    aff_tbl = pa.table(
        {
            "adv_id": pa.array(aff_rows["adv_id"], pa.int32()),
            "pkg_id": pa.array(aff_rows["pkg_id"], pa.int32()),
            "entry_json": aff_rows["entry_json"],
        }
    )
    alias_tbl = pa.table(
        {"osv_id": [a for a, _ in alias_pairs], "alias": [b for _, b in alias_pairs]}
    )

    for name, t in [
        ("packages", pk_tbl),
        ("versions", v_tbl),
        ("resolved", re_tbl),
        ("advisories", adv_tbl),
        ("affected", aff_tbl),
        ("aliases", alias_tbl),
    ]:
        pq.write_table(t, PQ / f"{name}.parquet")

    stats = {
        "packages": len(pkg),
        "versions": len(ver),
        "resolved_edges": len(resolved_edges),
        "advisories": A,
        "affected_entries": len(aff_rows["adv_id"]),
        "node_mentions": n_nodes,
    }
    (PQ / "_parse_stats.json").write_text(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    s = build_tables(
        str(base / "data" / "raw"), str(base / "data" / "parquet"), ["npm", "pypi"], smoke=True
    )
    print(json.dumps(s, indent=2))
