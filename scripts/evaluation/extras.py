#!/usr/bin/env python3
"""Smaller eval gaps:
  1. Power-law goodness-of-fit (Clauset-Shalizi-Newman): the bootstrapped p-value that
     tells you whether "power law" is even a defensible model for the in-degree tail,
     vs the KS distance alone (which we already report).
  2. Larger osv-scanner head-to-head: generate ~150 lockfiles from the graph (npm +
     pypi) and diff osv-scanner's finding set against our post-ladder alerting set.
  3. Reachability prior vs a weak symbol-level ground truth: Go/OSV advisories that name
     a vulnerable import path are "reachable-ish if the dep is runtime & shallow" -
     score the prior's agreement.

Writes results/metrics/powerlaw_gof.json and vs_osvscanner_big.json. Runs on the
full-corpus graph (see scripts/run_evaluation.py). Reproduction script, not library code.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from evaluation._paths import GRAPH as G
from evaluation._paths import OUT, ROOT

BP = ROOT / "blogpack"
t0 = time.time()


def say(m):
    print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)


# ============================ 1. power-law GoF =================================
def _discrete_pl_fit(x, xmin):
    x = x[x >= xmin]
    if len(x) < 50:
        return None, len(x)
    alpha = 1 + len(x) / np.sum(np.log(x / (xmin - 0.5)))
    return float(alpha), len(x)


def _ks(x, xmin, alpha):
    x = np.sort(x[x >= xmin])
    if len(x) < 2:
        return 1.0
    cdf_emp = np.arange(1, len(x) + 1) / len(x)
    grid = np.unique(x)
    w = grid.astype(float) ** (-alpha)
    cdf_fit = np.interp(x, grid, np.cumsum(w) / w.sum())
    return float(np.max(np.abs(cdf_emp - cdf_fit)))


def clauset_pvalue(deg, xmin=2, n_boot=200, seed=0):
    """Fraction of synthetic power-law datasets whose KS >= the observed KS.
    p >= 0.1 => power law is plausible; p < 0.1 => rule it out."""
    rng = np.random.default_rng(seed)
    d = np.asarray(deg, float)
    d = d[d >= 1]
    alpha, ntail = _discrete_pl_fit(d, xmin)
    if alpha is None:
        return {"alpha": None}
    ks_obs = _ks(d, xmin, alpha)
    tail = d[d >= xmin]
    ntail = len(tail)
    ge = 0
    for _ in range(n_boot):
        u = rng.random(ntail)
        synth = np.floor((xmin - 0.5) * (1 - u) ** (-1 / (alpha - 1)) + 0.5)
        synth = synth[np.isfinite(synth) & (synth >= xmin)]
        a2, _ = _discrete_pl_fit(synth, xmin)
        if a2 is None:
            continue
        if _ks(synth, xmin, a2) >= ks_obs:
            ge += 1
    return {
        "alpha": round(alpha, 3),
        "xmin": xmin,
        "n_tail": int(ntail),
        "ks_observed": round(ks_obs, 4),
        "p_value": round(ge / n_boot, 3),
        "n_boot": n_boot,
        "reading": (
            "power law is a plausible model (p>=0.1)"
            if ge / n_boot >= 0.1
            else "power law is RULED OUT (p<0.1) - the tail is heavy but "
            "not power-law; likely lognormal or power-law-with-cutoff"
        ),
    }


say("power-law goodness-of-fit (Clauset bootstrapped p-value)")
ga = np.load(BP / "graph_arrays.npz", allow_pickle=True)
gof = {
    "in_degree": clauset_pvalue(ga["deg_in"], xmin=2, n_boot=250),
    "out_degree": clauset_pvalue(ga["deg_out"], xmin=2, n_boot=250),
}
json.dump(gof, open(OUT / "powerlaw_gof.json", "w"), indent=2)
print(json.dumps(gof, indent=2))

# ============================ 2. bigger osv-scanner ===========================
OSVS = shutil.which("osv-scanner") or str(
    Path(__file__).resolve().parents[2] / "bin" / "osv-scanner"
)
if not os.path.exists(OSVS):
    say("fetching osv-scanner")
    Path(OSVS).parent.mkdir(exist_ok=True)
    v = "2.2.3"
    try:
        v = json.loads(
            subprocess.check_output(
                ["curl", "-fsSL", "https://api.github.com/repos/google/osv-scanner/releases/latest"]
            )
        )["tag_name"].lstrip("v")
    except Exception:
        pass
    subprocess.run(
        [
            "curl",
            "-fsSL",
            "-o",
            OSVS,
            f"https://github.com/google/osv-scanner/releases/download/v{v}/osv-scanner_linux_amd64",
        ],
        check=False,
    )
    os.chmod(OSVS, 0o755)

if os.path.exists(OSVS):
    from scgraph.kgstore import KGStore
    from scgraph.paths import exposure_paths
    from scgraph.report import resolved_requirements

    say("loading KGStore for lockfile generation")
    S = KGStore(str(G))
    rng = np.random.default_rng(1)
    _nodep = np.diff(np.asarray(S.rdep_indptr)) == 0
    roots = np.where(np.asarray(S.ver_default) & _nodep)[0]
    both = ours_only = scanner_only = nrepo = 0
    for r in rng.choice(roots, 4000, replace=False).tolist():
        pid = int(S.ver_pkg[r])
        eco = str(S.pkg_eco[pid])
        if eco not in ("pypi", "npm"):
            continue
        reqs = resolved_requirements(S, int(r), eco)
        if not reqs or len(reqs) < 30:
            continue
        d = tempfile.mkdtemp()
        fn = {"pypi": "requirements.txt", "npm": "package-lock.json"}[eco]
        open(f"{d}/{fn}", "w").write(reqs)
        try:
            o = subprocess.run(
                [OSVS, "--format", "json", "-L", f"{d}/{fn}"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            sc = set()
            if o.stdout.strip():
                j = json.loads(o.stdout)
                for rr in j.get("results", []):
                    for pkg in rr.get("packages", []):
                        for vv in pkg.get("vulnerabilities", []):
                            sc.add(vv.get("id", ""))
        except Exception:
            shutil.rmtree(d, ignore_errors=True)
            continue
        shutil.rmtree(d, ignore_errors=True)
        ours = {p.osv_id for p in exposure_paths(S, int(r), 12, 250) if not p.withdrawn}
        both += len(ours & sc)
        ours_only += len(ours - sc)
        scanner_only += len(sc - ours)
        nrepo += 1
        if nrepo >= 150:
            break
    vs = {
        "repos": nrepo,
        "both": both,
        "only_us": ours_only,
        "only_scanner": scanner_only,
        "agreement_pct": round(100 * both / max(both + ours_only + scanner_only, 1), 1),
    }
    json.dump(vs, open(OUT / "vs_osvscanner_big.json", "w"), indent=2)
    print(json.dumps(vs, indent=2))
else:
    say("osv-scanner unavailable")

say("DONE")
