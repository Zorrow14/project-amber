"""Combined development index - STUB, phase 2.

Nothing here is implemented. The intended construction:

Normalize each indicator, group into the three pillars of
:class:`~amber.config.Pillar` - economy, innovation/technology, human development
- and aggregate **geometric-mean style**, so that weakness in one pillar cannot
be masked by strength in another. That choice is the point of the index, not an
implementation detail.

Pillar weights are exposed as frontend controls: how development is defined
becomes an explicit, adjustable choice rather than a hidden assumption. Nothing
in this module may hardcode them.
"""

from __future__ import annotations

import pandas as pd

from amber.config import Pillar

__all__ = ["DEFAULT_PILLAR_WEIGHTS", "compute_index", "normalize_indicators"]

DEFAULT_PILLAR_WEIGHTS: dict[Pillar, float] = {
    Pillar.ECONOMY: 1 / 3,
    Pillar.INNOVATION: 1 / 3,
    Pillar.HUMAN_DEVELOPMENT: 1 / 3,
}
"""Equal weighting. A starting position for the UI sliders, not a claim."""


def normalize_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """Rescale each indicator to a comparable 0-1 range.

    Args:
        panel: Tidy panel from :mod:`amber.cleaning`.

    Returns:
        The panel with a normalized value column.

    Raises:
        NotImplementedError: Always - phase 2.
    """
    # TODO(phase-2): min-max against a fixed reference range per indicator, so
    #   that adding a country later cannot shift historical index values.
    #   Invert negative-direction series (under-5 mortality, poverty headcount).
    raise NotImplementedError("The index is phase 2; the data layer comes first.")


def compute_index(
    panel: pd.DataFrame,
    weights: dict[Pillar, float] | None = None,
) -> pd.DataFrame:
    """Aggregate normalized indicators into the combined index.

    Args:
        panel: Normalized panel from :func:`normalize_indicators`.
        weights: Pillar weights. Defaults to :data:`DEFAULT_PILLAR_WEIGHTS`.

    Returns:
        Index and pillar scores by country and year.

    Raises:
        NotImplementedError: Always - phase 2.
    """
    # TODO(phase-2): weighted geometric mean across pillars; decide and document
    #   how a pillar with a missing indicator is handled (drop vs. penalise).
    raise NotImplementedError("The index is phase 2; the data layer comes first.")
