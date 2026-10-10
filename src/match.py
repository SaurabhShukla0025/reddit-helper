"""Decides which fetched posts are worth drafting a comment for.

Pure logic — no network, no Reddit calls — so it is easy to test. Step 1 fetches
posts; this step filters them against each subreddit's `MatchRules`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .config import MatchRules, Subreddit
from .fetch import Post


@dataclass
class MatchResult:
    """The verdict for one post: whether it passed, and a human-readable reason."""

    post: Post
    matched: bool
    reason: str


def _haystack(post: Post) -> str:
    return f"{post.title}\n{post.selftext}".lower()


def _age_hours(post: Post, now: float) -> float:
    return max(0.0, (now - post.created_utc) / 3600.0)


def evaluate(post: Post, rules: MatchRules, now: float | None = None) -> MatchResult:
    """Checks one post against one subreddit's rules.

    Gates are checked in a fixed order and the first failure wins, so the reason
    explains exactly why a post was skipped (or, on success, why it qualified).
    """
    now = time.time() if now is None else now
    text = _haystack(post)

    # Normalize here so matching is correct however the rules were built, not
    # only when they came through the config loader.
    hit = next((term for term in rules.exclude if term.lower() in text), None)
    if hit is not None:
        return MatchResult(post, False, f"excluded by {hit.lower()!r}")

    if rules.keywords:
        matched_term = next((term for term in rules.keywords if term.lower() in text), None)
        if matched_term is None:
            return MatchResult(post, False, "no keyword match")
        keyword_reason = f"keyword {matched_term.lower()!r}"
    else:
        keyword_reason = "no keyword filter"

    if post.score < rules.min_score:
        return MatchResult(post, False, f"score {post.score} < min {rules.min_score}")
    if rules.max_score is not None and post.score > rules.max_score:
        return MatchResult(post, False, f"score {post.score} > max {rules.max_score}")

    if post.num_comments < rules.min_comments:
        return MatchResult(post, False, f"comments {post.num_comments} < min {rules.min_comments}")
    if rules.max_comments is not None and post.num_comments > rules.max_comments:
        return MatchResult(post, False, f"comments {post.num_comments} > max {rules.max_comments}")

    if rules.max_age_hours is not None:
        age = _age_hours(post, now)
        if age > rules.max_age_hours:
            return MatchResult(post, False, f"age {age:.1f}h > max {rules.max_age_hours:g}h")

    return MatchResult(post, True, keyword_reason)


def match_subreddit(
    posts: list[Post], sub: Subreddit, now: float | None = None
) -> list[MatchResult]:
    """Every post's verdict for one subreddit, in the order given."""
    return [evaluate(post, sub.rules, now) for post in posts]


def match_all(
    fetched: dict[str, list[Post]],
    subreddits: list[Subreddit],
    now: float | None = None,
) -> dict[str, list[MatchResult]]:
    """Verdicts for every configured subreddit, keyed by name."""
    by_name = {sub.name: sub for sub in subreddits}
    return {
        name: match_subreddit(posts, by_name[name], now)
        for name, posts in fetched.items()
        if name in by_name
    }
