"""Orchestrate the data layer: fetch -> clean -> write.

This is the whole of Phase 1. Running it takes the project from nothing to the
tidy country-year panel every later phase reads, with no manual steps in
between - re-running it after a World Bank data release is the only thing needed
to refresh the analysis.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from amber import cleaning, config, ingestion
from amber.config import Indicator
from amber.ingestion import IndicatorSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """What a pipeline run produced.

    Attributes:
        panel: Tidy long panel, missing values left as NaN.
        panel_interpolated: The same panel with interior gaps bridged.
        coverage: One row per country x indicator with observation counts.
        written: Every file written, in write order.
    """

    panel: pd.DataFrame
    panel_interpolated: pd.DataFrame
    coverage: pd.DataFrame
    written: tuple[Path, ...]


def configure_logging(level: str = config.LOG_LEVEL) -> None:
    """Set up module-level logging for a CLI run.

    Args:
        level: A standard logging level name.
    """
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s  %(levelname)-8s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def write_table(frame: pd.DataFrame, stem: str, output_dir: Path) -> tuple[Path, ...]:
    """Write one table in every configured output format.

    Args:
        frame: The table to write.
        stem: Filename without extension.
        output_dir: Destination directory, created if absent.

    Returns:
        The paths written.

    Raises:
        ValueError: If an unsupported output format is configured.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for fmt in config.OUTPUT_FORMATS:
        path = output_dir / f"{stem}.{fmt}"
        if fmt == "csv":
            frame.to_csv(path, index=False)
        elif fmt == "parquet":
            frame.to_parquet(path, index=False)
        else:
            msg = f"Unsupported output format: {fmt}"
            raise ValueError(msg)
        written.append(path)

    logger.info("Wrote %s (%d rows)", stem, len(frame))
    return tuple(written)


def run(
    *,
    indicators: Sequence[Indicator] = config.INDICATORS,
    countries: Sequence[str] = config.COUNTRY_CODES,
    year_start: int = config.YEAR_START,
    year_end: int = config.YEAR_END,
    source: IndicatorSource | None = None,
    cache_dir: Path = config.RAW_DATA_DIR,
    output_dir: Path = config.PROCESSED_DATA_DIR,
    refresh: bool = False,
) -> PipelineResult:
    """Run the data layer end to end.

    Args:
        indicators: Series to fetch. Defaults to every configured indicator.
        countries: ISO3 country codes.
        year_start: First year, inclusive.
        year_end: Last year, inclusive.
        source: Where to fetch from. Defaults to the World Bank.
        cache_dir: Directory holding cached raw pulls.
        output_dir: Destination for the processed tables.
        refresh: Re-pull every indicator instead of reading the cache.

    Returns:
        The three tables and the paths they were written to.
    """
    logger.info(
        "Building panel: %d indicators x %d countries, %d-%d (treatment year %d)",
        len(indicators),
        len(countries),
        year_start,
        year_end,
        config.TREATMENT_YEAR,
    )

    raw = ingestion.fetch_panel(
        indicators,
        source=source,
        countries=countries,
        year_start=year_start,
        year_end=year_end,
        cache_dir=cache_dir,
        refresh=refresh,
    )

    panel = cleaning.build_panel(raw)
    panel_interpolated = cleaning.interpolate_panel(panel)
    coverage = cleaning.build_coverage_report(panel)

    written = (
        *write_table(panel, config.PANEL_STEM, output_dir),
        *write_table(panel_interpolated, config.PANEL_INTERPOLATED_STEM, output_dir),
        *write_table(coverage, config.COVERAGE_REPORT_STEM, output_dir),
    )

    logger.info("Data layer complete: %d files in %s", len(written), output_dir)
    return PipelineResult(
        panel=panel,
        panel_interpolated=panel_interpolated,
        coverage=coverage,
        written=written,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the panel build."""
    parser = argparse.ArgumentParser(
        prog="amber-build-panel",
        description="Fetch World Bank indicators and build the tidy country-year panel.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-pull every indicator from the API instead of using the raw cache.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.PROCESSED_DATA_DIR,
        help="Where to write the processed tables (default: data/processed).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=config.RAW_DATA_DIR,
        help="Where cached raw pulls live (default: data/raw).",
    )
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
    args = build_arg_parser().parse_args(argv)
    configure_logging(args.log_level)

    result = run(
        source=None,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        refresh=args.refresh,
    )

    n_dark = int(result.coverage["is_dark"].sum())
    if n_dark:
        logger.warning(
            "%d series are dark from %d onward - see %s",
            n_dark,
            config.TREATMENT_YEAR,
            args.output_dir / f"{config.COVERAGE_REPORT_STEM}.csv",
        )
    return 0
