"""FastAPI application - STUB, phase 5.

Only ``/health`` is implemented. The endpoints that will serve panel, index,
counterfactual and scenario data wait on the modeling layers behind them.

Run locally with::

    uvicorn amber.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from amber import __version__

app = FastAPI(
    title="Amber API",
    version=__version__,
    summary="Myanmar development simulation - past, counterfactual, and future scenarios.",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe.

    Returns:
        Service name, version and status.
    """
    return {"status": "ok", "service": "amber", "version": __version__}


# TODO(phase-5): once the modeling layers land, expose:
#   GET /panel        - the tidy country-year panel, filterable by country/indicator
#   GET /index        - combined index with user-supplied pillar weights. The logic
#                       is ready (amber.modeling.index.compute_index takes weights
#                       on any scale); only the HTTP exposure is deferred.
#   GET /counterfactual - real vs synthetic Myanmar, with fit diagnostics
#   POST /scenario    - run the system-dynamics model against posted levers
# Every response carries its uncertainty and is labelled estimate, not forecast.
