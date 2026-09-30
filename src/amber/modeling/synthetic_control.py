"""Synthetic-control counterfactual - STUB, phase 3.

Nothing here is implemented. The intended method, recorded so the data layer can
be judged against what it has to feed:

Build a *synthetic Myanmar* as a weighted combination of donor-pool countries,
choosing weights so the synthetic unit tracks real Myanmar as closely as possible
over the pre-treatment window on both the outcome series and a set of predictors.
After :data:`~amber.config.TREATMENT_YEAR`, the divergence between real and
synthetic Myanmar is the estimate of what the coup interrupted.

Decisions already made (see ``docs/myanmar-precoup-calibration-reference.md``):

* Treatment year is 2021.
* The clean pre-treatment window is ~2011-2019: 2020 is COVID-confounded, and
  pre-2011 rows are military-era and carry the ``pre_2011`` flag. That leaves
  about nine usable years - workable, not luxurious.
* The donor pool excludes any country with its own concurrent 2021+ shock.
  Sri Lanka is out because of its 2022 crisis.
* Robustness is part of the deliverable, not an extra: placebo tests applying
  the method to untreated donors, plus varying the donor pool. Pre-treatment fit
  error gets reported alongside every estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

__all__ = ["SyntheticControlResult", "fit_synthetic_control", "run_placebo_tests"]


@dataclass(frozen=True, slots=True)
class SyntheticControlResult:
    """Placeholder for a fitted synthetic control.

    Attributes:
        weights: Donor country ISO3 -> weight, summing to 1.
        trajectory: Real and synthetic series by year, plus the gap between them.
        pre_treatment_rmspe: Fit error over the pre-treatment window. The
            credibility of the whole estimate rests on this being small.
    """

    weights: dict[str, float]
    trajectory: pd.DataFrame
    pre_treatment_rmspe: float


def fit_synthetic_control(
    panel: pd.DataFrame,
    outcome_indicator: str,
    predictor_indicators: tuple[str, ...] = (),
) -> SyntheticControlResult:
    """Fit a synthetic Myanmar against the donor pool.

    Args:
        panel: Tidy panel from :mod:`amber.cleaning`.
        outcome_indicator: WDI id of the series to match and project.
        predictor_indicators: Additional series used to fit the weights.

    Returns:
        The fitted weights, the real-vs-synthetic trajectory, and fit error.

    Raises:
        NotImplementedError: Always - phase 3.
    """
    # TODO(phase-3): fit donor weights over MODELING_WINDOW_START..TREATMENT_YEAR-1,
    #   excluding pre_2011 rows and handling the COVID-confounded 2020.
    raise NotImplementedError("Synthetic control is phase 3; the data layer comes first.")


def run_placebo_tests(panel: pd.DataFrame, outcome_indicator: str) -> pd.DataFrame:
    """Apply the method to each untreated donor to calibrate significance.

    Args:
        panel: Tidy panel from :mod:`amber.cleaning`.
        outcome_indicator: WDI id of the outcome series.

    Returns:
        One row per placebo unit with its post-treatment gap.

    Raises:
        NotImplementedError: Always - phase 3.
    """
    # TODO(phase-3): in-space placebos over the donor pool, plus donor-pool
    #   sensitivity (drop each donor in turn and report weight stability).
    raise NotImplementedError("Placebo tests are phase 3; the data layer comes first.")
