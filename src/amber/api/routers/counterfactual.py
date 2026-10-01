"""The synthetic-control counterfactual - precomputed, never refitted."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from .. import schemas as s
from ..caching import serve
from ..deps import Precomputed, get_precomputed

router = APIRouter(tags=["counterfactual"])


@router.get("/counterfactual", response_model=s.CounterfactualResponse)
def counterfactual(
    request: Request, pre: Annotated[Precomputed, Depends(get_precomputed)]
) -> Response:
    """Actual vs synthetic, donor weights, placebos, leave-one-out and the verdicts."""
    return serve(request, pre.bodies["counterfactual"])
