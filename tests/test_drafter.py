"""Tests for the Gemini drafter. A fake client stands in for the SDK, so these
tests make no network calls and cost nothing."""
from __future__ import annotations

from functools import partial
from types import SimpleNamespace

import pytest

from src.config import GeminiConfig, PolicyConfig
from src.drafter import SKIP, DraftError, render_prompt
from src.drafter import draft_comment as unchecked_draft
from src.fetch import Post
from src.policy import disclosed

CFG = GeminiConfig()
draft_comment = partial(unchecked_draft, policy=PolicyConfig(
    external_ai_approval_reference="test permission", provider_data_use_reviewed=True))


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
    """Mimics genai.Client: records generate_content kwargs, returns a response."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def resp(text, block_reason=None):
    feedback = SimpleNamespace(block_reason=block_reason)
    return SimpleNamespace(text=text, prompt_feedback=feedback)


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


def test_draft_comment_returns_text():
    client = FakeClient(resp("Use json.load(open('data.json'))."))
    result = draft_comment(client, make_post(), "Be concrete.", CFG)
    assert result == disclosed("Use json.load(open('data.json')).")


def test_unapproved_ai_processing_makes_no_request():
    client = FakeClient(resp("ok"))
    with pytest.raises(SystemExit, match="blocked"):
        unchecked_draft(client, make_post(), "", CFG)
    assert client.calls == []


def test_draft_comment_passes_model_and_config():
    client = FakeClient(resp("ok"))
    draft_comment(client, make_post(), "", GeminiConfig(model="gemini-3.8-flash", temperature=0.4, max_tokens=800))
    call = client.calls[0]
    assert call["model"] == "gemini-3.8-flash"
    assert call["config"]["temperature"] == 0.4
    assert call["config"]["max_output_tokens"] == 800
    assert "system_instruction" in call["config"]


def test_skip_sentinel_returns_none():
    client = FakeClient(resp(SKIP))
    assert draft_comment(client, make_post(), "", CFG) is None


def test_blocked_prompt_raises_drafterror():
    client = FakeClient(resp(None, block_reason="SAFETY"))
    with pytest.raises(DraftError, match="blocked"):
        draft_comment(client, make_post(), "", CFG)


def test_empty_text_raises_drafterror():
    client = FakeClient(resp("   "))  # whitespace only -> empty after strip
    with pytest.raises(DraftError, match="empty"):
        draft_comment(client, make_post(), "", CFG)
