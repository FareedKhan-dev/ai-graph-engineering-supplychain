#!/usr/bin/env python3
"""Guard: the committed notebook must keep its full-run outputs and figures.

The notebook is the primary artifact of this repository. It is committed with the
outputs and 14 figures from the full run so it renders completely on GitHub. This
check fails if that is no longer true, which usually means the notebook was edited
and committed without being re-executed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat

NB = Path(__file__).resolve().parent.parent / "notebooks" / "supply_chain_graph_engineering.ipynb"
MIN_OUTPUT_CELLS = 30
MIN_FIGURES = 12


def main() -> int:
    nb = nbformat.read(NB, as_version=4)
    with_output = sum(1 for c in nb.cells if c.cell_type == "code" and c.get("outputs"))
    figures = sum(
        1 for c in nb.cells for o in c.get("outputs", []) if "image/png" in o.get("data", {})
    )
    if with_output < MIN_OUTPUT_CELLS or figures < MIN_FIGURES:
        print(
            f"{NB.name} looks stripped: {with_output} output cells "
            f"(need >= {MIN_OUTPUT_CELLS}), {figures} figures (need >= {MIN_FIGURES}).\n"
            "Re-execute the notebook before committing. See notebooks/README.md.",
            file=sys.stderr,
        )
        return 1
    print(f"{NB.name}: {with_output} output cells, {figures} figures - ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
