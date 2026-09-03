#!/usr/bin/env python3
"""Run the evaluation suite against a built full-corpus graph.

    python scripts/run_evaluation.py --all
    python scripts/run_evaluation.py --timing --resolver
    python scripts/run_evaluation.py --list

Modules (each writes one or more JSON files into results/metrics/):

    timing              build / load / query latency, throughput, per-algorithm
                        wall-clock, and an edge-sampled scaling curve
    scaling             just the scaling curve, merged into timing.json, plus the figure
    resolver_fidelity   our resolver vs deps.dev's resolver (needs network)
    ablation            do the advanced graph signals change a decision?
    extras              Clauset power-law goodness-of-fit + a 150-lockfile osv-scanner diff

`timing`, `scaling`, `ablation` and `extras` need data/graph (run scripts/build_graph.py
first). `resolver_fidelity` and `extras` need outbound network. `extras` also needs an
`osv-scanner` binary on PATH or in ./bin for the head-to-head.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MODULES = ["timing", "scaling", "resolver_fidelity", "ablation", "extras"]


def run_module(name: str) -> tuple[str, int, float]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SCRIPTS), env.get("PYTHONPATH", "")])
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", f"evaluation.{name}"], cwd=ROOT, env=env, check=False
    )
    return name, proc.returncode, time.time() - t0


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--all", action="store_true", help="run every module")
    p.add_argument("--list", action="store_true", help="list modules and exit")
    for m in MODULES:
        p.add_argument(f"--{m.replace('_', '-')}", action="store_true", dest=m)
    a = p.parse_args()

    if a.list:
        for m in MODULES:
            print(m)
        return

    selected = MODULES if a.all else [m for m in MODULES if getattr(a, m)]
    if not selected:
        p.error("choose --all or one or more module flags (see --list)")

    if not (ROOT / "data" / "graph" / "res_indptr.npy").exists() and any(
        m in selected for m in ("timing", "scaling", "ablation", "extras")
    ):
        print("warning: data/graph is missing; run scripts/build_graph.py first", file=sys.stderr)

    results = [run_module(m) for m in selected]
    print("\n=== evaluation summary ===")
    for name, rc, secs in results:
        print(f"  {name:20} {'ok' if rc == 0 else f'FAILED (rc={rc})':16} {secs:6.0f}s")
    sys.exit(1 if any(rc != 0 for _, rc, _ in results) else 0)


if __name__ == "__main__":
    main()
