#!/usr/bin/env python
"""CLI entrypoint for the future layer.

Calibrates the system-dynamics model on Myanmar's 2011-2024 history, runs every
configured scenario as an ensemble to 2035, checks the no-coup scenario against
the phase 3 synthetic control, writes the tables to ``data/processed`` and
renders the charts to ``reports/figures``.

Usage::

    python scripts/build_system_dynamics.py
    python scripts/build_system_dynamics.py --ensemble-size 500
    python scripts/build_system_dynamics.py --no-figures
"""

from __future__ import annotations

import sys

from amber.dynamics import main

if __name__ == "__main__":
    sys.exit(main())
