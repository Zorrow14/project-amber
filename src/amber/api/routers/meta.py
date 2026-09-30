"""Health and metadata."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from .. import presenters
from .. import schemas as s
from ..deps import Precomputed, get_precomputed, get_store
from ..store import DataStore

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(store: Annotated[DataStore, Depends(get_store)]) -> s.HealthResponse:
    """Liveness probe, with which data snapshot is being served."""
    return presenters.health(store)


@router.get("/meta")
def meta(pre: Annotated[Precomputed, Depends(get_precomputed)]) -> s.MetaResponse:
    """Countries, indicators, pillars, levers, scenarios and framing - all from config."""
    return pre.meta
