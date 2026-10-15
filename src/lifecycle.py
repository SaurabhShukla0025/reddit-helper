"""Revalidate source posts before using queued material; fail closed on errors."""

import hashlib

from . import store
from .config import Config
from .policy import require_post


def fingerprint(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\0{body}".encode("utf-8")).hexdigest()


def available(submission) -> bool:
    body = submission.selftext or ""
    author = submission.author
    community = submission.subreddit
    return (
        author is not None
        and body.strip() not in {"[deleted]", "[removed]"}
        and not submission.removed_by_category
        and not community.quarantine
        and community.subreddit_type == "public"
        and not submission.over_18
    )


def verified_source(conn, reddit, draft, config: Config):
    """Return a current eligible source, or purge its data if no longer usable."""
    permitted = {s.name.casefold() for s in config.subreddits}
    if draft.subreddit.casefold() not in permitted:
        store.forget(conn, draft.post_id)
        return None
    try:
        source = reddit.submission(id=draft.post_id)
        usable = available(source)
        same_community = source.subreddit.display_name.casefold() == draft.subreddit.casefold()
        current_hash = fingerprint(source.title, source.selftext or "")
    except Exception as error:
        # PRAW exposes unavailable/protected sources as HTTP 404/403 too.
        # Other failures (auth, rate limits, timeouts, server errors) are unknown.
        response = getattr(error, "response", None)
        if getattr(response, "status_code", None) in {403, 404}:
            store.forget(conn, draft.post_id)
            return None
        raise RuntimeError("Source verification failed; queued content will not be displayed or posted") from None
    # Legacy rows without a source fingerprint cannot be revalidated safely.
    if not usable or not same_community or draft.source_hash != current_hash:
        store.forget(conn, draft.post_id)
        return None
    return source


def refresh(conn, reddit, drafts, config: Config) -> list:
    """Remove unavailable/changed/out-of-scope sources. Errors block use."""
    return [draft for draft in drafts if verified_source(conn, reddit, draft, config) is not None]


def submit_checked(conn, reddit, draft, body: str, config: Config, submit):
    """Recheck immediately before every submission (including retries)."""
    require_post(config, draft.subreddit)
    store.prune(conn, config.policy.retention_days)
    current = store.get_draft(conn, draft.post_id)
    if current is None or current.status != store.STATUS_APPROVED or current.comment != draft.comment:
        raise RuntimeError("Draft is no longer approved with the reviewed text")
    if current.model != "human":
        raise RuntimeError("Only human-written drafts can be published")
    if not body.strip() or len(body) > 10000:
        raise RuntimeError("Reply must contain 1-10,000 characters")
    if body != current.comment:
        raise RuntimeError("Submission text differs from the approved comment")
    source = verified_source(conn, reddit, draft, config)
    if source is None:
        raise RuntimeError("Source changed or became unavailable; local data was removed")
    if source.locked or source.archived:
        raise RuntimeError("Source is locked or archived")
    store.reserve_publish(conn, draft, config.post.max_posts_per_day)
    url = submit(reddit, draft.post_id, body)
    store.mark_posted(conn, draft.post_id, url)
    return url
