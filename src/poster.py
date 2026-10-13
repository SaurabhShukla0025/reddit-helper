"""Posts approved comments with load-control pauses and rate-limit backoff.

This is the only module that writes to Reddit. The network call, the pauses and
the pacing delay are all injected into `run_posts`, so the ordering, pacing and
rate-limit logic are tested with no network and no real waiting.
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from . import store
from .config import PostConfig
from .store import Draft

log = logging.getLogger(__name__)

_DEFAULT_RATELIMIT_WAIT = 600.0  # fallback when Reddit doesn't give a time


class RateLimited(Exception):
    """Reddit refused a post because we're going too fast; wait `seconds`."""

    def __init__(self, seconds: float):
        super().__init__(f"rate limited for about {seconds:.0f}s")
        self.seconds = seconds


@dataclass
class PostResult:
    post_id: str
    ok: bool
    url: str | None = None
    error: str | None = None


@dataclass
class PostRun:
    results: list[PostResult] = field(default_factory=list)
    stopped_early: bool = False  # True if rate limiting cut the run short

    @property
    def posted(self) -> list[PostResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> list[PostResult]:
        return [r for r in self.results if not r.ok]


def _parse_wait(message: str) -> float | None:
    """Pulls a wait time out of Reddit's 'try again in N minutes' message."""
    match = re.search(r"(\d+)\s*minute", message)
    if match:
        return float(match.group(1)) * 60
    match = re.search(r"(\d+)\s*second", message)
    if match:
        return float(match.group(1))
    return None


def _rate_limit_seconds(error: Exception) -> float | None:
    """If `error` is a PRAW rate-limit error, the seconds to wait, else None."""
    items = getattr(error, "items", None)
    if not items:
        return None
    for item in items:
        if getattr(item, "error_type", "") == "RATELIMIT":
            return _parse_wait(getattr(item, "message", "") or "") or _DEFAULT_RATELIMIT_WAIT
    return None


def submit_comment(reddit, post_id: str, body: str) -> str:
    """Posts one comment via PRAW and returns its permalink. Writes to Reddit."""
    try:
        comment = reddit.submission(id=post_id).reply(body)
    except Exception as error:  # noqa: BLE001 - re-raise as RateLimited or as-is
        seconds = _rate_limit_seconds(error)
        if seconds is not None:
            raise RateLimited(seconds) from error
        raise
    if comment is None:
        raise RuntimeError("Reddit accepted no comment (post may be locked or removed)")
    return f"https://www.reddit.com{comment.permalink}"


def delay_from(cfg: PostConfig, rng: Callable[[float, float], float] = random.uniform):
    """A callable returning a load-control pause within the configured range."""
    return lambda: rng(cfg.min_delay_seconds, cfg.max_delay_seconds)


def run_posts(
    conn,
    reddit,
    drafts: list[Draft],
    *,
    delay: Callable[[], float],
    submit: Callable[..., str] = submit_comment,
    sleep: Callable[[float], None] = time.sleep,
    out: Callable[[str], None] = print,
    rate_limit_retries: int = 1,
) -> PostRun:
    """Posts each approved draft in turn, pausing between posts.

    On a rate-limit error it waits the suggested time and retries that draft up
    to `rate_limit_retries` times; a second rate-limit stops the whole run so we
    don't keep hammering Reddit. Other errors are recorded and skipped.
    """
    run = PostRun()
    for index, draft in enumerate(drafts):
        if index > 0:  # no pause before the first post
            pause = delay()
            out(f"  pacing {pause:.0f}s before the next post...")
            sleep(pause)

        attempts = 0
        while True:
            try:
                url = submit(reddit, draft.post_id, draft.comment)
            except RateLimited as limited:
                attempts += 1
                if attempts > rate_limit_retries:
                    out(f"  rate limited again; stopping after {len(run.posted)} post(s).")
                    log.warning("rate limited again on %s; stopping run", draft.post_id)
                    run.stopped_early = True
                    return run
                out(f"  rate limited; waiting {limited.seconds:.0f}s then retrying...")
                log.warning("rate limited on %s; waiting %.0fs", draft.post_id, limited.seconds)
                sleep(limited.seconds)
                continue
            except Exception as error:  # noqa: BLE001 - record and move on
                run.results.append(PostResult(draft.post_id, ok=False, error=str(error)))
                out(f"  ! {draft.post_id}: {error}")
                log.error("post failed for %s: %s", draft.post_id, error)
                break

            store.mark_posted(conn, draft.post_id, url)
            run.results.append(PostResult(draft.post_id, ok=True, url=url))
            out(f"  + posted: {url}")
            log.info("posted %s -> %s", draft.post_id, url)
            break

    return run
