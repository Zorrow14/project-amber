"""Fetch indicator series from the World Bank and cache the raw pulls on disk.

The rules this module exists to enforce:

* **One source per indicator.** Every numeric series comes from World Bank WDI
  (database :data:`~amber.config.WDI_SOURCE_ID`), applied identically to every
  country. Mixing vintages or fiscal-year conventions across sources is treated
  as a defect, so there is deliberately no second fetcher here.
* **Raw pulls are cached unmodified.** A cache entry is keyed by indicator,
  country set and year range, so the pipeline re-runs offline and the path from
  raw response to modeling panel stays reproducible. Pass ``refresh=True`` to
  re-pull from the API.

The network call sits behind :class:`IndicatorSource` so that tests can inject a
fake and never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd

from amber import config
from amber.config import Indicator

logger = logging.getLogger(__name__)

CACHE_SUFFIX = ".parquet"
METADATA_SUFFIX = ".json"


# --------------------------------------------------------------------------- #
# Source interface
# --------------------------------------------------------------------------- #


@runtime_checkable
class IndicatorSource(Protocol):
    """A provider of one indicator's observations for a set of countries."""

    def fetch(
        self,
        indicator_id: str,
        countries: Sequence[str],
        year_start: int,
        year_end: int,
    ) -> pd.DataFrame:
        """Return long-format observations.

        Args:
            indicator_id: Source-specific series code.
            countries: ISO3 country codes.
            year_start: First year, inclusive.
            year_end: Last year, inclusive.

        Returns:
            A frame with at least ``country_iso3``, ``year`` and ``value``
            columns. Missing observations are returned as NaN rather than
            dropped, so gaps stay visible.
        """
        ...


class WorldBankSource:
    """Fetches WDI series through the official ``wbgapi`` client.

    Args:
        source_id: World Bank database id. Pinned to WDI so a series is never
            silently served from a database with a different vintage.
        max_attempts: Total tries per indicator before giving up.
        backoff_seconds: Base for exponential backoff between retries.
    """

    def __init__(
        self,
        source_id: int = config.WDI_SOURCE_ID,
        max_attempts: int = config.FETCH_MAX_ATTEMPTS,
        backoff_seconds: float = config.FETCH_BACKOFF_SECONDS,
    ) -> None:
        self.source_id = source_id
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds

    def fetch(
        self,
        indicator_id: str,
        countries: Sequence[str],
        year_start: int,
        year_end: int,
    ) -> pd.DataFrame:
        """Fetch one indicator from the World Bank API, retrying on failure.

        Args:
            indicator_id: WDI series code, e.g. ``NY.GDP.PCAP.KD``.
            countries: ISO3 country codes.
            year_start: First year, inclusive.
            year_end: Last year, inclusive.

        Returns:
            Long-format observations with ``country_iso3``, ``year``, ``value``.

        Raises:
            RuntimeError: If every attempt fails.
        """
        rows = self._fetch_with_retry(indicator_id, countries, year_start, year_end)
        return pd.DataFrame(
            rows,
            columns=[config.COL_COUNTRY_ISO3, config.COL_YEAR, config.COL_VALUE],
        )

    def _fetch_with_retry(
        self,
        indicator_id: str,
        countries: Sequence[str],
        year_start: int,
        year_end: int,
    ) -> list[dict[str, object]]:
        """Call the API, backing off exponentially between failed attempts."""
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._fetch_once(indicator_id, countries, year_start, year_end)
            except Exception as exc:  # transport errors vary by backend, so catch broadly
                last_error = exc
                if attempt == self.max_attempts:
                    break
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Fetch of %s failed (attempt %d/%d): %s - retrying in %.1fs",
                    indicator_id,
                    attempt,
                    self.max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)

        msg = f"Could not fetch {indicator_id} after {self.max_attempts} attempts"
        raise RuntimeError(msg) from last_error

    def _fetch_once(
        self,
        indicator_id: str,
        countries: Sequence[str],
        year_start: int,
        year_end: int,
    ) -> list[dict[str, object]]:
        """Perform a single API call and normalize the response rows."""
        import wbgapi as wb  # imported lazily so tests need not install it

        # wbgapi ships no annotations and defaults `economy` and `time` to the
        # string "all", so a type checker infers `str` for both and rejects the
        # list/range forms below. They are the library's own documented usage
        # (`economy=['USA', 'CAN']`, `time=range(2010, 2020)`), so the arguments
        # are correct and the diagnostic is the one that is wrong.
        observations = wb.data.fetch(
            indicator_id,
            economy=list(countries),  # type: ignore[arg-type]
            time=range(year_start, year_end + 1),  # type: ignore[arg-type]
            db=self.source_id,
            skipBlanks=False,  # keep gaps visible instead of silently dropping them
            numericTimeKeys=True,
        )

        return [
            {
                config.COL_COUNTRY_ISO3: obs["economy"],
                config.COL_YEAR: _parse_year(obs["time"]),
                config.COL_VALUE: obs["value"],
            }
            for obs in observations
        ]


def _parse_year(raw: object) -> int:
    """Coerce a World Bank time key to an integer year.

    The API returns either an int (with ``numericTimeKeys``) or a ``YR2015``
    style string depending on the endpoint, so both are handled.

    Args:
        raw: Time key from the API response.

    Returns:
        The four-digit year.

    Raises:
        ValueError: If the key cannot be read as a year.
    """
    if isinstance(raw, int):
        return raw
    text = str(raw).removeprefix("YR")
    try:
        return int(text)
    except ValueError as exc:
        msg = f"Unrecognized World Bank time key: {raw!r}"
        raise ValueError(msg) from exc


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


def cache_key(indicator_id: str, countries: Sequence[str], year_start: int, year_end: int) -> str:
    """Build a stable cache filename stem for one pull.

    The country set is sorted before hashing so that reordering the configured
    countries does not invalidate an otherwise identical cache entry.

    Args:
        indicator_id: WDI series code.
        countries: ISO3 country codes.
        year_start: First year, inclusive.
        year_end: Last year, inclusive.

    Returns:
        A filesystem-safe stem, e.g. ``NY.GDP.PCAP.KD_2000-2024_a1b2c3d4``.
    """
    digest = hashlib.sha256(",".join(sorted(countries)).encode()).hexdigest()[:8]
    return f"{indicator_id}_{year_start}-{year_end}_{digest}"


def cache_path(
    indicator_id: str,
    countries: Sequence[str],
    year_start: int,
    year_end: int,
    cache_dir: Path,
) -> Path:
    """Return the parquet path for one cached pull."""
    return cache_dir / f"{cache_key(indicator_id, countries, year_start, year_end)}{CACHE_SUFFIX}"


def _write_cache(
    frame: pd.DataFrame,
    path: Path,
    indicator_id: str,
    countries: Sequence[str],
    year_start: int,
    year_end: int,
) -> None:
    """Persist a raw pull plus a provenance sidecar next to it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)

    metadata = {
        "indicator_id": indicator_id,
        "countries": sorted(countries),
        "year_start": year_start,
        "year_end": year_end,
        "source": "World Bank WDI",
        "source_db": config.WDI_SOURCE_ID,
        "fetched_at": datetime.now(UTC).isoformat(),
        "row_count": len(frame),
    }
    path.with_suffix(METADATA_SUFFIX).write_text(json.dumps(metadata, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def fetch_indicator(
    indicator: Indicator,
    *,
    source: IndicatorSource | None = None,
    countries: Sequence[str] = config.COUNTRY_CODES,
    year_start: int = config.YEAR_START,
    year_end: int = config.YEAR_END,
    cache_dir: Path = config.RAW_DATA_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Fetch one indicator, using the on-disk cache unless asked to refresh.

    Args:
        indicator: The series to fetch, carrying its id, label and pillar.
        source: Where to fetch from. Defaults to :class:`WorldBankSource`.
        countries: ISO3 country codes.
        year_start: First year, inclusive.
        year_end: Last year, inclusive.
        cache_dir: Directory holding cached raw pulls.
        refresh: Re-pull from the source and overwrite the cache entry.

    Returns:
        A frame with :data:`~amber.config.INGESTION_COLUMNS`.
    """
    return fetch_series(
        indicator.id,
        indicator.name,
        source=source,
        countries=countries,
        year_start=year_start,
        year_end=year_end,
        cache_dir=cache_dir,
        refresh=refresh,
    )


def fetch_series(
    indicator_id: str,
    indicator_name: str,
    *,
    source: IndicatorSource | None = None,
    countries: Sequence[str] = config.COUNTRY_CODES,
    country_names: Mapping[str, str] = config.COUNTRIES,
    year_start: int = config.YEAR_START,
    year_end: int = config.YEAR_END,
    cache_dir: Path = config.RAW_DATA_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Fetch one WDI series by id, using the on-disk cache unless asked to refresh.

    The general form of :func:`fetch_indicator`, for series that are not panel
    indicators (the historical layer's population) or countries outside the
    panel (its comparators). Same source, same cache, same schema.

    Args:
        indicator_id: WDI series code.
        indicator_name: Label carried into the output.
        source: Where to fetch from. Defaults to :class:`WorldBankSource`.
        countries: ISO3 country codes.
        country_names: ISO3 -> display name for labelling.
        year_start: First year, inclusive.
        year_end: Last year, inclusive.
        cache_dir: Directory holding cached raw pulls.
        refresh: Re-pull from the source and overwrite the cache entry.

    Returns:
        A frame with :data:`~amber.config.INGESTION_COLUMNS`.
    """
    path = cache_path(indicator_id, countries, year_start, year_end, cache_dir)

    if path.exists() and not refresh:
        logger.info("Cache hit for %s -> %s", indicator_id, path.name)
        raw = pd.read_parquet(path)
    else:
        reason = "refresh requested" if refresh else "cache miss"
        logger.info("Fetching %s from World Bank (%s)", indicator_id, reason)
        source = source or WorldBankSource()
        raw = source.fetch(indicator_id, countries, year_start, year_end)
        _write_cache(raw, path, indicator_id, countries, year_start, year_end)
        logger.info("Cached %d rows for %s -> %s", len(raw), indicator_id, path.name)

    return _to_ingestion_schema(raw, indicator_id, indicator_name, country_names)


def _to_ingestion_schema(
    raw: pd.DataFrame,
    indicator_id: str,
    indicator_name: str,
    country_names: Mapping[str, str] = config.COUNTRIES,
) -> pd.DataFrame:
    """Attach indicator and country labels and coerce dtypes.

    Labels come from :mod:`amber.config` rather than from the API response, so
    that country and indicator names stay stable across source vintages.

    Args:
        raw: Source output with ``country_iso3``, ``year`` and ``value``.
        indicator_id: The series these observations belong to.
        indicator_name: Its label.
        country_names: ISO3 -> display name.

    Returns:
        A frame with :data:`~amber.config.INGESTION_COLUMNS`.

    Raises:
        ValueError: If the source omitted a required column.
    """
    required = {config.COL_COUNTRY_ISO3, config.COL_YEAR, config.COL_VALUE}
    missing = required - set(raw.columns)
    if missing:
        msg = f"Source output for {indicator_id} is missing columns: {sorted(missing)}"
        raise ValueError(msg)

    frame = raw.copy()
    frame[config.COL_INDICATOR_ID] = indicator_id
    frame[config.COL_INDICATOR_NAME] = indicator_name
    frame[config.COL_COUNTRY_NAME] = frame[config.COL_COUNTRY_ISO3].map(dict(country_names))
    frame[config.COL_YEAR] = frame[config.COL_YEAR].astype(int)
    frame[config.COL_VALUE] = pd.to_numeric(frame[config.COL_VALUE], errors="coerce")

    unknown = frame.loc[frame[config.COL_COUNTRY_NAME].isna(), config.COL_COUNTRY_ISO3].unique()
    if len(unknown):
        logger.warning("Unconfigured country codes in %s: %s", indicator_id, sorted(unknown))

    return frame[list(config.INGESTION_COLUMNS)]


def fetch_panel(
    indicators: Iterable[Indicator] = config.INDICATORS,
    *,
    source: IndicatorSource | None = None,
    countries: Sequence[str] = config.COUNTRY_CODES,
    year_start: int = config.YEAR_START,
    year_end: int = config.YEAR_END,
    cache_dir: Path = config.RAW_DATA_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Fetch every configured indicator and stack the results.

    Args:
        indicators: Series to fetch. Defaults to every configured indicator.
        source: Where to fetch from. Defaults to :class:`WorldBankSource`.
        countries: ISO3 country codes.
        year_start: First year, inclusive.
        year_end: Last year, inclusive.
        cache_dir: Directory holding cached raw pulls.
        refresh: Re-pull every indicator and overwrite the cache.

    Returns:
        One long frame with :data:`~amber.config.INGESTION_COLUMNS`.

    Raises:
        ValueError: If no indicators were supplied.
    """
    indicators = tuple(indicators)
    if not indicators:
        msg = "No indicators to fetch"
        raise ValueError(msg)

    # One source instance for the whole run, so retry state and any future
    # session reuse is shared across indicators.
    source = source or WorldBankSource()

    frames = [
        fetch_indicator(
            indicator,
            source=source,
            countries=countries,
            year_start=year_start,
            year_end=year_end,
            cache_dir=cache_dir,
            refresh=refresh,
        )
        for indicator in indicators
    ]

    panel = pd.concat(frames, ignore_index=True)
    logger.info("Ingested %d rows across %d indicators", len(panel), len(indicators))
    return panel
