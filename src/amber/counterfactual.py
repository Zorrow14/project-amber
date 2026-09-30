"""Orchestrate the counterfactual layer: inputs -> synthetic control -> tables + charts.

Phase 3 end to end. For every configured outcome, fits synthetic Myanmar, runs
the in-space and in-time placebos and the leave-one-out refits, writes the
tidy tables to ``data/processed`` and renders the charts to ``reports/figures``.

Tables written (csv + parquet):

* ``synthetic_control`` - actual, synthetic and gap by outcome and year.
* ``sc_weights`` - the donor weights that make up each synthetic unit.
* ``sc_placebo`` - the gap path of Myanmar and every in-space placebo, i.e. the
  full set the pseudo p-value ranks.
* ``sc_placebo_time`` - the in-time placebo's actual, synthetic and gap.
* ``sc_leave_one_out`` - each leave-one-out refit's synthetic and gap.
* ``sc_metrics`` - one row per outcome: fit, inference and robustness numbers.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from amber import config, figures
from amber.config import SCOutcome
from amber.modeling import synthetic_control as sc
from amber.pipeline import configure_logging, write_table

logger = logging.getLogger(__name__)

DEFAULT_PANEL = config.PROCESSED_DATA_DIR / f"{config.PANEL_INTERPOLATED_STEM}.csv"
DEFAULT_INDEX = config.PROCESSED_DATA_DIR / f"{config.INDEX_STEM}.csv"


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    """What a counterfactual run produced.

    Attributes:
        runs: One :class:`~amber.modeling.synthetic_control.CounterfactualRun`
            per outcome.
        tables: Stem -> tidy table, as written.
        written: Every table file written.
        figures: Every chart written.
    """

    runs: tuple[sc.CounterfactualRun, ...]
    tables: dict[str, pd.DataFrame]
    written: tuple[Path, ...]
    figures: tuple[Path, ...]


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


def load_inputs(
    outcomes: Sequence[SCOutcome],
    *,
    panel_path: Path = DEFAULT_PANEL,
    index_path: Path = DEFAULT_INDEX,
    settings: sc.SCSettings | None = None,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Read only the inputs the requested outcomes need.

    Args:
        outcomes: Outcomes to be estimated.
        panel_path: Interpolated panel from the data layer.
        index_path: Index table from the reconstruction layer.
        settings: Fit settings, to know whether covariates are needed.

    Returns:
        ``(panel, index)``, each ``None`` if nothing needs it.

    Raises:
        FileNotFoundError: If a needed input has not been built yet.
    """
    settings = settings or sc.SCSettings()
    sources = {sc.resolve_outcome_source(o.name) for o in outcomes}

    panel = None
    if "panel" in sources or settings.predictors:
        if not panel_path.exists():
            msg = f"{panel_path} not found - build the panel first with `make panel`"
            raise FileNotFoundError(msg)
        panel = pd.read_csv(panel_path)

    index = None
    if "index" in sources:
        if not index_path.exists():
            msg = f"{index_path} not found - build the index first with `make index`"
            raise FileNotFoundError(msg)
        index = pd.read_csv(index_path)
    return panel, index


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


def _paths(outcome: str, result: sc.SyntheticControlResult) -> pd.DataFrame:
    """Actual, synthetic and gap for one fit, as tidy rows."""
    frames = [
        pd.DataFrame(
            {
                config.COL_OUTCOME: outcome,
                config.COL_YEAR: series.index.astype(int),
                config.COL_SERIES: series.name,
                config.COL_VALUE: series.to_numpy(),
            }
        )
        for series in (result.actual, result.synthetic, result.gap)
    ]
    return pd.concat(frames, ignore_index=True)


def results_table(runs: Sequence[sc.CounterfactualRun]) -> pd.DataFrame:
    """``[outcome, year, series, value]`` for every outcome's base fit."""
    return pd.concat([_paths(run.outcome.name, run.base) for run in runs], ignore_index=True)


def weights_table(runs: Sequence[sc.CounterfactualRun]) -> pd.DataFrame:
    """``[outcome, donor_iso3, donor_name, weight]`` for every outcome's base fit."""
    rows = [
        {
            config.COL_OUTCOME: run.outcome.name,
            config.COL_DONOR_ISO3: donor,
            config.COL_DONOR_NAME: config.COUNTRIES.get(donor, donor),
            config.COL_WEIGHT: weight,
        }
        for run in runs
        for donor, weight in run.base.weights.items()
    ]
    return pd.DataFrame(rows)


def placebo_table(runs: Sequence[sc.CounterfactualRun]) -> pd.DataFrame:
    """``[outcome, unit_iso3, year, gap]`` for the treated unit and every placebo."""
    frames = []
    for run in runs:
        fits = {run.base.treated: run.base, **run.placebo_space.placebos}
        for unit, fit in fits.items():
            frames.append(
                pd.DataFrame(
                    {
                        config.COL_OUTCOME: run.outcome.name,
                        config.COL_UNIT_ISO3: unit,
                        config.COL_YEAR: fit.gap.index.astype(int),
                        config.COL_GAP: fit.gap.to_numpy(),
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


def placebo_time_table(runs: Sequence[sc.CounterfactualRun]) -> pd.DataFrame:
    """``[outcome, year, series, value]`` for every outcome's in-time placebo."""
    frames = [_paths(run.outcome.name, run.placebo_time) for run in runs if run.placebo_time]
    columns = [config.COL_OUTCOME, config.COL_YEAR, config.COL_SERIES, config.COL_VALUE]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def leave_one_out_table(runs: Sequence[sc.CounterfactualRun]) -> pd.DataFrame:
    """``[outcome, dropped_donor, year, series, value]`` for every refit."""
    frames = []
    for run in runs:
        for donor, refit in run.leave_one_out.items():
            paths = _paths(run.outcome.name, refit)
            paths = paths[paths[config.COL_SERIES] != "actual"]  # actual is in the main table
            paths.insert(1, config.COL_DROPPED_DONOR, donor)
            frames.append(paths)
    columns = [
        config.COL_OUTCOME,
        config.COL_DROPPED_DONOR,
        config.COL_YEAR,
        config.COL_SERIES,
        config.COL_VALUE,
    ]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def metrics_table(runs: Sequence[sc.CounterfactualRun]) -> pd.DataFrame:
    """One row per outcome: fit quality, inference and robustness.

    Beyond the core fit numbers: ``pre_rmse_share`` (pre-RMSE over the mean
    pre-period level - comparable across outcomes), ``n_units`` (so the p-value
    floor, 1 / n_units, is explicit), ``intime_rmse_ratio`` and
    ``loo_max_deviation``.
    """
    rows = []
    for run in runs:
        base = run.base
        rows.append(
            {
                config.COL_OUTCOME: run.outcome.name,
                "pre_rmse": base.pre_rmse,
                "post_rmse": base.post_rmse,
                "rmse_ratio": base.rmse_ratio,
                "pseudo_p_value": run.p_value,
                "n_effective_donors": base.n_effective_donors,
                "pre_rmse_share": base.pre_rmse_share,
                "n_units": len(run.placebo_space.ratios),
                "intime_rmse_ratio": (
                    run.placebo_time.rmse_ratio if run.placebo_time else float("nan")
                ),
                "loo_max_deviation": run.loo_max_deviation,
            }
        )
    return pd.DataFrame(rows)


def build_tables(runs: Sequence[sc.CounterfactualRun]) -> dict[str, pd.DataFrame]:
    """Every output table, keyed by its file stem."""
    return {
        config.SC_STEM: results_table(runs),
        config.SC_WEIGHTS_STEM: weights_table(runs),
        config.SC_PLACEBO_STEM: placebo_table(runs),
        config.SC_PLACEBO_TIME_STEM: placebo_time_table(runs),
        config.SC_LEAVE_ONE_OUT_STEM: leave_one_out_table(runs),
        config.SC_METRICS_STEM: metrics_table(runs),
    }


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #


def run(
    *,
    outcomes: Sequence[SCOutcome] = config.SC_OUTCOMES,
    panel_path: Path = DEFAULT_PANEL,
    index_path: Path = DEFAULT_INDEX,
    output_dir: Path = config.PROCESSED_DATA_DIR,
    figures_dir: Path = config.FIGURES_DIR,
    settings: sc.SCSettings | None = None,
    render: bool = True,
) -> CounterfactualResult:
    """Estimate, test and chart every outcome.

    Args:
        outcomes: Outcomes to estimate. Defaults to every configured one.
        panel_path: Interpolated panel from the data layer.
        index_path: Index table from the reconstruction layer.
        output_dir: Destination for the tables.
        figures_dir: Destination for the charts.
        settings: Fit settings; defaults to config.
        render: Skip the charts when false.

    Returns:
        The runs, tables and every path written.
    """
    settings = settings or sc.SCSettings()
    panel, index = load_inputs(
        outcomes, panel_path=panel_path, index_path=index_path, settings=settings
    )

    runs = tuple(sc.run(o, panel=panel, index=index, settings=settings) for o in outcomes)
    tables = build_tables(runs)
    written = tuple(
        path for stem, table in tables.items() for path in write_table(table, stem, output_dir)
    )
    rendered = (
        tuple(path for r in runs for path in figures.render_counterfactual(r, figures_dir))
        if render
        else ()
    )

    for r in runs:
        base = r.base
        logger.info(
            "%s: final-year gap %.4g, pre-RMSE %.4g (%.1f%% of level%s), p = %.3f (floor %.3f)",
            r.outcome.name,
            base.gap.dropna().iloc[-1],
            base.pre_rmse,
            100 * base.pre_rmse_share,
            ", POOR FIT" if base.poor_fit else "",
            r.p_value,
            1 / len(r.placebo_space.ratios),
        )
    logger.info("Counterfactual complete: %d tables, %d figures", len(written), len(rendered))
    return CounterfactualResult(runs=runs, tables=tables, written=written, figures=rendered)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the counterfactual build."""
    names = [o.name for o in config.SC_OUTCOMES]
    parser = argparse.ArgumentParser(
        prog="amber-build-sc",
        description="Estimate the synthetic-control counterfactual and render its charts.",
    )
    parser.add_argument(
        "--outcome",
        action="append",
        choices=names,
        help="Outcome to estimate; repeat for several. Default: all configured.",
    )
    parser.add_argument(
        "--pre-period-end",
        type=int,
        default=config.SC_PRE_PERIOD_END,
        help=f"Last fit year (default {config.SC_PRE_PERIOD_END}). "
        f"{config.TREATMENT_YEAR - 2} drops Myanmar's anomalous 2020.",
    )
    parser.add_argument(
        "--rebase",
        action="store_true",
        default=config.SC_REBASE,
        help=f"Index every series to 100 at {config.MODELING_WINDOW_START} (robustness variant).",
    )
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL, help="Interpolated panel.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="Index table.")
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

    chosen = args.outcome or [o.name for o in config.SC_OUTCOMES]
    outcomes = tuple(o for o in config.SC_OUTCOMES if o.name in chosen)
    settings = replace(sc.SCSettings(), pre_end=args.pre_period_end, rebase=args.rebase)

    try:
        run(
            outcomes=outcomes,
            panel_path=args.panel,
            index_path=args.index,
            output_dir=args.output_dir,
            figures_dir=args.figures_dir,
            settings=settings,
            render=not args.no_figures,
        )
    except (FileNotFoundError, ValueError) as exc:
        # A missing input or an unfittable setting is a usage error, not a crash.
        parser.error(str(exc))
    return 0
