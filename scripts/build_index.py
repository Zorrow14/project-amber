#!/usr/bin/env python
"""CLI entrypoint for the reconstruction layer.

Reads ``data/processed/panel_interpolated.csv``, builds the combined development
index, writes ``data/processed/index.csv``, and renders the charts to
``reports/figures``.

Usage::

    python scripts/build_index.py
    python scripts/build_index.py --weights economy=2,innovation=1,human_development=1
    python scripts/build_index.py --no-figures
"""

from __future__ import annotations

import sys

from amber.reconstruction import main

if __name__ == "__main__":
    sys.exit(main())
