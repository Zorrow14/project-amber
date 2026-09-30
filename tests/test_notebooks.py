"""Committed notebooks carry no outputs.

The charts are committed once, as PNGs in reports/figures. Storing them again
inline would duplicate them and make every notebook diff noisy, so notebooks
are committed stripped and regenerate on run. `make notebook` executes into the
gitignored build/ so running one never dirties the tracked file.

Reads the .ipynb as plain JSON so the check needs no notebook dependency.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amber import config

NOTEBOOKS = sorted((config.PROJECT_ROOT / "notebooks").glob("*.ipynb"))


def test_there_are_notebooks_to_check():
    assert NOTEBOOKS


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_committed_without_outputs(path: Path):
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    dirty = [
        i
        for i, cell in enumerate(cells)
        if cell["cell_type"] == "code" and (cell.get("outputs") or cell.get("execution_count"))
    ]

    assert not dirty, (
        f"{path.name} has outputs in cells {dirty}. Clear them before committing "
        "(Jupyter: Clear All Outputs), or run `make notebook`, which writes to build/."
    )
