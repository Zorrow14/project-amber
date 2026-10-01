"""Health and metadata."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from .. import presenters
from .. import schemas as s
from ..caching import NO_STORE, serve
from ..deps import Precomputed, get_precomputed, get_store
from ..store import DataStore

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(store: Annotated[DataStore, Depends(get_store)], response: Response) -> s.HealthResponse:
    """Liveness probe, with which data snapshot is being served. Never cached."""
    response.headers["Cache-Control"] = NO_STORE
    return presenters.health(store)


@router.get("/meta", response_model=s.MetaResponse)
def meta(request: Request, pre: Annotated[Precomputed, Depends(get_precomputed)]) -> Response:
    """Countries, indicators, pillars, levers, scenarios and framing - all from config."""
    return serve(request, pre.bodies["meta"])
