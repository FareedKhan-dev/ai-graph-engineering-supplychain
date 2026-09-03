#!/usr/bin/env python3
"""Just the scaling curve (edge-sampled), merged into out/timing.json + a fresh figure."""

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np

from evaluation._paths import FIGURES, OUT
from evaluation._paths import GRAPH as G

t0 = time.time()
say = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)

from scgraph import centrality as ctr
from scgraph import graphshape as gsh
from scgraph import systemic as sysm
from scgraph.kgstore import KGStore

S = KGStore(str(G))
P = len(S.pkg_name)
rng = np.random.default_rng(0)
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
    row = {"V": int(k), "E": int(len(sidx)), "frac_edges": frac}
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
            row[nm + "_s"] = round(time.time() - s, 3)
        except Exception as e:
            row[nm + "_s"] = f"ERR {e}"
    SC.append(row)
    say(str(row))
json.dump(SC, open(OUT / "scaling.json", "w"), indent=2, default=str)

# merge into timing.json
T = json.load(open(OUT / "timing.json"))
T["scaling"] = SC
json.dump(T, open(OUT / "timing.json", "w"), indent=2, default=str)

# figure
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

good = [r for r in SC if isinstance(r.get("kcore_s"), (int, float))]
V = [r["V"] for r in good]
Ee = [r["E"] for r in good]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
for nm, c in (
    ("kcore", "#2a78d6"),
    ("pagerank", "#eb6834"),
    ("articulation", "#1baf7a"),
    ("wcc", "#4a3aa7"),
):
    ax[0].plot(Ee, [r[nm + "_s"] for r in good], "-o", label=nm, color=c)
ax[0].set_xscale("log")
ax[0].set_yscale("log")
ax[0].set_xlabel("edges |E|")
ax[0].set_ylabel("seconds")
ax[0].legend(fontsize=8)
ax[0].set_title("graph-algorithm time vs |E|  (edge-sampled subgraphs)", fontsize=9, loc="left")
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
    f"query latency on the {P / 1e6:.1f}M-pkg / {E_tot / 1e6:.1f}M-edge graph  "
    f"({T['audit_throughput_per_s']:.0f} audits/s, in-process)",
    fontsize=9,
    loc="left",
)
fig.tight_layout()
fig.savefig(FIGURES / "timing_scaling.png", dpi=120, bbox_inches="tight")
say("scaling.json + timing_scaling.png updated")
