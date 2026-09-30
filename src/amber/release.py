"""Release snapshot - phase 5.

Copies the processed tables the API serves into :data:`~amber.config.RELEASE_DATA_DIR`,
which is committed, and writes a manifest recording when and from which commit
the snapshot was built, plus a hash and row count for every file. The deployed
API reads this snapshot, so a deploy never touches the World Bank API and two
deploys of one commit serve identical numbers.

Regenerate it deliberately, after ``make models``, with ``make release`` - never
by editing the files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from amber import __version__, config
from amber.pipeline import configure_logging

logger = logging.getLogger(__name__)

__all__ = ["Manifest", "build_release", "main", "read_manifest"]


@dataclass(frozen=True, slots=True)
class Manifest:
    """What a snapshot contains and where it came from.

    Attributes:
        built_at: UTC build time, ISO 8601.
        commit: Git commit the tables were built from, if known.
        version: Amber package version.
        files: File name -> ``{"sha256": ..., "rows": ...}``.
    """

    built_at: str
    commit: str | None
    version: str
    files: dict[str, dict[str, object]]


def _git_commit() -> str | None:
    """The current commit, or None outside a git checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=config.PROJECT_ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release(
    source_dir: Path = config.PROCESSED_DATA_DIR,
    release_dir: Path = config.RELEASE_DATA_DIR,
    stems: Sequence[str] = config.RELEASE_STEMS,
) -> Manifest:
    """Copy the served tables into the release directory and write the manifest.

    Every table must exist before anything is copied, so a partial build never
    leaves a half-updated snapshot.

    Args:
        source_dir: Where ``make models`` wrote the tables.
        release_dir: The committed snapshot directory.
        stems: Table stems to copy (as csv).

    Returns:
        The manifest written.

    Raises:
        FileNotFoundError: If any table is missing from ``source_dir``.
    """
    sources = [source_dir / f"{stem}.csv" for stem in stems]
    missing = [path.name for path in sources if not path.exists()]
    if missing:
        msg = (
            f"Cannot build a release: {missing} not found in {source_dir}. "
            "Run `make panel`, `make index` and `make models` first."
        )
        raise FileNotFoundError(msg)

    release_dir.mkdir(parents=True, exist_ok=True)
    for stale in release_dir.glob("*.csv"):
        if stale.stem not in stems:
            stale.unlink()
            logger.info("Removed %s: no longer a release table", stale.name)

    files: dict[str, dict[str, object]] = {}
    for path in sources:
        target = release_dir / path.name
        # LF on every platform, so the hashes hold wherever the snapshot is checked out.
        target.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        files[path.name] = {"sha256": _sha256(target), "rows": len(pd.read_csv(target))}
        logger.info("Released %s (%d rows)", path.name, files[path.name]["rows"])

    manifest = Manifest(
        built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        commit=_git_commit(),
        version=__version__,
        files=files,
    )
    (release_dir / config.RELEASE_MANIFEST).write_text(
        json.dumps(
            {
                "built_at": manifest.built_at,
                "commit": manifest.commit,
                "version": manifest.version,
                "files": manifest.files,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("Release snapshot: %d tables in %s", len(files), release_dir)
    return manifest


def read_manifest(release_dir: Path = config.RELEASE_DATA_DIR) -> Manifest | None:
    """The manifest of a snapshot, or None if it has none.

    Args:
        release_dir: Snapshot directory.

    Returns:
        The parsed manifest.
    """
    path = release_dir / config.RELEASE_MANIFEST
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Manifest(
        built_at=raw["built_at"],
        commit=raw.get("commit"),
        version=raw["version"],
        files=raw["files"],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Command-line interface for the release builder."""
    parser = argparse.ArgumentParser(
        description="Copy the processed tables the API serves into the committed release snapshot."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=config.PROCESSED_DATA_DIR,
        help="Where the model tables are (default: data/processed).",
    )
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=config.RELEASE_DATA_DIR,
        help="Snapshot destination (default: data/release).",
    )
    parser.add_argument(
        "--log-level",
        default=config.LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Argument vector, defaulting to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    try:
        build_release(args.source_dir, args.release_dir)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    return 0
