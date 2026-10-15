"""Publish one comment, without background batches or automatic retries."""

from __future__ import annotations


def submit_comment(reddit, post_id: str, body: str) -> str:
    try:
        comment = reddit.submission(id=post_id).reply(body)
    except Exception:
        raise RuntimeError(
            "Submission failed or its outcome is unknown. Check Reddit before attempting another publish."
        ) from None
    if comment is None:
        raise RuntimeError("Reddit returned no comment. Check Reddit before trying again.")
    return f"https://www.reddit.com{comment.permalink}"
