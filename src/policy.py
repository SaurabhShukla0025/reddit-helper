"""Fail-closed operational checks for the contribution assistant.

Configuration records permissions obtained elsewhere; it cannot verify or grant
Reddit approval. No network is used by these checks.
"""
from datetime import date

from .config import Config, PolicyConfig, Subreddit

AI_DISCLOSURE = "AI-assisted draft, reviewed and edited as needed by a human."


def require_api(config: Config) -> None:
    p = config.policy
    required = {
        "api_approval_reference": p.api_approval_reference,
        "app_registration_reference": p.app_registration_reference,
        "dedicated_app_username": p.dedicated_app_username,
        "privacy_policy_reviewed": p.privacy_policy_reviewed,
        "data_security_reviewed": p.data_security_reviewed,
        "deletion_contact": p.deletion_contact,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise SystemExit("Live API access blocked: record real permissions/settings in policy: " + ", ".join(missing))
    if config.reddit.username.casefold() != p.dedicated_app_username.casefold():
        raise SystemExit("Live API access blocked: reddit.username must match the dedicated app account")
    for sub in config.subreddits:
        require_community(sub)


def require_community(sub: Subreddit, *, comments: bool = False) -> None:
    if not sub.access_reference:
        raise SystemExit(f"r/{sub.name}: record access_reference for the approved community scope")
    try:
        reviewed = date.fromisoformat(sub.rules_reviewed_on)
    except ValueError:
        raise SystemExit(f"r/{sub.name}: rules_reviewed_on must be a YYYY-MM-DD date")
    age = (date.today() - reviewed).days
    if not 0 <= age <= 30:
        raise SystemExit(f"r/{sub.name}: review current community rules (review must be within 30 days)")
    if comments and (not sub.comments_reference or not sub.ai_comments_allowed):
        raise SystemExit(f"r/{sub.name}: posting requires comments_reference and permission for disclosed AI comments")


def require_external_ai(p: PolicyConfig) -> None:
    if not p.external_ai_approval_reference or not p.provider_data_use_reviewed:
        raise SystemExit("Gemini drafting blocked: record explicit authorization for "
                         "third-party AI processing and review provider data use")


def require_post(config: Config, subreddit: str) -> None:
    require_api(config)
    require_external_ai(config.policy)
    sub = next((s for s in config.subreddits if s.name.casefold() == subreddit.casefold()), None)
    if sub is None:
        raise SystemExit(f"r/{subreddit}: not in the currently approved community list")
    require_community(sub, comments=True)


def disclosed(comment: str) -> str:
    """Append a fixed disclosure; the operator cannot configure it away."""
    if comment.rstrip().endswith(AI_DISCLOSURE):
        return comment.strip()
    return f"{comment.strip()}\n\n{AI_DISCLOSURE}"
