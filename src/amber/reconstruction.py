"""Orchestrate the past layer: panel -> index -> table + charts.

Phase 2 end to end. Reads the interpolated panel the data layer wrote, builds
the development index, writes it to ``data/processed`` and renders the static
reconstruction charts to ``reports/figures``.

Pillar weights can be passed on the command line, which is the point: how
development is defined is a setting, not a buried assumption.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from amber import config, figures
from amber.config import Normalization
from amber.modeling import index as dev_index
from amber.pipeline import configure_logging, write_table

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    """What a reconstruction run produced.

    Attributes:
        index: Tidy index rows in :data:`~amber.config.INDEX_COLUMNS`.
        tables: Index files written, one per output format.
        figures: Chart PNGs written.
    """

    index: pd.DataFrame
    tables: tuple[Path, ...]
    figures: tuple[Path, ...]


def load_panel(path: Path) -> pd.DataFrame:
    """Read the interpolated panel written by the data layer.

    Args:
        path: CSV written by :func:`amber.pipeline.run`.

    Returns:
        The panel.

    Raises:
        FileNotFoundError: If the data layer has not been run yet.
    """
    if not path.exists():
        msg = f"{path} not found - build the panel first with `make panel`"
        raise FileNotFoundError(msg)
    return pd.read_csv(path)


def run(
    *,
    panel_path: Path = config.PROCESSED_DATA_DIR / f"{config.PANEL_INTERPOLATED_STEM}.csv",
    output_dir: Path = config.PROCESSED_DATA_DIR,
    figures_dir: Path = config.FIGURES_DIR,
    weights: Mapping[str, float] | None = None,
    method: Normalization | str | None = None,
    render: bool = True,
) -> ReconstructionResult:
    """Build the index, write it, and render the charts.

    Args:
        panel_path: The interpolated panel to read.
        output_dir: Destination for the index table.
        figures_dir: Destination for the chart PNGs.
        weights: Pillar weights on any non-negative scale. Defaults to equal.
        method: Normalization - ``goalposts`` (default) or ``pooled``.
        render: Skip the charts when false.

    Returns:
        The index and every path written.
    """
    panel = load_panel(panel_path)
    result = dev_index.compute_index(panel, weights, method)
    tables = write_table(result, config.INDEX_STEM, output_dir)
    rendered = (
        figures.render_all(result, panel, figures_dir, method=method, weights=weights)
        if render
        else ()
    )

    logger.info("Reconstruction complete: %d tables, %d figures", len(tables), len(rendered))
    return ReconstructionResult(index=result, tables=tables, figures=rendered)


def parse_weights(text: str) -> dict[str, float]:
    """Parse ``economy=2,innovation=1,human_development=1``.

    Args:
        text: Comma-separated ``pillar=weight`` pairs.

    Returns:
        Pillar -> weight, as given (renormalized later by the index).

    Raises:
        argparse.ArgumentTypeError: If a pair is malformed or a weight is not a
            number.
    """
    weights: dict[str, float] = {}
    for pair in filter(None, (part.strip() for part in text.split(","))):
        name, sep, value = pair.partition("=")
        if not sep:
            msg = f"expected pillar=weight, got {pair!r}"
            raise argparse.ArgumentTypeError(msg)
        try:
            weights[name.strip()] = float(value)
        except ValueError as exc:
            msg = f"weight for {name.strip()!r} is not a number: {value!r}"
            raise argparse.ArgumentTypeError(msg) from exc
    return weights


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the reconstruction build."""
    parser = argparse.ArgumentParser(
        prog="amber-build-index",
        description="Build the combined development index and render the reconstruction charts.",
    )
    parser.add_argument(
        "--weights",
        type=parse_weights,
        default=None,
        help="Pillar weights, e.g. economy=2,innovation=1,human_development=1 "
        "(any scale; renormalized). Default: equal.",
    )
    parser.add_argument(
        "--normalization",
        choices=[str(m) for m in Normalization],
        default=str(config.DEFAULT_NORMALIZATION),
        help="goalposts: fixed per-indicator bounds (default, stable as data is added); "
        "pooled: this panel's own min-max, for comparison.",
    )
    parser.add_argument(
        "--panel",
        type=Path,
        default=config.PROCESSED_DATA_DIR / f"{config.PANEL_INTERPOLATED_STEM}.csv",
        help="Interpolated panel to read (default: data/processed/panel_interpolated.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.PROCESSED_DATA_DIR,
        help="Where to write index.csv / index.parquet (default: data/processed).",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=config.FIGURES_DIR,
        help="Where to write the chart PNGs (default: reports/figures).",
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

    try:
        run(
            panel_path=args.panel,
            output_dir=args.output_dir,
            figures_dir=args.figures_dir,
            weights=args.weights,
            method=args.normalization,
            render=not args.no_figures,
        )
    except (FileNotFoundError, ValueError) as exc:
        # Bad weights or a missing panel are user errors, not crashes.
        parser.error(str(exc))
    return 0
