"""API runtime settings, read from the environment.

``AMBER_DATA_SOURCE``
    ``release`` (default) serves the committed ``data/release`` snapshot;
    ``processed`` serves the working outputs of ``make models``.
``AMBER_CORS_ORIGINS``
    Comma-separated allowed origins, e.g. ``https://amber.vercel.app``.
    Defaults to the Vite dev server.
``AMBER_LOG_LEVEL``
    Logging verbosity.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from amber import config
from amber.config import DataSource

__all__ = ["Settings"]


@dataclass(frozen=True, slots=True)
class Settings:
    """Where the data comes from and who may call the API.

    Attributes:
        data_source: Which snapshot to serve.
        data_dir: The directory it resolves to.
        cors_origins: Origins allowed by CORS.
    """

    data_source: DataSource
    data_dir: Path
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Read settings from ``env`` (default: the process environment).

        Args:
            env: Variables to read.

        Returns:
            The settings.

        Raises:
            ValueError: If ``AMBER_DATA_SOURCE`` is not a known source.
        """
        env = os.environ if env is None else env
        raw_source = env.get("AMBER_DATA_SOURCE", str(config.DEFAULT_DATA_SOURCE)).strip().lower()
        try:
            source = DataSource(raw_source)
        except ValueError as exc:
            valid = ", ".join(str(s) for s in DataSource)
            msg = f"AMBER_DATA_SOURCE must be one of {valid}; got {raw_source!r}"
            raise ValueError(msg) from exc
        data_dir = (
            config.RELEASE_DATA_DIR if source is DataSource.RELEASE else config.PROCESSED_DATA_DIR
        )
        raw_origins = env.get("AMBER_CORS_ORIGINS", "")
        origins = tuple(o.strip().rstrip("/") for o in raw_origins.split(",") if o.strip())
        return cls(
            data_source=source,
            data_dir=data_dir,
            cors_origins=origins or config.API_DEFAULT_CORS_ORIGINS,
        )
