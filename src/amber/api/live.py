"""The only two computations the API performs on request.

Both are cheap forward passes over precomputed inputs:

* :func:`index_under_weights` - the development index under user weights, via
  :func:`amber.modeling.index.compute_index` on the loaded panel.
* :func:`simulate` - a system-dynamics ensemble under user levers, via
  :func:`amber.modeling.system_dynamics.run_scenarios` on the calibration and
  profile nodes rebuilt from ``sd_calibration`` and ``sd_profile``.

Nothing here fits anything: no least squares, no profile, no synthetic control.
Results are memoized, so dragging a slider back and forth costs one run per
distinct setting.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Hashable, Mapping
from threading import Lock

import pandas as pd

from amber import config
from amber.config import Normalization, Scenario
from amber.modeling import index as dev_index
from amber.modeling import system_dynamics as sd

from .store import DataStore

logger = logging.getLogger(__name__)

__all__ = ["custom_scenario", "index_under_weights", "simulate"]


class _Memo:
    """A small thread-safe LRU for live results."""

    def __init__(self, size: int) -> None:
        self._size = size
        self._items: OrderedDict[Hashable, object] = OrderedDict()
        self._lock = Lock()

    def get(self, key: Hashable) -> object | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: Hashable, value: object) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._size:
                self._items.popitem(last=False)


_INDEX_MEMO = _Memo(config.API_SIMULATE_CACHE_SIZE)
_SIMULATE_MEMO = _Memo(config.API_SIMULATE_CACHE_SIZE)


def index_under_weights(
    store: DataStore,
    weights: Mapping[str, float] | None,
    method: Normalization,
) -> tuple[dict[str, float], pd.DataFrame]:
    """The development index for every country under the given pillar weights.

    Args:
        store: The loaded data.
        weights: Pillar -> weight on any non-negative scale; None for the default.
        method: Normalization method.

    Returns:
        The weights as applied (summing to 1) and the tidy index rows.

    Raises:
        ValueError: On unknown or missing pillars, negative or non-finite
            weights, or all-zero weights (from ``resolve_weights``).
    """
    resolved = dev_index.resolve_weights(weights)
    applied = {str(pillar): weight for pillar, weight in resolved.items()}
    key = (id(store), method, tuple(sorted(applied.items())))
    cached = _INDEX_MEMO.get(key)
    if cached is None:
        cached = dev_index.compute_index(store.panel, applied, method)
        _INDEX_MEMO.put(key, cached)
    return applied, cached  # type: ignore[return-value]


def custom_scenario(base: Scenario, overrides: Mapping[str, float]) -> Scenario:
    """The base scenario with lever overrides; the base itself if nothing changes.

    Args:
        base: A configured scenario - it supplies the stability path.
        overrides: Lever -> value, already validated against config.

    Returns:
        The scenario to run.
    """
    levers = {name: base.lever(name) for name in config.LEVERS}
    changed = {name: value for name, value in overrides.items() if value != levers[name]}
    if not changed:
        return base
    levers.update(changed)
    return Scenario(
        name="custom",
        label=config.CUSTOM_SCENARIO_LABEL.format(base=base.label),
        stability=base.stability,
        levers=levers,
        description=config.CUSTOM_SCENARIO_DESCRIPTION.format(base=base.description),
    )


def simulate(store: DataStore, scenario: Scenario) -> sd.SimulationResult:
    """Run one scenario as an ensemble on the precomputed calibration.

    The baseline scenario runs alongside it on the same parameter draws, so the
    result carries its paired gap exactly as the precomputed tables do.

    Args:
        store: The loaded data.
        scenario: The scenario to run.

    Returns:
        The scenario's ensemble result.
    """
    key = (
        id(store),
        scenario.name,
        scenario.stability,
        tuple(sorted((name, scenario.lever(name)) for name in config.LEVERS)),
    )
    cached = _SIMULATE_MEMO.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    baseline = store.scenarios[config.SD_BASELINE_SCENARIO]
    runs = [baseline] if scenario.name == baseline.name else [baseline, scenario]
    results = sd.run_scenarios(store.calibration, runs, nodes=store.nodes)
    result = results[scenario.name]
    _SIMULATE_MEMO.put(key, result)
    logger.info("Simulated %s live (%d members)", scenario.name, config.SD_ENSEMBLE_SIZE)
    return result
