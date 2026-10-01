"""The development index, recomputed live under user weights."""

from __future__ import annotations

import argparse
import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from amber import config
from amber.config import Normalization
from amber.reconstruction import parse_weights

from .. import live, presenters
from .. import schemas as s
from ..caching import cacheable
from ..deps import get_store
from ..store import DataStore

router = APIRouter(tags=["past"])


@router.get("/index", dependencies=[Depends(cacheable)])
def index(
    store: Annotated[DataStore, Depends(get_store)],
    weights: Annotated[
        str | None,
        Query(
            description="Pillar weights on any non-negative scale, e.g. "
            "economy=2,innovation=1,human_development=1. Default: equal.",
        ),
    ] = None,
    method: Annotated[
        Normalization, Query(description="Normalization method.")
    ] = config.DEFAULT_NORMALIZATION,
) -> s.IndexResponse:
    """Pillar and combined series for every country, with coverage on every row."""
    parsed = None
    if weights is not None:
        try:
            parsed = parse_weights(weights)
        except argparse.ArgumentTypeError as exc:
            raise HTTPException(status_code=422, detail=f"Malformed weights: {exc}") from exc
        bad = {k: v for k, v in parsed.items() if not math.isfinite(v) or v < 0}
        if bad:
            raise HTTPException(
                status_code=422, detail=f"Weights must be finite and non-negative, got {bad}"
            )
    try:
        applied, frame = live.index_under_weights(store, parsed, method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return presenters.index_response(applied, method, frame)
