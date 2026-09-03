"""The package's public surface and its lazy-import guarantee."""

from __future__ import annotations

import subprocess
import sys

import scgraph


def test_version_is_exported() -> None:
    assert isinstance(scgraph.__version__, str)
    assert scgraph.__version__.count(".") == 2


def test_public_names_are_importable() -> None:
    for name in scgraph.__all__:
        assert hasattr(scgraph, name), name


def test_importing_scgraph_does_not_pull_torch() -> None:
    # the heavy model layer must stay lazy: a bare `import scgraph` must not import torch
    code = "import sys, scgraph; assert 'torch' not in sys.modules; print('ok')"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
