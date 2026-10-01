#!/usr/bin/env python
"""CLI entrypoint for the historical layer.

Discovers which series have real pre-2000 coverage, pulls them back to 1960 for
Myanmar, Thailand and the donor pool, flags Myanmar's pre-1990 observations as
low reliability, adds any pre-1960 Maddison export, computes the illustrative
divergence scenarios and renders the two historical charts.

Usage::

    python scripts/build_historical.py
    python scripts/build_historical.py --anchor 1962
    python scripts/build_historical.py --refresh --no-figures
"""

from __future__ import annotations

import sys

from amber.historical import main

if __name__ == "__main__":
    sys.exit(main())
