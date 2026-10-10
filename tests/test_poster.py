"""Tests for the posting logic. A fake submit stands in for Reddit, and sleep is
a no-op recorder, so these tests post nothing and never actually wait."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src import poster, store


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def seed_approved(conn, *post_ids):
    for pid in post_ids:
        store.add_draft(
            conn, post_id=pid, subreddit="learnpython", post_title=f"title {pid}",
            post_url=f"https://reddit.com/{pid}", post_author="someone",
            comment=f"comment {pid}", model="claude-opus-5-5",
            status=store.STATUS_APPROVED,
        )
    return store.list_drafts(conn, status=store.STATUS_APPROVED)


def test_posts_all_and_marks_posted(conn):
    batch = seed_approved(conn, "t3_a", "t3_b")
    submit = lambda reddit, pid, body: f"https://www.reddit.com/c/{pid}"
    run = poster.run_posts(
        conn, reddit=None, drafts=batch,
        delay=lambda: 0, submit=submit, sleep=lambda s: None, out=lambda m: None,
    )
    assert len(run.posted) == 2
    assert not run.failed
    for draft in batch:
        row = store.get_draft(conn, draft.post_id)
        assert row.status == store.STATUS_POSTED
        assert row.posted_url == f"https://www.reddit.com/c/{draft.post_id}"


def test_pacing_sleeps_between_but_not_before_first(conn):
    batch = seed_approved(conn, "t3_a", "t3_b", "t3_c")
    sleeps: list[float] = []
    poster.run_posts(
        conn, reddit=None, drafts=batch,
        delay=lambda: 42, submit=lambda r, p, b: "url",
        sleep=sleeps.append, out=lambda m: None,
    )
    # Three posts -> two pauses (none before the first).
    assert sleeps == [42, 42]


def test_generic_error_is_recorded_and_draft_stays_approved(conn):
    batch = seed_approved(conn, "t3_a")

    def boom(reddit, pid, body):
        raise RuntimeError("post is locked")

    run = poster.run_posts(
        conn, reddit=None, drafts=batch,
        delay=lambda: 0, submit=boom, sleep=lambda s: None, out=lambda m: None,
    )
    assert len(run.failed) == 1
    assert run.failed[0].error == "post is locked"
    assert store.get_draft(conn, "t3_a").status == store.STATUS_APPROVED


def test_rate_limit_then_success_retries(conn):
    batch = seed_approved(conn, "t3_a")
    calls = {"n": 0}

    def flaky(reddit, pid, body):
        calls["n"] += 1
        if calls["n"] == 1:
            raise poster.RateLimited(120)
        return "https://www.reddit.com/c/t3_a"

    sleeps: list[float] = []
    run = poster.run_posts(
        conn, reddit=None, drafts=batch,
        delay=lambda: 0, submit=flaky, sleep=sleeps.append, out=lambda m: None,
    )
    assert calls["n"] == 2          # retried once
    assert sleeps == [120]           # waited the suggested time
    assert len(run.posted) == 1
    assert store.get_draft(conn, "t3_a").status == store.STATUS_POSTED


def test_second_rate_limit_stops_run(conn):
    batch = seed_approved(conn, "t3_a", "t3_b")

    def always_limited(reddit, pid, body):
        raise poster.RateLimited(60)

    run = poster.run_posts(
        conn, reddit=None, drafts=batch,
        delay=lambda: 0, submit=always_limited, sleep=lambda s: None,
        out=lambda m: None, rate_limit_retries=1,
    )
    assert run.stopped_early
    assert not run.posted
    # Nothing was posted, so both drafts remain approved and untouched.
    assert len(store.list_drafts(conn, status=store.STATUS_APPROVED)) == 2


def test_rate_limit_parsing_from_praw_error_shape():
    item = SimpleNamespace(
        error_type="RATELIMIT",
        message="you are doing that too much. try again in 9 minutes.",
    )
    praw_error = SimpleNamespace(items=[item])
    assert poster._parse_wait("try again in 9 minutes.") == 540
    assert poster._parse_wait("wait 30 seconds") == 30
    assert poster._parse_wait("no number here") is None
    assert poster._rate_limit_seconds(praw_error) == 540
    assert poster._rate_limit_seconds(SimpleNamespace(items=None)) is None


def test_delay_from_stays_in_range():
    from src.config import PostConfig
    cfg = PostConfig(min_delay_seconds=100, max_delay_seconds=200)
    captured = {}

    def fake_rng(lo, hi):
        captured["lo"], captured["hi"] = lo, hi
        return 150.0

    delay = poster.delay_from(cfg, rng=fake_rng)
    assert delay() == 150.0
    assert (captured["lo"], captured["hi"]) == (100, 200)
