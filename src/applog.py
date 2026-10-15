"""Console-only operational logging and cleanup of legacy local log files."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "reddit-helper.log"


def setup_logging(verbose: bool = False, path: Path = LOG_PATH) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s: %(message)s")


def cleanup_logs(path: Path = LOG_PATH) -> None:
    # Exact application-owned filenames only. New versions do not persist logs.
    for candidate in (path, *(path.with_name(path.name + f".{index}") for index in range(1, 4))):
        candidate.unlink(missing_ok=True)
