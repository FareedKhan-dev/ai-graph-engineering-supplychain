#!/usr/bin/env python3
"""Feature ablation: do the ADVANCED graph signals (articulation-point membership,
betweenness, community) actually change a decision, or are they decoration?

Two concrete decision surfaces:

  A. ALERT PRIORITISATION.  Baseline priority = severity, then depth. Advanced
     priority adds a "structural criticality" boost if the terminal package is an
     articulation point / high-betweenness / in a large multi-ecosystem community.
     We measure: how often does the advanced score reorder the top-k? (Kendall tau,
     and top-10 overlap.)  A reordering that never happens => the signal is inert.

  B. REMEDIATION TARGETING.  When a manifest has an UNFIXABLE package, which one do
     you escalate first?  Baseline = highest severity.  Advanced = the one whose
     compromise reaches the most other manifests (blast radius) AND/OR is an
     articulation point.  We measure how often the two disagree on the #1 escalation.

Also: does adding these as FEATURES to a simple logistic model change which manifests
it flags as "high risk"?  (a proper ablation - fit with / without, compare the flagged set)

Writes results/metrics/ablation.json. Runs on the full-corpus graph (see
scripts/run_evaluation.py). This is a reproduction script, not library code.
"""

import json
import time

import numpy as np

from evaluation._paths import GRAPH as G
from evaluation._paths import OUT, ROOT

BP = ROOT / "blogpack"
t0 = time.time()


def say(m):
    print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)


from scgraph import systemic as sysm
from scgraph.kgstore import KGStore
from scgraph.paths import exposure_paths

say("load KGStore + precomputed arrays")
S = KGStore(str(G))
P = len(S.pkg_name)
ga = np.load(BP / "graph_arrays.npz", allow_pickle=True)
art = ga["articulation"]
bw = ga["betweenness"]
comm = ga["community"]
csz = np.bincount(comm)
comm_size = csz[comm]  # size of each package's community
deg_in = ga["deg_in"]

rng = np.random.default_rng(0)
_nodep = np.diff(np.asarray(S.rdep_indptr)) == 0
roots = np.where(np.asarray(S.ver_default) & _nodep)[0]
sample = rng.choice(roots, 6000, replace=False)

# ---- gather exposures with terminal pkg + severity + depth --------------------
say("collecting exposure paths")
rows = []  # (manifest_idx, terminal_pid, severity, depth)
man_adv = {}
for mi, r in enumerate(sample.tolist()):
    ps = [p for p in exposure_paths(S, int(r), 12, 120) if not p.withdrawn]
    for p in ps:
        tp = int(S.ver_pkg[p.hops[-1]])
        rows.append((mi, tp, p.severity, p.depth))
    if ps:
        man_adv[mi] = len({p.advisory for p in ps})
rows = np.array(rows, dtype=object)
say(f"{len(rows):,} (manifest, exposure) rows over {len(man_adv)} exposed manifests")

sev = np.array([x[2] for x in rows], float)
dep = np.array([x[3] for x in rows], int)
tpid = np.array([x[1] for x in rows], int)

# structural-criticality boost for each row's terminal package
bw_r = bw[tpid]
bw_n = (bw_r - bw_r.min()) / (np.ptp(bw_r) + 1e-12)
crit = 0.6 * art[tpid].astype(float) + 0.3 * bw_n + 0.1 * (comm_size[tpid] > 5000)

base_score = sev + 0.01 * (12 - dep)  # severity, tie-break shallow
adv_score = base_score + 2.0 * crit  # + structural boost


def kendall_tau(a, b):
    from scipy.stats import kendalltau

    return float(kendalltau(a, b).statistic)


def topk_overlap(a, b, k=20):
    ta = set(np.argsort(-a)[:k])
    tb = set(np.argsort(-b)[:k])
    return len(ta & tb) / k


A = {}
A["alert_prioritisation"] = {
    "n_exposures": len(rows),
    "kendall_tau_base_vs_advanced": round(kendall_tau(base_score, adv_score), 4),
    "top20_overlap": round(topk_overlap(base_score, adv_score, 20), 3),
    "top100_overlap": round(topk_overlap(base_score, adv_score, 100), 3),
    "reordered_top20": int(20 - topk_overlap(base_score, adv_score, 20) * 20),
    "median_rank_shift": int(
        np.median(np.abs(np.argsort(np.argsort(-base_score)) - np.argsort(np.argsort(-adv_score))))
    ),
    "n_exposures_where_crit_boost_nonzero": int((crit > 0.05).sum()),
    "reading": None,
}

# ---- B. #1 escalation target per manifest: severity vs blast-radius ----------
say("escalation targeting: severity vs blast radius")
# blast radius (reverse) for the affected packages only - cap the frontier
from scgraph.paths import blast_radius as pkg_blast

uniq_tp = np.unique(tpid)
br = {}
for i, tp in enumerate(uniq_tp[:4000]):
    hit = pkg_blast(S, int(tp), max_up=5, node_budget=120_000)
    br[int(tp)] = len([h for h in hit if h != -1])
disagree = same = 0
for mi in man_adv:
    sel = [j for j in range(len(rows)) if rows[j][0] == mi]
    if len(sel) < 2:
        continue
    by_sev = max(sel, key=lambda j: sev[j])
    by_blast = max(sel, key=lambda j: br.get(int(tpid[j]), 0))
    if tpid[by_sev] == tpid[by_blast]:
        same += 1
    else:
        disagree += 1
A["escalation_target"] = {
    "manifests_scored": same + disagree,
    "top_choice_agrees": same,
    "top_choice_disagrees": disagree,
    "disagreement_pct": round(100 * disagree / max(same + disagree, 1), 1),
}

# ---- C. proper ablation: logistic "high-risk manifest" with/without features --
say("logistic ablation: does adding structural features change the flagged set?")
from sklearn.linear_model import LogisticRegression

mans = sorted(man_adv)
y = np.array([man_adv[m] >= 5 for m in mans], int)  # "high advisory load" label
# per-manifest features
feat_base, feat_adv = [], []
for m in mans:
    sel = [j for j in range(len(rows)) if rows[j][0] == m]
    s_max = max(sev[j] for j in sel)
    d_min = min(dep[j] for j in sel)
    n_term = len({tpid[j] for j in sel})
    feat_base.append([s_max, d_min, n_term, len(sel)])
    c_max = max(crit[j] for j in sel)
    bw_max = max(bw_n[j] for j in sel)
    n_art = sum(art[tpid[j]] for j in sel)
    feat_adv.append([s_max, d_min, n_term, len(sel), c_max, bw_max, n_art])
feat_base = np.array(feat_base)
feat_adv = np.array(feat_adv)
if y.sum() >= 10 and (y == 0).sum() >= 10:
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_predict

    pb = cross_val_predict(
        LogisticRegression(max_iter=500, class_weight="balanced"),
        feat_base,
        y,
        cv=5,
        method="predict_proba",
    )[:, 1]
    pa = cross_val_predict(
        LogisticRegression(max_iter=500, class_weight="balanced"),
        feat_adv,
        y,
        cv=5,
        method="predict_proba",
    )[:, 1]
    flag_b = set(np.argsort(-pb)[:200])
    flag_a = set(np.argsort(-pa)[:200])
    A["logistic_ablation"] = {
        "n_manifests": len(mans),
        "n_high_risk": int(y.sum()),
        "auroc_base": round(float(roc_auc_score(y, pb)), 4),
        "auroc_advanced": round(float(roc_auc_score(y, pa)), 4),
        "auroc_delta": round(float(roc_auc_score(y, pa) - roc_auc_score(y, pb)), 4),
        "top200_flagged_overlap": round(len(flag_b & flag_a) / 200, 3),
        "manifests_flagged_only_by_advanced": len(flag_a - flag_b),
    }
else:
    A["logistic_ablation"] = {"skipped": "class imbalance"}

# readings
kt = A["alert_prioritisation"]["kendall_tau_base_vs_advanced"]
A["alert_prioritisation"]["reading"] = (
    "structural boost meaningfully reorders the queue"
    if kt < 0.9
    else "structural boost barely changes the ordering - severity already dominates"
)
A["verdict"] = (
    "the advanced graph signals DO change decisions"
    if (
        A["alert_prioritisation"]["top20_overlap"] < 0.8
        or A["escalation_target"]["disagreement_pct"] > 15
        or A["logistic_ablation"].get("auroc_delta", 0) > 0.02
    )
    else "the advanced graph signals are mostly inert for these decisions - "
    "severity + depth already carry the signal (honest negative)"
)
json.dump(A, open(OUT / "ablation.json", "w"), indent=2, default=str)
print(json.dumps(A, indent=2, default=str))
say("ablation.json written")
