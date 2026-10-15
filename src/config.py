"""Configuration for the single-community manual assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .credentials import KEYS, load_secrets


@dataclass
class RedditCreds:
    client_id: str
    client_secret: str
    username: str
    password: str
    user_agent: str


@dataclass
class Subreddit:
    name: str
    guidelines: str = ""
    access_reference: str = ""
    comments_reference: str = ""
    rules_reviewed_on: str = ""


@dataclass
class PolicyConfig:
    api_approval_reference: str = ""
    app_registration_reference: str = ""
    dedicated_app_username: str = ""
    privacy_policy_reviewed: bool = False
    data_security_reviewed: bool = False
    deletion_contact: str = ""
    approved_purpose: str = ""
    approval_conditions: str = ""
    approval_expires_on: str = ""
    retention_days: int = 7
    operator_identity: str = ""
    app_profile_label_reference: str = ""
    terms_accepted_on: str = ""
    devvit_assessment_reference: str = ""
    external_api_exception_reference: str = ""
    storage_security_reference: str = ""
    backup_deletion_procedure_reference: str = ""
    cleanup_schedule_reference: str = ""
    privacy_notice_sha256: str = ""


@dataclass
class PostConfig:
    max_posts_per_day: int = 3


@dataclass
class Config:
    reddit: RedditCreds
    subreddits: list[Subreddit]
    post: PostConfig = field(default_factory=PostConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _policy_config(raw: dict) -> PolicyConfig:
    if not isinstance(raw, dict):
        raise SystemExit("policy must be a mapping")
    unknown = set(raw) - set(PolicyConfig.__dataclass_fields__)
    if unknown:
        raise SystemExit(f"Unknown policy settings: {', '.join(sorted(unknown))}; migrate config.example.yaml")
    values = dict(raw)
    for key in ("privacy_policy_reviewed", "data_security_reviewed"):
        if key in values and not isinstance(values[key], bool):
            raise SystemExit(f"policy.{key} must be true or false")
    days = values.get("retention_days", 7)
    if type(days) is not int or not 1 <= days <= 30:
        raise SystemExit("policy.retention_days must be an integer between 1 and 30")
    for key in set(values) - {"retention_days", "privacy_policy_reviewed", "data_security_reviewed"}:
        values[key] = str(values[key] or "").strip()
    return PolicyConfig(**values)


def load_config(path: Path = CONFIG_PATH, *, require_credentials: bool = True) -> Config:
    if not path.exists():
        raise SystemExit("Copy config.example.yaml to config.yaml and record real authorization.")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except OSError:
        raise SystemExit("Cannot read protected config; run as the owning Windows user") from None
    except yaml.YAMLError:
        raise SystemExit("Configuration must be valid YAML") from None
    if not isinstance(data, dict):
        raise SystemExit("Configuration must be a mapping")
    if set(data) - {"reddit", "policy", "post", "subreddits"}:
        raise SystemExit("Legacy/unknown configuration: migrate using config.example.yaml")
    settings = data.get("reddit") or {}
    if set(settings) - {"username", "user_agent"}:
        raise SystemExit("Store Reddit credentials in environment variables, not config.yaml")
    username = str(settings.get("username") or "")
    secrets = load_secrets() if require_credentials else dict.fromkeys(KEYS, "")
    creds = RedditCreds(
        secrets["REDDIT_CLIENT_ID"],
        secrets["REDDIT_CLIENT_SECRET"],
        username,
        secrets["REDDIT_PASSWORD"],
        str(settings.get("user_agent") or ""),
    )
    if require_credentials and (not all(vars(creds).values()) or username == "YOUR_APP_USERNAME"):
        raise SystemExit("Set Reddit environment credentials and configure the app username/user agent")
    communities = data.get("subreddits") or []
    if len(communities) != 1:
        raise SystemExit("Configure exactly one approved community")
    community = communities[0]
    if set(community) - set(Subreddit.__dataclass_fields__):
        raise SystemExit("Legacy/unknown community settings: migrate config.example.yaml")
    sub = Subreddit(**{key: str(value or "").strip() for key, value in community.items()})
    if not sub.name or not sub.name.replace("_", "").isalnum():
        raise SystemExit("Use a community name without r/ or a URL")
    posting = data.get("post") or {}
    cap = posting.get("max_posts_per_day", 3)
    if set(posting) - {"max_posts_per_day"} or type(cap) is not int or not 1 <= cap <= 10:
        raise SystemExit("post.max_posts_per_day must be an integer between 1 and 10; remove legacy settings")
    return Config(creds, [sub], PostConfig(cap), _policy_config(data.get("policy") or {}))
