"""Tests for the SQLite review queue. Uses an in-memory database."""
from __future__ import annotations

import pytest

from src import store


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def add(conn, post_id="t3_1", status=store.STATUS_PENDING, subreddit="learnpython"):
    return store.add_draft(
        conn,
        post_id=post_id,
        subreddit=subreddit,
        post_title="How do I fix this?",
        post_url=f"https://reddit.com/{post_id}",
        post_author="someone",
        comment="Here is a concrete suggestion...",
        model="claude-opus-5-5",
        status=status,
    )


def test_add_and_has_draft(conn):
    assert not store.has_draft(conn, "t3_1")
    draft = add(conn)
    assert draft.status == store.STATUS_PENDING
    assert store.has_draft(conn, "t3_1")


def test_duplicate_post_id_is_rejected(conn):
    add(conn, post_id="t3_dup")
    with pytest.raises(Exception):
        add(conn, post_id="t3_dup")


def test_list_and_filter_by_status(conn):
    add(conn, post_id="t3_a", status=store.STATUS_PENDING)
    add(conn, post_id="t3_b", status=store.STATUS_APPROVED)

    assert {d.post_id for d in store.list_drafts(conn)} == {"t3_a", "t3_b"}
    pending = store.list_drafts(conn, status=store.STATUS_PENDING)
    assert [d.post_id for d in pending] == ["t3_a"]


def test_count_by_status(conn):
    add(conn, post_id="t3_a", status=store.STATUS_PENDING)
    add(conn, post_id="t3_b", status=store.STATUS_PENDING)
    add(conn, post_id="t3_c", status=store.STATUS_APPROVED)
    assert store.count_by_status(conn) == {
        store.STATUS_PENDING: 2,
        store.STATUS_APPROVED: 1,
    }


def test_schema_survives_reconnect(tmp_path):
    db = tmp_path / "queue.db"
    first = store.connect(db)
    add(first, post_id="t3_persist")
    first.close()

    second = store.connect(db)  # reopening must not wipe the row
    assert store.has_draft(second, "t3_persist")
    second.close()
