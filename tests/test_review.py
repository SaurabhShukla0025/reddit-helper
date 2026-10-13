"""Tests for the review orchestration and the queue mutations it relies on.

A real in-memory SQLite queue is seeded, and the reviewer's actions/edits are
supplied as canned callables, so the whole flow runs with no terminal."""
from __future__ import annotations

import pytest

from src import review, store
from src.policy import disclosed


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def seed(conn, *post_ids):
    for pid in post_ids:
        store.add_draft(
            conn,
            post_id=pid,
            subreddit="learnpython",
            post_title=f"title {pid}",
            post_url=f"https://reddit.com/{pid}",
            post_author="someone",
            comment=f"draft for {pid}",
            model="claude-opus-5-5",
        )


def scripted(actions):
    """A prompt_fn that returns each queued action in turn."""
    seq = iter(actions)
    return lambda draft: next(seq)


def test_store_set_status_and_get(conn):
    seed(conn, "t3_1")
    store.set_status(conn, "t3_1", store.STATUS_APPROVED)
    assert store.get_draft(conn, "t3_1").status == store.STATUS_APPROVED


def test_store_set_status_rejects_unknown(conn):
    seed(conn, "t3_1")
    with pytest.raises(ValueError):
        store.set_status(conn, "t3_1", "banana")


def test_store_update_comment(conn):
    seed(conn, "t3_1")
    store.update_comment(conn, "t3_1", "a better comment")
    assert store.get_draft(conn, "t3_1").comment == "a better comment"


def test_get_missing_draft_is_none(conn):
    assert store.get_draft(conn, "nope") is None


def test_approve_reject_skip(conn):
    seed(conn, "t3_a", "t3_b", "t3_c")
    # Apply actions in whatever order the queue actually presents drafts.
    order = [d.post_id for d in store.list_drafts(conn, status=store.STATUS_PENDING)]
    summary = review.run_review(
        conn,
        prompt=scripted([review.APPROVE, review.REJECT, review.SKIP]),
        edit=lambda c: c,
        out=lambda _msg: None,
    )
    assert (summary.approved, summary.rejected, summary.skipped) == (1, 1, 1)
    assert store.get_draft(conn, order[0]).status == store.STATUS_APPROVED
    assert store.get_draft(conn, order[1]).status == store.STATUS_REJECTED
    assert store.get_draft(conn, order[2]).status == store.STATUS_PENDING  # skipped stays


def test_edit_then_approve_updates_comment_and_status(conn):
    seed(conn, "t3_1")
    summary = review.run_review(
        conn,
        prompt=scripted([review.EDIT, review.APPROVE]),
        edit=lambda current: "edited comment text",
        out=lambda _msg: None,
    )
    assert summary.edited == 1
    assert summary.approved == 1
    draft = store.get_draft(conn, "t3_1")
    assert draft.comment == disclosed("edited comment text")
    assert draft.status == store.STATUS_APPROVED


def test_edit_with_no_change_is_not_counted(conn):
    seed(conn, "t3_1")
    summary = review.run_review(
        conn,
        prompt=scripted([review.EDIT, review.SKIP]),
        edit=lambda current: current,  # returns the same text
        out=lambda _msg: None,
    )
    assert summary.edited == 0


def test_quit_stops_and_leaves_rest_pending(conn):
    seed(conn, "t3_a", "t3_b", "t3_c")
    summary = review.run_review(
        conn,
        prompt=scripted([review.APPROVE, review.QUIT]),
        edit=lambda c: c,
        out=lambda _msg: None,
    )
    assert summary.approved == 1
    # One approved, two never reached -> two still pending.
    assert len(store.list_drafts(conn, status=store.STATUS_PENDING)) == 2


def test_render_draft_shows_title_and_comment_lines():
    draft = store.Draft(
        post_id="t3_1", subreddit="learnpython", post_title="a title",
        post_url="https://reddit.com/t3_1", post_author="me",
        comment="line one\nline two", status="pending",
        model="claude-opus-5-5", created_at="now", updated_at="now",
    )
    text = review.render_draft(draft, 1, 3)
    assert "[1/3]" in text
    assert "a title" in text
    assert "| line one" in text
    assert "| line two" in text
