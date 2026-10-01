"""Static charts for the reconstruction layer.

Built on matplotlib's object API (``Figure``, never ``pyplot``), so rendering
needs no display backend and works the same in CI, the CLI and a notebook -
where a returned ``Figure`` displays inline.

Encoding rules, applied the same way in every chart:

* **Color follows the entity.** Each country keeps one fixed hue across every
  chart, assigned in :data:`~amber.config.COUNTRY_CODES` order - never by rank.
* **Hollow points mark partial coverage.** Where a score was computed from fewer
  than all of its indicators, the point is drawn as a ring. Coverage changes can
  move a pillar on their own, so they must not read as ordinary data.
* **Context is factual.** 2020 is shaded as the COVID year and 2021 is marked as
  the coup, so the two shocks are not conflated.

The palette is a validated categorical order (adjacent-pair colorblind
separation checked); three of its hues sit below 3:1 contrast on the light
surface, so series are always legend- or direct-labelled and ``index.csv`` is
the table view.
"""

from __future__ import annotations

import logging
import textwrap
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from amber import config
from amber.config import Normalization, Pillar, SCOutcome
from amber.modeling.divergence import DivergenceResult
from amber.modeling.index import resolve_weights
from amber.modeling.synthetic_control import CounterfactualRun, SyntheticControlResult
from amber.modeling.system_dynamics import FutureRun, SimulationResult, divergence_year

logger = logging.getLogger(__name__)

__all__ = [
    "actual_vs_synthetic_figure",
    "backtest_figure",
    "combined_index_figure",
    "donor_weights_figure",
    "future_fan_figure",
    "future_gdp_figure",
    "gdp_pc_divergence_figure",
    "historical_divergence_figure",
    "historical_gdp_figure",
    "myanmar_pillars_figure",
    "placebo_gaps_figure",
    "render_all",
    "render_counterfactual",
    "render_future",
    "render_historical",
    "save_figure",
    "stocks_figure",
]

# --------------------------------------------------------------------------- #
# Palette and chrome
# --------------------------------------------------------------------------- #

SERIES_PALETTE: tuple[str, ...] = (
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
)
"""Categorical slots in validated order. Slot order is the colorblind-safety
mechanism, not decoration - do not reorder or cycle."""

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
CONTEXT_FILL = "#f0efec"
DE_EMPHASIS = "#c3c2b7"

COUNTRY_COLORS: dict[str, str] = dict(zip(config.COUNTRY_CODES, SERIES_PALETTE, strict=True))
PILLAR_COLORS: dict[str, str] = dict(zip((str(p) for p in Pillar), SERIES_PALETTE, strict=False))
PILLAR_LABELS: dict[str, str] = {
    Pillar.ECONOMY: "Economy",
    Pillar.INNOVATION: "Innovation / technology",
    Pillar.HUMAN_DEVELOPMENT: "Human development",
}

FIGSIZE = (10.0, 5.8)
DPI = 200
LINE_WIDTH = 2.0
EMPHASIS_WIDTH = 2.8
MARKER_SIZE = 6.0
FONT_CANDIDATES = ("Segoe UI", "Helvetica Neue", "Helvetica", "Arial")


def _resolve_font(candidates: Sequence[str]) -> str:
    """Pick the first installed font, falling back to matplotlib's bundled one.

    Resolving once avoids a findfont warning per text element on machines
    that lack the earlier candidates.
    """
    installed = {entry.name for entry in font_manager.fontManager.ttflist}
    return next((name for name in candidates if name in installed), "DejaVu Sans")


FONT_FAMILY = _resolve_font(FONT_CANDIDATES)

SUBTITLE_WIDTH = 140
TITLE_INSET_IN = 0.261
SUBTITLE_INSET_IN = 0.551
"""Title and subtitle baselines, in inches below the top edge."""
"""Characters per subtitle line at 10pt across the figure; longer captions
(custom weights) wrap to a second line instead of running off the edge."""

PARTIAL_COVERAGE_NOTE = "Hollow points: computed from fewer than all indicators."

SHORT_NAMES: dict[str, str] = {
    "SI.POV.DDAY": "poverty",
    "TX.VAL.TECH.MF.ZS": "high-tech exports",
}


def _index_composition_note() -> str:
    """Which panel series the index leaves out, from config - so no caption drifts."""
    total = len(config.INDICATORS)
    note = f"Built from {len(config.INDEX_INDICATORS)} of the panel's {total} indicators"
    if config.INDEX_EXCLUDED:
        names = [SHORT_NAMES.get(i, config.INDICATORS_BY_ID[i].name) for i in config.INDEX_EXCLUDED]
        note += (
            f"; {' and '.join(names)} stay as history only, since no counterfactual or "
            "projection can produce them"
        )
    return note + "."


SCALE_NOTES: dict[Normalization, tuple[str, str]] = {
    Normalization.GOALPOSTS: (
        "scored against fixed goalposts (HDI / SDG standards where published)",
        "Fixed goalposts: adding data does not move past scores.",
    ),
    Normalization.POOLED: (
        "scored against the pooled 7-country range",
        "Pooled scale: scores are relative to this panel, not absolute.",
    ),
}
"""(subtitle phrase, footer note) per normalization, so a chart never
misdescribes the scale it was drawn on."""


# --------------------------------------------------------------------------- #
# Shared scaffolding
# --------------------------------------------------------------------------- #


def _new_figure() -> tuple[Figure, Axes]:
    """Create a figure with the shared chrome applied."""
    fig = Figure(figsize=FIGSIZE, dpi=DPI, facecolor=SURFACE)
    ax = fig.add_subplot()
    _style_axis(ax)
    return fig, ax


def _style_axis(ax: Axes, *, labelsize: float = 9) -> None:
    """Apply the shared chrome to one axes - also used for small multiples."""
    ax.set_facecolor(SURFACE)

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(0.8)

    ax.grid(axis="y", color=GRID, linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(
        which="both",
        colors=INK_MUTED,
        labelcolor=INK_SECONDARY,
        labelsize=labelsize,
        labelfontfamily=FONT_FAMILY,
        length=0,
        pad=6,
    )

    for text in (ax.xaxis.label, ax.yaxis.label):
        text.set_color(INK_SECONDARY)
        text.set_fontsize(10)
        text.set_family(FONT_FAMILY)


def _set_titles(fig: Figure, title: str, subtitle: str) -> None:
    """Left-aligned title and subtitle above the plot.

    Placed in inches from the top edge, so figures of any height keep the same
    spacing (on the standard 5.8in figure these are 0.955 and 0.905).
    """
    height = fig.get_figheight()
    fig.text(
        0.06,
        1 - TITLE_INSET_IN / height,
        title,
        fontsize=15,
        fontweight="bold",
        color=INK_PRIMARY,
        family=FONT_FAMILY,
        ha="left",
        va="top",
    )
    fig.text(
        0.06,
        1 - SUBTITLE_INSET_IN / height,
        textwrap.fill(subtitle, SUBTITLE_WIDTH),
        fontsize=10,
        color=INK_SECONDARY,
        family=FONT_FAMILY,
        ha="left",
        va="top",
    )


def _set_footer(fig: Figure, *notes: str) -> None:
    """Source line and any caveats, bottom-left."""
    fig.text(
        0.06,
        0.025,
        "  ·  ".join((config.SOURCE_NOTE, *notes)),
        fontsize=8,
        color=INK_MUTED,
        family=FONT_FAMILY,
        ha="left",
        va="bottom",
    )


def _mark_context(ax: Axes, y_text: float, *, dashed_treatment: bool = False) -> None:
    """Shade the COVID year and mark the treatment year, with plain labels.

    Args:
        ax: Target axes.
        y_text: Where to place the labels, in axes-fraction coordinates.
        dashed_treatment: Dash the treatment line - used on counterfactual
            charts, where 2021 is the point the estimate turns on.
    """
    for year in config.COVID_CONFOUNDED_YEARS:
        ax.axvspan(year - 0.5, year + 0.5, color=CONTEXT_FILL, zorder=0, linewidth=0)
        ax.text(
            year,
            y_text,
            "COVID-19",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8,
            color=INK_MUTED,
            family=FONT_FAMILY,
        )

    ax.axvline(
        config.TREATMENT_YEAR,
        color=INK_MUTED,
        linewidth=0.9 if dashed_treatment else 0.8,
        linestyle=(0, (4, 3)) if dashed_treatment else "-",
        zorder=1,
    )
    ax.text(
        config.TREATMENT_YEAR + 0.12,
        y_text,
        "Feb 2021 coup",
        transform=ax.get_xaxis_transform(),
        ha="left",
        va="top",
        fontsize=8,
        color=INK_SECONDARY,
        family=FONT_FAMILY,
    )


def _year_axis(ax: Axes, years: Sequence[int]) -> None:
    """Integer year ticks every other year, padded half a year each side."""
    first, last = min(years), max(years)
    ax.set_xlim(first - 0.5, last + 0.9)
    ax.set_xticks(range(first, last + 1, 2))


def _plot_series(
    ax: Axes,
    frame: pd.DataFrame,
    color: str,
    label: str,
    *,
    width: float = LINE_WIDTH,
    zorder: float = 3,
) -> None:
    """Draw one series, ringing every point computed from partial coverage."""
    frame = frame.sort_values(config.COL_YEAR)
    years = frame[config.COL_YEAR].to_numpy()
    values = frame[config.COL_VALUE].to_numpy()

    ax.plot(
        years,
        values,
        color=color,
        linewidth=width,
        label=label,
        zorder=zorder,
        solid_capstyle="round",
    )

    partial = frame[config.COL_COVERAGE].to_numpy() < 1
    if partial.any():
        ax.plot(
            years[partial],
            values[partial],
            linestyle="none",
            marker="o",
            markersize=MARKER_SIZE,
            markerfacecolor=SURFACE,
            markeredgecolor=color,
            markeredgewidth=1.6,
            zorder=zorder + 0.5,
        )


def _partial_coverage_handle() -> Line2D:
    """Legend key explaining the hollow-point encoding."""
    return Line2D(
        [],
        [],
        linestyle="none",
        marker="o",
        markersize=MARKER_SIZE,
        markerfacecolor=SURFACE,
        markeredgecolor=INK_MUTED,
        markeredgewidth=1.6,
        label="Partial indicator coverage",
    )


def _legend(ax: Axes, handles: list[Line2D] | None = None, **kwargs: object) -> None:
    """Frameless legend with ink-colored text."""
    legend = ax.legend(
        handles=handles,
        frameon=False,
        fontsize=9,
        labelcolor=INK_PRIMARY,
        handlelength=1.6,
        **kwargs,
    )
    for text in legend.get_texts():
        text.set_family(FONT_FAMILY)


def _spread(positions: dict[str, float], min_gap: float) -> dict[str, float]:
    """Nudge label positions apart so none sit closer than ``min_gap``.

    Works in whatever space the positions are given in - pass log values for a
    log axis. Order is preserved, so labels still line up with their lines.
    """
    ordered = sorted(positions.items(), key=lambda item: item[1])
    placed: list[tuple[str, float]] = []
    for key, pos in ordered:
        if placed and pos - placed[-1][1] < min_gap:
            pos = placed[-1][1] + min_gap
        placed.append((key, pos))

    # Re-centre so the nudging does not drift the whole stack upward.
    shift = np.mean([p for _, p in ordered]) - np.mean([p for _, p in placed])
    return {key: pos + shift for key, pos in placed}


def _weights_phrase(weights: Mapping[str, float] | None) -> str:
    """Describe the pillar weighting actually used, e.g. "equal weights"."""
    resolved = resolve_weights(weights)
    shares = list(resolved.values())
    if max(shares) - min(shares) < 1e-9:
        return "equal weights"
    parts = [f"{PILLAR_LABELS[p].lower()} {w:.0%}" for p, w in resolved.items()]
    return "weights: " + ", ".join(parts)


def _series_frame(index: pd.DataFrame, iso3: str, series: str) -> pd.DataFrame:
    return index[(index[config.COL_COUNTRY_ISO3] == iso3) & (index[config.COL_SERIES] == series)]


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #


def combined_index_figure(
    index: pd.DataFrame,
    *,
    method: Normalization | str | None = None,
    weights: Mapping[str, float] | None = None,
) -> Figure:
    """Combined index over time for every country.

    Args:
        index: Output of :func:`amber.modeling.index.compute_index`.
        method: The normalization the index was built with, for the caption.
        weights: The pillar weights it was built with, for the caption.

    Returns:
        The rendered figure.
    """
    scale_phrase, scale_footer = SCALE_NOTES[Normalization(method or config.DEFAULT_NORMALIZATION)]
    combined = index[index[config.COL_SERIES] == config.COMBINED_SERIES]
    years = sorted(combined[config.COL_YEAR].unique())
    fig, ax = _new_figure()

    for iso3 in config.COUNTRY_CODES:
        frame = combined[combined[config.COL_COUNTRY_ISO3] == iso3]
        if frame.empty:
            continue
        treated = iso3 == config.TREATED_COUNTRY
        _plot_series(
            ax,
            frame,
            COUNTRY_COLORS[iso3],
            config.COUNTRIES[iso3],
            width=EMPHASIS_WIDTH if treated else LINE_WIDTH,
            zorder=4 if treated else 3,
        )

    myanmar = combined[combined[config.COL_COUNTRY_ISO3] == config.TREATED_COUNTRY]
    if not myanmar.empty:
        last = myanmar.sort_values(config.COL_YEAR).iloc[-1]
        ax.annotate(
            config.COUNTRIES[config.TREATED_COUNTRY],
            (last[config.COL_YEAR], last[config.COL_VALUE]),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            color=INK_PRIMARY,
            family=FONT_FAMILY,
        )

    _year_axis(ax, years)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Combined development index (0.01–1)")
    _mark_context(ax, y_text=0.985)

    handles, _ = ax.get_legend_handles_labels()
    _legend(
        ax,
        [*handles, _partial_coverage_handle()],
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0,
    )

    _set_titles(
        fig,
        f"Combined development index, {years[0]}–{years[-1]}",
        f"Weighted geometric mean of the three pillars ({_weights_phrase(weights)}), "
        f"{scale_phrase}",
    )
    _set_wrapped_footer(fig, PARTIAL_COVERAGE_NOTE, _index_composition_note(), scale_footer)
    fig.subplots_adjust(left=0.07, right=0.80, top=0.84, bottom=0.13)
    return fig


def myanmar_pillars_figure(
    index: pd.DataFrame,
    *,
    method: Normalization | str | None = None,
) -> Figure:
    """Myanmar's three pillar sub-indices over time.

    Args:
        index: Output of :func:`amber.modeling.index.compute_index`.
        method: The normalization the index was built with, for the caption.

    Returns:
        The rendered figure.
    """
    scale_phrase, _ = SCALE_NOTES[Normalization(method or config.DEFAULT_NORMALIZATION)]
    country = config.TREATED_COUNTRY
    fig, ax = _new_figure()
    years: list[int] = []
    ends: dict[str, tuple[float, float]] = {}

    for pillar in Pillar:
        frame = _series_frame(index, country, str(pillar)).sort_values(config.COL_YEAR)
        if frame.empty:
            continue
        years.extend(frame[config.COL_YEAR].tolist())
        _plot_series(ax, frame, PILLAR_COLORS[pillar], PILLAR_LABELS[pillar])
        last = frame.iloc[-1]
        ends[str(pillar)] = (float(last[config.COL_YEAR]), float(last[config.COL_VALUE]))

    # Direct labels at the line ends, nudged apart - the light hues need them.
    spread = _spread({k: v for k, (_, v) in ends.items()}, min_gap=0.05)
    for pillar, (year, _) in ends.items():
        ax.text(
            year + 0.25,
            spread[pillar],
            PILLAR_LABELS[Pillar(pillar)],
            va="center",
            fontsize=9,
            color=INK_PRIMARY,
            family=FONT_FAMILY,
        )

    unique_years = sorted(set(years))
    _year_axis(ax, unique_years)
    ax.set_xlim(unique_years[0] - 0.5, unique_years[-1] + 2.6)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Pillar sub-index (0.01–1)")
    _mark_context(ax, y_text=0.985)

    handles, _ = ax.get_legend_handles_labels()
    _legend(ax, [*handles, _partial_coverage_handle()], loc="upper left")

    _set_titles(
        fig,
        f"Myanmar: pillar sub-indices, {unique_years[0]}–{unique_years[-1]}",
        f"Geometric mean of each pillar's normalized indicators, {scale_phrase}",
    )
    _set_wrapped_footer(
        fig,
        PARTIAL_COVERAGE_NOTE,
        _index_composition_note(),
        "Which series are missing: coverage_report.csv.",
    )
    fig.subplots_adjust(left=0.07, right=0.97, top=0.84, bottom=0.13)
    return fig


def gdp_pc_divergence_figure(panel: pd.DataFrame) -> Figure:
    """Real GDP per capita for every country, with Myanmar emphasised.

    Args:
        panel: Tidy panel from :mod:`amber.cleaning` (raw or interpolated).

    Returns:
        The rendered figure.
    """
    gdp = panel[
        (panel[config.COL_INDICATOR_ID] == config.GDP_PC_INDICATOR)
        & (panel[config.COL_YEAR] >= config.MODELING_WINDOW_START)
    ].dropna(subset=[config.COL_VALUE])
    years = sorted(gdp[config.COL_YEAR].unique())
    fig, ax = _new_figure()
    ax.set_yscale("log")

    ends: dict[str, tuple[float, float]] = {}
    for iso3 in config.COUNTRY_CODES:
        frame = gdp[gdp[config.COL_COUNTRY_ISO3] == iso3].sort_values(config.COL_YEAR)
        if frame.empty:
            continue
        treated = iso3 == config.TREATED_COUNTRY
        ax.plot(
            frame[config.COL_YEAR],
            frame[config.COL_VALUE],
            color=COUNTRY_COLORS[iso3] if treated else DE_EMPHASIS,
            linewidth=EMPHASIS_WIDTH if treated else LINE_WIDTH,
            zorder=4 if treated else 3,
            solid_capstyle="round",
            label=config.COUNTRIES[iso3] if treated else None,
        )
        last = frame.iloc[-1]
        ends[iso3] = (float(last[config.COL_YEAR]), float(last[config.COL_VALUE]))

    # Direct labels in log space so the spacing matches what the eye sees.
    spread = _spread({k: np.log10(v) for k, (_, v) in ends.items()}, min_gap=0.035)
    for iso3, (year, _) in ends.items():
        treated = iso3 == config.TREATED_COUNTRY
        ax.text(
            year + 0.25,
            10 ** spread[iso3],
            config.COUNTRIES[iso3],
            va="center",
            fontsize=9.5 if treated else 9,
            fontweight="bold" if treated else "normal",
            color=INK_PRIMARY if treated else INK_SECONDARY,
            family=FONT_FAMILY,
        )

    _year_axis(ax, years)
    ax.set_xlim(years[0] - 0.5, years[-1] + 2.4)
    # 1-1.5-2-3-5-7 per decade: enough labelled rungs to read a log axis.
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 1.5, 2.0, 3.0, 5.0, 7.0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_ylabel("GDP per capita, constant 2015 US$ (log scale)")
    _mark_context(ax, y_text=0.985)

    handles = [
        Line2D(
            [],
            [],
            color=COUNTRY_COLORS[config.TREATED_COUNTRY],
            linewidth=EMPHASIS_WIDTH,
            label=config.COUNTRIES[config.TREATED_COUNTRY],
        ),
        Line2D([], [], color=DE_EMPHASIS, linewidth=LINE_WIDTH, label="Donor-pool peers"),
    ]
    _legend(ax, handles, loc="upper left")

    _set_titles(
        fig,
        f"Real GDP per capita, {years[0]}–{years[-1]}",
        "Myanmar against the six regional peers used as its comparison pool. "
        "On a log scale, equal slopes are equal growth rates.",
    )
    _set_footer(fig, "Myanmar is reported on its fiscal-year basis (Oct–Sep).")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.12)
    return fig


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def save_figure(fig: Figure, path: Path) -> Path:
    """Write a figure as PNG.

    Args:
        fig: Figure to save.
        path: Destination; parent directories are created.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    logger.info("Wrote figure %s", path.name)
    return path


def render_all(
    index: pd.DataFrame,
    panel: pd.DataFrame,
    figures_dir: Path = config.FIGURES_DIR,
    *,
    method: Normalization | str | None = None,
    weights: Mapping[str, float] | None = None,
) -> tuple[Path, ...]:
    """Render and save the three reconstruction charts.

    Args:
        index: Output of :func:`amber.modeling.index.compute_index`.
        panel: The panel the index was built from, for the GDP chart.
        figures_dir: Destination directory.
        method: The normalization the index was built with.
        weights: The pillar weights it was built with.

    Returns:
        The paths written.
    """
    combined = combined_index_figure(index, method=method, weights=weights)
    pillars = myanmar_pillars_figure(index, method=method)
    return (
        save_figure(combined, figures_dir / config.FIGURE_COMBINED_ALL),
        save_figure(pillars, figures_dir / config.FIGURE_MYANMAR_PILLARS),
        save_figure(gdp_pc_divergence_figure(panel), figures_dir / config.FIGURE_GDP_PC_DIVERGENCE),
    )


# --------------------------------------------------------------------------- #
# Counterfactual charts
# --------------------------------------------------------------------------- #

SYNTHETIC_COLOR = INK_SECONDARY
"""Synthetic Myanmar's line, its leave-one-out band and its weight bars share a
neutral ink: it is a composite, not a country, so it gets no country hue."""

PLACEBO_COLOR = DE_EMPHASIS
PLACEBO_POOR_FIT_COLOR = GRID
WEIGHTS_FIGSIZE = (10.0, 4.6)
DASH = (0, (4, 3))

FISCAL_YEAR_NOTE = "Myanmar's WDI year runs Oct–Sep, so 2021 includes four pre-coup months."


def _format_value(value: float, outcome: SCOutcome, *, signed: bool = False) -> str:
    """Format a value in the outcome's units, e.g. ``-$413`` or ``-0.118``."""
    if outcome.is_currency:
        sign = "-" if value < 0 else ("+" if signed and value > 0 else "")
        return f"{sign}${abs(value):,.0f}"
    return f"{value:+.3f}" if signed else f"{value:.3f}"


def _donor_mix(result: SyntheticControlResult) -> str:
    """Describe the synthetic unit, e.g. ``61% Nepal + 39% Cambodia``."""
    parts = [
        f"{weight:.0%} {config.COUNTRIES.get(donor, donor)}"
        for donor, weight in result.weights.items()
        if weight >= result.settings.weight_threshold
    ]
    return " + ".join(parts)


def _fit_verdict(result: SyntheticControlResult, outcome: SCOutcome) -> str:
    """Say how far the pre-fit supports reading the gap as an effect."""
    rmse = _format_value(result.pre_rmse, outcome)
    share = f"{result.pre_rmse_share:.0%} of the pre-period level"
    start = result.settings.treatment_year
    if not result.credible:
        return (
            f"Pre-treatment RMSE {rmse} ({share}): the fit is poor, so the gap from "
            f"{start} is not a credible effect estimate."
        )
    return f"Pre-treatment RMSE {rmse} ({share}); the gap from {start} is the estimated effect."


def _value_axis(ax: Axes, outcome: SCOutcome) -> None:
    """Dollar tick labels for currency outcomes."""
    if outcome.is_currency:
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda v, _: f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}")
        )


def actual_vs_synthetic_figure(run: CounterfactualRun) -> Figure:
    """Actual against synthetic, with the leave-one-out range shaded.

    Args:
        run: Output of :func:`amber.modeling.synthetic_control.run`.

    Returns:
        The rendered figure.
    """
    base, outcome, settings = run.base, run.outcome, run.base.settings
    name = config.COUNTRIES.get(base.treated, base.treated)
    years = base.actual.index
    fig, ax = _new_figure()

    if run.leave_one_out:
        family = pd.concat(
            [base.synthetic, *(refit.synthetic for refit in run.leave_one_out.values())],
            axis=1,
        )
        ax.fill_between(
            family.index,
            family.min(axis=1),
            family.max(axis=1),
            color=SYNTHETIC_COLOR,
            alpha=0.12,
            linewidth=0,
            zorder=1,
            label="Leave-one-out range",
        )
    ax.plot(
        years,
        base.synthetic,
        color=SYNTHETIC_COLOR,
        linestyle=DASH,
        linewidth=LINE_WIDTH,
        zorder=3,
        label=f"Synthetic {name}",
    )
    ax.plot(
        years,
        base.actual,
        color=COUNTRY_COLORS.get(base.treated, SERIES_PALETTE[0]),
        linewidth=EMPHASIS_WIDTH,
        solid_capstyle="round",
        zorder=4,
        label=f"{name} (actual)",
    )

    # Bracket and label the latest-year gap.
    last = int(base.gap.dropna().index.max())
    actual, synthetic, gap = base.actual[last], base.synthetic[last], base.gap[last]
    label = f"{last} gap: {_format_value(gap, outcome, signed=True)}"
    if outcome.is_currency:
        label += f" ({gap / synthetic:+.0%})"
    ax.plot([last + 0.2] * 2, [actual, synthetic], color=INK_MUTED, linewidth=0.9, zorder=2)
    ax.text(
        last + 0.35,
        (actual + synthetic) / 2,
        label,
        va="center",
        fontsize=9,
        fontweight="bold",
        color=INK_PRIMARY,
        family=FONT_FAMILY,
    )

    _year_axis(ax, list(years))
    ax.set_xlim(years.min() - 0.5, years.max() + 3.6)
    units = outcome.units + (f" (rebased, {settings.pre_start} = 100)" if settings.rebase else "")
    ax.set_ylabel(units)
    _value_axis(ax, outcome)
    _mark_context(ax, y_text=0.985, dashed_treatment=True)

    handles, _ = ax.get_legend_handles_labels()
    order = [h for key in ("actual", "Synthetic", "Leave") for h in handles if key in h.get_label()]
    _legend(ax, order, loc="upper left")

    _set_titles(
        fig,
        f"{outcome.label}: {name} and synthetic {name}, {years.min()}–{years.max()}",
        f"Synthetic {name} = {_donor_mix(base)}, fitted {settings.pre_start}–{settings.pre_end}. "
        + _fit_verdict(base, outcome),
    )
    _set_footer(fig, "Shaded: range across leave-one-out refits.", FISCAL_YEAR_NOTE)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.12)
    return fig


def placebo_gaps_figure(run: CounterfactualRun) -> Figure:
    """The treated unit's gap against every in-space placebo's.

    Args:
        run: Output of :func:`amber.modeling.synthetic_control.run`.

    Returns:
        The rendered figure.
    """
    base, outcome, settings = run.base, run.outcome, run.base.settings
    placebos = run.placebo_space
    name = config.COUNTRIES.get(base.treated, base.treated)
    color = COUNTRY_COLORS.get(base.treated, SERIES_PALETTE[0])
    fig, ax = _new_figure()

    ax.axhline(0, color=AXIS, linewidth=0.9, zorder=1)
    poor_limit = config.SC_PLACEBO_POOR_FIT_MULTIPLE * base.pre_rmse
    any_poor = False
    for fit in placebos.placebos.values():
        poor = fit.pre_rmse > poor_limit
        any_poor |= poor
        ax.plot(
            fit.gap.index,
            fit.gap,
            color=PLACEBO_POOR_FIT_COLOR if poor else PLACEBO_COLOR,
            linewidth=1.2 if poor else 1.6,
            zorder=2,
        )
    ax.plot(
        base.gap.index,
        base.gap,
        color=color,
        linewidth=EMPHASIS_WIDTH,
        solid_capstyle="round",
        zorder=4,
    )
    last = int(base.gap.dropna().index.max())
    ax.annotate(
        name,
        (last, base.gap[last]),
        xytext=(8, 0),
        textcoords="offset points",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=INK_PRIMARY,
        family=FONT_FAMILY,
    )

    years = list(base.gap.index)
    _year_axis(ax, years)
    ax.set_xlim(min(years) - 0.5, max(years) + 1.6)
    ax.set_ylabel(f"Actual minus synthetic: {outcome.units}")
    _value_axis(ax, outcome)
    _mark_context(ax, y_text=0.985, dashed_treatment=True)

    handles = [
        Line2D([], [], color=color, linewidth=EMPHASIS_WIDTH, label=name),
        Line2D([], [], color=PLACEBO_COLOR, linewidth=1.6, label="Donors, each placebo-treated"),
    ]
    if any_poor:
        handles.append(
            Line2D(
                [],
                [],
                color=PLACEBO_POOR_FIT_COLOR,
                linewidth=1.2,
                label="Placebo with poor pre-fit",
            )
        )
    _legend(ax, handles, loc="lower left")

    ratios = placebos.ratios
    n_units = len(ratios)
    rank = int((ratios >= ratios[base.treated]).sum())
    _set_titles(
        fig,
        f"{outcome.label}: {name}'s gap against placebo gaps",
        f"Each donor refitted as if it had been treated in {settings.treatment_year}. "
        f"{name}'s post/pre RMSE ratio ranks {rank} of {n_units}: pseudo p = "
        f"{placebos.p_value:.2f} (the smallest possible with {n_units} units is "
        f"{1 / n_units:.2f}).",
    )
    notes = [config.SOURCE_NOTE]
    if any_poor:
        notes.append(
            f"Faint: pre-RMSE over {config.SC_PLACEBO_POOR_FIT_MULTIPLE:g}x {name}'s "
            "(edge of the donor hull); still counted in the p-value."
        )
    fig.text(
        0.06,
        0.025,
        "  ·  ".join(notes),
        fontsize=8,
        color=INK_MUTED,
        family=FONT_FAMILY,
        ha="left",
        va="bottom",
    )
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.12)
    return fig


def donor_weights_figure(run: CounterfactualRun) -> Figure:
    """What synthetic Myanmar is made of.

    Args:
        run: Output of :func:`amber.modeling.synthetic_control.run`.

    Returns:
        The rendered figure.
    """
    base, outcome, settings = run.base, run.outcome, run.base.settings
    name = config.COUNTRIES.get(base.treated, base.treated)
    ordered = sorted(base.weights.items(), key=lambda kv: kv[1])  # largest on top
    labels = [config.COUNTRIES.get(donor, donor) for donor, _ in ordered]
    shares = [weight * 100 for _, weight in ordered]

    fig = Figure(figsize=WEIGHTS_FIGSIZE, dpi=DPI, facecolor=SURFACE)
    ax = fig.add_subplot()
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.tick_params(
        which="both",
        length=0,
        labelsize=9.5,
        labelcolor=INK_PRIMARY,
        labelfontfamily=FONT_FAMILY,
        pad=6,
    )
    ax.set_xticks([])

    ax.barh(labels, shares, height=0.62, color=SYNTHETIC_COLOR, zorder=2)
    for y, share in enumerate(shares):
        ax.text(
            share + 1.2,
            y,
            f"{share:.0f}%",
            va="center",
            fontsize=9,
            fontweight="bold" if share >= settings.weight_threshold * 100 else "normal",
            color=INK_PRIMARY if share >= settings.weight_threshold * 100 else INK_MUTED,
            family=FONT_FAMILY,
        )
    ax.set_xlim(0, 110)

    _set_titles(
        fig,
        f"{outcome.label}: what synthetic {name} is made of",
        f"Convex weights, non-negative and summing to 100%, fitted {settings.pre_start}–"
        f"{settings.pre_end}. Effective number of donors: {base.n_effective_donors:.1f}.",
    )
    notes = [config.SOURCE_NOTE]
    if base.dropped_donors:
        dropped = ", ".join(config.COUNTRIES.get(d, d) for d in base.dropped_donors)
        notes.append(f"Dropped for incomplete data: {dropped}.")
    fig.text(
        0.06,
        0.03,
        "  ·  ".join(notes),
        fontsize=8,
        color=INK_MUTED,
        family=FONT_FAMILY,
        ha="left",
        va="bottom",
    )
    fig.subplots_adjust(left=0.15, right=0.95, top=0.76, bottom=0.14)
    return fig


def render_counterfactual(
    run: CounterfactualRun,
    figures_dir: Path = config.FIGURES_DIR,
) -> tuple[Path, ...]:
    """Render and save the three charts for one outcome.

    Args:
        run: Output of :func:`amber.modeling.synthetic_control.run`.
        figures_dir: Destination directory.

    Returns:
        The paths written.
    """
    slug = run.outcome.slug
    return (
        save_figure(
            actual_vs_synthetic_figure(run),
            figures_dir / config.SC_FIGURE_ACTUAL.format(slug=slug),
        ),
        save_figure(
            placebo_gaps_figure(run),
            figures_dir / config.SC_FIGURE_GAPS.format(slug=slug),
        ),
        save_figure(
            donor_weights_figure(run),
            figures_dir / config.SC_FIGURE_WEIGHTS.format(slug=slug),
        ),
    )


# --------------------------------------------------------------------------- #
# Future-scenario charts
# --------------------------------------------------------------------------- #

SCENARIO_COLORS: dict[str, str] = dict(
    zip((s.name for s in config.SCENARIOS), SERIES_PALETTE, strict=False)
)
"""One fixed hue per scenario, in config order - scenarios are the entities here."""

HISTORY_COLOR = INK_PRIMARY
BAND_ALPHA = 0.16
BACKTEST_FIGSIZE = (10.0, 8.6)
STOCKS_FIGSIZE = (10.0, 7.4)

STOCK_LABELS: dict[str, str] = {
    "K": "Physical capital per head (2015 US$)",
    "H": "Human capital (2011 = 1)",
    "I": "Connectivity: internet users (%)",
    "S": "Institutional stability (reform era = 1)",
}


PARAMETER_LABELS: dict[str, str] = {
    "connectivity_tfp": "κ (connectivity → productivity)",
    "savings_rate": "the savings rate",
}


def _ensemble_phrase(future: FutureRun) -> str:
    """What the bands span: the jitter and, where profiled, the unidentified parameters."""
    phrase = (
        f"Bands: p10–p90 of a {config.SD_ENSEMBLE_SIZE}-member ensemble, calibrated "
        f"parameters jittered ±{config.SD_PARAM_JITTER:.0%}"
    )
    if future.profile:
        names = [PARAMETER_LABELS.get(n, n) for n in future.profile[0].values]
        phrase += (
            f"; {' and '.join(names)}, which the data cannot pin down, spread over their "
            "plausible ranges with history refitted at each"
        )
    return phrase + "."


def _set_wrapped_footer(fig: Figure, *notes: str, width: int = 175) -> None:
    """Source line and caveats, wrapped - for the future charts' longer notes."""
    fig.text(
        0.06,
        0.025,
        textwrap.fill("  ·  ".join((config.SOURCE_NOTE, *notes)), width),
        fontsize=8,
        color=INK_MUTED,
        family=FONT_FAMILY,
        ha="left",
        va="bottom",
    )


def _signed_dollars(value: float) -> str:
    """+$1,234 / -$1,234, escaped so matplotlib does not read a $ pair as math."""
    return f"{'+' if value >= 0 else '-'}\\${abs(value):,.0f}"


def _paired_gap_phrase(future: FutureRun, series: str, fmt: Callable[[float], str]) -> str:
    """The counterfactual's member-by-member lead over the baseline in the final year."""
    result = future.results.get(config.SD_COUNTERFACTUAL_SCENARIO)
    if result is None or result.gaps is None:
        return ""
    rows = result.gaps[result.gaps[config.COL_SERIES] == series].set_index(config.COL_YEAR)
    end = rows.loc[rows.index.max()]
    return (
        f" Paired member by member, no coup ends {fmt(end['p50'])} above actual "
        f"continuation in {int(rows.index.max())} (p10–p90 {fmt(end['p10'])} to "
        f"{fmt(end['p90'])}), and above it in {end['share_above']:.0%} of members."
    )


def _composition_note(future: FutureRun) -> str:
    """How much of the history-to-scenario step is composition, and how much misfit.

    History scores only the indicators Myanmar reports; scenarios score all of
    them. Stating both parts from the run keeps a coverage step from being read
    as a scenario effect.
    """
    bt = future.backtest
    year = bt.last_observed_year
    reported = int(bt.actual.loc[year].notna().sum())
    return (
        f"History scores the indicators Myanmar reports ({reported} of "
        f"{len(config.INDEX_INDICATORS)} in {year}; hollow points); scenarios score all "
        f"{len(config.INDEX_INDICATORS)}. In {year} that alone lifts the modeled index by "
        f"{bt.composition_gap:+.3f} - a composition step, not a scenario effect - and like for "
        f"like the model sits {bt.fit_gap:+.3f} from history."
    )


def _gate_phrase(future: FutureRun) -> str:
    """The credibility verdict in words - every future chart opens with it."""
    bt = future.backtest
    start, end = config.SD_BACKTEST_START, config.SD_BACKTEST_END
    if future.credible:
        return (
            f"Scenarios, not forecasts: calibrated on {start}–{end} "
            f"(backtest error {bt.overall:.3f} on the index scale)."
        )
    return (
        f"Illustrative dynamics, not a calibrated projection: the backtest error "
        f"({bt.overall:.3f}) exceeds {config.SD_CREDIBLE_NRMSE:.2f}."
    )


def _mark_panel(ax: Axes) -> None:
    """COVID band and dashed treatment line, unlabelled - for small multiples."""
    for year in config.COVID_CONFOUNDED_YEARS:
        ax.axvspan(year - 0.5, year + 0.5, color=CONTEXT_FILL, zorder=0, linewidth=0)
    ax.axvline(config.TREATMENT_YEAR, color=INK_MUTED, linewidth=0.8, linestyle=DASH, zorder=1)


def _mark_projection(ax: Axes, y_text: float) -> None:
    """Label where the projection begins."""
    start = config.SD_PROJECTION_START
    ax.axvline(start - 0.5, color=GRID, linewidth=0.8, zorder=0)
    ax.text(
        start - 0.3,
        y_text,
        "Projection",
        transform=ax.get_xaxis_transform(),
        ha="left",
        va="top",
        fontsize=8,
        color=INK_MUTED,
        family=FONT_FAMILY,
    )


def _scenario_band(
    ax: Axes,
    result: SimulationResult,
    series: str,
    *,
    start: int,
    label: str | None = None,
) -> tuple[int, float]:
    """Draw one scenario's p10-p90 band and p50 line from ``start``; return its end."""
    color = SCENARIO_COLORS.get(result.scenario.name, INK_SECONDARY)
    low = result.band(series, "p10").loc[start:]
    mid = result.band(series, "p50").loc[start:]
    high = result.band(series, "p90").loc[start:]
    ax.fill_between(low.index, low, high, color=color, alpha=BAND_ALPHA, linewidth=0, zorder=2)
    ax.plot(
        mid.index,
        mid,
        color=color,
        linewidth=LINE_WIDTH,
        zorder=3,
        solid_capstyle="round",
        label=label or result.scenario.label,
    )
    return int(mid.index[-1]), float(mid.iloc[-1])


def _band_start(result: SimulationResult) -> int:
    """Where a scenario's band begins: the year before it leaves history.

    A scenario that never leaves history continues it from the last observed
    year, so identical paths are not drawn on top of each other.
    """
    year = divergence_year(result.scenario)
    return config.SD_BACKTEST_END if year is None else max(year - 1, config.SD_BACKTEST_START)


def _label_ends(ax: Axes, ends: dict[str, tuple[int, float]], min_gap: float) -> None:
    """Direct-label each scenario at its final value, nudged apart."""
    spread = _spread({name: value for name, (_, value) in ends.items()}, min_gap=min_gap)
    labels = {s.name: s.label for s in config.SCENARIOS}
    for name, (year, _) in ends.items():
        ax.text(
            year + 0.35,
            spread[name],
            labels.get(name, name),
            va="center",
            fontsize=9,
            color=INK_PRIMARY,
            family=FONT_FAMILY,
        )


def future_fan_figure(future: FutureRun) -> Figure:
    """The combined index: history, then every scenario as a p10-p90 band.

    Args:
        future: Output of :func:`amber.modeling.system_dynamics.run`.

    Returns:
        The rendered figure.
    """
    bt = future.backtest
    fig, ax = _new_figure()

    history = pd.DataFrame(
        {config.COL_VALUE: bt.combined_actual, config.COL_COVERAGE: bt.combined_coverage}
    ).dropna(subset=[config.COL_VALUE])
    _plot_series(
        ax,
        history.rename_axis(config.COL_YEAR).reset_index(),
        HISTORY_COLOR,
        "History",
        width=EMPHASIS_WIDTH,
        zorder=4,
    )
    # The fitted path runs to the last observed year, so a band that continues
    # the model visibly starts where the model is - its post-coup miss shows.
    fitted = bt.combined_modeled
    ax.plot(
        fitted.index,
        fitted,
        color=INK_MUTED,
        linewidth=1.3,
        linestyle=DASH,
        zorder=3,
        label="Model fitted to history",
    )

    ends = {
        name: _scenario_band(ax, result, config.COMBINED_SERIES, start=_band_start(result))
        for name, result in future.results.items()
    }
    _label_ends(ax, ends, min_gap=0.022)

    _year_axis(ax, list(range(config.SD_BACKTEST_START, config.SD_HORIZON_END + 1)))
    ax.set_xlim(config.SD_BACKTEST_START - 0.5, config.SD_HORIZON_END + 4.2)
    ax.set_ylabel("Combined development index (0.01–1)")
    _mark_context(ax, y_text=0.985, dashed_treatment=True)
    _mark_projection(ax, y_text=0.93)

    handles, _ = ax.get_legend_handles_labels()
    _legend(ax, [*handles[:2], _partial_coverage_handle()], loc="upper left")

    _set_titles(
        fig,
        f"Myanmar's development index: {len(future.results)} scenarios to {config.SD_HORIZON_END}",
        f"{_gate_phrase(future)} Each band starts where its scenario leaves history; "
        f"policy levers apply from {config.SD_PROJECTION_START}.",
    )
    notes = [_composition_note(future), _ensemble_phrase(future)]
    sc_check = next((c for c in future.sc_checks if c.outcome == config.COMBINED_SERIES), None)
    if sc_check is not None and not sc_check.sc_credible:
        notes.append("Phase 3's counterfactual for this index is not credible, so not overlaid.")
    _set_wrapped_footer(fig, *notes)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.84, bottom=0.17)
    return fig


def future_gdp_figure(future: FutureRun, sc_paths: pd.DataFrame | None = None) -> Figure:
    """GDP per capita under no-coup against actual continuation.

    Overlays the phase 3 synthetic control over the overlap where it is credible,
    and says how far the no-coup scenario sits from it.

    Args:
        future: Output of :func:`amber.modeling.system_dynamics.run`.
        sc_paths: Phase 3 ``synthetic_control`` table, for the overlay.

    Returns:
        The rendered figure.
    """
    bt = future.backtest
    gdp = config.SD_OUTPUT_INDICATOR
    pair = [config.SD_COUNTERFACTUAL_SCENARIO, config.SD_BASELINE_SCENARIO]
    fig, ax = _new_figure()

    actual = bt.actual[gdp].dropna()
    ax.plot(
        actual.index,
        actual,
        color=HISTORY_COLOR,
        linewidth=EMPHASIS_WIDTH,
        zorder=5,
        solid_capstyle="round",
        label="Actual",
    )
    ax.plot(
        bt.modeled.index,
        bt.modeled[gdp],
        color=INK_MUTED,
        linewidth=1.3,
        linestyle=DASH,
        zorder=4,
        label="Model fitted to history",
    )
    ends = {}
    for name in pair:
        if name in future.results:
            result = future.results[name]
            ends[name] = _scenario_band(ax, result, gdp, start=_band_start(result))

    check = next((c for c in future.sc_checks if c.outcome == gdp), None)
    overlay = check is not None and check.sc_credible and sc_paths is not None
    if overlay:
        synthetic = sc_paths[
            (sc_paths[config.COL_OUTCOME] == gdp) & (sc_paths[config.COL_SERIES] == "synthetic")
        ].set_index(config.COL_YEAR)[config.COL_VALUE]
        ax.plot(
            synthetic.index,
            synthetic,
            color=SYNTHETIC_COLOR,
            linestyle=DASH,
            linewidth=LINE_WIDTH,
            zorder=4,
            label="Synthetic control (phase 3)",
        )

    _label_ends(ax, ends, min_gap=110)
    _year_axis(ax, list(range(config.SD_BACKTEST_START, config.SD_HORIZON_END + 1)))
    ax.set_xlim(config.SD_BACKTEST_START - 0.5, config.SD_HORIZON_END + 4.2)
    ax.set_ylabel("GDP per capita, constant 2015 US$")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    _mark_context(ax, y_text=0.985, dashed_treatment=True)
    _mark_projection(ax, y_text=0.93)

    handles, labels = ax.get_legend_handles_labels()
    keep = [
        h
        for h, lab in zip(handles, labels, strict=True)
        if lab in {"Actual", "Model fitted to history", "Synthetic control (phase 3)"}
    ]
    _legend(ax, keep, loc="upper left")

    comparison = ""
    if check is not None and check.sc_credible and not np.isnan(check.deviation):
        verdict = "within" if check.consistent else "beyond"
        comparison = (
            f" Over {check.years[0]}–{check.years[-1]} no-coup runs up to {check.deviation:.0%} "
            f"from the synthetic control, {verdict} the {config.SD_SC_TOLERANCE:.0%} tolerance"
            + ("." if check.consistent else ": read it as an optimistic scenario.")
        )
    _set_titles(
        fig,
        f"Real GDP per capita: no coup against actual continuation, to {config.SD_HORIZON_END}",
        f"{_gate_phrase(future)}{_paired_gap_phrase(future, gdp, _signed_dollars)}{comparison}",
    )
    last = int(actual.index.max())
    miss = bt.modeled[gdp][last] / actual[last] - 1
    _set_wrapped_footer(
        fig,
        f"Model vs actual in {last}: {miss:+.1%}, so actual continuation starts from the "
        "model's own path.",
        _ensemble_phrase(future),
        FISCAL_YEAR_NOTE,
    )
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.14)
    return fig


def backtest_figure(future: FutureRun) -> Figure:
    """Each modeled indicator against Myanmar's actuals over the calibration window.

    Args:
        future: Output of :func:`amber.modeling.system_dynamics.run`.

    Returns:
        The rendered figure.
    """
    bt = future.backtest
    indicators = list(bt.modeled.columns)
    n_cols = 3
    n_rows = -(-len(indicators) // n_cols)
    fig = Figure(figsize=BACKTEST_FIGSIZE, dpi=DPI, facecolor=SURFACE)
    axes = fig.subplots(n_rows, n_cols, squeeze=False)

    for ax, indicator_id in zip(axes.flat, indicators, strict=False):
        _style_axis(ax, labelsize=7.5)
        _mark_panel(ax)
        actual = bt.actual[indicator_id]
        ax.plot(
            actual.index,
            actual,
            linestyle="none",
            marker="o",
            markersize=4,
            color=HISTORY_COLOR,
            zorder=4,
        )
        ax.plot(
            bt.modeled.index,
            bt.modeled[indicator_id],
            color=SERIES_PALETTE[0],
            linewidth=1.8,
            zorder=3,
        )
        name = config.INDICATORS_BY_ID[indicator_id].name
        ax.set_title(
            f"{textwrap.shorten(name, 34, placeholder='…')}\nnRMSE {bt.nrmse[indicator_id]:.3f}",
            fontsize=8.5,
            color=INK_PRIMARY,
            family=FONT_FAMILY,
            loc="left",
        )
        ax.set_xticks([config.SD_BACKTEST_START, config.TREATMENT_YEAR, config.SD_BACKTEST_END])
    for ax in list(axes.flat)[len(indicators) :]:
        ax.set_visible(False)

    handles = [
        Line2D(
            [], [], linestyle="none", marker="o", markersize=5, color=HISTORY_COLOR, label="Actual"
        ),
        Line2D([], [], color=SERIES_PALETTE[0], linewidth=1.8, label="Calibrated model"),
    ]
    legend = fig.legend(
        handles=handles,
        loc="upper right",
        bbox_to_anchor=(0.97, 0.955),
        frameon=False,
        fontsize=9,
        labelcolor=INK_PRIMARY,
        ncols=2,
    )
    for text in legend.get_texts():
        text.set_family(FONT_FAMILY)

    verdict = "credible" if future.credible else "not credible"
    _set_titles(
        fig,
        f"Backtest: the calibrated model against Myanmar, {config.SD_BACKTEST_START}–"
        f"{config.SD_BACKTEST_END}",
        f"In-sample fit. Overall error {bt.overall:.3f} on the index scale ({verdict} at "
        f"{config.SD_CREDIBLE_NRMSE:.2f}); per-panel nRMSE in index units.",
    )
    _set_footer(fig, "Dashed line: the coup. Shaded: COVID year.")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.07, hspace=0.62, wspace=0.28)
    return fig


def stocks_figure(future: FutureRun) -> Figure:
    """The four stocks under every scenario (ensemble medians).

    Args:
        future: Output of :func:`amber.modeling.system_dynamics.run`.

    Returns:
        The rendered figure.
    """
    fig = Figure(figsize=STOCKS_FIGSIZE, dpi=DPI, facecolor=SURFACE)
    axes = fig.subplots(2, 2, squeeze=False)

    for ax, stock in zip(axes.flat, STOCK_LABELS, strict=True):
        _style_axis(ax, labelsize=8)
        _mark_panel(ax)
        for name, result in future.results.items():
            median = result.band(stock, "p50")
            ax.plot(
                median.index,
                median,
                color=SCENARIO_COLORS.get(name, INK_SECONDARY),
                linewidth=1.8,
                zorder=3,
                label=result.scenario.label,
            )
        ax.set_title(
            STOCK_LABELS[stock], fontsize=9.5, color=INK_PRIMARY, family=FONT_FAMILY, loc="left"
        )
        ax.set_xticks(range(config.SD_BACKTEST_START, config.SD_HORIZON_END + 1, 6))

    handles, _ = axes.flat[0].get_legend_handles_labels()
    legend = fig.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.055, 0.905),
        frameon=False,
        fontsize=9,
        labelcolor=INK_PRIMARY,
        ncols=len(handles),
    )
    for text in legend.get_texts():
        text.set_family(FONT_FAMILY)

    _set_titles(
        fig,
        f"The model's stocks under each scenario, {config.SD_BACKTEST_START}–"
        f"{config.SD_HORIZON_END}",
        f"{_gate_phrase(future)} Lines are ensemble medians.",
    )
    _set_footer(fig, "Dashed line: the coup. Shaded: COVID year.")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.8, bottom=0.08, hspace=0.42, wspace=0.22)
    return fig


def render_future(
    future: FutureRun,
    sc_paths: pd.DataFrame | None = None,
    figures_dir: Path = config.FIGURES_DIR,
) -> tuple[Path, ...]:
    """Render and save the four future-layer charts.

    Args:
        future: Output of :func:`amber.modeling.system_dynamics.run`.
        sc_paths: Phase 3 ``synthetic_control`` table, for the GDP overlay.
        figures_dir: Destination directory.

    Returns:
        The paths written.
    """
    return (
        save_figure(future_fan_figure(future), figures_dir / config.SD_FIGURE_FAN),
        save_figure(future_gdp_figure(future, sc_paths), figures_dir / config.SD_FIGURE_GDP),
        save_figure(backtest_figure(future), figures_dir / config.SD_FIGURE_BACKTEST),
        save_figure(stocks_figure(future), figures_dir / config.SD_FIGURE_STOCKS),
    )


# --------------------------------------------------------------------------- #
# Historical charts (phase 7)
# --------------------------------------------------------------------------- #
#
# Two encodings carry the layer's caveats wherever its data are drawn:
#   * low reliability (Myanmar before 1990): a hatched background band, and the
#     line itself dotted and lighter - so the cue survives print and CVD;
#   * separate rulers: Maddison PPP, when present, gets its own panel and axis,
#     never a segment of the constant-US$ line.

COMPARATOR_COLOR = INK_SECONDARY
"""Thailand is a reference line, not one of the panel's seven countries, so it
takes ink rather than a categorical slot (which would cycle the palette)."""

DIVERGENCE_PATH_COLOR = INK_SECONDARY
"""The divergence path is a construct, like synthetic Myanmar, so it is neutral."""

LOW_RELIABILITY_ALPHA = 0.5
LOW_RELIABILITY_DASH = (0, (1, 1.8))
HATCH = "///"
WINDOW_COLOR = INK_SECONDARY
"""The modeling-window bracket: ink, thin, unhatched - nothing like the
reliability cue, because it marks a different concept."""
HATCH_COLOR = "#d5d4cc"
"""Between GRID and AXIS: legible as a band and in the legend key, quieter than the data."""
GAP_ALPHA = 0.10
HISTORICAL_FIGSIZE = (10.0, 6.0)
MADDISON_WIDTH_RATIO = (1.0, 4.0)


def _wdi_levels(historical: pd.DataFrame, indicator: str = config.GDP_PC_INDICATOR) -> pd.DataFrame:
    """Wide year x country levels of one series, WDI constant-US$ ruler only."""
    rows = historical[
        (historical[config.COL_INDICATOR_ID] == indicator)
        & (historical[config.COL_SOURCE] == str(config.HistoricalSource.WB_CONSTANT))
    ]
    return rows.pivot(
        index=config.COL_YEAR, columns=config.COL_COUNTRY_ISO3, values=config.COL_VALUE
    )


def _plot_reliability_line(
    ax: Axes,
    series: pd.Series,
    color: str,
    label: str,
    *,
    cutoff: int | None,
    width: float = LINE_WIDTH,
    zorder: float = 3,
) -> None:
    """One line, dotted and lighter before ``cutoff`` (low reliability), solid after.

    The two segments share the cutoff year, so the line stays continuous.
    """
    series = series.dropna().sort_index()
    if cutoff is None or series.index.min() >= cutoff:
        ax.plot(series.index, series, color=color, linewidth=width, zorder=zorder, label=label)
        return
    low, standard = series.loc[:cutoff], series.loc[cutoff:]
    ax.plot(
        low.index,
        low,
        color=color,
        alpha=LOW_RELIABILITY_ALPHA,
        linewidth=width,
        linestyle=LOW_RELIABILITY_DASH,
        dash_capstyle="round",
        zorder=zorder,
    )
    ax.plot(standard.index, standard, color=color, linewidth=width, zorder=zorder, label=label)


def _mark_low_reliability(ax: Axes, start: float, cutoff: float) -> None:
    """Hatch the low-reliability years; :func:`_low_reliability_band_handle` keys it."""
    ax.axvspan(
        start, cutoff, facecolor="none", edgecolor=HATCH_COLOR, hatch=HATCH, linewidth=0, zorder=0
    )


def _low_reliability_band_handle(cutoff: int) -> Patch:
    return Patch(
        facecolor="none",
        edgecolor=HATCH_COLOR,
        hatch=HATCH,
        linewidth=0,
        label=f"Low reliability: Myanmar before {cutoff}",
    )


def _tex_safe(text: str) -> str:
    """Escape dollar signs, which matplotlib would read in pairs as mathtext."""
    return text.replace("$", "\\$")


def _mark_events(ax: Axes, end: int) -> None:
    """Quiet dated markers, labels alternating between two rows so neighbours clear."""
    for i, event in enumerate(config.HISTORICAL_EVENTS):
        ax.axvline(event.year, color=INK_MUTED, linewidth=0.7, zorder=1)
        near_end = event.year > end - 8
        ax.text(
            event.year + (-0.4 if near_end else 0.4),
            0.985 - 0.055 * (i % 2),
            event.label,
            transform=ax.get_xaxis_transform(),
            ha="right" if near_end else "left",
            va="top",
            fontsize=8,
            color=INK_SECONDARY,
            family=FONT_FAMILY,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.0},
            zorder=5,
        )


def _mark_modeling_window(ax: Axes, start: int, end: int, y: float = 0.86) -> None:
    """Bracket the modeling window along the top of the plot - a scope cue.

    Deliberately unlike the hatching (data quality): a thin horizontal rule with
    end caps and a label, in axes-fraction height so it ignores the data scale.
    """
    transform = ax.get_xaxis_transform()
    ax.plot(
        [start, end],
        [y, y],
        transform=transform,
        color=WINDOW_COLOR,
        linewidth=1.0,
        marker="|",
        markersize=7,
        markeredgewidth=1.0,
        solid_capstyle="butt",
        zorder=5,
    )
    ax.text(
        (start + end) / 2,
        y - 0.015,
        f"Modeling window, {start}–{end}",
        transform=transform,
        ha="center",
        va="top",
        fontsize=8,
        color=WINDOW_COLOR,
        family=FONT_FAMILY,
        zorder=5,
    )


def _modeling_window_handle() -> Line2D:
    return Line2D(
        [],
        [],
        color=WINDOW_COLOR,
        linewidth=1.0,
        marker="|",
        markersize=7,
        markeredgewidth=1.0,
        label=f"Modeling window ({config.MODELING_WINDOW_START}+): scope, not data quality",
    )


def _dollar_log_axis(ax: Axes, label: str, subs: tuple[float, ...] = (1.0, 2.0, 5.0)) -> None:
    """Log y-axis with labelled dollar rungs (1-2-5 per decade by default)."""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=subs))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_ylabel(label)


def _decade_axis(ax: Axes, first: int, last: int, *, pad_right: float) -> None:
    ax.set_xlim(first - 0.5, last + pad_right)
    ax.set_xticks(range(first - first % 10, last + 1, 10))


def _low_reliability_handle() -> Line2D:
    return Line2D(
        [],
        [],
        color=COUNTRY_COLORS[config.TREATED_COUNTRY],
        alpha=LOW_RELIABILITY_ALPHA,
        linewidth=EMPHASIS_WIDTH,
        linestyle=LOW_RELIABILITY_DASH,
        label=f"{config.COUNTRIES[config.TREATED_COUNTRY]}, low reliability",
    )


def historical_gdp_figure(historical: pd.DataFrame) -> Figure:
    """Myanmar's GDP per capita 1960 onward, with Thailand and dated markers.

    The pre-1990 segment carries the low-reliability cue. If the historical table
    holds Maddison rows, they are drawn in a separate left panel on their own
    axis (2011 int$, PPP) - a different ruler, never joined to the WDI line.

    Args:
        historical: The ``historical`` table from :mod:`amber.historical`.

    Returns:
        The rendered figure.
    """
    treated = config.TREATED_COUNTRY
    default = next(
        s for s in config.DIVERGENCE_SCENARIOS if s.name == config.DIVERGENCE_DEFAULT_SCENARIO
    )
    comparator = config.DIVERGENCE_COMPARATORS[default.comparator]
    levels = _wdi_levels(historical)
    maddison = historical[historical[config.COL_SOURCE] == str(config.HistoricalSource.MADDISON)]
    cutoff = config.RELIABILITY_LOW_BEFORE.get(treated)
    first, last = int(levels.index.min()), int(levels.index.max())

    fig = Figure(figsize=HISTORICAL_FIGSIZE, dpi=DPI, facecolor=SURFACE)
    if maddison.empty:
        ax = fig.add_subplot()
    else:
        grid = fig.add_gridspec(1, 2, width_ratios=MADDISON_WIDTH_RATIO, wspace=0.16)
        early = fig.add_subplot(grid[0])
        ax = fig.add_subplot(grid[1])
        _maddison_panel(early, maddison, cutoff)
    _style_axis(ax)
    _dollar_log_axis(ax, "GDP per capita, constant 2015 US$ (log scale)")

    if cutoff is not None:
        _mark_low_reliability(ax, first - 0.5, cutoff)
    _mark_events(ax, last)
    _mark_modeling_window(ax, config.MODELING_WINDOW_START, last)

    ends: dict[str, tuple[float, float]] = {}
    for unit in comparator.units:
        if unit in levels:
            line = levels[unit].dropna()
            ax.plot(line.index, line, color=COMPARATOR_COLOR, linewidth=LINE_WIDTH, zorder=3)
            ends[config.HISTORICAL_COUNTRIES[unit]] = (float(line.index[-1]), float(line.iloc[-1]))
    mmr = levels[treated].dropna()
    _plot_reliability_line(
        ax,
        mmr,
        COUNTRY_COLORS[treated],
        config.COUNTRIES[treated],
        cutoff=cutoff,
        width=EMPHASIS_WIDTH,
        zorder=4,
    )
    ends[config.COUNTRIES[treated]] = (float(mmr.index[-1]), float(mmr.iloc[-1]))

    spread = _spread({k: np.log10(v) for k, (_, v) in ends.items()}, min_gap=0.05)
    for name, (year, _) in ends.items():
        bold = name == config.COUNTRIES[treated]
        ax.text(
            year + 0.6,
            10 ** spread[name],
            name,
            va="center",
            fontsize=9.5 if bold else 9,
            fontweight="bold" if bold else "normal",
            color=INK_PRIMARY if bold else INK_SECONDARY,
            family=FONT_FAMILY,
        )
    _decade_axis(ax, first, last, pad_right=7.5)
    low, high = ax.get_ylim()
    ax.set_ylim(low, high * 2.8)  # headroom for the event labels and the window bracket

    handles = [
        Line2D(
            [],
            [],
            color=COUNTRY_COLORS[treated],
            linewidth=EMPHASIS_WIDTH,
            label=config.COUNTRIES[treated],
        ),
        _low_reliability_handle(),
        Line2D([], [], color=COMPARATOR_COLOR, linewidth=LINE_WIDTH, label=comparator.label),
    ]
    if cutoff is not None:
        handles.append(_low_reliability_band_handle(cutoff))
    handles.append(_modeling_window_handle())
    _legend(ax, handles, loc="lower right")

    _set_titles(
        fig,
        f"Real GDP per capita, {first}–{last}",
        f"Myanmar and {comparator.label} on one ruler: WDI constant 2015 US$, log scale - equal "
        f"slopes are equal growth. Myanmar's figures before {cutoff} are low reliability.",
    )
    notes = [
        config.LOW_RELIABILITY_MESSAGE,
        config.MODELING_WINDOW_MESSAGE,
        config.RULERS_MESSAGE,
        config.HISTORICAL_FISCAL_YEAR_MESSAGE,
    ]
    if not maddison.empty:
        notes.append(f"{config.MADDISON_RULER_MESSAGE}: {config.MADDISON_CITATION}.")
    _set_wrapped_footer(fig, *(_tex_safe(n) for n in notes), width=165)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.84, bottom=0.15)
    return fig


def _maddison_panel(ax: Axes, maddison: pd.DataFrame, cutoff: int | None) -> None:
    """The pre-1960 Maddison series on its own axis, labelled as a different ruler."""
    _style_axis(ax, labelsize=8)
    series = maddison.set_index(config.COL_YEAR)[config.COL_VALUE].sort_index()
    color = COUNTRY_COLORS[config.TREATED_COUNTRY]
    low_reliability = cutoff is not None and series.index.max() < cutoff
    ax.plot(
        series.index,
        series,
        color=color,
        alpha=LOW_RELIABILITY_ALPHA if low_reliability else 1.0,
        linewidth=LINE_WIDTH,
        linestyle=LOW_RELIABILITY_DASH if low_reliability else "-",
        marker="o",
        markersize=MARKER_SIZE * 0.6,
        zorder=3,
    )
    first, last = int(series.index.min()), int(series.index.max())
    if low_reliability:
        _mark_low_reliability(ax, first - 0.5, last + 0.5)
    ax.set_xlim(first - 0.5, last + 0.5)
    _dollar_log_axis(ax, "2011 int$, PPP (log scale)")
    ax.set_title(
        f"Before {config.HISTORICAL_START}: Maddison\n(a different ruler)",
        fontsize=9,
        color=INK_SECONDARY,
        family=FONT_FAMILY,
        loc="left",
    )


def _anchor_phrase(result: DivergenceResult, sensitivity: pd.DataFrame | None) -> str:
    """How the latest-year ratio moves with the anchor - the result turns on it."""
    if sensitivity is None:
        return ""
    rows = sensitivity[
        (sensitivity[config.COL_SCENARIO] == result.scenario.name)
        & (sensitivity["anchor_year"] != result.scenario.anchor_year)
    ].sort_values("anchor_year")
    if rows.empty:
        return ""
    years = ", ".join(str(int(y)) for y in rows["anchor_year"])
    ratios = ", ".join(f"{r:.2f}\u00d7" for r in rows["ratio_latest"])
    return f"Anchor-sensitive: started in {years} instead, the path ends at {ratios} actual."


def historical_divergence_figure(
    historical: pd.DataFrame,
    result: DivergenceResult,
    sensitivity: pd.DataFrame | None = None,
) -> Figure:
    """Myanmar's actual GDP per capita against an illustrative divergence path.

    Args:
        historical: The ``historical`` table, for Myanmar's actual line.
        result: One divergence scenario from :mod:`amber.modeling.divergence`.
        sensitivity: The ``historical_divergence_sensitivity`` table; when
            given, the footer states how the ratio moves with the anchor.

    Returns:
        The rendered figure.
    """
    treated = config.TREATED_COUNTRY
    cutoff = config.RELIABILITY_LOW_BEFORE.get(treated)
    anchor = result.scenario.anchor_year
    path = result.path.set_index(config.COL_YEAR)
    actual = path["actual"].dropna()
    scenario_path = path["path"].dropna()
    latest = result.latest
    latest_year = int(latest[config.COL_YEAR])

    fig, ax = _new_figure()
    fig.set_size_inches(*HISTORICAL_FIGSIZE)
    _dollar_log_axis(
        ax, "GDP per capita, constant 2015 US$ (log scale)", subs=(1.0, 1.5, 2.0, 3.0, 5.0, 7.0)
    )
    low_anchor = cutoff is not None and anchor < cutoff
    if cutoff is not None and low_anchor:
        _mark_low_reliability(ax, anchor - 0.5, cutoff)

    both = path.dropna(subset=["actual", "path"])
    ax.fill_between(
        both.index,
        both["actual"],
        both["path"],
        color=COUNTRY_COLORS[treated],
        alpha=GAP_ALPHA,
        linewidth=0,
        zorder=1,
    )
    path_label = f"Tracking {result.comparator.label}'s growth since {anchor}"
    ax.plot(
        scenario_path.index,
        scenario_path,
        color=DIVERGENCE_PATH_COLOR,
        linewidth=LINE_WIDTH,
        linestyle=DASH,
        zorder=3,
    )
    _plot_reliability_line(
        ax,
        actual,
        COUNTRY_COLORS[treated],
        config.COUNTRIES[treated],
        cutoff=cutoff,
        width=EMPHASIS_WIDTH,
        zorder=4,
    )

    ends = {
        "path": (float(scenario_path.index[-1]), float(scenario_path.iloc[-1])),
        "actual": (float(actual.index[-1]), float(actual.iloc[-1])),
    }
    spread = _spread({k: np.log10(v) for k, (_, v) in ends.items()}, min_gap=0.05)
    names = {"path": "Illustrative path", "actual": f"{config.COUNTRIES[treated]}, actual"}
    for key, (year, _) in ends.items():
        ax.text(
            year + 0.6,
            10 ** spread[key],
            names[key],
            va="center",
            fontsize=9.5 if key == "actual" else 9,
            fontweight="bold" if key == "actual" else "normal",
            color=INK_PRIMARY if key == "actual" else INK_SECONDARY,
            family=FONT_FAMILY,
        )
    middle = float(np.sqrt(latest["actual"] * latest["path"]))
    ax.text(
        latest_year + 0.6,
        middle,
        f"{latest['ratio']:.2f}×",
        va="center",
        fontsize=9,
        color=INK_SECONDARY,
        family=FONT_FAMILY,
    )
    ax.text(
        0.012,
        0.975,
        "Illustrative scenario - not a causal estimate",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color=INK_PRIMARY,
        family=FONT_FAMILY,
        bbox={"facecolor": SURFACE, "edgecolor": INK_SECONDARY, "linewidth": 0.8, "pad": 4},
        zorder=6,
    )
    _decade_axis(ax, anchor, int(path.index.max()), pad_right=9.5)

    handles = [
        Line2D(
            [],
            [],
            color=COUNTRY_COLORS[treated],
            linewidth=EMPHASIS_WIDTH,
            label=f"{config.COUNTRIES[treated]}, actual",
        ),
        _low_reliability_handle(),
        Line2D(
            [],
            [],
            color=DIVERGENCE_PATH_COLOR,
            linewidth=LINE_WIDTH,
            linestyle=DASH,
            label=path_label,
        ),
    ]
    if cutoff is not None and low_anchor:
        handles.append(_low_reliability_band_handle(cutoff))
    _legend(ax, handles, loc="lower right")

    _set_titles(
        fig,
        f"Myanmar and an illustrative path: {result.comparator.label}'s growth since {anchor}",
        f"{config.DIVERGENCE_FRAMING} By {latest_year} the path is {latest['ratio']:.2f}× "
        f"Myanmar's actual level (\\${latest['path']:,.0f} against \\${latest['actual']:,.0f}).",
    )
    reliability = ", itself low reliability" if low_anchor else ""
    notes = [
        f"The path starts at Myanmar's actual {anchor} level{reliability}.",
        _anchor_phrase(result, sensitivity),
        config.CHAINED_LEVEL_MESSAGE,
        "Nothing is fitted, so there is no p-value or credibility check.",
        config.LOW_RELIABILITY_MESSAGE,
        config.HISTORICAL_FISCAL_YEAR_MESSAGE,
    ]
    _set_wrapped_footer(fig, *(_tex_safe(n) for n in notes if n), width=165)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.84, bottom=0.2)
    return fig


def render_historical(
    historical: pd.DataFrame,
    divergence: DivergenceResult,
    sensitivity: pd.DataFrame | None = None,
    figures_dir: Path = config.FIGURES_DIR,
) -> tuple[Path, ...]:
    """Render and save the two historical-layer charts.

    Args:
        historical: The ``historical`` table.
        divergence: The default divergence scenario.
        sensitivity: The anchor-sensitivity table, for the divergence footer.
        figures_dir: Destination directory.

    Returns:
        The paths written.
    """
    return (
        save_figure(historical_gdp_figure(historical), figures_dir / config.HISTORICAL_FIGURE_GDP),
        save_figure(
            historical_divergence_figure(historical, divergence, sensitivity),
            figures_dir / config.HISTORICAL_FIGURE_DIVERGENCE,
        ),
    )
