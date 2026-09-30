#!/usr/bin/env python
"""CLI entrypoint for the counterfactual layer.

Reads the interpolated panel and the index table, fits synthetic Myanmar for
every configured outcome, runs the placebo and leave-one-out checks, writes the
tables to ``data/processed`` and renders the charts to ``reports/figures``.

Usage::

    python scripts/build_synthetic_control.py
    python scripts/build_synthetic_control.py --outcome NY.GDP.PCAP.KD
    python scripts/build_synthetic_control.py --pre-period-end 2019   # drop 2020 from the fit
    python scripts/build_synthetic_control.py --rebase                # 2011 = 100 variant
"""

from __future__ import annotations

import sys

from amber.counterfactual import main

if __name__ == "__main__":
    sys.exit(main())
