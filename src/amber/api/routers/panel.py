"""The tidy indicator panel, for the descriptive charts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from amber import config

from .. import presenters
from .. import schemas as s
from ..deps import get_store
from ..store import DataStore

router = APIRouter(tags=["past"])


def parse_list(raw: str | None, known: list[str], default: list[str], what: str) -> list[str]:
    """Parse a comma-separated list against the known values.

    Args:
        raw: The query value, or None for the default.
        known: Valid values.
        default: What an absent value means.
        what: Noun for the error message.

    Returns:
        The requested values, in the order given.

    Raises:
        HTTPException: 422 on an unknown value or an empty list.
    """
    if raw is None:
        return default
    values = [v.strip() for v in raw.split(",") if v.strip()]
    unknown = [v for v in values if v not in known]
    if unknown or not values:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown or empty {what}: {unknown or raw!r}; expected any of {known}",
        )
    return list(dict.fromkeys(values))


@router.get("/panel")
def panel(
    store: Annotated[DataStore, Depends(get_store)],
    indicators: Annotated[
        str | None,
        Query(description="Comma-separated indicator ids; default GDP per capita."),
    ] = None,
    countries: Annotated[
        str | None, Query(description="Comma-separated ISO3 codes; default all.")
    ] = None,
    include_pre_window: Annotated[
        bool, Query(description="Include pre-2011 rows (unreliable, excluded from modeling).")
    ] = False,
) -> s.PanelResponse:
    """Indicator series by country and year, with imputation and dark-series flags."""
    chosen = parse_list(
        indicators,
        list(config.INDICATORS_BY_ID),
        list(config.API_PANEL_DEFAULT_INDICATORS),
        "indicators",
    )
    nations = parse_list(countries, list(config.COUNTRIES), list(config.COUNTRIES), "countries")
    return presenters.panel(store, chosen, nations, include_pre_window)
