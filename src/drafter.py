"""Drafts a review-queue comment for one post using the Claude API.

The drafter never posts. It returns comment *text* that a human reviews later
(step 4). `draft_comment` takes an already-built client so it can be tested with
a fake - the only function that imports the Anthropic SDK is `make_client`.
"""
from __future__ import annotations

import os

from .config import ClaudeConfig
from .fetch import Post

# Sentinel the model returns when a post is not worth a genuine comment.
SKIP = "SKIP"

SYSTEM_PROMPT = (
    "You draft a single Reddit comment for a human to review before anything is "
    "posted. You never post; your output is a draft only.\n\n"
    "Rules:\n"
    "- Follow the community's guidelines exactly (given with each post).\n"
    "- Be genuinely helpful, specific and concrete - add real value, not filler.\n"
    "- Match the subreddit's tone.\n"
    "- No self-promotion, no links to your own products, no spam.\n"
    "- Write ONLY the comment text: no preamble, no surrounding quotes, no "
    "\"Here is a comment\".\n"
    f"- If the post is not something you can add genuine value to, reply with "
    f"exactly: {SKIP}"
)


class DraftError(RuntimeError):
    """Raised when the model declines or returns nothing usable."""


def render_prompt(post: Post, guidelines: str) -> str:
    """The user-turn text for one post. Pure - no network, easy to test."""
    body = post.selftext.strip() or "(link/image post, no body text)"
    guide = guidelines.strip() or "(no specific guidelines provided)"
    return (
        f"Subreddit: r/{post.subreddit}\n"
        f"Community guidelines:\n{guide}\n\n"
        f"Post title: {post.title}\n"
        f"Post body:\n{body}\n\n"
        f"Draft a comment that follows the guidelines, or reply {SKIP}."
    )


def _text_of(response) -> str:
    """Joins the text blocks of a Messages response, ignoring thinking blocks."""
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


def draft_comment(client, post: Post, guidelines: str, cfg: ClaudeConfig) -> str | None:
    """Returns a draft comment, or None when the model chose to skip the post.

    Raises DraftError if the model refused on safety grounds or returned nothing.
    """
    response = client.messages.create(
        model=cfg.model,
        max_tokens=cfg.max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": cfg.effort},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": render_prompt(post, guidelines)}],
    )

    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None)
        raise DraftError(f"the model declined this post (category: {category})")

    text = _text_of(response)
    if not text:
        raise DraftError("the model returned an empty draft")
    if text == SKIP:
        return None
    return text


def make_client():
    """Builds an authenticated Anthropic client, or exits with clear guidance.

    The API key comes from the environment, never from config.yaml.
    """
    try:
        import anthropic
    except ImportError:
        raise SystemExit(
            "The 'anthropic' package is not installed. Run:\n"
            "  pip install -r requirements.txt"
        )

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise SystemExit(
            "No Claude API key found. Set it before drafting:\n"
            '  PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."\n'
            "Get a key at https://console.anthropic.com/"
        )
    return anthropic.Anthropic()
