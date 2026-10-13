"""Walk the pending drafts so a human can approve, reject or edit each one.

The loop here is kept free of real I/O: it takes a `prompt` callable (returns the
reviewer's action), an `edit` callable (returns new comment text) and an `out`
callable (prints). `main.py` wires those to stdin and the user's editor; tests
wire them to canned functions, so the whole flow runs with no terminal.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from . import store
from .store import Draft
from .policy import disclosed

# Reviewer actions.
APPROVE = "approve"
REJECT = "reject"
EDIT = "edit"
SKIP = "skip"
QUIT = "quit"

PromptFn = Callable[[Draft], str]
EditFn = Callable[[str], str]
OutFn = Callable[[str], None]


@dataclass
class ReviewSummary:
    approved: int = 0
    rejected: int = 0
    edited: int = 0
    skipped: int = 0
    remaining: int = 0  # still pending when the reviewer quit


def render_draft(draft: Draft, index: int, total: int) -> str:
    """A readable block for one draft under review."""
    lines = [
        f"[{index}/{total}] r/{draft.subreddit}  (drafted by {draft.model})",
        f"  {draft.post_title}",
        f"  {draft.post_url}",
        "  --- draft comment ---",
        *(f"  | {line}" for line in draft.comment.splitlines() or [""]),
        "  ---------------------",
    ]
    return "\n".join(lines)


def run_review(
    conn: sqlite3.Connection,
    prompt: PromptFn,
    edit: EditFn,
    out: OutFn = print,
) -> ReviewSummary:
    """Reviews every pending draft, applying the reviewer's choice to the queue."""
    pending = store.list_drafts(conn, status=store.STATUS_PENDING)
    summary = ReviewSummary(remaining=len(pending))
    total = len(pending)

    for index, draft in enumerate(pending, start=1):
        comment = disclosed(draft.comment)
        if comment != draft.comment:
            store.update_comment(conn, draft.post_id, comment)
        while True:
            out(render_draft(_with_comment(draft, comment), index, total))
            action = prompt(_with_comment(draft, comment))

            if action == APPROVE:
                store.set_status(conn, draft.post_id, store.STATUS_APPROVED)
                summary.approved += 1
                summary.remaining -= 1
                break
            if action == REJECT:
                store.set_status(conn, draft.post_id, store.STATUS_REJECTED)
                summary.rejected += 1
                summary.remaining -= 1
                break
            if action == EDIT:
                edited = edit(comment).strip()
                new_comment = disclosed(edited) if edited else comment
                if new_comment and new_comment != comment:
                    store.update_comment(conn, draft.post_id, new_comment)
                    comment = new_comment
                    summary.edited += 1
                    out("  (comment updated)")
                else:
                    out("  (no change)")
                continue  # stay on this draft so the reviewer can then approve it
            if action == SKIP:
                summary.skipped += 1
                break
            if action == QUIT:
                return summary
            # Any unexpected action is treated as skip-and-continue defensively.
            summary.skipped += 1
            break

    return summary


def _with_comment(draft: Draft, comment: str) -> Draft:
    """A copy of `draft` showing possibly-edited comment text (display only)."""
    if comment == draft.comment:
        return draft
    return Draft(**{**draft.__dict__, "comment": comment})
