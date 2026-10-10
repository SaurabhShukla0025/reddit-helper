"""Tests for karma tracking. A fake score lookup stands in for Reddit, so these
tests read no network and record into an in-memory queue."""
from __future__ import annotations

import pytest

from src import karma, store


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def seed_posted(conn, post_id, url="https://www.reddit.com/c/abc"):
    store.add_draft(
        conn, post_id=post_id, subreddit="learnpython", post_title=f"title {post_id}",
        post_url=f"https://reddit.com/{post_id}", post_author="someone",
        comment="comment", model="claude-opus-5-5", status=store.STATUS_POSTED,
    )
    store.mark_posted(conn, post_id, url)
    return store.list_drafts(conn, status=store.STATUS_POSTED)


def test_record_and_history_order(conn):
    seed_posted(conn, "t3_a")
    store.record_karma(conn, "t3_a", 1)
    store.record_karma(conn, "t3_a", 5)
    store.record_karma(conn, "t3_a", 12)
    history = store.karma_history(conn, "t3_a")
    assert [h.score for h in history] == [1, 5, 12]  # oldest first


def test_check_karma_records_scores(conn):
    posted = seed_posted(conn, "t3_a")
    scores = {"https://www.reddit.com/c/abc": 7}
    checked = karma.check_karma(
        conn, reddit=None, posted=posted,
        get_score=lambda reddit, url: scores[url], out=lambda m: None,
    )
    assert checked == 1
    assert store.karma_history(conn, "t3_a")[-1].score == 7


def test_check_karma_skips_unreadable_comment(conn):
    posted = seed_posted(conn, "t3_a")

    def boom(reddit, url):
        raise RuntimeError("comment deleted")

    checked = karma.check_karma(
        conn, reddit=None, posted=posted, get_score=boom, out=lambda m: None,
    )
    assert checked == 0
    assert store.karma_history(conn, "t3_a") == []  # nothing recorded


def test_check_karma_skips_draft_without_url(conn):
    # A 'posted' row with no posted_url shouldn't be queried.
    store.add_draft(
        conn, post_id="t3_nourl", subreddit="x", post_title="t", post_url="u",
        post_author="a", comment="c", model="m", status=store.STATUS_POSTED,
    )
    posted = store.list_drafts(conn, status=store.STATUS_POSTED)
    calls = []
    karma.check_karma(
        conn, reddit=None, posted=posted,
        get_score=lambda r, u: calls.append(u) or 1, out=lambda m: None,
    )
    assert calls == []  # never called for a url-less draft


def test_report_computes_first_latest_delta_and_total(conn):
    seed_posted(conn, "t3_a", url="https://www.reddit.com/c/a")
    seed_posted(conn, "t3_b", url="https://www.reddit.com/c/b")
    posted = store.list_drafts(conn, status=store.STATUS_POSTED)
    store.record_karma(conn, "t3_a", 2)
    store.record_karma(conn, "t3_a", 10)
    store.record_karma(conn, "t3_b", 3)

    a = next(r for r in karma.report(conn, posted) if r.post_title == "title t3_a")
    b = next(r for r in karma.report(conn, posted) if r.post_title == "title t3_b")

    assert (a.first_score, a.latest_score, a.delta, a.samples) == (2, 10, 8, 2)
    assert (b.first_score, b.latest_score, b.delta, b.samples) == (3, 3, 0, 1)
    assert karma.total_karma(karma.report(conn, posted)) == 10 + 3


def test_report_omits_comments_with_no_readings(conn):
    posted = seed_posted(conn, "t3_a")
    # No record_karma call -> no history -> not in the report.
    assert karma.report(conn, posted) == []
