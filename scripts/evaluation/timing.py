#!/usr/bin/env python3
"""Timing & scaling evaluation. Rebuilds the CSR (timed per stage), then:
  - KGStore load latency
  - single exposure-query latency  (p50/p90/p99 over N random manifest roots)
  - alerting throughput             (manifests audited per second)
  - graph-algorithm wall-clock at FULL scale
  - a scaling curve: the same ops on random node-induced subgraphs at
    100k / 500k / 1M / 4.46M packages   (time & peak RSS vs |V|)

Writes ~/ev/out/timing.json + scaling.json + a figure.
"""

import gc
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np

from evaluation._paths import FIGURES, OUT
from evaluation._paths import GRAPH as G
from evaluation._paths import PARQUET as PQ

OUT.mkdir(exist_ok=True)
t0 = time.time()
say = lambda m: print(f"[{time.time() - t0:7.1f}s] {m}", flush=True)
rss_mb = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

T = {}

# ---- 1. build the CSR, timed per stage ----------------------------------------
if not (G / "res_indptr.npy").exists():
    say("building CSR from parquet (timed)")
    from scgraph.kgstore import build as csr_build
    from scgraph.osv import materialise

    s = time.time()
    mstats = materialise(str(PQ))
    T["osv_materialise_s"] = round(time.time() - s, 1)
    say(f"  materialise {T['osv_materialise_s']}s")
    s = time.time()
    cstats = csr_build(str(PQ), str(G))
    T["csr_build_s"] = round(time.time() - s, 1)
    say(f"  csr_build {T['csr_build_s']}s")
else:
    say("CSR already present")

from scgraph.kgstore import KGStore

s = time.time()
S = KGStore(str(G))
T["kgstore_load_s"] = round(time.time() - s, 2)
P = len(S.pkg_name)
say(f"KGStore load {T['kgstore_load_s']}s   P={P:,}  N={S.N:,}  RSS={rss_mb():.0f}MB")

# ---- 2. single exposure-query latency ----------------------------------------
from scgraph.ground import Grounder
from scgraph.ladder import AlertLadder, audit_manifest
from scgraph.paths import exposure_paths

say("Grounder build (timed)")
s = time.time()
GR = Grounder(S)
T["grounder_build_s"] = round(time.time() - s, 1)
say(f"  grounder {T['grounder_build_s']}s")

rng = np.random.default_rng(0)
_nodep = np.diff(np.asarray(S.rdep_indptr)) == 0
roots = np.where(np.asarray(S.ver_default) & _nodep)[0]
sample = rng.choice(roots, 2000, replace=False)

# 2a. exposure_paths latency
lat = []
for r in sample[:1000]:
    s = time.perf_counter()
    _ = exposure_paths(S, int(r), 12, 120)
    lat.append((time.perf_counter() - s) * 1000)
lat = np.array(lat)
T["exposure_paths_ms"] = {
    "p50": round(float(np.percentile(lat, 50)), 3),
    "p90": round(float(np.percentile(lat, 90)), 3),
    "p99": round(float(np.percentile(lat, 99)), 3),
    "max": round(float(lat.max()), 2),
    "mean": round(float(lat.mean()), 3),
}
say(
    f"exposure_paths latency p50={T['exposure_paths_ms']['p50']}ms "
    f"p99={T['exposure_paths_ms']['p99']}ms"
)

# 2b. full audit_manifest (ground + paths + 7-gate ladder) latency
lad = AlertLadder(S)
alat = []
for r in sample[:600]:
    s = time.perf_counter()
    _ = audit_manifest(S, lad, GR, int(r), 12, 200)
    alat.append((time.perf_counter() - s) * 1000)
alat = np.array(alat)
T["audit_manifest_ms"] = {
    "p50": round(float(np.percentile(alat, 50)), 2),
    "p90": round(float(np.percentile(alat, 90)), 2),
    "p99": round(float(np.percentile(alat, 99)), 2),
    "mean": round(float(alat.mean()), 2),
}
T["audit_throughput_per_s"] = round(1000.0 / alat.mean(), 1)
say(
    f"audit_manifest p50={T['audit_manifest_ms']['p50']}ms  "
    f"throughput={T['audit_throughput_per_s']}/s"
)

# 2c. grounding-only latency (the free-text -> graph step)
qs = [
    "are we exposed to log4shell",
    "CVE-2021-44228",
    "is lodash vulnerable",
    "spring4shell",
    "the xz backdoor",
    "prototype pollution in minimist",
]
glat = []
for _ in range(200):
    q = qs[rng.integers(len(qs))]
    s = time.perf_counter()
    _ = GR.ground(q)
    glat.append((time.perf_counter() - s) * 1000)
T["ground_ms"] = {
    "p50": round(float(np.percentile(glat, 50)), 3),
    "p99": round(float(np.percentile(glat, 99)), 3),
}
say(f"ground() p50={T['ground_ms']['p50']}ms")

# ---- 3. graph-algorithm wall-clock at FULL scale ----------------------------
from scgraph import centrality as ctr
from scgraph import community as cmty
from scgraph import graphshape as gsh
from scgraph import systemic as sysm


def timed(name, fn):
    gc.collect()
    s = time.time()
    try:
        fn()
        dt = round(time.time() - s, 1)
    except Exception as e:
        dt = f"ERR {e}"
    T.setdefault("algos_s", {})[name] = dt
    say(f"  {name}: {dt}")


timed("degree_stats", lambda: gsh.degree_stats(S.pkgdep_indptr, S.pkgrev_indptr))
timed("kcore", lambda: gsh.kcore(S.pkgdep_indptr, S.pkgdep_indices, P))
timed("wcc", lambda: gsh.components(P, S.pkgdep_indptr, S.pkgdep_indices, strong=False))
timed("scc", lambda: gsh.components(P, S.pkgdep_indptr, S.pkgdep_indices, strong=True))
timed(
    "pagerank_rev_40it", lambda: sysm.pagerank_rev(S.pkgrev_indptr, S.pkgrev_indices, P, iters=40)
)
timed(
    "articulation_bridges",
    lambda: ctr.articulation_points_and_bridges(S.pkgdep_indptr, S.pkgdep_indices, P),
)
timed(
    "betweenness_core",
    lambda: ctr.betweenness_core(
        S.pkgdep_indptr, S.pkgdep_indices, P, cutoff=4, max_core_nodes=40000, sample_k=120
    ),
)
timed("label_propagation", lambda: cmty.label_propagation(S.pkgdep_indptr, S.pkgdep_indices, P))
timed(
    "sample_distances_120",
    lambda: gsh.sample_distances(P, S.pkgdep_indptr, S.pkgdep_indices, k=120),
)

T["peak_rss_mb"] = round(rss_mb())
T["wall_total_s"] = round(time.time() - t0, 1)
json.dump(T, open(OUT / "timing.json", "w"), indent=2, default=str)
say(f"timing.json written  (peak RSS {T['peak_rss_mb']}MB)")

# ---- 4. scaling curve: same core ops on EDGE-sampled subgraphs (density-preserving;
#        node-induced subsampling of a sparse graph gives near-empty subgraphs) -------
say("scaling curve (edge-sampled)")
ip = np.asarray(S.pkgdep_indptr)
ix = np.asarray(S.pkgdep_indices)
src_all = np.repeat(np.arange(P, dtype=np.int64), np.diff(ip))
E_tot = len(ix)
SC = []
for frac in (0.02, 0.1, 0.25, 0.5, 1.0):
    me = int(E_tot * frac)
    esel = np.sort(rng.choice(E_tot, me, replace=False)) if frac < 1.0 else np.arange(E_tot)
    a0, b0 = src_all[esel], ix[esel]
    nodes = np.unique(np.concatenate([a0, b0]))
    remap = np.full(P, -1, np.int64)
    remap[nodes] = np.arange(len(nodes))
    a, b = remap[a0], remap[b0]
    k = len(nodes)
    o = np.argsort(a, kind="stable")
    a, b = a[o], b[o]
    sip = np.zeros(k + 1, np.int64)
    np.add.at(sip, a + 1, 1)
    np.cumsum(sip, out=sip)
    sidx = b.astype(np.int64)
    row = {"V": int(k), "E": int(len(sidx))}
    for nm, fn in (
        ("kcore", lambda: gsh.kcore(sip, sidx, k)),
        ("pagerank", lambda: sysm.pagerank_rev(sip, sidx, k, iters=40)),
        ("articulation", lambda: ctr.articulation_points_and_bridges(sip, sidx, k)),
        ("wcc", lambda: gsh.components(k, sip, sidx, strong=False)),
    ):
        gc.collect()
        s = time.time()
        try:
            fn()
            row[nm + "_s"] = round(time.time() - s, 2)
        except Exception as e:
            row[nm + "_s"] = f"ERR {e}"
    SC.append(row)
    say(f"  V={k:>9,} E={len(sidx):>10,}  {row}")
json.dump(SC, open(OUT / "scaling.json", "w"), indent=2, default=str)

# ---- figure ------------------------------------------------------------------
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    good = [r for r in SC if isinstance(r.get("kcore_s"), (int, float))]
    V = [r["V"] for r in good]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    for nm, c in (
        ("kcore", "#2a78d6"),
        ("pagerank", "#eb6834"),
        ("articulation", "#1baf7a"),
        ("wcc", "#4a3aa7"),
    ):
        y = [r.get(nm + "_s") for r in good]
        y = [v if isinstance(v, (int, float)) else np.nan for v in y]
        ax[0].plot(V, y, "-o", label=nm, color=c)
    ax[0].set_xscale("log")
    ax[0].set_yscale("log")
    ax[0].set_xlabel("packages |V|")
    ax[0].set_ylabel("seconds")
    ax[0].legend(fontsize=8)
    ax[0].set_title("graph-algorithm time vs graph size", fontsize=9, loc="left")
    lab = ["exposure\npath", "full audit\n(ground+ladder)", "ground()"]
    val = [T["exposure_paths_ms"]["p50"], T["audit_manifest_ms"]["p50"], T["ground_ms"]["p50"]]
    p99 = [T["exposure_paths_ms"]["p99"], T["audit_manifest_ms"]["p99"], T["ground_ms"]["p99"]]
    x = np.arange(3)
    ax[1].bar(x - 0.18, val, 0.36, label="p50", color="#2a78d6")
    ax[1].bar(x + 0.18, p99, 0.36, label="p99", color="#e34948")
    ax[1].set_xticks(x)
    ax[1].set_xticklabels(lab, fontsize=8)
    ax[1].set_ylabel("ms")
    ax[1].legend(fontsize=8)
    ax[1].set_title(
        f"query latency on the {P / 1e6:.1f}M-package graph  "
        f"({T['audit_throughput_per_s']} audits/s)",
        fontsize=9,
        loc="left",
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "timing_scaling.png", dpi=120, bbox_inches="tight")
    say("timing_scaling.png written")
except Exception as e:
    say(f"figure skipped: {e}")

say("DONE")
