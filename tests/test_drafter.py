"""Tests for the Claude-API drafter. A fake client stands in for the SDK, so
these tests make no network calls and cost nothing."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import ClaudeConfig
from src.drafter import DraftError, SKIP, draft_comment, render_prompt
from src.fetch import Post

CFG = ClaudeConfig()


def make_post(**over) -> Post:
    base = dict(
        id="t3_1",
        subreddit="learnpython",
        title="How do I read a JSON file?",
        author="someone",
        score=5,
        num_comments=1,
        url="https://reddit.com/r/learnpython/comments/1",
        selftext="I have a file called data.json and I want the dict.",
        created_utc=1_000_000.0,
    )
    base.update(over)
    return Post(**base)


class FakeClient:
    """Records the create() kwargs and returns a canned response."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def text_response(text: str, stop_reason: str = "end_turn"):
    content = [SimpleNamespace(type="thinking", thinking="...")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(content=content, stop_reason=stop_reason, stop_details=None)


def test_render_prompt_includes_guidelines_title_and_body():
    prompt = render_prompt(make_post(), "Be concrete and kind.")
    assert "Be concrete and kind." in prompt
    assert "How do I read a JSON file?" in prompt
    assert "data.json" in prompt
    assert "r/learnpython" in prompt


def test_render_prompt_handles_empty_body_and_guidelines():
    prompt = render_prompt(make_post(selftext=""), "")
    assert "(link/image post, no body text)" in prompt
    assert "(no specific guidelines provided)" in prompt


def test_draft_comment_returns_text_and_skips_thinking_blocks():
    client = FakeClient(text_response("Use json.load(open('data.json'))."))
    result = draft_comment(client, make_post(), "Be concrete.", CFG)
    assert result == "Use json.load(open('data.json'))."


def test_draft_comment_passes_model_and_effort():
    client = FakeClient(text_response("ok"))
    draft_comment(client, make_post(), "", ClaudeConfig(model="claude-opus-5-5", effort="low"))
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert call["thinking"] == {"type": "adaptive"}


def test_skip_sentinel_returns_none():
    client = FakeClient(text_response(SKIP))
    assert draft_comment(client, make_post(), "", CFG) is None


def test_refusal_raises_drafterror():
    response = SimpleNamespace(
        content=[],
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber", explanation="no"),
    )
    client = FakeClient(response)
    with pytest.raises(DraftError, match="declined"):
        draft_comment(client, make_post(), "", CFG)


def test_empty_text_raises_drafterror():
    client = FakeClient(text_response("   "))  # whitespace only -> empty after strip
    with pytest.raises(DraftError, match="empty"):
        draft_comment(client, make_post(), "", CFG)
