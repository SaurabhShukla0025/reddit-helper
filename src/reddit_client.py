"""Builds the authenticated Reddit API client."""

from __future__ import annotations

import praw

from .config import RedditCreds


def make_client(creds: RedditCreds) -> praw.Reddit:
    """Logs in to Reddit's API with the script-app credentials from config."""
    reddit = praw.Reddit(
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        username=creds.username,
        password=creds.password,
        user_agent=creds.user_agent,
    )
    # Read-only stays False so later steps can comment; this slice only reads.
    return reddit


def whoami(reddit: praw.Reddit) -> str:
    """Confirms the login works by returning the signed-in username."""
    return str(reddit.user.me())
