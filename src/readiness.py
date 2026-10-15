"""Offline preparation checks. Never authenticate, inspect tokens, or grant access."""

from __future__ import annotations

from pathlib import Path

import yaml

from . import policy
from .config import CONFIG_PATH, load_config

ROOT = Path(__file__).resolve().parent.parent


def initialize(username: str, community: str, path: Path = CONFIG_PATH) -> None:
    """Record public setup details only; never fabricate an approval or overwrite config."""
    if path.exists():
        raise SystemExit("Configuration already exists; edit it without overwriting recorded evidence")
    for value in (username, community):
        if not value or not value.replace("_", "").replace("-", "").isalnum():
            raise SystemExit("Use a plain Reddit username and community name")
    data = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8-sig"))
    data["reddit"]["username"] = username
    data["reddit"]["user_agent"] = f"contribution-helper/0.3 by u/{username}"
    data["subreddits"][0]["name"] = community
    data["policy"]["operator_identity"] = f"u/{username}"
    data["policy"]["approved_purpose"] = "Personal, non-commercial, human-written contributions"
    with path.open("x", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    print("Public details recorded. Approval, dedicated-account and review attestations remain unset.")


def report(path: Path = CONFIG_PATH) -> bool:
    try:
        config = load_config(path, require_credentials=False)
    except SystemExit as error:
        print(f"BLOCKED: {error}")
        return False
    required = (
        "api_approval_reference",
        "app_registration_reference",
        "app_profile_label_reference",
        "dedicated_app_username",
        "operator_identity",
        "deletion_contact",
        "approved_purpose",
        "terms_accepted_on",
        "devvit_assessment_reference",
        "external_api_exception_reference",
        "storage_security_reference",
        "backup_deletion_procedure_reference",
        "cleanup_schedule_reference",
        "privacy_policy_reviewed",
        "data_security_reviewed",
        "privacy_notice_sha256",
    )
    for key in required:
        print(f"{'RECORDED' if getattr(config.policy, key) else 'MISSING'}: policy.{key}")
    try:
        policy.require_post(config, config.subreddits[0].name)
    except SystemExit as error:
        print(f"BLOCKED: {error}")
        return False
    print("Local attestations pass. Credentials, actual approval and Reddit access were NOT verified.")
    return True


def review_privacy(path: Path = CONFIG_PATH) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    settings = data.get("policy") or {}
    notice = policy.PRIVACY_PATH.read_text(encoding="utf-8-sig")
    identity = settings.get("operator_identity", "")
    contact = settings.get("deletion_contact", "")
    if "[REQUIRED" in notice or not identity or not contact or identity not in notice or contact not in notice:
        raise SystemExit("Complete the notice and include your configured operator identity/deletion contact first")
    print(notice)
    try:
        confirmation = input("Have you reviewed this notice against your actual practices? Type reviewed: ")
    except EOFError:
        confirmation = ""
    if confirmation.strip() != "reviewed":
        raise SystemExit("Privacy review was not recorded")
    settings["privacy_notice_sha256"] = policy.privacy_digest()
    settings["privacy_policy_reviewed"] = True
    data["policy"] = settings
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print("Privacy review recorded for these exact bytes. Later notice edits invalidate it.")
