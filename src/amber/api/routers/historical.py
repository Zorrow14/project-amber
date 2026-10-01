"""The historical arc (phase 7) - descriptive history and an illustrative divergence.

Precomputed and served as-is: nothing in this layer is user-parameterized, so
nothing is recomputed. Every row keeps its ``source`` and ``reliability``, and
every divergence payload keeps ``scenario_illustrative``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from amber import config

from .. import presenters
from .. import schemas as s
from ..caching import cacheable, serve
from ..deps import Precomputed, get_precomputed, get_store
from ..store import DataStore
from .panel import parse_list

router = APIRouter(tags=["historical"])


@router.get("/historical", dependencies=[Depends(cacheable)])
def historical(
    store: Annotated[DataStore, Depends(get_store)],
    indicators: Annotated[
        str | None,
        Query(description="Comma-separated ids; default GDP per capita (WDI) plus Maddison."),
    ] = None,
    countries: Annotated[
        str | None, Query(description="Comma-separated ISO3 codes; default Myanmar + Thailand.")
    ] = None,
) -> s.HistoricalResponse:
    """1960+ series by country and year, each row with its ruler and reliability."""
    chosen = parse_list(
        indicators,
        presenters.historical_indicators(store),
        presenters.default_historical_indicators(),
        "indicators",
    )
    nations = parse_list(
        countries,
        list(config.HISTORICAL_COUNTRIES),
        presenters.default_historical_countries(),
        "countries",
    )
    return presenters.historical(store, chosen, nations)


@router.get("/historical/divergence", response_model=s.DivergenceResponse)
def divergence(
    request: Request,
    pre: Annotated[Precomputed, Depends(get_precomputed)],
    comparator: Annotated[
        str | None, Query(description="Comparator key from /meta; default Thailand.")
    ] = None,
) -> Response:
    """The illustrative long-run divergence scenario for one comparator."""
    key = comparator if comparator is not None else pre.meta.historical.default_comparator
    if key not in pre.divergence:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown comparator {key!r}; expected one of {sorted(pre.divergence)}",
        )
    return serve(request, pre.bodies[f"divergence:{key}"])
