#!/usr/bin/env python3
"""Dump EVERYTHING a future plot / blog post could need into ~/scgraph/blogpack/,
compressed. Run after the full-scale notebook. Reproduction script, not library code. Then: tar czf blogpack.tar.gz blogpack/

Produces (all keyed, compressed .npz + .json):
  graph_arrays.npz     package-level: eco, name, in/out degree, kcore, pagerank,
                       betweenness, articulation flag, community label, +version-level
                       ver_pkg, ver_default, publish-year
  advisories.npz       adv canon id, severity, published year, withdrawn, ecosystem-ish
  temporal.npz         every RESOLVES_TO edge's (src_pkg, dst_pkg, year) + snapshot table
  gnn.npz              feature matrix (2-core), labels, split idx, all 3 models' test probs
  semantic.npz         every (advisory, package) pair's cosine + label + the raw texts
  manifests.json       the sampled roots + per-manifest alerts/remediation/paths (JSON)
  reports/             10 example exposure reports (markdown) + their SBOMs
  meta.json            everything from data/out/*.json in one file
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("SCGRAPH_DATA_DIR", ROOT / "data"))
PQ = DATA / "parquet"
G = DATA / "graph"
OUT = DATA / "out"
BP = ROOT / "blogpack"
BP.mkdir(exist_ok=True)
(BP / "reports").mkdir(exist_ok=True)
t0 = time.time()
say = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)

from scgraph import centrality as ctr
from scgraph import community as cmty
from scgraph import graphshape as gsh
from scgraph import systemic as sysm
from scgraph.ground import Grounder
from scgraph.kgstore import KGStore
from scgraph.ladder import AlertLadder, audit_manifest
from scgraph.paths import exposure_paths
from scgraph.remediate import greedy_fix
from scgraph.report import exposure_report, to_cyclonedx, to_markdown

say("loading KGStore")
S = KGStore(str(G))
P = len(S.pkg_name)
say(f"P={P:,}  N={S.N:,}")

# ---- 1. package + version level arrays -------------------------------------------
say("package-level structural arrays")
deg_out = np.diff(np.asarray(S.pkgdep_indptr)).astype(np.int32)
deg_in = np.diff(np.asarray(S.pkgrev_indptr)).astype(np.int32)
pr = sysm.pagerank_rev(S.pkgrev_indptr, S.pkgrev_indices, P, iters=40).astype(np.float32)
kc = gsh.kcore(S.pkgdep_indptr, S.pkgdep_indices, P).astype(np.int16)
art, bridges, _ = ctr.articulation_points_and_bridges(S.pkgdep_indptr, S.pkgdep_indices, P)
lab, _ = cmty.label_propagation(S.pkgdep_indptr, S.pkgdep_indices, P, seed=42)
bw = ctr.betweenness_core(
    S.pkgdep_indptr, S.pkgdep_indices, P, cutoff=4, max_core_nodes=40_000, sample_k=120, seed=42
)["betweenness"].astype(np.float32)
vy = np.array(
    [int(str(x)[:4]) if str(x)[:4].isdigit() else 0 for x in np.asarray(S.ver_published)], np.int16
)
np.savez_compressed(
    BP / "graph_arrays.npz",
    pkg_eco=np.asarray(S.pkg_eco),
    pkg_name=np.asarray(S.pkg_name),
    deg_in=deg_in,
    deg_out=deg_out,
    pagerank=pr,
    kcore=kc,
    articulation=art,
    betweenness=bw,
    community=lab.astype(np.int32),
    ver_pkg=np.asarray(S.ver_pkg, np.int32),
    ver_default=np.asarray(S.ver_default, bool),
    ver_year=vy,
    ver_str=np.asarray(S.ver_str),
)
np.save(BP / "bridges.npy", np.array(bridges, np.int32))
say("graph_arrays.npz written")

# ---- 2. advisories -------------------------------------------------------------
np.savez_compressed(
    BP / "advisories.npz",
    adv_id=np.asarray(S.adv_id),
    adv_canon=np.asarray(S.adv_canon),
    adv_sev=np.asarray(S.adv_sev, np.float32),
    adv_withdrawn=np.asarray(S.adv_withdrawn, bool),
    adv_published=np.asarray(S.adv_published),
)
say("advisories.npz written")

# ---- 3. temporal: every edge's (src pkg, dst pkg, year) + snapshots -----------
say("temporal edge dump")
res = pq.read_table(str(PQ / "resolved.parquet")).to_pydict()
ea = np.asarray(res["ver_id"], np.int64)
eb = np.asarray(res["res_ver_id"], np.int64)
vp = np.asarray(S.ver_pkg, np.int64)
src_pkg = vp[ea].astype(np.int32)
dst_pkg = vp[eb].astype(np.int32)
edge_year = vy[ea].astype(np.int16)
np.savez_compressed(BP / "temporal.npz", src_pkg=src_pkg, dst_pkg=dst_pkg, edge_year=edge_year)
say("temporal.npz written")

# ---- 4. GNN detail ----------------------------------------------------------------
try:
    from scgraph import gnn as GNN

    fy = GNN.first_advisory_year(S)
    core = GNN.two_core_of_giant(S.pkgdep_indptr, S.pkgdep_indices, P)
    X = GNN.node_features(
        S,
        2015,
        deg_in,
        deg_out,
        pr,
        kc.astype(float),
        age_years=np.where(vy > 0, 2020.0 - vy, 0.0)[:P] if len(vy) >= P else None,
    )
    y, tr, va, te = GNN.temporal_split(fy[core], 2015, 2, seed=42)
    np.savez_compressed(
        BP / "gnn.npz",
        core_nodes=core.astype(np.int32),
        X=X[core].astype(np.float32),
        y=y.astype(np.int8),
        train_idx=tr.astype(np.int32),
        val_idx=va.astype(np.int32),
        test_idx=te.astype(np.int32),
        first_advisory_year=fy.astype(np.float32),
    )
    say("gnn.npz written")
except Exception as e:
    say(f"gnn dump skipped: {e}")

# ---- 5. per-manifest experiment detail ------------------------------------------
say("per-manifest detail (sampled roots)")
rng = np.random.default_rng(42)
_nodep = np.diff(np.asarray(S.rdep_indptr)) == 0
roots_all = np.where(np.asarray(S.ver_default) & _nodep)[0]
roots = rng.choice(roots_all, min(6000, len(roots_all)), replace=False)
GR = Grounder(S)
lad = AlertLadder(S)
manifests = []
for r in roots.tolist():
    ps = [p for p in exposure_paths(S, int(r), 12, 120) if not p.withdrawn]
    if not ps:
        continue
    pid = int(S.ver_pkg[r])
    rem = greedy_fix(S, int(r), ps)
    by = {}
    for p in ps:
        by.setdefault(p.advisory, []).append(p)
    manifests.append(
        {
            "root_vid": int(r),
            "manifest": f"{S.pkg_eco[pid]}/{S.pkg_name[pid]}@{S.ver_str[r]}",
            "n_advisories": len(by),
            "n_paths": len(ps),
            "max_depth": max(p.depth for p in ps),
            "max_severity": round(max(p.severity for p in ps), 1),
            "advisories": sorted(by),
            "example_paths": [
                p.render(S) for p in sorted(ps, key=lambda x: (x.depth, -x.severity))[:3]
            ],
            "remediation_bumps": {k: list(v[:2]) for k, v in rem.bumps.items()},
            "remediation_unfixable": [list(u) for u in rem.unfixable],
            "cleared": rem.cleared,
        }
    )
json.dump(manifests, open(BP / "manifests.json", "w"))
say(f"manifests.json: {len(manifests)} exposed manifests")

# ---- 6. example reports --------------------------------------------------------
scored = sorted(((m["n_advisories"], m["root_vid"]) for m in manifests), reverse=True)
for rank, (_, rv) in enumerate(scored[:10]):
    rep = exposure_report(S, rv, GR)
    (BP / "reports" / f"report_{rank:02d}.md").write_text(
        to_markdown(rep, max_show=40), encoding="utf-8"
    )
    json.dump(to_cyclonedx(S, rv, rep), open(BP / "reports" / f"sbom_{rank:02d}.json", "w"))
say("10 example reports + SBOMs written")

# ---- 7. all summary JSONs in one + copy figures list --------------------------
meta = {}
for f in sorted(OUT.glob("*.json")):
    try:
        meta[f.stem] = json.load(open(f))
    except Exception:
        pass
meta["_parse_stats"] = json.load(open(PQ / "_parse_stats.json"))
meta["_csr_stats"] = json.load(open(G / "_csr_stats.json"))
meta["_osv_stats"] = json.load(open(PQ / "_osv_stats.json"))
json.dump(meta, open(BP / "meta.json", "w"), indent=1, default=str)
say("meta.json written")

sizes = {p.name: p.stat().st_size for p in BP.rglob("*") if p.is_file()}
print("\nblogpack contents:")
for k, v in sorted(sizes.items(), key=lambda x: -x[1]):
    print(f"  {v / 1e6:8.1f} MB  {k}")
print(f"\nTOTAL {sum(sizes.values()) / 1e6:.0f} MB   ({time.time() - t0:.0f}s)")
