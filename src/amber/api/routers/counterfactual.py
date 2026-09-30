"""The synthetic-control counterfactual - precomputed, never refitted."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from .. import schemas as s
from ..deps import Precomputed, get_precomputed

router = APIRouter(tags=["counterfactual"])


@router.get("/counterfactual")
def counterfactual(
    pre: Annotated[Precomputed, Depends(get_precomputed)],
) -> s.CounterfactualResponse:
    """Actual vs synthetic, donor weights, placebos, leave-one-out and the verdicts."""
    return pre.counterfactual
