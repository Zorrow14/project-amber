"""Combined development index - phase 2.

Three steps, all driven by :mod:`amber.config`:

1. **Normalize** each indicator to [0, 1] against fixed per-indicator goalposts
   (:data:`~amber.config.GOALPOSTS`), so scores compare across countries and
   over time on one ruler. Income is logged first
   (:data:`~amber.config.LOG_TRANSFORM`); lower-is-better series are inverted
   (:data:`~amber.config.INDICATOR_POLARITY`). Scores are clipped to
   [:data:`~amber.config.NORMALIZED_FLOOR`, 1].
2. **Pillar sub-index** - geometric mean of the normalized indicators observed
   in each pillar for that country-year.
3. **Combined index** - weighted geometric mean of the three pillars.

Only :data:`~amber.config.INDEX_INDICATORS` enter: the series in
:data:`~amber.config.INDEX_EXCLUDED` stay in the panel as history but no
counterfactual or projection can produce them, and an index that changed
composition between the past and the futures would splice two different
measures into one line.

Why geometric means: an arithmetic mean lets a strong pillar paper over a weak
one, and "strong economy, collapsing health system" should not score like
"moderate at everything". The floor exists for the same reason - without it the
worst country-year on any one indicator scores 0, and a geometric mean with a 0
in it is 0.

Two properties worth knowing before reading the output:

* **Missing is not zero.** A pillar is computed over the indicators actually
  observed, and ``coverage`` records the share that were. When coverage moves,
  the pillar is being computed from a different set of indicators, and part of
  any movement is that change of composition rather than development.
* **Goalposts are fixed, so history is stable.** Adding a country or a data
  vintage cannot move an existing score, and a value outside the historical
  range - a no-coup counterfactual, a 2035 projection - lands on the same ruler
  rather than being squashed into it. Pooled min-max (``method="pooled"``) is
  kept for comparison, but it has neither property.

API exposure of the index is deferred to phase 5 (see :mod:`amber.api.main`).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from amber import config
from amber.config import Normalization, Pillar, Polarity

logger = logging.getLogger(__name__)

__all__ = [
    "compute_index",
    "compute_pillar_indices",
    "normalize_indicators",
    "resolve_weights",
    "seed_goalpost",
    "weighted_geometric_mean",
]

REQUIRED_COLUMNS: tuple[str, ...] = (
    config.COL_INDICATOR_ID,
    config.COL_COUNTRY_ISO3,
    config.COL_COUNTRY_NAME,
    config.COL_YEAR,
    config.COL_VALUE,
    config.COL_PRE_2011,
)

_N_AVAILABLE = "n_available"


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #


def weighted_geometric_mean(
    values: Sequence[float],
    weights: Sequence[float] | None = None,
) -> float:
    """Return exp(sum(w * ln v) / sum(w)).

    Args:
        values: Strictly positive values.
        weights: Non-negative weights, one per value, renormalized internally.
            Defaults to equal weights, giving the plain geometric mean.

    Returns:
        The weighted geometric mean.

    Raises:
        ValueError: If there are no values, a value is not positive, the weights
            do not match the values, or the weights are negative or all zero.
    """
    if not values:
        msg = "Geometric mean of no values is undefined"
        raise ValueError(msg)
    if any(v <= 0 for v in values):
        msg = f"Geometric mean needs strictly positive values, got {list(values)}"
        raise ValueError(msg)

    if weights is None:
        weights = [1.0] * len(values)
    if len(weights) != len(values):
        msg = f"Got {len(weights)} weights for {len(values)} values"
        raise ValueError(msg)
    if any(w < 0 for w in weights) or sum(weights) <= 0:
        msg = f"Weights must be non-negative and not all zero, got {list(weights)}"
        raise ValueError(msg)

    total = sum(weights)
    return math.exp(sum(w * math.log(v) for w, v in zip(weights, values, strict=True)) / total)


def resolve_weights(weights: Mapping[str, float] | None = None) -> dict[Pillar, float]:
    """Validate pillar weights and rescale them to sum to 1.

    Callers may pass any non-negative scale - slider positions, percentages,
    raw counts - and get the same index as the equivalent normalized weights.

    Args:
        weights: Pillar -> weight. Keys may be :class:`~amber.config.Pillar`
            members or their string values. Defaults to
            :data:`~amber.config.DEFAULT_PILLAR_WEIGHTS`.

    Returns:
        Pillar -> weight, summing to 1.

    Raises:
        ValueError: If a pillar is missing or unknown, or a weight is negative,
            non-finite, or all weights are zero.
    """
    if weights is None:
        weights = config.DEFAULT_PILLAR_WEIGHTS

    try:
        resolved = {Pillar(key): float(value) for key, value in weights.items()}
    except ValueError as exc:
        msg = f"Unknown pillar in weights: {sorted(map(str, weights))}"
        raise ValueError(msg) from exc

    missing = set(Pillar) - set(resolved)
    if missing:
        msg = f"Weights must cover every pillar; missing {sorted(str(p) for p in missing)}"
        raise ValueError(msg)
    if any(not math.isfinite(w) or w < 0 for w in resolved.values()):
        msg = f"Weights must be finite and non-negative, got {resolved}"
        raise ValueError(msg)

    total = sum(resolved.values())
    if total <= 0:
        msg = "At least one pillar weight must be positive"
        raise ValueError(msg)

    return {pillar: weight / total for pillar, weight in resolved.items()}


def _pillar_sizes() -> dict[str, int]:
    """Number of index indicators per pillar - the coverage denominator."""
    sizes: dict[str, int] = {}
    for indicator_id in config.INDEX_INDICATORS:
        pillar = str(config.PILLAR_BY_INDICATOR[indicator_id])
        sizes[pillar] = sizes.get(pillar, 0) + 1
    return sizes


# --------------------------------------------------------------------------- #
# Goalposts
# --------------------------------------------------------------------------- #


def seed_goalpost(
    values: Sequence[float],
    *,
    padding: float = config.GOALPOST_PADDING,
    log: bool = False,
    domain: tuple[float | None, float | None] = (None, None),
) -> tuple[float, float]:
    """Derive goalposts for an indicator with no published standard.

    Used once, by hand, to seed :data:`~amber.config.GOALPOSTS` - never at
    runtime, which would bring back the drift fixed goalposts exist to remove.
    Kept here so a seeded bound can be re-derived and audited.

    Args:
        values: Observed values across the modeling window.
        padding: Share of the observed span added on each side.
        log: Pad in log space, for log-transformed indicators.
        domain: Natural limits to clamp to, e.g. ``(0, 100)`` for a share.

    Returns:
        ``(low, high)`` in raw units, before any rounding.

    Raises:
        ValueError: If there are no values, or log is requested for
            non-positive values.
    """
    observed = np.asarray(values, dtype=float)
    observed = observed[~np.isnan(observed)]
    if observed.size == 0:
        msg = "Cannot seed a goalpost from no observations"
        raise ValueError(msg)
    if log and (observed <= 0).any():
        msg = "Cannot pad in log space with non-positive values"
        raise ValueError(msg)

    scaled = np.log(observed) if log else observed
    span = scaled.max() - scaled.min()
    low, high = scaled.min() - padding * span, scaled.max() + padding * span
    if log:
        low, high = math.exp(low), math.exp(high)

    floor, ceiling = domain
    low = low if floor is None else max(low, floor)
    high = high if ceiling is None else min(high, ceiling)
    return float(low), float(high)


def _to_scale(values: pd.Series, logged: pd.Series) -> pd.Series:
    """Take logs where the indicator is log-transformed, leave the rest as-is."""
    values = values.astype(float)
    # where() masks non-logged rows before the log, so negatives are never logged.
    return values.where(~logged, np.log(values.where(logged)))


# --------------------------------------------------------------------------- #
# Step 1: normalize
# --------------------------------------------------------------------------- #


def normalize_indicators(
    panel: pd.DataFrame,
    method: Normalization | str | None = None,
) -> pd.DataFrame:
    """Rescale every index indicator to [floor, 1].

    Only index indicators (:data:`~amber.config.INDEX_INDICATORS`) in
    modeling-window rows (``pre_2011`` false) with a real value enter.
    Missing values are dropped here rather than scored, which is how "missing"
    stays distinct from "worst".

    Args:
        panel: Tidy panel, normally ``panel_interpolated``.
        method: ``goalposts`` (default) scales against the fixed bounds in
            :data:`~amber.config.GOALPOSTS`; ``pooled`` scales against this
            panel's own min and max.

    Returns:
        One row per observed country-year-indicator with ``pillar`` and
        ``normalized`` columns added.

    Raises:
        ValueError: If columns are missing, an indicator is not configured, a
            log-transformed indicator has a non-positive value, or the method
            is unknown.
    """
    method = Normalization(method or config.DEFAULT_NORMALIZATION)

    missing_cols = set(REQUIRED_COLUMNS) - set(panel.columns)
    if missing_cols:
        msg = f"Panel is missing columns: {sorted(missing_cols)}"
        raise ValueError(msg)

    unknown = sorted(set(panel[config.COL_INDICATOR_ID]) - set(config.INDICATOR_POLARITY))
    if unknown:
        msg = f"Indicators have no configured polarity: {unknown}"
        raise ValueError(msg)

    indexed = panel[panel[config.COL_INDICATOR_ID].isin(config.INDEX_INDICATORS)]
    window = indexed[~indexed[config.COL_PRE_2011].astype(bool)]
    frame = window.dropna(subset=[config.COL_VALUE]).copy()
    logger.info(
        "Normalizing %d observations on %s (%d rows of non-index indicators, %d pre-%d "
        "rows and %d missing values excluded)",
        len(frame),
        method,
        len(panel) - len(indexed),
        len(indexed) - len(window),
        config.MODELING_WINDOW_START,
        len(window) - len(frame),
    )

    ids = frame[config.COL_INDICATOR_ID]
    raw = frame[config.COL_VALUE].astype(float)
    logged = ids.isin(config.LOG_TRANSFORM)
    non_positive = logged & (raw <= 0)
    if non_positive.any():
        bad = sorted(set(ids[non_positive]))
        msg = f"Cannot log-transform non-positive values in {bad}"
        raise ValueError(msg)

    scaled = _to_scale(raw, logged)

    if method is Normalization.GOALPOSTS:
        low_raw = ids.map({k: g.low for k, g in config.GOALPOSTS.items()})
        high_raw = ids.map({k: g.high for k, g in config.GOALPOSTS.items()})
        low, high = _to_scale(low_raw, logged), _to_scale(high_raw, logged)

        outside = (raw < low_raw) | (raw > high_raw)
        if outside.any():
            # Clipped to the scale's end, as the HDI does. Worth hearing about:
            # it means a goalpost may need widening.
            logger.warning(
                "%d observations fall outside their goalposts and are clipped: %s",
                int(outside.sum()),
                sorted(set(ids[outside])),
            )
    else:
        low = scaled.groupby(ids).transform("min")
        high = scaled.groupby(ids).transform("max")

    span = high - low
    flat = sorted(set(ids[span == 0]))
    if flat:
        # Only reachable on the pooled path. No spread means no information;
        # scoring it would add a constant to every pillar it touches, so it is
        # treated as unavailable - and so counts as absent in coverage.
        logger.warning("Dropping indicators with no spread in the window: %s", flat)

    negative = ids.map(config.INDICATOR_POLARITY) == Polarity.NEGATIVE
    upward = (scaled - low) / span
    score = upward.where(~negative, 1 - upward)

    frame[config.COL_PILLAR] = ids.map(config.PILLAR_BY_INDICATOR).astype(str)
    frame[config.COL_NORMALIZED] = score.clip(config.NORMALIZED_FLOOR, config.NORMALIZED_CEILING)

    return frame[span > 0][
        [
            config.COL_INDICATOR_ID,
            config.COL_PILLAR,
            config.COL_COUNTRY_ISO3,
            config.COL_COUNTRY_NAME,
            config.COL_YEAR,
            config.COL_VALUE,
            config.COL_NORMALIZED,
        ]
    ].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Step 2: pillars
# --------------------------------------------------------------------------- #


def compute_pillar_indices(normalized: pd.DataFrame) -> pd.DataFrame:
    """Geometric mean of the observed indicators in each pillar.

    Args:
        normalized: Output of :func:`normalize_indicators`.

    Returns:
        One row per country-year-pillar in :data:`~amber.config.INDEX_COLUMNS`
        order, plus ``n_available``. A pillar with no observed indicators in a
        country-year gets no row.
    """
    keys = [config.COL_COUNTRY_ISO3, config.COL_COUNTRY_NAME, config.COL_YEAR, config.COL_PILLAR]

    pillars = (
        normalized.assign(_log=np.log(normalized[config.COL_NORMALIZED]))
        .groupby(keys, sort=True)
        .agg(_mean_log=("_log", "mean"), n_available=("_log", "size"))
        .reset_index()
    )

    pillars[config.COL_VALUE] = np.exp(pillars["_mean_log"])
    pillars[config.COL_COVERAGE] = pillars[_N_AVAILABLE] / pillars[config.COL_PILLAR].map(
        _pillar_sizes()
    )

    return pillars.rename(columns={config.COL_PILLAR: config.COL_SERIES})[
        [*config.INDEX_COLUMNS, _N_AVAILABLE]
    ]


# --------------------------------------------------------------------------- #
# Step 3: combined
# --------------------------------------------------------------------------- #


def _combine(pillars: pd.DataFrame, weights: dict[Pillar, float]) -> pd.DataFrame:
    """Weighted geometric mean across pillars.

    A country-year gets a combined score only if every pillar with a positive
    weight is present. Averaging over whichever pillars happen to exist would
    let a strong pillar stand in for a missing one - the masking the geometric
    mean is there to prevent.

    Coverage counts only the indicators in positively-weighted pillars. A
    zero-weighted pillar is out of the score, so its gaps must not drag the
    reported coverage down either.
    """
    keys = [config.COL_COUNTRY_ISO3, config.COL_COUNTRY_NAME, config.COL_YEAR]
    required = [str(p) for p, w in weights.items() if w > 0]

    log_values = pillars.pivot_table(
        index=keys, columns=config.COL_SERIES, values=config.COL_VALUE, aggfunc="first"
    ).map(np.log)
    weighted_pillars = pillars[pillars[config.COL_SERIES].isin(required)]
    available = weighted_pillars.groupby(keys)[_N_AVAILABLE].sum()
    sizes = _pillar_sizes()
    denominator = sum(sizes[p] for p in required)

    for pillar in required:
        if pillar not in log_values.columns:
            log_values[pillar] = np.nan

    complete = log_values[required].notna().all(axis=1)
    n_incomplete = int((~complete).sum())
    if n_incomplete:
        logger.info(
            "%d country-years lack a weighted pillar and get no combined score", n_incomplete
        )

    weighted = sum(log_values.loc[complete, p] * weights[Pillar(p)] for p in required)
    combined = pd.DataFrame({config.COL_VALUE: np.exp(weighted)})
    combined[config.COL_COVERAGE] = available.reindex(combined.index) / denominator
    combined[config.COL_SERIES] = config.COMBINED_SERIES

    return combined.reset_index()[list(config.INDEX_COLUMNS)]


def compute_index(
    panel: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
    method: Normalization | str | None = None,
) -> pd.DataFrame:
    """Build the pillar sub-indices and the combined development index.

    Args:
        panel: Tidy panel, normally ``panel_interpolated``. Pre-2011 rows are
            excluded here, so the full panel can be passed as-is.
        weights: Pillar weights on any non-negative scale; renormalized to sum
            to 1. Defaults to equal weights.
        method: Normalization - ``goalposts`` (default) or ``pooled``. See
            :func:`normalize_indicators`.

    Returns:
        Tidy rows in :data:`~amber.config.INDEX_COLUMNS`, where ``series`` is a
        pillar name or ``combined``. Every value lies in
        [:data:`~amber.config.NORMALIZED_FLOOR`, 1].
    """
    resolved = resolve_weights(weights)
    logger.info(
        "Computing index with weights %s",
        {str(p): round(w, 3) for p, w in resolved.items()},
    )

    normalized = normalize_indicators(panel, method)
    pillars = compute_pillar_indices(normalized)
    combined = _combine(pillars, resolved)

    index = pd.concat(
        [pillars[list(config.INDEX_COLUMNS)], combined],
        ignore_index=True,
    )
    # Every input is already in [floor, 1], so this only absorbs float error from
    # the exp/log round trip - exp(ln 0.01) is not exactly 0.01.
    index[config.COL_VALUE] = index[config.COL_VALUE].clip(
        config.NORMALIZED_FLOOR, config.NORMALIZED_CEILING
    )

    series_order = {name: i for i, name in enumerate(config.INDEX_SERIES)}
    index = index.sort_values(
        [config.COL_SERIES, config.COL_COUNTRY_ISO3, config.COL_YEAR],
        key=lambda col: col.map(series_order) if col.name == config.COL_SERIES else col,
    ).reset_index(drop=True)

    partial = int((index[config.COL_COVERAGE] < 1).sum())
    logger.info(
        "Index built: %d rows, %d computed from partial indicator coverage",
        len(index),
        partial,
    )
    return index
