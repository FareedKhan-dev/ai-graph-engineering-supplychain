"""Materialise OSV `affected` entries against the version table.

Structural gates 3-5 depend on one derived relation: for every (advisory, package)
pair, WHICH concrete versions in our snapshot fall inside the affected range. We
compute it once here (numpy bitset-style: a sorted int32 array of affected ver_ids
per advisory) so the runtime check is a membership test, not a range walk.

Also builds:
  * canon map      osv_id -> canonical id (CVE preferred) via alias union-find
  * withdrawn set  advisories OSV marks `withdrawn` (never alert on these)
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .versions import affected as _affected
from .versions import fixed_versions


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def materialise(pq_dir: str) -> dict:
    PQ = Path(pq_dir)
    pkgs = pq.read_table(PQ / "packages.parquet").to_pydict()
    vers = pq.read_table(PQ / "versions.parquet").to_pydict()
    advs = pq.read_table(PQ / "advisories.parquet").to_pydict()
    affs = pq.read_table(PQ / "affected.parquet").to_pydict()
    aliases = pq.read_table(PQ / "aliases.parquet").to_pydict()

    eco_of_pkg = pkgs["ecosystem"]
    # pkg_id -> list of (version_str, ver_id) — only for packages an advisory names
    # (on the FULL corpus that is ~50k of ~4M packages; building the full map wastes GBs)
    want_pids = set(affs["pkg_id"])
    by_pkg: dict[int, list[tuple[str, int]]] = {}
    for vid, pid, v in zip(vers["ver_id"], vers["pkg_id"], vers["version"]):
        if pid in want_pids:
            by_pkg.setdefault(pid, []).append((v, vid))

    # alias union-find -> canonical id (prefer CVE-*). The CVE is usually an *alias*,
    # not itself an advisory row, so fold aliases into the group before choosing.
    uf = _UF()
    alias_of: dict[str, list[str]] = {}
    for oid, al in zip(aliases["osv_id"], aliases["alias"]):
        uf.union(oid, al)
        alias_of.setdefault(oid, []).append(al)
        alias_of.setdefault(al, []).append(oid)
    groups: dict[str, list[str]] = {}
    for oid in advs["osv_id"]:
        groups.setdefault(uf.find(oid), []).append(oid)
    canon = {}
    for _, members in groups.items():
        names = set(members)
        for m in members:
            names.update(alias_of.get(m, []))
        cve = sorted(n for n in names if str(n).startswith("CVE-"))
        c = cve[0] if cve else sorted(members)[0]
        for m in members:
            canon[m] = c
    for oid in advs["osv_id"]:
        canon.setdefault(oid, oid)

    withdrawn = {oid for oid, w in zip(advs["osv_id"], advs["withdrawn"]) if w}

    # materialise affected ver_ids per advisory
    adv_hits: dict[int, set[int]] = {}  # adv_id -> set(ver_id)
    adv_fixed: dict[int, set[str]] = {}  # adv_id -> set(fixed version strings)
    n_pairs = 0
    for aid, pid, ent_json in zip(affs["adv_id"], affs["pkg_id"], affs["entry_json"]):
        ent = json.loads(ent_json)
        eco = eco_of_pkg[pid] if pid < len(eco_of_pkg) else "npm"
        cand = by_pkg.get(pid, [])
        for vstr, vid in cand:
            if _affected(vstr, ent, eco):
                adv_hits.setdefault(aid, set()).add(vid)
                n_pairs += 1
        for f in fixed_versions(ent):
            adv_fixed.setdefault(aid, set()).add(f)

    # emit affected_versions.parquet
    rows_a, rows_v = [], []
    for aid, vids in adv_hits.items():
        for vid in vids:
            rows_a.append(aid)
            rows_v.append(vid)
    pq.write_table(
        pa.table({"adv_id": pa.array(rows_a, pa.int32()), "ver_id": pa.array(rows_v, pa.int32())}),
        PQ / "affected_versions.parquet",
    )

    (PQ / "_osv_meta.json").write_text(
        json.dumps(
            {
                "canon": canon,
                "withdrawn": sorted(withdrawn),
                "adv_fixed": {str(k): sorted(v) for k, v in adv_fixed.items()},
            }
        )
    )
    stats = {
        "advisories": len(advs["osv_id"]),
        "alias_groups": len(groups),
        "withdrawn": len(withdrawn),
        "affected_pkg_entries": len(affs["adv_id"]),
        "materialised_affected_versions": len(rows_a),
        "advisories_with_a_hit": len(adv_hits),
    }
    (PQ / "_osv_stats.json").write_text(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    print(json.dumps(materialise(str(base / "data" / "parquet")), indent=2))
