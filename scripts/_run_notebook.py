#!/usr/bin/env python3
"""Execute a notebook in place with nbclient and print a per-cell status summary.

    python scripts/_run_notebook.py notebooks/supply_chain_graph_engineering.ipynb scgraph 1800

Positional args: notebook path, kernel name (default "scgraph"), timeout seconds
(default 1800). Pass --allow-errors to keep going past a failing cell (the failing
cells are still listed at the end and the exit code is still non-zero).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

args = [a for a in sys.argv[1:] if not a.startswith("--")]
nb_path = Path(args[0]) if args else Path("notebooks/supply_chain_graph_engineering.ipynb")
kernel = args[1] if len(args) > 1 else "scgraph"
timeout = int(args[2]) if len(args) > 2 else 1800
allow_errors = "--allow-errors" in sys.argv

nb = nbformat.read(nb_path, as_version=4)
client = NotebookClient(
    nb,
    timeout=timeout,
    kernel_name=kernel,
    allow_errors=allow_errors,
    resources={"metadata": {"path": str(nb_path.parent.parent)}},
)

t0 = time.time()
errors: list[str] = []
try:
    client.execute()
except CellExecutionError as e:  # only reached when allow_errors is False
    errors.append(str(e))

nbformat.write(nb, nb_path)

n_fig = 0
for i, cell in enumerate(nb.cells):
    if cell.cell_type != "code":
        continue
    for out in cell.get("outputs", []):
        if out.get("output_type") == "error":
            print(f"\n=== ERROR in cell {i} ===")
            print("SRC:", "\n".join(cell.source.splitlines()[:6]))
            print(("  " + "\n  ".join(out.get("traceback", [])))[-3000:])
            errors.append(f"cell {i}: {out.get('ename')}: {out.get('evalue')}")
        elif out.get("output_type") in (
            "display_data",
            "execute_result",
        ) and "image/png" in out.get("data", {}):
            n_fig += 1

verdict = "ALL OK" if not errors else f"ERRORS: {len(errors)}"
print(f"\n{verdict}  {time.time() - t0:.0f}s  figures={n_fig}  cells={len(nb.cells)}")
for e in errors:
    print("  -", e[:200])
sys.exit(1 if errors else 0)
