"""Turn raw ingestion output into the tidy country-year panel the models read.

Three products come out of this module:

* :func:`build_panel` - the tidy long panel. This *enriches* ingestion output by
  attaching each series' pillar and a ``pre_2011`` flag. Missing values stay NaN;
  nothing is silently filled.
* :func:`interpolate_panel` - a separate, clearly-labelled interpolated copy.
  Linear within each country-indicator series and strictly **interior**: a gap
  between two real observations is bridged, but nothing is extrapolated past the
  last real observation or back before the first.
* :func:`build_coverage_report` - non-null counts per country x indicator, which
  is how "dark" series surface. Several Myanmar series stop reporting around the
  coup; that has to be visible rather than inferred from a chart later.

The ``pre_2011`` flag exists because military-era statistics are not reliable
enough to calibrate a synthetic control against. The rows are kept - dropping
data at the cleaning stage would hide it - but downstream fitting excludes them.
"""

from __future__ import annotations

import logging

import pandas as pd

from amber import config

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate_ingestion_schema(raw: pd.DataFrame) -> None:
    """Check that a frame carries the columns cleaning expects.

    Args:
        raw: Candidate ingestion output.

    Raises:
        ValueError: If any required column is absent.
    """
    missing = set(config.INGESTION_COLUMNS) - set(raw.columns)
    if missing:
        msg = f"Ingestion output is missing columns: {sorted(missing)}"
        raise ValueError(msg)


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #


def build_panel(raw: pd.DataFrame) -> pd.DataFrame:
    """Build the tidy long panel from ingestion output.

    Enrichment only: one row in, one row out. Missing values are preserved as
    NaN so that gaps remain explicit - :func:`interpolate_panel` produces the
    filled variant as a separate artifact.

    Args:
        raw: Ingestion output with :data:`~amber.config.INGESTION_COLUMNS`.

    Returns:
        A frame with :data:`~amber.config.PANEL_COLUMNS`, sorted by indicator,
        country and year.

    Raises:
        ValueError: If the input schema is wrong, or carries an indicator that
            is not configured (and therefore has no pillar).
    """
    validate_ingestion_schema(raw)

    panel = raw.copy()
    panel[config.COL_YEAR] = panel[config.COL_YEAR].astype(int)
    panel[config.COL_VALUE] = pd.to_numeric(panel[config.COL_VALUE], errors="coerce")

    unknown = sorted(set(panel[config.COL_INDICATOR_ID]) - set(config.PILLAR_BY_INDICATOR))
    if unknown:
        msg = f"Indicators are not configured, so they have no pillar: {unknown}"
        raise ValueError(msg)

    panel[config.COL_PILLAR] = (
        panel[config.COL_INDICATOR_ID].map(config.PILLAR_BY_INDICATOR).astype(str)
    )
    panel[config.COL_PRE_2011] = panel[config.COL_YEAR] < config.MODELING_WINDOW_START

    duplicates = panel.duplicated(subset=list(config.PANEL_SORT_KEYS)).sum()
    if duplicates:
        logger.warning("Dropping %d duplicate country-indicator-year rows", duplicates)
        panel = panel.drop_duplicates(subset=list(config.PANEL_SORT_KEYS), keep="first")

    panel = panel.sort_values(list(config.PANEL_SORT_KEYS)).reset_index(drop=True)

    flagged = int(panel[config.COL_PRE_2011].sum())
    logger.info(
        "Built panel: %d rows, %d flagged pre-%d and excluded from calibration",
        len(panel),
        flagged,
        config.MODELING_WINDOW_START,
    )
    return panel[list(config.PANEL_COLUMNS)]


# --------------------------------------------------------------------------- #
# Interpolation
# --------------------------------------------------------------------------- #


def interpolate_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Fill interior gaps within each country-indicator series.

    Interpolation is linear in *year* (not in row position, which would distort
    a series whose year rows are unevenly present) and uses
    ``limit_area="inside"``, which is what keeps this honest: values between two
    real observations are bridged, while anything past the last real observation
    or before the first stays NaN. A series that goes dark is not quietly
    extended to the end of the window.

    Args:
        panel: Output of :func:`build_panel`.

    Returns:
        The panel with interior gaps filled, plus a boolean ``imputed`` column
        marking every cell this function wrote.
    """
    frame = panel.sort_values(list(config.PANEL_SORT_KEYS)).reset_index(drop=True)
    was_missing = frame[config.COL_VALUE].isna()

    # transform() returns values in the input frame's row order, and the frame is
    # already sorted by year within each group, so positions line up.
    filled = (
        frame.set_index(config.COL_YEAR)
        .groupby(
            [config.COL_COUNTRY_ISO3, config.COL_INDICATOR_ID],
            sort=False,
        )[config.COL_VALUE]
        .transform(lambda series: series.interpolate(method="index", limit_area="inside"))
    )

    frame[config.COL_VALUE] = filled.to_numpy()
    frame[config.COL_IMPUTED] = was_missing & frame[config.COL_VALUE].notna()

    n_imputed = int(frame[config.COL_IMPUTED].sum())
    n_still_missing = int(frame[config.COL_VALUE].isna().sum())
    logger.info(
        "Interpolated %d interior gaps; %d values remain missing (no extrapolation)",
        n_imputed,
        n_still_missing,
    )
    return frame


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def build_coverage_report(panel: pd.DataFrame) -> pd.DataFrame:
    """Summarize how complete each country-indicator series is.

    A series is flagged ``is_dark`` when it has no observation at or after the
    treatment year - the pattern where reporting stops around the coup. Those
    series need a documented proxy before they can carry any weight downstream.

    Args:
        panel: Output of :func:`build_panel`.

    Returns:
        One row per country x indicator, with observation counts, the observed
        year range, pre/post-treatment counts and the ``is_dark`` flag.
    """
    grouped = panel.groupby(
        [
            config.COL_COUNTRY_ISO3,
            config.COL_COUNTRY_NAME,
            config.COL_INDICATOR_ID,
            config.COL_INDICATOR_NAME,
            config.COL_PILLAR,
        ],
        dropna=False,
        sort=True,
    )

    post_treatment = panel[config.COL_YEAR] >= config.TREATMENT_YEAR
    observed = panel[config.COL_VALUE].notna()

    report = grouped.apply(
        lambda group: pd.Series(
            {
                "n_years": len(group),
                "n_observed": int(group[config.COL_VALUE].notna().sum()),
                "n_missing": int(group[config.COL_VALUE].isna().sum()),
                "first_year_observed": _observed_year(group, "min"),
                "last_year_observed": _observed_year(group, "max"),
            }
        ),
        include_groups=False,
    ).reset_index()

    # Counts either side of the treatment point, computed on the full frame so
    # the windows stay defined in one place.
    windows = (
        panel.assign(_observed=observed, _post=post_treatment)
        .groupby(
            [config.COL_COUNTRY_ISO3, config.COL_INDICATOR_ID],
            sort=False,
        )
        .apply(
            lambda group: pd.Series(
                {
                    "n_observed_pre_treatment": int((group["_observed"] & ~group["_post"]).sum()),
                    "n_observed_post_treatment": int((group["_observed"] & group["_post"]).sum()),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )

    report = report.merge(
        windows, on=[config.COL_COUNTRY_ISO3, config.COL_INDICATOR_ID], how="left"
    )

    report["coverage"] = (report["n_observed"] / report["n_years"]).round(3)
    report["is_dark"] = report["n_observed_post_treatment"] == 0

    n_dark = int(report["is_dark"].sum())
    if n_dark:
        logger.warning(
            "%d series have no observation from %d onward and are flagged dark",
            n_dark,
            config.TREATMENT_YEAR,
        )

    return report.sort_values([config.COL_COUNTRY_ISO3, config.COL_INDICATOR_ID]).reset_index(
        drop=True
    )


def _observed_year(group: pd.DataFrame, how: str) -> float:
    """Return the first or last year with a real observation, else NaN.

    Args:
        group: Rows for one country-indicator series.
        how: Either ``"min"`` or ``"max"``.

    Returns:
        The year as a float (NaN-able), since a fully empty series has neither.
    """
    years = group.loc[group[config.COL_VALUE].notna(), config.COL_YEAR]
    if years.empty:
        return float("nan")
    return float(years.min() if how == "min" else years.max())
