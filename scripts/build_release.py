#!/usr/bin/env python
"""CLI entrypoint for the release snapshot.

Copies the processed tables the API serves into the committed ``data/release``
directory, with a manifest of hashes and provenance. Run after ``make models``.

Usage::

    python scripts/build_release.py
"""

from __future__ import annotations

import sys

from amber.release import main

if __name__ == "__main__":
    sys.exit(main())
