"""Reads recent posts from the configured subreddits. Read-only."""
from __future__ import annotations

from dataclasses import dataclass

import praw

from .config import Config, Subreddit


@dataclass
class Post:
    id: str
    subreddit: str
    title: str
    author: str
    score: int
    num_comments: int
    url: str
    selftext: str
    created_utc: float


def _listing(reddit: praw.Reddit, name: str, which: str, limit: int):
    sub = reddit.subreddit(name)
    if which == "rising":
        return sub.rising(limit=limit)
    if which == "hot":
        return sub.hot(limit=limit)
    return sub.new(limit=limit)


def fetch_subreddit(reddit: praw.Reddit, sub: Subreddit, which: str, limit: int) -> list[Post]:
    """One subreddit's recent posts, newest listing by default."""
    posts: list[Post] = []
    for s in _listing(reddit, sub.name, which, limit):
        posts.append(
            Post(
                id=s.id,
                subreddit=sub.name,
                title=s.title,
                author=str(s.author),
                score=int(s.score),
                num_comments=int(s.num_comments),
                url=f"https://reddit.com{s.permalink}",
                selftext=s.selftext or "",
                created_utc=float(s.created_utc),
            )
        )
    return posts


def fetch_all(reddit: praw.Reddit, config: Config) -> dict[str, list[Post]]:
    """Recent posts for every configured subreddit, keyed by name."""
    return {
        sub.name: fetch_subreddit(reddit, sub, config.listing, config.limit)
        for sub in config.subreddits
    }
