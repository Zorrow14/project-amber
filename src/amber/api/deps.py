"""Request dependencies: the loaded store and its precomputed responses."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from . import presenters
from . import schemas as s
from .caching import CachedBody
from .store import DataStore

__all__ = ["Precomputed", "build_precomputed", "get_precomputed", "get_store"]


@dataclass(frozen=True, slots=True)
class Precomputed:
    """Responses that never change for a given store, built once at startup.

    Each is kept both as its model and as its serialized body, so a request
    costs neither presenting nor serializing.
    """

    meta: s.MetaResponse
    counterfactual: s.CounterfactualResponse
    scenarios: s.ScenariosResponse
    divergence: dict[str, s.DivergenceResponse]
    bodies: dict[str, CachedBody]


def build_precomputed(store: DataStore) -> Precomputed:
    """Build and serialize every static response from the store."""
    meta = presenters.meta(store)
    counterfactual = presenters.counterfactual(store)
    scenarios = presenters.scenarios(store)
    divergence = {c.key: presenters.divergence(store, c.key) for c in meta.historical.comparators}
    return Precomputed(
        meta=meta,
        counterfactual=counterfactual,
        scenarios=scenarios,
        divergence=divergence,
        bodies={
            "meta": CachedBody.of(meta),
            "counterfactual": CachedBody.of(counterfactual),
            "scenarios": CachedBody.of(scenarios),
            **{f"divergence:{key}": CachedBody.of(body) for key, body in divergence.items()},
        },
    )


def get_store(request: Request) -> DataStore:
    """The store loaded at startup."""
    return request.app.state.store


def get_precomputed(request: Request) -> Precomputed:
    """The static responses built at startup."""
    return request.app.state.precomputed
