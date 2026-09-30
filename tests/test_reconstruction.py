"""Reconstruction tests: charts render, the CLI wires through, weights parse.

Rendering is checked for completion and output, not pixels - the charts are
reviewed by eye. Everything runs against synthetic data, offline.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from amber import config, figures, reconstruction
from amber.modeling import index


@pytest.fixture
def panel() -> pd.DataFrame:
    """Every indicator for every country, 2009-2016, with some gaps."""
    rng = np.random.default_rng(11)
    rows = []
    for iso3 in config.COUNTRY_CODES:
        for indicator in config.INDICATORS:
            for year in range(2009, 2017):
                value = float(
                    rng.uniform(500, 5000)
                    if indicator.id in config.LOG_TRANSFORM
                    else rng.uniform(1, 100)
                )
                # Drop some values so partial-coverage rings are exercised.
                if iso3 == config.TREATED_COUNTRY and indicator.id == "IT.NET.USER.ZS":
                    value = np.nan if year >= 2015 else value
                rows.append(
                    {
                        config.COL_INDICATOR_ID: indicator.id,
                        config.COL_INDICATOR_NAME: indicator.name,
                        config.COL_PILLAR: str(indicator.pillar),
                        config.COL_COUNTRY_ISO3: iso3,
                        config.COL_COUNTRY_NAME: config.COUNTRIES[iso3],
                        config.COL_YEAR: year,
                        config.COL_VALUE: value,
                        config.COL_PRE_2011: year < config.MODELING_WINDOW_START,
                    }
                )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def test_every_country_has_a_fixed_distinct_color():
    colors = [figures.COUNTRY_COLORS[iso3] for iso3 in config.COUNTRY_CODES]

    assert len(set(colors)) == len(config.COUNTRY_CODES)
    # Myanmar always takes the first slot, whatever else is plotted.
    assert figures.COUNTRY_COLORS[config.TREATED_COUNTRY] == figures.SERIES_PALETTE[0]


@pytest.mark.parametrize(
    "builder",
    [figures.combined_index_figure, figures.myanmar_pillars_figure],
)
def test_index_figures_build(panel, builder):
    fig = builder(index.compute_index(panel))

    assert isinstance(fig, Figure)
    assert fig.axes


def test_gdp_figure_builds(panel):
    fig = figures.gdp_pc_divergence_figure(panel)

    assert isinstance(fig, Figure)
    assert fig.axes[0].get_yscale() == "log"


def test_render_all_writes_the_three_pngs(tmp_path, panel):
    paths = figures.render_all(index.compute_index(panel), panel, tmp_path)

    assert {p.name for p in paths} == {
        config.FIGURE_COMBINED_ALL,
        config.FIGURE_MYANMAR_PILLARS,
        config.FIGURE_GDP_PC_DIVERGENCE,
    }
    for path in paths:
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def _figure_text(fig: Figure) -> str:
    return " ".join(text.get_text() for text in fig.texts)


def test_captions_describe_the_scale_actually_used(panel):
    goalposts = figures.combined_index_figure(index.compute_index(panel))
    pooled = figures.combined_index_figure(
        index.compute_index(panel, method="pooled"), method="pooled"
    )

    assert "goalposts" in _figure_text(goalposts)
    assert "pooled" not in _figure_text(goalposts)
    assert "pooled" in _figure_text(pooled)


def test_captions_describe_the_weights_actually_used(panel):
    weights = {"economy": 2, "innovation": 1, "human_development": 1}
    fig = figures.combined_index_figure(index.compute_index(panel, weights), weights=weights)

    caption = _figure_text(fig)
    assert "equal weights" not in caption
    assert "economy 50%" in caption
    assert figures._weights_phrase({"economy": 3, "innovation": 3, "human_development": 3}) == (
        "equal weights"
    )


def test_spread_keeps_labels_apart_and_in_order():
    spread = figures._spread({"a": 0.30, "b": 0.31, "c": 0.32, "d": 0.80}, min_gap=0.05)

    ordered = sorted(spread, key=spread.get)
    assert ordered == ["a", "b", "c", "d"]
    gaps = np.diff([spread[k] for k in ordered])
    assert (gaps >= 0.05 - 1e-9).all()


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def test_run_writes_index_and_figures(tmp_path, panel):
    panel_path = tmp_path / "panel_interpolated.csv"
    panel.to_csv(panel_path, index=False)

    result = reconstruction.run(
        panel_path=panel_path,
        output_dir=tmp_path / "processed",
        figures_dir=tmp_path / "figures",
    )

    assert {p.name for p in result.tables} == {"index.csv", "index.parquet"}
    assert len(result.figures) == 3
    reloaded = pd.read_csv(tmp_path / "processed" / "index.csv")
    assert tuple(reloaded.columns) == config.INDEX_COLUMNS


def test_run_can_skip_figures(tmp_path, panel):
    panel_path = tmp_path / "panel_interpolated.csv"
    panel.to_csv(panel_path, index=False)

    result = reconstruction.run(
        panel_path=panel_path,
        output_dir=tmp_path,
        figures_dir=tmp_path / "figures",
        render=False,
    )

    assert result.figures == ()
    assert not (tmp_path / "figures").exists()


def test_missing_panel_points_at_make_panel(tmp_path):
    with pytest.raises(FileNotFoundError, match="make panel"):
        reconstruction.load_panel(tmp_path / "absent.csv")


def test_parse_weights_reads_pillar_pairs():
    assert reconstruction.parse_weights("economy=2, innovation=1,human_development=0.5") == {
        "economy": 2.0,
        "innovation": 1.0,
        "human_development": 0.5,
    }


@pytest.mark.parametrize("text", ["economy", "economy=lots"])
def test_parse_weights_rejects_malformed_input(text):
    with pytest.raises(argparse.ArgumentTypeError):
        reconstruction.parse_weights(text)


def test_cli_turns_bad_weights_into_a_usage_error(tmp_path, panel, capsys):
    panel_path = tmp_path / "panel_interpolated.csv"
    panel.to_csv(panel_path, index=False)

    with pytest.raises(SystemExit) as exc:
        reconstruction.main(
            [
                "--panel",
                str(panel_path),
                "--output-dir",
                str(tmp_path),
                "--no-figures",
                "--weights",
                "economy=1,innovation=1",
            ]
        )

    assert exc.value.code == 2
    assert "every pillar" in capsys.readouterr().err
