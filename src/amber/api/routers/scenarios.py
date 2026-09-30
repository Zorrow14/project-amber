"""Future scenarios: the precomputed defaults, and live runs under user levers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from amber import config

from .. import live, presenters
from .. import schemas as s
from ..deps import Precomputed, get_precomputed, get_store
from ..store import DataStore

router = APIRouter(tags=["future"])


@router.get("/scenarios")
def scenarios(pre: Annotated[Precomputed, Depends(get_precomputed)]) -> s.ScenariosResponse:
    """Every configured scenario's p10/p50/p90 trajectory, paired gaps and verdicts."""
    return pre.scenarios


@router.post("/simulate")
def simulate(
    request: s.SimulateRequest, store: Annotated[DataStore, Depends(get_store)]
) -> s.SimulateResponse:
    """Run a scenario live on the precomputed calibration - never refitted.

    ``levers`` override the named scenario's; the scenario (default: actual
    continuation) supplies the stability path.
    """
    base = store.scenarios[request.scenario or config.SD_BASELINE_SCENARIO]
    scenario = live.custom_scenario(base, request.levers)
    result = live.simulate(store, scenario)
    return presenters.simulated(store, scenario, result, custom=scenario is not base)
