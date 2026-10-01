"""Orchestrate the historical layer: discover -> fetch -> flag -> tables + charts.

Phase 7 end to end. A descriptive reconstruction back to
:data:`~amber.config.HISTORICAL_START` plus one assumption-based divergence
scenario, kept apart from everything else: it reads its own World Bank pulls,
writes its own tables, and nothing in phases 1-6 reads them. The combined index
stays 2011+, and the synthetic control stays the only counterfactual estimate.

Tables written (csv + parquet):

* ``historical_coverage`` - one row per candidate series: whether it extends
  back, and why (non-zero pre-2000 observations, or a ruler exclusion).
* ``historical`` - ``[country_iso3, year, indicator_id, value, source,
  reliability]`` for the series that extend, plus any pre-1960 Maddison rows.
* ``historical_divergence`` - the divergence paths, one row per scenario-year.
* ``historical_divergence_metrics`` - anchor, comparator, latest-year ratio
  and gap, and ``scenario_illustrative`` (always true).
* ``historical_divergence_sensitivity`` - the same metrics with every scenario
  re-anchored at each :data:`~amber.config.DIVERGENCE_SENSITIVITY_ANCHORS` year.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from amber import config, figures, ingestion
from amber.config import CoverageStatus, DivergenceScenario, HistoricalSource, Reliability
from amber.ingestion import IndicatorSource
from amber.modeling import divergence as dv
from amber.pipeline import configure_logging, write_table

logger = logging.getLogger(__name__)

DEFAULT_PANEL = config.PROCESSED_DATA_DIR / f"{config.PANEL_STEM}.csv"

COL_NAME = config.COL_INDICATOR_NAME
COL_STATUS = "status"
COL_N_OBSERVED = "n_observed_before"
COL_N_ZERO = "n_zero_before"
COL_FIRST_YEAR = "first_year"
COL_REASON = "reason"
COL_ILLUSTRATIVE = "scenario_illustrative"


@dataclass(frozen=True, slots=True)
class HistoricalResult:
    """What a historical-layer run produced.

    Attributes:
        coverage: The coverage-discovery report.
        historical: The tidy historical table.
        divergences: Scenario name -> computed divergence.
        tables: Stem -> table, as written.
        written: Every table file written.
        figures: Every chart written.
    """

    coverage: pd.DataFrame
    historical: pd.DataFrame
    divergences: dict[str, dv.DivergenceResult]
    tables: dict[str, pd.DataFrame]
    written: tuple[Path, ...]
    figures: tuple[Path, ...]


# --------------------------------------------------------------------------- #
# Coverage discovery
# --------------------------------------------------------------------------- #


def candidate_series(
    ruler_excluded: Mapping[str, str] = config.HISTORICAL_RULER_EXCLUDED,
) -> dict[str, str]:
    """Every series checked for long coverage, as id -> name, ruler exclusions removed.

    The panel's indicators plus :data:`~amber.config.HISTORICAL_EXTRA_CANDIDATES`.
    """
    candidates = {ind.id: ind.name for ind in config.INDICATORS}
    candidates.update(config.HISTORICAL_EXTRA_CANDIDATES)
    return {i: name for i, name in candidates.items() if i not in ruler_excluded}


def fetch_candidates(
    candidates: Mapping[str, str],
    *,
    source: IndicatorSource | None = None,
    countries: Sequence[str] = config.HISTORICAL_COUNTRY_CODES,
    year_start: int = config.HISTORICAL_START,
    year_end: int = config.HISTORICAL_END,
    cache_dir: Path = config.RAW_DATA_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Pull every candidate from the World Bank back to the historical start.

    Raises:
        ValueError: If a current-US$ or otherwise ruler-excluded series is
            asked for - the historical layer never fetches one.
    """
    forbidden = sorted(
        i
        for i in candidates
        if i in config.HISTORICAL_RULER_EXCLUDED or i.endswith(config.CURRENT_USD_SUFFIX)
    )
    if forbidden:
        msg = f"Ruler-excluded series cannot enter the historical layer: {forbidden}"
        raise ValueError(msg)

    source = source or ingestion.WorldBankSource()
    frames = [
        ingestion.fetch_series(
            indicator_id,
            name,
            source=source,
            countries=countries,
            country_names=config.HISTORICAL_COUNTRIES,
            year_start=year_start,
            year_end=year_end,
            cache_dir=cache_dir,
            refresh=refresh,
        )
        for indicator_id, name in candidates.items()
    ]
    return pd.concat(frames, ignore_index=True)


def discover_coverage(
    raw: pd.DataFrame,
    candidates: Mapping[str, str],
    *,
    treated: str = config.TREATED_COUNTRY,
    before: int = config.HISTORICAL_COVERAGE_BEFORE,
    min_observations: int = config.HISTORICAL_MIN_OBSERVATIONS,
    ruler_excluded: Mapping[str, str] = config.HISTORICAL_RULER_EXCLUDED,
) -> pd.DataFrame:
    """Decide, from the data, which series extend back.

    A series extends when the treated country has at least
    ``min_observations`` non-zero observations before ``before``. Zeros are
    counted separately and never qualify (see
    :data:`~amber.config.HISTORICAL_MIN_OBSERVATIONS`). Ruler-excluded series are
    listed with their reason and never counted.

    Args:
        raw: Ingestion-schema pulls of the candidates.
        candidates: Id -> name of every series checked.
        treated: Whose coverage decides.
        before: Count observations before this year.
        min_observations: Threshold for extending.
        ruler_excluded: Id -> reason for the series excluded outright.

    Returns:
        One row per series (candidates, then exclusions) with the decision.
    """
    rows: list[dict[str, object]] = []
    for indicator_id, name in candidates.items():
        series = raw[
            (raw[config.COL_INDICATOR_ID] == indicator_id)
            & (raw[config.COL_COUNTRY_ISO3] == treated)
            & (raw[config.COL_YEAR] < before)
        ].dropna(subset=[config.COL_VALUE])
        nonzero = series[series[config.COL_VALUE] != 0]
        n_observed, n_zero = len(nonzero), len(series) - len(nonzero)
        extends = n_observed >= min_observations
        reason = (
            f"{n_observed} non-zero {treated} observations before {before} "
            f"(needs {min_observations})"
        )
        if n_zero:
            reason += f"; {n_zero} zeros not counted"
        rows.append(
            {
                config.COL_INDICATOR_ID: indicator_id,
                COL_NAME: name,
                COL_STATUS: str(CoverageStatus.EXTENDS if extends else CoverageStatus.INSUFFICIENT),
                COL_N_OBSERVED: n_observed,
                COL_N_ZERO: n_zero,
                COL_FIRST_YEAR: int(nonzero[config.COL_YEAR].min()) if n_observed else np.nan,
                COL_REASON: reason,
            }
        )
    for indicator_id, reason in ruler_excluded.items():
        rows.append(
            {
                config.COL_INDICATOR_ID: indicator_id,
                COL_NAME: config.INDICATORS_BY_ID[indicator_id].name
                if indicator_id in config.INDICATORS_BY_ID
                else indicator_id,
                COL_STATUS: str(CoverageStatus.EXCLUDED_RULER),
                COL_N_OBSERVED: np.nan,
                COL_N_ZERO: np.nan,
                COL_FIRST_YEAR: np.nan,
                COL_REASON: reason,
            }
        )

    report = pd.DataFrame(rows)
    for status in CoverageStatus:
        ids = report.loc[report[COL_STATUS] == str(status), config.COL_INDICATOR_ID].tolist()
        logger.info("Coverage %s (%d): %s", status, len(ids), ", ".join(ids) or "none")
    return report


def extended_series(coverage: pd.DataFrame) -> list[str]:
    """The ids coverage discovery says extend, in report order."""
    extends = coverage[COL_STATUS] == str(CoverageStatus.EXTENDS)
    return coverage.loc[extends, config.COL_INDICATOR_ID].tolist()


# --------------------------------------------------------------------------- #
# The historical table
# --------------------------------------------------------------------------- #


def assign_reliability(
    frame: pd.DataFrame, rule: Mapping[str, int] = config.RELIABILITY_LOW_BEFORE
) -> pd.Series:
    """``low`` for a country-year before its cutoff in ``rule``, else ``standard``."""
    cutoff = frame[config.COL_COUNTRY_ISO3].map(dict(rule))
    low = cutoff.notna() & (frame[config.COL_YEAR] < cutoff)
    return pd.Series(
        np.where(low, str(Reliability.LOW), str(Reliability.STANDARD)), index=frame.index
    )


def build_historical(raw: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    """The WDI part of ``historical.csv``: the series that extend, flagged.

    Missing years stay as NaN rows, as in the panel - nothing is interpolated in
    a descriptive layer, and nothing is silently dropped. Current-US$ rows are
    refused even if a caller slips them in.

    Args:
        raw: Ingestion-schema pulls.
        coverage: Output of :func:`discover_coverage`.

    Returns:
        A frame in :data:`~amber.config.HISTORICAL_COLUMNS`.
    """
    keep = set(extended_series(coverage))
    ruler = raw[config.COL_INDICATOR_ID].isin(list(config.HISTORICAL_RULER_EXCLUDED)) | raw[
        config.COL_INDICATOR_ID
    ].str.endswith(config.CURRENT_USD_SUFFIX)
    if ruler.any():
        dropped = sorted(raw.loc[ruler, config.COL_INDICATOR_ID].unique())
        logger.warning("Refusing current-US$ / ruler-excluded rows: %s", dropped)
    frame = raw[raw[config.COL_INDICATOR_ID].isin(list(keep)) & ~ruler].copy()
    frame[config.COL_SOURCE] = str(HistoricalSource.WB_CONSTANT)
    frame[config.COL_RELIABILITY] = assign_reliability(frame)
    return _tidy(frame)


def load_maddison(
    path: Path = config.MADDISON_PATH,
    *,
    country: str = config.TREATED_COUNTRY,
    last_year: int = config.MADDISON_LAST_YEAR,
) -> pd.DataFrame:
    """The optional pre-1960 Maddison rows, on their own ruler.

    Reads the user's export of MPD 2023 (see ``data/external/README.md``). Rows
    get their own indicator id and the ``maddison`` source tag, and only years up
    to ``last_year`` are kept, so they can never overlap - let alone merge with -
    the WDI constant-US$ spine.

    Args:
        path: The CSV export.
        country: ISO3 code to keep.
        last_year: Last year kept.

    Returns:
        A frame in :data:`~amber.config.HISTORICAL_COLUMNS`, empty if the file is
        absent.

    Raises:
        ValueError: If the file lacks the MPD columns.
    """
    if not path.exists():
        logger.info(
            "No Maddison export at %s - the pre-%d series is skipped (see data/external/README.md)",
            path,
            last_year + 1,
        )
        return pd.DataFrame(columns=list(config.HISTORICAL_COLUMNS))

    raw = pd.read_csv(path)
    code, year, gdppc = config.MADDISON_COLUMNS
    missing = sorted({code, year, gdppc} - set(raw.columns))
    if missing:
        msg = f"{path.name} lacks the MPD columns {missing} (expected {config.MADDISON_COLUMNS})"
        raise ValueError(msg)

    rows = raw[raw[code] == country].dropna(subset=[gdppc])
    later = int((rows[year] > last_year).sum())
    rows = rows[rows[year] <= last_year]
    frame = pd.DataFrame(
        {
            config.COL_COUNTRY_ISO3: country,
            config.COL_YEAR: rows[year].astype(int).to_numpy(),
            config.COL_INDICATOR_ID: config.MADDISON_INDICATOR,
            config.COL_VALUE: pd.to_numeric(rows[gdppc], errors="coerce").to_numpy(),
            config.COL_SOURCE: str(HistoricalSource.MADDISON),
        }
    )
    frame[config.COL_RELIABILITY] = assign_reliability(frame)
    logger.info(
        "Maddison: %d %s rows to %d kept; %d later rows left out (WDI is the spine from %d)",
        len(frame),
        country,
        last_year,
        later,
        last_year + 1,
    )
    return _tidy(frame)


def combine(wdi: pd.DataFrame, maddison: pd.DataFrame) -> pd.DataFrame:
    """Stack the two rulers in one tidy table without merging them.

    Raises:
        ValueError: If a Maddison row claims a WDI indicator id, or a series
            would carry two sources.
    """
    if (maddison[config.COL_INDICATOR_ID] != config.MADDISON_INDICATOR).any():
        msg = "Maddison rows must keep their own indicator id"
        raise ValueError(msg)
    frames = [f for f in (wdi, maddison) if not f.empty]
    table = pd.concat(frames, ignore_index=True) if frames else wdi
    sources = table.groupby(config.COL_INDICATOR_ID)[config.COL_SOURCE].nunique()
    if (sources > 1).any():
        msg = f"Series mixing rulers: {sorted(sources[sources > 1].index)}"
        raise ValueError(msg)
    return _tidy(table)


def _tidy(frame: pd.DataFrame) -> pd.DataFrame:
    columns = list(config.HISTORICAL_COLUMNS)
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame = frame.astype({config.COL_YEAR: int, config.COL_VALUE: float})
    order = [config.COL_INDICATOR_ID, config.COL_COUNTRY_ISO3, config.COL_YEAR]
    return frame.sort_values(order)[columns].reset_index(drop=True)


def check_vintage(historical: pd.DataFrame, panel_path: Path = DEFAULT_PANEL) -> float | None:
    """Compare the overlap with the 2011+ panel's own pull, and log any drift.

    The two pulls are separate cache entries, so a later historical pull can
    carry a newer WDI vintage. They are never spliced, but a difference is worth
    knowing - ``make refresh`` and a historical ``--refresh`` realign them.

    Returns:
        The largest relative difference over the overlap, or ``None`` without
        a panel to compare.
    """
    if not panel_path.exists():
        return None
    panel = pd.read_csv(panel_path)
    keys = [config.COL_INDICATOR_ID, config.COL_COUNTRY_ISO3, config.COL_YEAR]
    merged = historical.merge(panel[[*keys, config.COL_VALUE]], on=keys, suffixes=("", "_panel"))
    merged = merged.dropna(subset=[config.COL_VALUE, f"{config.COL_VALUE}_panel"])
    if merged.empty:
        return None
    reference = merged[f"{config.COL_VALUE}_panel"]
    difference = (merged[config.COL_VALUE] - reference).abs()
    drift = float((difference / reference.abs().where(reference != 0)).max())
    if drift > 1e-9:
        logger.warning(
            "Historical pull differs from the panel's by up to %.2f%% over %d shared cells "
            "(a newer WDI vintage?); refresh both to realign",
            100 * drift,
            len(merged),
        )
    else:
        logger.info("Historical pull matches the panel over %d shared cells", len(merged))
    return drift


# --------------------------------------------------------------------------- #
# Divergence scenarios
# --------------------------------------------------------------------------- #


def run_divergence(
    historical: pd.DataFrame,
    scenarios: Sequence[DivergenceScenario] = config.DIVERGENCE_SCENARIOS,
    *,
    quiet: bool = False,
) -> dict[str, dv.DivergenceResult]:
    """Compute every divergence scenario on the WDI constant-US$ spine only."""
    gdp = historical[
        (historical[config.COL_INDICATOR_ID] == config.GDP_PC_INDICATOR)
        & (historical[config.COL_SOURCE] == str(HistoricalSource.WB_CONSTANT))
    ]
    if gdp.empty:
        msg = f"{config.GDP_PC_INDICATOR} is not in the historical table - did it fail coverage?"
        raise ValueError(msg)
    levels = gdp.pivot(
        index=config.COL_YEAR, columns=config.COL_COUNTRY_ISO3, values=config.COL_VALUE
    )
    actual = levels[config.TREATED_COUNTRY]
    results = {}
    for scenario in scenarios:
        comparator = config.DIVERGENCE_COMPARATORS[scenario.comparator]
        result = dv.divergence_path(actual, levels, scenario, comparator)
        latest = result.latest
        logger.log(
            logging.DEBUG if quiet else logging.INFO,
            "Divergence %s (illustrative): %s-tracking path at %.1fx actual in %d",
            scenario.name,
            comparator.label,
            latest[dv.COL_RATIO],
            latest[config.COL_YEAR],
        )
        results[scenario.name] = result
    return results


def divergence_table(results: Mapping[str, dv.DivergenceResult]) -> pd.DataFrame:
    """Every path, long, with the reliability of Myanmar's actual value."""
    frames = []
    for name, result in results.items():
        path = result.path.copy()
        path.insert(0, "anchor_year", result.scenario.anchor_year)
        path.insert(0, "comparator", result.scenario.comparator)
        path.insert(0, config.COL_SCENARIO, name)
        path[config.COL_RELIABILITY] = assign_reliability(
            path.assign(**{config.COL_COUNTRY_ISO3: config.TREATED_COUNTRY})
        )
        path[COL_ILLUSTRATIVE] = result.illustrative
        frames.append(path)
    return pd.concat(frames, ignore_index=True)


def divergence_metrics(results: Mapping[str, dv.DivergenceResult]) -> pd.DataFrame:
    """One row per scenario: anchor, comparator, latest-year ratio and gap.

    No p-value and no credibility column, by design: nothing was fitted.
    """
    rows = []
    for name, result in results.items():
        latest = result.latest
        span = int(latest[config.COL_YEAR]) - result.scenario.anchor_year
        used = result.path[result.path[config.COL_YEAR] > result.scenario.anchor_year]
        rows.append(
            {
                config.COL_SCENARIO: name,
                "comparator": result.scenario.comparator,
                "comparator_label": result.comparator.label,
                "anchor_year": result.scenario.anchor_year,
                "anchor_value": result.anchor_value,
                "latest_year": int(latest[config.COL_YEAR]),
                "actual_latest": float(latest[dv.COL_ACTUAL]),
                "path_latest": float(latest[dv.COL_PATH]),
                "gap_latest": float(latest[config.COL_GAP]),
                "ratio_latest": float(latest[dv.COL_RATIO]),
                "actual_growth_pa": _annualized(result.anchor_value, latest[dv.COL_ACTUAL], span),
                "path_growth_pa": _annualized(result.anchor_value, latest[dv.COL_PATH], span),
                "min_units": int(used[dv.COL_N_UNITS].min()) if not used.empty else 0,
                "default": name == config.DIVERGENCE_DEFAULT_SCENARIO,
                COL_ILLUSTRATIVE: result.illustrative,
            }
        )
    return pd.DataFrame(rows)


def sensitivity_metrics(
    historical: pd.DataFrame,
    scenarios: Sequence[DivergenceScenario] = config.DIVERGENCE_SCENARIOS,
    anchors: Sequence[int] = config.DIVERGENCE_SENSITIVITY_ANCHORS,
) -> pd.DataFrame:
    """Every scenario re-run from each sensitivity anchor (and its own), as metrics rows.

    The anchor decides whether the path ends above or below actual, so it is
    reported across a range rather than chosen once.
    """
    frames = []
    for anchor in sorted({*anchors, *(s.anchor_year for s in scenarios)}):
        moved = [replace(s, anchor_year=anchor) for s in scenarios]
        frames.append(divergence_metrics(run_divergence(historical, moved, quiet=True)))
    table = pd.concat(frames, ignore_index=True)
    defaults = [s.anchor_year for s in scenarios if s.name == config.DIVERGENCE_DEFAULT_SCENARIO]
    table["default"] = table["default"] & table["anchor_year"].isin(defaults)
    return table.sort_values([config.COL_SCENARIO, "anchor_year"]).reset_index(drop=True)


def _annualized(start: float, end: float, years: int) -> float:
    return float((end / start) ** (1 / years) - 1) if years > 0 else float("nan")


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #


def run(
    *,
    source: IndicatorSource | None = None,
    cache_dir: Path = config.RAW_DATA_DIR,
    output_dir: Path = config.PROCESSED_DATA_DIR,
    figures_dir: Path = config.FIGURES_DIR,
    maddison_path: Path = config.MADDISON_PATH,
    panel_path: Path = DEFAULT_PANEL,
    scenarios: Sequence[DivergenceScenario] = config.DIVERGENCE_SCENARIOS,
    countries: Sequence[str] = config.HISTORICAL_COUNTRY_CODES,
    refresh: bool = False,
    render: bool = True,
) -> HistoricalResult:
    """Discover coverage, build the historical table, run the divergence, write and chart.

    Args:
        source: Where to fetch from. Defaults to the World Bank.
        cache_dir: Directory holding cached raw pulls.
        output_dir: Destination for the tables.
        figures_dir: Destination for the charts.
        maddison_path: The optional Maddison export.
        panel_path: The raw 2011+ panel, for the vintage check only.
        scenarios: Divergence scenarios to compute.
        countries: ISO3 codes to fetch.
        refresh: Re-pull from the World Bank instead of the cache.
        render: Skip the charts when false.

    Returns:
        Every table, the divergences and every path written.
    """
    candidates = candidate_series()
    logger.info(
        "Historical layer: %d candidate series x %d countries, %d-%d",
        len(candidates),
        len(countries),
        config.HISTORICAL_START,
        config.HISTORICAL_END,
    )
    raw = fetch_candidates(
        candidates, source=source, countries=countries, cache_dir=cache_dir, refresh=refresh
    )
    coverage = discover_coverage(raw, candidates)
    historical = combine(build_historical(raw, coverage), load_maddison(maddison_path))
    check_vintage(historical, panel_path)

    low = int((historical[config.COL_RELIABILITY] == str(Reliability.LOW)).sum())
    logger.info("Historical table: %d rows, %d flagged low reliability", len(historical), low)

    divergences = run_divergence(historical, scenarios)
    sensitivity = sensitivity_metrics(historical, scenarios)
    tables = {
        config.HISTORICAL_COVERAGE_STEM: coverage,
        config.HISTORICAL_STEM: historical,
        config.HISTORICAL_DIVERGENCE_STEM: divergence_table(divergences),
        config.HISTORICAL_DIVERGENCE_METRICS_STEM: divergence_metrics(divergences),
        config.HISTORICAL_DIVERGENCE_SENSITIVITY_STEM: sensitivity,
    }
    written = tuple(
        path for stem, table in tables.items() for path in write_table(table, stem, output_dir)
    )
    default = divergences.get(config.DIVERGENCE_DEFAULT_SCENARIO)
    if default is None:
        default = next(iter(divergences.values()))
    rendered = (
        figures.render_historical(historical, default, sensitivity, figures_dir) if render else ()
    )

    logger.info(
        "Historical layer complete: %d tables, %d figures (divergence is illustrative only)",
        len(written),
        len(rendered),
    )
    return HistoricalResult(
        coverage=coverage,
        historical=historical,
        divergences=divergences,
        tables=tables,
        written=written,
        figures=rendered,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the historical build."""
    parser = argparse.ArgumentParser(
        prog="amber-build-historical",
        description="Build the 1960+ historical layer and the illustrative divergence scenario.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-pull the long series from the World Bank instead of the raw cache.",
    )
    parser.add_argument(
        "--anchor",
        type=int,
        default=None,
        help=f"Divergence anchor year for every scenario (default {config.HISTORICAL_START}).",
    )
    parser.add_argument(
        "--maddison",
        type=Path,
        default=config.MADDISON_PATH,
        help="Optional Maddison export (default: data/external/maddison_myanmar.csv).",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=config.RAW_DATA_DIR, help="Raw cache directory."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.PROCESSED_DATA_DIR,
        help="Where to write the tables (default: data/processed).",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=config.FIGURES_DIR,
        help="Where to write the charts (default: reports/figures).",
    )
    parser.add_argument("--no-figures", action="store_true", help="Skip rendering the charts.")
    parser.add_argument(
        "--log-level",
        default=config.LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Argument vector, defaulting to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    scenarios = config.DIVERGENCE_SCENARIOS
    if args.anchor is not None:
        scenarios = tuple(
            DivergenceScenario(s.name, s.comparator, args.anchor)
            for s in config.DIVERGENCE_SCENARIOS
        )
    try:
        config._check_historical_config(scenarios=scenarios)
        run(
            cache_dir=args.cache_dir,
            output_dir=args.output_dir,
            figures_dir=args.figures_dir,
            maddison_path=args.maddison,
            scenarios=scenarios,
            refresh=args.refresh,
            render=not args.no_figures,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    return 0
