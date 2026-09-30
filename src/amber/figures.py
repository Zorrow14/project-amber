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
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from amber import config
from amber.config import Normalization, Pillar
from amber.modeling.index import resolve_weights

logger = logging.getLogger(__name__)

__all__ = [
    "combined_index_figure",
    "gdp_pc_divergence_figure",
    "myanmar_pillars_figure",
    "render_all",
    "save_figure",
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
"""Characters per subtitle line at 10pt across the figure; longer captions
(custom weights) wrap to a second line instead of running off the edge."""

PARTIAL_COVERAGE_NOTE = "Hollow points: computed from fewer than all indicators."

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
        labelsize=9,
        labelfontfamily=FONT_FAMILY,
        length=0,
        pad=6,
    )

    for text in (ax.xaxis.label, ax.yaxis.label):
        text.set_color(INK_SECONDARY)
        text.set_fontsize(10)
        text.set_family(FONT_FAMILY)
    return fig, ax


def _set_titles(fig: Figure, title: str, subtitle: str) -> None:
    """Left-aligned title and subtitle above the plot."""
    fig.text(
        0.06,
        0.955,
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
        0.905,
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


def _mark_context(ax: Axes, y_text: float) -> None:
    """Shade the COVID year and mark the treatment year, with plain labels.

    Args:
        ax: Target axes.
        y_text: Where to place the labels, in axes-fraction coordinates.
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

    ax.axvline(config.TREATMENT_YEAR, color=INK_MUTED, linewidth=0.8, zorder=1)
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
    _set_footer(fig, PARTIAL_COVERAGE_NOTE, scale_footer)
    fig.subplots_adjust(left=0.07, right=0.80, top=0.84, bottom=0.12)
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
    _set_footer(fig, PARTIAL_COVERAGE_NOTE, "Which series are missing: coverage_report.csv.")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.84, bottom=0.12)
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
