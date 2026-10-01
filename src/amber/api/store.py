"""The in-memory data store the API serves from.

Loaded once at startup from the release snapshot or the processed outputs. It
holds every precomputed table plus the three things the two live endpoints
need - the panel, the calibrated parameters and the profile nodes - rebuilt
from the tables, so nothing is ever fitted on a request.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from amber import config
from amber.config import DataSource, Scenario
from amber.modeling import system_dynamics as sd
from amber.release import Manifest, read_manifest

logger = logging.getLogger(__name__)

__all__ = ["DataStore", "DataUnavailableError", "load_store"]


class DataUnavailableError(RuntimeError):
    """The tables the API needs are missing, corrupt, or out of step with config."""


@dataclass(frozen=True, slots=True)
class DataStore:
    """Everything the API serves, loaded once.

    Attributes:
        source: Which snapshot this is.
        data_dir: Where it was read from.
        manifest: The release manifest, when the snapshot has one.
        tables: Stem -> table, exactly as written by phases 1-4.
        calibration: The central calibration, rebuilt from ``sd_calibration``.
        nodes: The profile nodes, rebuilt from ``sd_profile`` (central first).
        scenarios: Configured scenarios by name.
    """

    source: DataSource
    data_dir: Path
    manifest: Manifest | None
    tables: dict[str, pd.DataFrame]
    calibration: sd.Calibration
    nodes: tuple[sd.ProfileNode, ...]
    scenarios: dict[str, Scenario]

    @property
    def panel(self) -> pd.DataFrame:
        """The interpolated panel - input to the live index."""
        return self.tables[config.PANEL_INTERPOLATED_STEM]

    def table(self, stem: str) -> pd.DataFrame:
        """One precomputed table by stem."""
        return self.tables[stem]


def _check_manifest(data_dir: Path, manifest: Manifest) -> None:
    """Fail if a released file no longer matches the hash its manifest recorded."""
    for name, entry in manifest.files.items():
        path = data_dir / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            msg = (
                f"{path} does not match its manifest hash: the release snapshot was edited "
                "by hand or partly regenerated. Rebuild it with `make release`."
            )
            raise DataUnavailableError(msg)


def _rebuild_calibration(
    tables: dict[str, pd.DataFrame],
) -> tuple[sd.Calibration, tuple[sd.ProfileNode, ...]]:
    """The central calibration and the profile nodes, from their tables."""
    panel = tables[config.PANEL_INTERPOLATED_STEM]
    calibration_table = tables[config.SD_CALIBRATION_STEM]
    params = dict(
        zip(
            calibration_table[config.COL_PARAMETER],
            calibration_table[config.COL_VALUE],
            strict=True,
        )
    )
    expected = set(config.SD_PARAMETERS)
    if set(params) != expected:
        msg = (
            "sd_calibration is out of step with config.SD_PARAMETERS "
            f"(missing {sorted(expected - set(params))}, extra {sorted(set(params) - expected)}). "
            "Rebuild with `make models` and `make release`."
        )
        raise DataUnavailableError(msg)
    initial = sd.initial_state(panel)
    central = sd.Calibration(
        params={k: float(v) for k, v in params.items()},
        initial=initial,
        cost=float("nan"),  # not carried by the tables, and not needed to simulate
        n_residuals=0,
    )

    profile = tables[config.SD_PROFILE_STEM]
    missing = sorted(expected - set(profile.columns))
    if missing or int(profile["central"].astype(bool).sum()) != 1:
        msg = "sd_profile must carry every parameter and exactly one central node"
        raise DataUnavailableError(msg)
    nodes = []
    for row in profile.sort_values("node").itertuples(index=False):
        row_params = {name: float(getattr(row, name)) for name in config.SD_PARAMETERS}
        is_central = bool(row.central)
        fit = (
            central
            if is_central
            else sd.Calibration(row_params, initial, cost=float("nan"), n_residuals=0)
        )
        nodes.append(
            sd.ProfileNode(
                values={name: row_params[name] for name in sd.UNIDENTIFIED},
                calibration=fit,
                nrmse=float(row.nrmse),
                nrmse_change=float(row.nrmse_change),
                central=is_central,
            )
        )
    nodes.sort(key=lambda node: not node.central)  # central first, as the ensemble expects
    return central, tuple(nodes)


def _check_historical(tables: dict[str, pd.DataFrame]) -> None:
    """Fail if the historical tables lost their caveat columns or drifted from config."""
    table = tables[config.HISTORICAL_STEM]
    missing = sorted(set(config.HISTORICAL_COLUMNS) - set(table.columns))
    if missing:
        msg = f"historical.csv lacks {missing}: its source and reliability must travel with it"
        raise DataUnavailableError(msg)
    if not set(table[config.COL_RELIABILITY]) <= {str(r) for r in config.Reliability}:
        msg = "historical.csv carries an unknown reliability value"
        raise DataUnavailableError(msg)
    if not set(table[config.COL_SOURCE]) <= {str(r) for r in config.HistoricalSource}:
        msg = "historical.csv carries an unknown source"
        raise DataUnavailableError(msg)
    configured = {sc.name for sc in config.DIVERGENCE_SCENARIOS}
    for stem in (config.HISTORICAL_DIVERGENCE_STEM, config.HISTORICAL_DIVERGENCE_METRICS_STEM):
        frame = tables[stem]
        if set(frame[config.COL_SCENARIO]) != configured:
            msg = f"{stem} lists other scenarios than config; rebuild with `make historical`"
            raise DataUnavailableError(msg)
        if not frame["scenario_illustrative"].map(bool_or_none).all():
            msg = f"{stem} has a row not flagged scenario_illustrative"
            raise DataUnavailableError(msg)


def _check_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Fail if the snapshot does not describe the configured model."""
    names = set(tables[config.SD_SCENARIOS_STEM][config.COL_SCENARIO])
    configured = {s.name for s in config.SCENARIOS}
    if names != configured:
        msg = (
            f"sd_scenarios lists {sorted(names)} but config has {sorted(configured)}. "
            "Rebuild with `make models` and `make release`."
        )
        raise DataUnavailableError(msg)
    series = set(tables[config.INDEX_STEM][config.COL_SERIES])
    if series != set(config.INDEX_SERIES):
        msg = f"index.csv has series {sorted(series)}, expected {sorted(config.INDEX_SERIES)}"
        raise DataUnavailableError(msg)
    indicators = set(tables[config.PANEL_INTERPOLATED_STEM][config.COL_INDICATOR_ID])
    if not set(config.INDEX_INDICATORS) <= indicators:
        msg = (
            f"The panel lacks index indicators: {sorted(set(config.INDEX_INDICATORS) - indicators)}"
        )
        raise DataUnavailableError(msg)
    _check_historical(tables)
    years = set(tables[config.SD_TRAJECTORY_STEM][config.COL_YEAR])
    wanted = set(range(config.SD_BACKTEST_START, config.SD_HORIZON_END + 1))
    if not wanted <= years:
        msg = f"sd_trajectory does not span {config.SD_BACKTEST_START}-{config.SD_HORIZON_END}"
        raise DataUnavailableError(msg)


def load_store(source: DataSource, data_dir: Path) -> DataStore:
    """Load every table the API serves, and rebuild the live-simulation inputs.

    Args:
        source: Which snapshot ``data_dir`` holds.
        data_dir: Directory of csv tables.

    Returns:
        The store.

    Raises:
        DataUnavailableError: If a table is missing, a released file fails its
            hash, or the tables are out of step with config.
    """
    missing = [stem for stem in config.RELEASE_STEMS if not (data_dir / f"{stem}.csv").exists()]
    if missing:
        how = "Build them with `make panel`, `make index` and `make models`" + (
            ", then `make release`." if source is DataSource.RELEASE else "."
        )
        msg = (
            f"The API cannot start: {len(missing)} table(s) missing from {data_dir} "
            f"({', '.join(missing)}). {how}"
        )
        raise DataUnavailableError(msg)

    manifest = read_manifest(data_dir) if source is DataSource.RELEASE else None
    if source is DataSource.RELEASE:
        if manifest is None:
            msg = f"{data_dir} has no {config.RELEASE_MANIFEST}; rebuild it with `make release`."
            raise DataUnavailableError(msg)
        _check_manifest(data_dir, manifest)

    tables = {stem: pd.read_csv(data_dir / f"{stem}.csv") for stem in config.RELEASE_STEMS}
    tables[config.SD_PROFILE_STEM]["at_bound"] = (
        tables[config.SD_PROFILE_STEM]["at_bound"].fillna("").astype(str)
    )
    _check_tables(tables)
    calibration, nodes = _rebuild_calibration(tables)

    store = DataStore(
        source=source,
        data_dir=data_dir,
        manifest=manifest,
        tables=tables,
        calibration=calibration,
        nodes=nodes,
        scenarios={s.name: s for s in config.SCENARIOS},
    )
    logger.info(
        "Loaded %d tables from %s (%s%s); %d profile nodes",
        len(tables),
        data_dir,
        source,
        f", built {manifest.built_at}" if manifest else "",
        len(nodes),
    )
    return store


def finite_or_none(value: object) -> float | None:
    """A float for JSON, with NaN and infinities as null."""
    if value is None or value is pd.NA:
        return None
    number = float(value)  # type: ignore[arg-type]
    return number if np.isfinite(number) else None


def bool_or_none(value: object) -> bool | None:
    """A bool for JSON, with a missing value as null."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)
