"""System-dynamics future model - STUB, phase 4.

Nothing here is implemented. The intended model, recorded so later phases start
from the decisions already made:

A stock-and-flow model (PySD) representing development as interacting stocks -
physical capital, human capital, infrastructure/connectivity and institutional
stability - linked by feedback loops. The central loop is
connectivity -> productivity -> investment -> infrastructure, which is what made
the 2013 telecom liberalization matter so much in the reform era.

Users adjust levers and a coup / no-coup switch to generate divergent
trajectories to ~2035. Outputs are scenarios, never forecasts, and the UI has to
say so.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

__all__ = ["ScenarioLevers", "simulate"]

HORIZON_YEAR = 2035
"""How far the future model projects."""


@dataclass(frozen=True, slots=True)
class ScenarioLevers:
    """User-adjustable inputs to a future scenario.

    Each lever is a 0-1 dial rather than a natural unit, so the frontend can
    expose them uniformly and the mapping to model parameters stays in one place.

    Attributes:
        stability: Institutional stability. MSDP Pillar 1 is the high setting;
            the coup is the drop.
        investment_openness: How open the economy is to foreign investment.
        education_spending: Human-capital investment rate.
        connectivity: Rate of connectivity expansion.
        coup: Whether the 2021 rupture happens in this scenario.
    """

    stability: float = 0.5
    investment_openness: float = 0.5
    education_spending: float = 0.5
    connectivity: float = 0.5
    coup: bool = True


def simulate(
    levers: ScenarioLevers,
    start_year: int,
    end_year: int = HORIZON_YEAR,
) -> pd.DataFrame:
    """Run a future scenario.

    Args:
        levers: Scenario settings.
        start_year: First projected year, normally the last observed year.
        end_year: Last projected year.

    Returns:
        Projected stocks and the combined index by year.

    Raises:
        NotImplementedError: Always - phase 4.
    """
    # TODO(phase-4): build the stock-and-flow model in PySD; initialise stocks
    #   from the observed panel; wire levers to flow rates.
    raise NotImplementedError("System dynamics is phase 4; the data layer comes first.")
