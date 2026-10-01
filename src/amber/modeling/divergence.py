"""The long-run divergence scenario: an illustration, not an estimate.

Myanmar's actual GDP per capita at an anchor year, grown forward at a
comparator's actual annual growth (see :class:`amber.config.DivergenceScenario`)::

    P(anchor) = Y_MMR(anchor)
    P(t)      = P(t-1) * exp(g_t),   g_t = mean over units u of ln(Y_u,t / Y_u,t-1)

Nothing is fitted, so there is nothing to test: no p-value, no pre-period fit,
no credibility verdict. Every result carries ``scenario_illustrative = True``,
and the words "counterfactual estimate" stay reserved for the phase 3 synthetic
control. The path bundles every difference between Myanmar and its comparator,
so it shows how far the two diverged, not what caused it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from amber import config
from amber.config import DivergenceComparator, DivergenceScenario

logger = logging.getLogger(__name__)

COL_ACTUAL = "actual"
COL_PATH = "path"
COL_RATIO = "ratio"
COL_GROWTH = "growth"
COL_N_UNITS = "n_units"

PATH_COLUMNS: tuple[str, ...] = (
    config.COL_YEAR,
    COL_ACTUAL,
    COL_PATH,
    config.COL_GAP,
    COL_RATIO,
    COL_GROWTH,
    COL_N_UNITS,
)


@dataclass(frozen=True, slots=True)
class DivergenceResult:
    """One divergence scenario, computed.

    Attributes:
        scenario: The configuration it was computed from.
        comparator: The resolved comparator.
        anchor_value: Myanmar's actual level in the anchor year.
        path: One row per year from the anchor, in :data:`PATH_COLUMNS`:
            Myanmar's actual level, the scenario path, ``gap = path - actual``,
            ``ratio = path / actual``, the comparator log growth applied in that
            year and how many comparator units it averaged.
    """

    scenario: DivergenceScenario
    comparator: DivergenceComparator
    anchor_value: float
    path: pd.DataFrame

    @property
    def illustrative(self) -> bool:
        """Always true: an assumption-driven scenario, never an estimate."""
        return True

    @property
    def latest(self) -> pd.Series:
        """The last year with both an actual value and a path value."""
        both = self.path.dropna(subset=[COL_ACTUAL, COL_PATH])
        if both.empty:
            msg = f"Divergence scenario {self.scenario.name!r} has no year with both series"
            raise ValueError(msg)
        return both.iloc[-1]


def comparator_growth(levels: pd.DataFrame, units: tuple[str, ...]) -> pd.DataFrame:
    """Mean annual log growth of the comparator units.

    Growth in year t needs a unit observed in both t-1 and t; nothing is
    interpolated, so a unit with a gap simply drops out of the mean for the
    years it cannot supply.

    Args:
        levels: Wide levels, one row per year (the index), one column per ISO3.
        units: The comparator's units.

    Returns:
        Indexed by year: ``growth`` (NaN where no unit can supply it) and
        ``n_units``.

    Raises:
        ValueError: If a unit is missing from ``levels``.
    """
    missing = sorted(set(units) - set(levels.columns))
    if missing:
        msg = f"No level series for comparator units {missing}"
        raise ValueError(msg)
    frame = levels[list(units)].sort_index()
    frame = frame.reindex(range(int(frame.index.min()), int(frame.index.max()) + 1))
    log_growth = np.log(frame.where(frame > 0)).diff()
    return pd.DataFrame(
        {
            COL_GROWTH: log_growth.mean(axis=1, skipna=True),
            COL_N_UNITS: log_growth.notna().sum(axis=1).astype(int),
        }
    )


def divergence_path(
    actual: pd.Series,
    levels: pd.DataFrame,
    scenario: DivergenceScenario,
    comparator: DivergenceComparator,
    *,
    end_year: int = config.HISTORICAL_END,
) -> DivergenceResult:
    """Grow Myanmar's anchor-year level at the comparator's growth.

    The path stops at the first year no comparator unit can supply growth
    (it is never bridged), and the run logs where.

    Args:
        actual: Myanmar's level, indexed by year.
        levels: Wide comparator levels, indexed by year, one column per ISO3.
        scenario: Anchor year and comparator key.
        comparator: The resolved comparator.
        end_year: Last year of the path.

    Returns:
        The path and its anchor.

    Raises:
        ValueError: If Myanmar has no observation in the anchor year.
    """
    anchor = scenario.anchor_year
    anchor_value = actual.get(anchor, np.nan)
    if not np.isfinite(anchor_value):
        msg = f"Divergence scenario {scenario.name!r}: no Myanmar value in anchor year {anchor}"
        raise ValueError(msg)

    years = pd.Index(range(anchor, end_year + 1), name=config.COL_YEAR)
    growth = comparator_growth(levels, comparator.units).reindex(years)
    growth.loc[anchor, :] = (0.0, 0)  # the anchor year is the starting level, not a step
    growth[COL_N_UNITS] = growth[COL_N_UNITS].fillna(0).astype(int)

    steps = growth[COL_GROWTH].to_numpy(dtype=float)
    # NaN propagates through the cumulative sum, so the path ends at the first gap.
    path = anchor_value * np.exp(np.cumsum(steps))
    first_gap = next((int(y) for y, s in zip(years, steps, strict=True) if np.isnan(s)), None)
    if first_gap is not None:
        logger.warning(
            "Divergence scenario %s stops in %d: no %s growth observed",
            scenario.name,
            first_gap,
            comparator.label,
        )

    observed = actual.reindex(years).to_numpy(dtype=float)
    table = pd.DataFrame(
        {
            config.COL_YEAR: years,
            COL_ACTUAL: observed,
            COL_PATH: path,
            config.COL_GAP: path - observed,
            COL_RATIO: path / observed,
            COL_GROWTH: steps,
            COL_N_UNITS: growth[COL_N_UNITS].to_numpy(),
        }
    )
    return DivergenceResult(
        scenario=scenario,
        comparator=comparator,
        anchor_value=float(anchor_value),
        path=table[list(PATH_COLUMNS)],
    )
