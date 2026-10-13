"""Loads and validates config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml


@dataclass
class RedditCreds:
    client_id: str
    client_secret: str
    username: str
    password: str
    user_agent: str


@dataclass(frozen=True)
class MatchRules:
    """Which posts count as worth a draft. Empty lists disable that gate.

    A post matches when every gate passes: it contains at least one `keywords`
    term (or `keywords` is empty), none of the `exclude` terms, and its score,
    comment count and age fall within the given bounds.
    """

    keywords: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    min_score: int = 0
    max_score: int | None = None
    min_comments: int = 0
    max_comments: int | None = None
    max_age_hours: float | None = None


@dataclass
class Subreddit:
    name: str
    guidelines: str
    rules: MatchRules
    access_reference: str = ""
    comments_reference: str = ""
    ai_comments_allowed: bool = False
    rules_reviewed_on: str = ""


@dataclass
class PolicyConfig:
    """Operator records of real permissions, not a grant of permission."""

    api_approval_reference: str = ""
    app_registration_reference: str = ""
    dedicated_app_username: str = ""
    privacy_policy_reviewed: bool = False
    data_security_reviewed: bool = False
    deletion_contact: str = ""
    external_ai_approval_reference: str = ""
    provider_data_use_reviewed: bool = False
    retention_days: int = 30


@dataclass
class GeminiConfig:
    """Settings for the Gemini (Google) comment drafter (step 3).

    The API key is NOT stored here - it is read from the GEMINI_API_KEY
    environment variable so no secret lands in a file.
    """

    model: str = "gemini-3.8-flash"
    temperature: float = 0.7
    max_tokens: int = 1024
    max_drafts_per_run: int = 10


@dataclass
class PostConfig:
    """Pacing and safety limits for posting approved comments (step 5)."""

    min_delay_seconds: int = 300   # shortest load-control pause between posts
    max_delay_seconds: int = 900   # longest pause; a random value in [min, max] is used
    max_posts_per_run: int = 5     # safety cap on posts per `post` run


@dataclass
class Config:
    reddit: RedditCreds
    subreddits: list[Subreddit]
    listing: str
    limit: int
    gemini: GeminiConfig
    post: PostConfig
    policy: PolicyConfig = field(default_factory=PolicyConfig)


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
_REQUIRED_CREDS = ("client_id", "client_secret", "username", "password", "user_agent")
_PLACEHOLDERS = {"YOUR_CLIENT_ID", "YOUR_CLIENT_SECRET", "YOUR_REDDIT_USERNAME", "YOUR_REDDIT_PASSWORD"}


def _as_terms(value) -> tuple[str, ...]:
    """A YAML string or list of strings becomes a tuple of non-empty, lowercased terms."""
    if value is None:
        return ()
    items = [value] if isinstance(value, str) else list(value)
    return tuple(term for term in (str(item).strip().lower() for item in items) if term)


def _as_int(value, field: str) -> int | None:
    """Parses a whole number, or exits naming the full `field` path that was bad."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise SystemExit(f"config.yaml: {field} must be a whole number, got {value!r}")


def _as_hours(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SystemExit(f"config.yaml: match.max_age_hours must be a number, got {value!r}")


def _match_rules(raw: dict, base: MatchRules) -> MatchRules:
    """Builds rules from a `match:` block, inheriting any key left unset from `base`."""
    raw = raw or {}
    unknown = set(raw) - {
        "keywords", "exclude", "min_score", "max_score",
        "min_comments", "max_comments", "max_age_hours",
    }
    if unknown:
        raise SystemExit(f"config.yaml: unknown match keys: {', '.join(sorted(unknown))}")

    return replace(
        base,
        keywords=_as_terms(raw["keywords"]) if "keywords" in raw else base.keywords,
        exclude=_as_terms(raw["exclude"]) if "exclude" in raw else base.exclude,
        min_score=_as_int(raw["min_score"], "match.min_score") if "min_score" in raw else base.min_score,
        max_score=_as_int(raw["max_score"], "match.max_score") if "max_score" in raw else base.max_score,
        min_comments=_as_int(raw["min_comments"], "match.min_comments") if "min_comments" in raw else base.min_comments,
        max_comments=_as_int(raw["max_comments"], "match.max_comments") if "max_comments" in raw else base.max_comments,
        max_age_hours=_as_hours(raw["max_age_hours"]) if "max_age_hours" in raw else base.max_age_hours,
    )


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Reads config.yaml, or raises a clear error telling the user what to fix."""
    if not path.exists():
        raise SystemExit(
            f"No config found at {path}.\n"
            "Copy config.example.yaml to config.yaml and fill in your details."
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    reddit = data.get("reddit") or {}
    missing = [key for key in _REQUIRED_CREDS if not reddit.get(key)]
    if missing:
        raise SystemExit(f"config.yaml is missing reddit values: {', '.join(missing)}")
    if _PLACEHOLDERS & {str(v) for v in reddit.values()}:
        raise SystemExit("config.yaml still has example placeholders. Put your real credentials in.")

    # Global match defaults; each subreddit's own `match:` block overrides these.
    defaults = _match_rules(data.get("match") or {}, MatchRules())

    subreddits = [
        Subreddit(
            name=str(item["name"]),
            guidelines=str(item.get("guidelines", "")).strip(),
            rules=_match_rules(item.get("match") or {}, defaults),
            access_reference=str(item.get("access_reference") or "").strip(),
            comments_reference=str(item.get("comments_reference") or "").strip(),
            ai_comments_allowed=_as_bool(item.get("ai_comments_allowed", False), "subreddits.ai_comments_allowed"),
            rules_reviewed_on=str(item.get("rules_reviewed_on") or "").strip(),
        )
        for item in (data.get("subreddits") or [])
        if item.get("name")
    ]
    if not subreddits:
        raise SystemExit("List at least one subreddit under 'subreddits:' in config.yaml.")

    fetch = data.get("fetch") or {}
    listing = str(fetch.get("listing", "new"))
    if listing not in ("new", "rising", "hot"):
        raise SystemExit("fetch.listing must be one of: new, rising, hot")

    return Config(
        reddit=RedditCreds(**{key: str(reddit[key]) for key in _REQUIRED_CREDS}),
        subreddits=subreddits,
        listing=listing,
        limit=int(fetch.get("limit", 10)),
        gemini=_gemini_config(data.get("gemini") or {}),
        post=_post_config(data.get("post") or {}),
        policy=_policy_config(data.get("policy") or {}),
    )


def _as_bool(value, field: str) -> bool:
    if not isinstance(value, bool):
        raise SystemExit(f"config.yaml: {field} must be true or false (not quoted)")
    return value


def _policy_config(raw: dict) -> PolicyConfig:
    if not isinstance(raw, dict):
        raise SystemExit("config.yaml: policy must be a mapping")
    unknown = set(raw) - set(PolicyConfig.__dataclass_fields__)
    if unknown:
        raise SystemExit(f"config.yaml: unknown policy keys: {', '.join(sorted(unknown))}")
    values = {}
    for key in PolicyConfig.__dataclass_fields__:
        if key not in raw:
            continue
        if key in {"privacy_policy_reviewed", "provider_data_use_reviewed", "data_security_reviewed"}:
            values[key] = _as_bool(raw[key], f"policy.{key}")
        elif key == "retention_days":
            value = _as_int(raw[key], "policy.retention_days")
            if value is None or not 1 <= value <= 30:
                raise SystemExit("config.yaml: policy.retention_days must be between 1 and 30")
            values[key] = value
        else:
            values[key] = str(raw[key] or "").strip()
    return PolicyConfig(**values)


def _post_config(raw: dict) -> PostConfig:
    """Builds posting settings from a `post:` block, with sane defaults."""
    defaults = PostConfig()
    unknown = set(raw) - {"min_delay_seconds", "max_delay_seconds", "max_posts_per_run"}
    if unknown:
        raise SystemExit(f"config.yaml: unknown post keys: {', '.join(sorted(unknown))}")

    def non_negative(key: str, fallback: int) -> int:
        if raw.get(key) is None:
            return fallback
        value = _as_int(raw[key], f"post.{key}")
        if value < 0:
            raise SystemExit(f"config.yaml: post.{key} must be 0 or more, got {value}")
        return value

    min_delay = non_negative("min_delay_seconds", defaults.min_delay_seconds)
    max_delay = non_negative("max_delay_seconds", defaults.max_delay_seconds)
    if max_delay < min_delay:
        raise SystemExit(
            f"config.yaml: post.max_delay_seconds ({max_delay}) must be >= "
            f"post.min_delay_seconds ({min_delay})"
        )
    max_posts = non_negative("max_posts_per_run", defaults.max_posts_per_run)
    if max_posts < 1:
        raise SystemExit("config.yaml: post.max_posts_per_run must be at least 1")

    return PostConfig(
        min_delay_seconds=min_delay,
        max_delay_seconds=max_delay,
        max_posts_per_run=max_posts,
    )


def _gemini_config(raw: dict) -> GeminiConfig:
    """Builds the drafter settings from a `gemini:` block, with sane defaults."""
    defaults = GeminiConfig()
    unknown = set(raw) - {"model", "temperature", "max_tokens", "max_drafts_per_run"}
    if unknown:
        raise SystemExit(f"config.yaml: unknown gemini keys: {', '.join(sorted(unknown))}")

    temperature = defaults.temperature
    if raw.get("temperature") is not None:
        try:
            temperature = float(raw["temperature"])
        except (TypeError, ValueError):
            raise SystemExit(f"config.yaml: gemini.temperature must be a number, got {raw['temperature']!r}")
        if not 0.0 <= temperature <= 2.0:
            raise SystemExit(f"config.yaml: gemini.temperature must be between 0 and 2, got {temperature}")

    def positive(key: str, fallback: int) -> int:
        if raw.get(key) is None:
            return fallback
        value = _as_int(raw[key], f"gemini.{key}")
        if value < 1:
            raise SystemExit(f"config.yaml: gemini.{key} must be at least 1, got {value}")
        return value

    return GeminiConfig(
        model=str(raw.get("model", defaults.model)),
        temperature=temperature,
        max_tokens=positive("max_tokens", defaults.max_tokens),
        max_drafts_per_run=positive("max_drafts_per_run", defaults.max_drafts_per_run),
    )
