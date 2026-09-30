"""Amber - a simulation of Myanmar's development.

Three layers over one shared country-year panel:

* **Past** - an empirical reconstruction from World Bank WDI series, 2011 onward.
* **Counterfactual** - a synthetic Myanmar built from regional peers that did not
  rupture in 2021, estimating what the coup interrupted.
* **Future** - a system-dynamics model of scenarios to ~2035.

Only the data layer (:mod:`amber.ingestion`, :mod:`amber.cleaning`,
:mod:`amber.pipeline`) is implemented. :mod:`amber.modeling` and :mod:`amber.api`
are stubs awaiting phases 2-5.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
