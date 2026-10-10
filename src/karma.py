"""Tracks the score (karma) of comments this tool has posted.

Reading a comment's score uses Reddit's free API. The score lookup is injected
into `check_karma`, so recording and reporting are tested with no network.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from . import store
from .store import Draft

log = logging.getLogger(__name__)


@dataclass
class KarmaReport:
    subreddit: str
    post_title: str
    posted_url: str | None
    first_score: int
    latest_score: int
    samples: int
    checked_at: str

    @property
    def delta(self) -> int:
        """Change in score since the first reading."""
        return self.latest_score - self.first_score


def fetch_score(reddit, url: str) -> int:
    """Current score of the comment at `url`, via PRAW. Reads from Reddit."""
    return int(reddit.comment(url=url).score)


def check_karma(
    conn,
    reddit,
    posted: list[Draft],
    *,
    get_score: Callable[..., int] = fetch_score,
    out: Callable[[str], None] = print,
) -> int:
    """Reads and records the current score for each posted comment.

    Returns how many were read successfully. A comment that can't be read
    (deleted, removed) is warned about and skipped, not fatal.
    """
    checked = 0
    for draft in posted:
        if not draft.posted_url:
            continue
        try:
            score = get_score(reddit, draft.posted_url)
        except Exception as error:  # noqa: BLE001 - one bad comment shouldn't stop the rest
            out(f"  ! {draft.post_id}: could not read score ({error})")
            log.warning("karma read failed for %s: %s", draft.post_id, error)
            continue
        store.record_karma(conn, draft.post_id, score)
        checked += 1
        out(f"  r/{draft.subreddit} score {score:>5}: {draft.post_title}")
        log.info("karma %s score=%s", draft.post_id, score)
    return checked


def report(conn, posted: list[Draft]) -> list[KarmaReport]:
    """Builds a per-comment karma summary from recorded history."""
    reports: list[KarmaReport] = []
    for draft in posted:
        history = store.karma_history(conn, draft.post_id)
        if not history:
            continue
        reports.append(
            KarmaReport(
                subreddit=draft.subreddit,
                post_title=draft.post_title,
                posted_url=draft.posted_url,
                first_score=history[0].score,
                latest_score=history[-1].score,
                samples=len(history),
                checked_at=history[-1].checked_at,
            )
        )
    return reports


def total_karma(reports: list[KarmaReport]) -> int:
    """Sum of the latest score across all tracked comments."""
    return sum(r.latest_score for r in reports)
