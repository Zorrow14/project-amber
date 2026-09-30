"""Orchestrate the future layer: inputs -> calibration -> scenarios -> tables + charts.

Phase 4 end to end, shared by ``scripts/build_system_dynamics.py`` and the
notebook. The model itself - equations, calibration, ensemble - lives in
:mod:`amber.modeling.system_dynamics`; this module handles inputs, the phase 3
consistency check's data, the tidy tables and the charts.

Tables written (csv + parquet):

* ``sd_trajectory`` - ``[scenario, year, series, quantile, value]`` for the
  stocks, the mapped indicators, the pillars and the combined index.
* ``sd_scenarios`` - ``[scenario, lever, value]``: every lever, plus the
  stability recovery at the treatment year and the horizon.
* ``sd_calibration`` - ``[parameter, value, calibrated, low, high, at_bound]``.
* ``sd_metrics`` - ``[scope, nrmse, credible, n_obs, sc_overlap_deviation,
  sc_consistent]``: the overall backtest (whose ``credible`` is the gate), each
  indicator, the combined index, and the phase 3 overlap check.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from amber import config, figures
from amber.modeling import system_dynamics as sd
from amber.pipeline import configure_logging, write_table

logger = logging.getLogger(__name__)

DEFAULT_PANEL = config.PROCESSED_DATA_DIR / f"{config.PANEL_INTERPOLATED_STEM}.csv"
DEFAULT_SC_PATHS = config.PROCESSED_DATA_DIR / f"{config.SC_STEM}.csv"
DEFAULT_SC_METRICS = config.PROCESSED_DATA_DIR / f"{config.SC_METRICS_STEM}.csv"

OVERALL_SCOPE = "overall"


@dataclass(frozen=True, slots=True)
class DynamicsResult:
    """What a future-layer run produced.

    Attributes:
        run: The model run - calibration, backtest, scenarios, SC checks.
        tables: Stem -> tidy table, as written.
        written: Every table file written.
        figures: Every chart written.
    """

    run: sd.FutureRun
    tables: dict[str, pd.DataFrame]
    written: tuple[Path, ...]
    figures: tuple[Path, ...]


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


def load_inputs(
    *,
    panel_path: Path = DEFAULT_PANEL,
    sc_paths_path: Path = DEFAULT_SC_PATHS,
    sc_metrics_path: Path = DEFAULT_SC_METRICS,
) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """Read the panel and, if present, the phase 3 outputs.

    Args:
        panel_path: Interpolated panel from the data layer.
        sc_paths_path: Phase 3 ``synthetic_control`` table.
        sc_metrics_path: Phase 3 ``sc_metrics`` table.

    Returns:
        ``(panel, sc_paths, sc_metrics)``; the SC tables are ``None`` if phase 3
        has not been run, and the consistency check is then skipped.

    Raises:
        FileNotFoundError: If the panel has not been built.
    """
    if not panel_path.exists():
        msg = f"{panel_path} not found - build the panel first with `make panel`"
        raise FileNotFoundError(msg)
    panel = pd.read_csv(panel_path)

    if sc_paths_path.exists() and sc_metrics_path.exists():
        return panel, pd.read_csv(sc_paths_path), pd.read_csv(sc_metrics_path)
    logger.warning(
        "Phase 3 outputs not found (%s) - run `make sc` for the consistency check",
        sc_paths_path.name,
    )
    return panel, None, None


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


def trajectory_table(run: sd.FutureRun) -> pd.DataFrame:
    """``[scenario, year, series, quantile, value]`` for every scenario."""
    frames = []
    for name, result in run.results.items():
        bands = result.bands.copy()
        bands.insert(0, config.COL_SCENARIO, name)
        frames.append(bands)
    return pd.concat(frames, ignore_index=True)


def scenarios_table(scenarios: Sequence[config.Scenario] = config.SCENARIOS) -> pd.DataFrame:
    """``[scenario, lever, value]``: levers plus stability recovery at key years."""
    rows = []
    for scenario in scenarios:
        for lever in config.LEVERS:
            rows.append((scenario.name, lever, scenario.lever(lever)))
        xs, rs = zip(*scenario.stability, strict=True)
        for year in (config.TREATMENT_YEAR, config.SD_HORIZON_END):
            rows.append(
                (scenario.name, f"stability_recovery_{year}", float(np.interp(year, xs, rs)))
            )
    return pd.DataFrame(rows, columns=[config.COL_SCENARIO, config.COL_LEVER, config.COL_VALUE])


def calibration_table(calibration: sd.Calibration) -> pd.DataFrame:
    """Every parameter, whether it was fitted, its bounds, and whether it hit one.

    A fitted parameter resting on a bound is a warning sign - the data may want
    it further, or may not identify it at all - so it is flagged rather than
    left to be noticed.
    """
    rows = []
    for name, spec in config.SD_PARAMETERS.items():
        value = calibration.params[name]
        span = max(abs(spec.high - spec.low), 1.0)
        at_bound = (
            spec.calibrate and min(abs(value - spec.low), abs(value - spec.high)) < 1e-6 * span
        )
        rows.append(
            {
                config.COL_PARAMETER: name,
                config.COL_VALUE: value,
                "calibrated": spec.calibrate,
                "low": spec.low,
                "high": spec.high,
                "at_bound": bool(at_bound),
            }
        )
    return pd.DataFrame(rows)


def metrics_table(run: sd.FutureRun, threshold: float = config.SD_CREDIBLE_NRMSE) -> pd.DataFrame:
    """Backtest error by scope, the credibility gate, and the phase 3 overlap check.

    ``credible`` on the ``overall`` row is the gate every chart caption follows;
    on the other rows it says whether that scope alone would pass.
    """
    bt = run.backtest
    checks = {check.outcome: check for check in run.sc_checks}

    def sc_fields(scope: str) -> dict[str, object]:
        check = checks.get(scope)
        if check is None:
            return {"sc_overlap_deviation": float("nan"), "sc_consistent": pd.NA}
        consistent = pd.NA if check.consistent is None else bool(check.consistent)
        return {"sc_overlap_deviation": check.deviation, "sc_consistent": consistent}

    rows = [
        {
            config.COL_SCOPE: OVERALL_SCOPE,
            "nrmse": bt.overall,
            "credible": bt.credible,
            "n_obs": int(bt.n_obs.sum()),
            **sc_fields(OVERALL_SCOPE),
        }
    ]
    for indicator_id, error in bt.nrmse.items():
        rows.append(
            {
                config.COL_SCOPE: indicator_id,
                "nrmse": error,
                "credible": bool(error <= threshold),
                "n_obs": int(bt.n_obs[indicator_id]),
                **sc_fields(str(indicator_id)),
            }
        )
    combined = bt.combined_nrmse
    rows.append(
        {
            config.COL_SCOPE: config.COMBINED_SERIES,
            "nrmse": combined,
            "credible": bool(combined <= threshold),
            "n_obs": int((bt.combined_modeled - bt.combined_actual).notna().sum()),
            **sc_fields(config.COMBINED_SERIES),
        }
    )
    table = pd.DataFrame(rows)
    table["sc_consistent"] = table["sc_consistent"].astype("boolean")
    return table


def build_tables(run: sd.FutureRun) -> dict[str, pd.DataFrame]:
    """Every output table, keyed by its file stem."""
    return {
        config.SD_TRAJECTORY_STEM: trajectory_table(run),
        config.SD_SCENARIOS_STEM: scenarios_table([r.scenario for r in run.results.values()]),
        config.SD_CALIBRATION_STEM: calibration_table(run.calibration),
        config.SD_METRICS_STEM: metrics_table(run),
    }


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #


def run(
    *,
    panel_path: Path = DEFAULT_PANEL,
    sc_paths_path: Path = DEFAULT_SC_PATHS,
    sc_metrics_path: Path = DEFAULT_SC_METRICS,
    output_dir: Path = config.PROCESSED_DATA_DIR,
    figures_dir: Path = config.FIGURES_DIR,
    size: int = config.SD_ENSEMBLE_SIZE,
    seed: int = config.SD_SEED,
    render: bool = True,
) -> DynamicsResult:
    """Calibrate, run every scenario, check against phase 3, write and chart.

    Args:
        panel_path: Interpolated panel from the data layer.
        sc_paths_path: Phase 3 ``synthetic_control`` table.
        sc_metrics_path: Phase 3 ``sc_metrics`` table.
        output_dir: Destination for the tables.
        figures_dir: Destination for the charts.
        size: Ensemble members per scenario.
        seed: RNG seed for calibration restarts and the ensemble.
        render: Skip the charts when false.

    Returns:
        The model run, tables and every path written.
    """
    panel, sc_paths, sc_metrics = load_inputs(
        panel_path=panel_path, sc_paths_path=sc_paths_path, sc_metrics_path=sc_metrics_path
    )
    future = sd.run(panel, sc_paths=sc_paths, sc_metrics=sc_metrics, size=size, seed=seed)

    tables = build_tables(future)
    written = tuple(
        path for stem, table in tables.items() for path in write_table(table, stem, output_dir)
    )
    rendered = figures.render_future(future, sc_paths, figures_dir) if render else ()

    at_bound = tables[config.SD_CALIBRATION_STEM].query("at_bound")[config.COL_PARAMETER].tolist()
    if at_bound:
        logger.warning("Calibrated parameters at a bound (weakly identified?): %s", at_bound)
    logger.info(
        "Future layer complete: backtest nRMSE %.3f (%s), %d tables, %d figures",
        future.backtest.overall,
        "credible" if future.credible else "NOT credible - illustrative only",
        len(written),
        len(rendered),
    )
    return DynamicsResult(run=future, tables=tables, written=written, figures=rendered)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the future-layer build."""
    parser = argparse.ArgumentParser(
        prog="amber-build-sd",
        description="Calibrate the system-dynamics model and run the future scenarios.",
    )
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL, help="Interpolated panel.")
    parser.add_argument(
        "--sc-paths", type=Path, default=DEFAULT_SC_PATHS, help="Phase 3 synthetic_control table."
    )
    parser.add_argument(
        "--sc-metrics", type=Path, default=DEFAULT_SC_METRICS, help="Phase 3 sc_metrics table."
    )
    parser.add_argument(
        "--ensemble-size",
        type=int,
        default=config.SD_ENSEMBLE_SIZE,
        help=f"Members per scenario (default {config.SD_ENSEMBLE_SIZE}).",
    )
    parser.add_argument(
        "--seed", type=int, default=config.SD_SEED, help="RNG seed for restarts and ensemble."
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
    if args.ensemble_size < 1:
        parser.error("--ensemble-size must be at least 1")

    try:
        run(
            panel_path=args.panel,
            sc_paths_path=args.sc_paths,
            sc_metrics_path=args.sc_metrics,
            output_dir=args.output_dir,
            figures_dir=args.figures_dir,
            size=args.ensemble_size,
            seed=args.seed,
            render=not args.no_figures,
        )
    except (FileNotFoundError, ValueError) as exc:
        # A missing input or an unusable setting is a usage error, not a crash.
        parser.error(str(exc))
    return 0
