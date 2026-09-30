"""Request dependencies: the loaded store and its precomputed responses."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from . import presenters
from . import schemas as s
from .store import DataStore

__all__ = ["Precomputed", "build_precomputed", "get_precomputed", "get_store"]


@dataclass(frozen=True, slots=True)
class Precomputed:
    """Responses that never change for a given store, built once at startup."""

    meta: s.MetaResponse
    counterfactual: s.CounterfactualResponse
    scenarios: s.ScenariosResponse


def build_precomputed(store: DataStore) -> Precomputed:
    """Build every static response from the store."""
    return Precomputed(
        meta=presenters.meta(store),
        counterfactual=presenters.counterfactual(store),
        scenarios=presenters.scenarios(store),
    )


def get_store(request: Request) -> DataStore:
    """The store loaded at startup."""
    return request.app.state.store


def get_precomputed(request: Request) -> Precomputed:
    """The static responses built at startup."""
    return request.app.state.precomputed
