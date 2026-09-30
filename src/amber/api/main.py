"""FastAPI application - phase 5.

Serves Amber's three layers. Two kinds of endpoint, and the split is deliberate:

* **Precomputed, served as-is** - ``/meta``, ``/panel``, ``/counterfactual``,
  ``/scenarios``. Loaded once at startup from the release snapshot (or the
  processed outputs) into memory.
* **Live, cheap forward passes** - ``/index`` (the index under user weights) and
  ``/simulate`` (a scenario under user levers, on the precomputed calibration).
  See :mod:`amber.api.live`; nothing is ever fitted on a request.

Every modeled series goes out with its caveats: ``coverage`` on index rows,
``credibility`` on the counterfactual and scenarios, and the phase 3 check.

Run locally with::

    uvicorn amber.api.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from amber import __version__, config
from amber.pipeline import configure_logging

from .deps import build_precomputed
from .routers import counterfactual, index, meta, panel, scenarios
from .settings import Settings
from .store import DataStore, load_store

logger = logging.getLogger(__name__)

__all__ = ["app", "create_app"]


def create_app(settings: Settings | None = None, store: DataStore | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Runtime settings; read from the environment by default.
        store: A preloaded store (tests); loaded at startup from
            ``settings.data_dir`` otherwise.

    Returns:
        The FastAPI app. Startup fails with
        :class:`~amber.api.store.DataUnavailableError` if the data is absent.
    """
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loaded = store or load_store(settings.data_source, settings.data_dir)
        app.state.store = loaded
        app.state.precomputed = build_precomputed(loaded)
        logger.info(
            "Amber API ready: %s data, CORS origins %s", settings.data_source, settings.cors_origins
        )
        yield

    app = FastAPI(
        title="Amber API",
        version=__version__,
        summary="Myanmar development simulation - past, counterfactual, and future scenarios.",
        description=config.PROJECT_FRAMING + " " + config.SCENARIO_FRAMING,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    for router in (
        meta.router,
        panel.router,
        index.router,
        counterfactual.router,
        scenarios.router,
    ):
        app.include_router(router)
    return app


configure_logging()
app = create_app()
