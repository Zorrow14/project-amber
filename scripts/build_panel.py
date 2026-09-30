#!/usr/bin/env python
"""CLI entrypoint for the data layer.

Fetches every configured indicator, caches the raw pulls, and writes the tidy
panel, its interpolated variant and the coverage report to ``data/processed``.

Usage::

    python scripts/build_panel.py
    python scripts/build_panel.py --refresh        # bypass the raw cache
    python scripts/build_panel.py --log-level DEBUG
"""

from __future__ import annotations

import sys

from amber.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
