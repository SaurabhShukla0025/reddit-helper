"""Fail-closed checks. Operator attestations never grant Reddit permission."""

from datetime import date
from hashlib import sha256
from pathlib import Path

from .config import Config, Subreddit

PRIVACY_PATH = Path(__file__).resolve().parent.parent / "PRIVACY.md"


def privacy_digest() -> str:
    return sha256(PRIVACY_PATH.read_bytes()).hexdigest()


def require_api(config: Config) -> None:
    p = config.policy
    required = (
        "api_approval_reference",
        "app_registration_reference",
        "dedicated_app_username",
        "privacy_policy_reviewed",
        "data_security_reviewed",
        "deletion_contact",
        "approved_purpose",
        "operator_identity",
        "app_profile_label_reference",
        "terms_accepted_on",
        "devvit_assessment_reference",
        "external_api_exception_reference",
        "storage_security_reference",
        "backup_deletion_procedure_reference",
        "cleanup_schedule_reference",
        "privacy_notice_sha256",
    )
    missing = [key for key in required if not getattr(p, key)]
    if missing:
        raise SystemExit("Live API access blocked: record real authorization: " + ", ".join(missing))
    try:
        terms_date = date.fromisoformat(p.terms_accepted_on)
    except ValueError:
        raise SystemExit("Record the actual developer/API terms acceptance date (YYYY-MM-DD)")
    if terms_date > date.today():
        raise SystemExit("Terms acceptance cannot be future-dated")
    try:
        notice = PRIVACY_PATH.read_text(encoding="utf-8-sig")
    except OSError:
        raise SystemExit("Live access blocked: privacy notice is unavailable") from None
    if "[REQUIRED" in notice or p.privacy_notice_sha256 != privacy_digest():
        raise SystemExit("Live access blocked: complete and review the current privacy notice")
    if p.operator_identity not in notice or p.deletion_contact not in notice:
        raise SystemExit("Live access blocked: privacy notice must identify the operator and deletion contact")
    if config.reddit.username.casefold() != p.dedicated_app_username.casefold():
        raise SystemExit("Live API access blocked: dedicated app username mismatch")
    if p.approval_expires_on:
        try:
            expiry = date.fromisoformat(p.approval_expires_on)
        except ValueError:
            raise SystemExit("approval_expires_on must be YYYY-MM-DD")
        if date.today() > expiry:
            raise SystemExit("Live API access blocked: approval expired")
    if len(config.subreddits) != 1:
        raise SystemExit("Exactly one approved community is required")
    require_community(config.subreddits[0])


def require_community(sub: Subreddit, *, comments: bool = False) -> None:
    if not sub.access_reference:
        raise SystemExit("Community access approval is missing")
    try:
        reviewed = date.fromisoformat(sub.rules_reviewed_on)
    except ValueError:
        raise SystemExit("rules_reviewed_on must be YYYY-MM-DD")
    if not 0 <= (date.today() - reviewed).days <= 30:
        raise SystemExit("Review current community rules before continuing")
    if comments and not sub.comments_reference:
        raise SystemExit("Community permission for app replies is missing")


def require_post(config: Config, subreddit: str) -> None:
    require_api(config)
    sub = config.subreddits[0]
    if sub.name.casefold() != subreddit.casefold():
        raise SystemExit("Post is outside the approved community")
    require_community(sub, comments=True)
