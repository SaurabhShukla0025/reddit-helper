"""Central logging setup: a persistent, rotating audit log of what the tool did.

`main.py` calls `setup_logging()` once at startup. Library modules just use
`logging.getLogger(__name__)`; their records propagate to the root logger
configured here and land in reddit-helper.log (git-ignored).
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "reddit-helper.log"

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(verbose: bool = False, path: Path = LOG_PATH) -> None:
    """Configures file logging (and optional console echo). Safe to call once."""
    root = logging.getLogger()
    if any(getattr(h, "_reddit_helper", False) for h in root.handlers):
        return  # already configured
    root.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    file_handler.setLevel(logging.INFO)
    file_handler._reddit_helper = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if verbose:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_FORMAT))
        console.setLevel(logging.INFO)
        console._reddit_helper = True  # type: ignore[attr-defined]
        root.addHandler(console)
