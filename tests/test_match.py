"""Tests for the matching logic. No network — Posts are built by hand."""
from __future__ import annotations

import time

from src.config import MatchRules, Subreddit
from src.fetch import Post
from src.match import evaluate, match_all

NOW = 1_000_000.0  # fixed "current time" so age tests are deterministic


def make_post(**over) -> Post:
    base = dict(
        id="t3_1",
        subreddit="learnpython",
        title="How do I fix this TypeError?",
        author="someone",
        score=5,
        num_comments=2,
        url="https://reddit.com/r/learnpython/comments/1",
        selftext="I keep getting an error when I run my script.",
        created_utc=NOW - 3600,  # 1 hour old
    )
    base.update(over)
    return Post(**base)


def test_matches_when_all_gates_pass():
    rules = MatchRules(keywords=("typeerror",), min_score=1)
    result = evaluate(make_post(), rules, now=NOW)
    assert result.matched
    assert "typeerror" in result.reason


def test_empty_keywords_matches_any_post():
    result = evaluate(make_post(), MatchRules(), now=NOW)
    assert result.matched
    assert result.reason == "no keyword filter"


def test_keyword_miss_is_rejected():
    rules = MatchRules(keywords=("django",))
    result = evaluate(make_post(), rules, now=NOW)
    assert not result.matched
    assert result.reason == "no keyword match"


def test_exclude_wins_over_keyword():
    rules = MatchRules(keywords=("typeerror",), exclude=("hiring",))
    post = make_post(title="Hiring a Python dev — TypeError bounty")
    result = evaluate(post, rules, now=NOW)
    assert not result.matched
    assert "hiring" in result.reason


def test_keywords_and_exclude_are_case_insensitive():
    rules = MatchRules(keywords=("TypeError",), exclude=("HIRING",))
    assert evaluate(make_post(), rules, now=NOW).matched
    assert not evaluate(make_post(title="HIRING now"), rules, now=NOW).matched


def test_keyword_checks_selftext_too():
    rules = MatchRules(keywords=("script",))
    post = make_post(title="Totally unrelated headline")
    assert evaluate(post, rules, now=NOW).matched


def test_score_bounds():
    rules = MatchRules(min_score=10, max_score=100)
    assert not evaluate(make_post(score=5), rules, now=NOW).matched
    assert evaluate(make_post(score=50), rules, now=NOW).matched
    assert not evaluate(make_post(score=200), rules, now=NOW).matched


def test_comment_bounds():
    rules = MatchRules(max_comments=5)
    assert evaluate(make_post(num_comments=3), rules, now=NOW).matched
    assert not evaluate(make_post(num_comments=9), rules, now=NOW).matched


def test_age_gate():
    rules = MatchRules(max_age_hours=2)
    assert evaluate(make_post(created_utc=NOW - 3600), rules, now=NOW).matched       # 1h old
    assert not evaluate(make_post(created_utc=NOW - 10 * 3600), rules, now=NOW).matched  # 10h old


def test_match_all_keys_by_subreddit_and_skips_unknown():
    sub = Subreddit(name="learnpython", guidelines="", rules=MatchRules(keywords=("typeerror",)))
    fetched = {
        "learnpython": [make_post(), make_post(title="no match here", selftext="")],
        "notconfigured": [make_post()],  # not in subreddits -> ignored
    }
    results = match_all(fetched, [sub], now=NOW)
    assert set(results) == {"learnpython"}
    verdicts = results["learnpython"]
    assert [v.matched for v in verdicts] == [True, False]


def test_default_now_uses_wall_clock():
    # No `now` passed: a fresh post should still be within a generous age gate.
    rules = MatchRules(max_age_hours=24)
    assert evaluate(make_post(created_utc=time.time()), rules).matched
