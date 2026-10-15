"""Local manual review queue, legacy cleanup and persistent daily publishing counters."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "queue.db"

# Draft lifecycle. Only PENDING is produced in step 3; the rest are the states
# later steps will move drafts through.
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_POSTED = "posted"
STATUS_UNCERTAIN = "uncertain"

VALID_STATUSES = frozenset({STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_POSTED, STATUS_UNCERTAIN})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    post_id     TEXT PRIMARY KEY,   -- Reddit submission id; keeps drafts unique
    subreddit   TEXT NOT NULL,
    post_title  TEXT NOT NULL,
    post_url    TEXT NOT NULL,
    post_author TEXT NOT NULL,
    comment     TEXT NOT NULL,
    status      TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    posted_url  TEXT                -- permalink once posted (step 5); NULL before
);
"""


@dataclass
class Draft:
    post_id: str
    subreddit: str
    post_title: str
    post_url: str
    post_author: str
    comment: str
    status: str
    model: str
    created_at: str
    updated_at: str
    posted_url: str | None = None
    source_hash: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str = DB_PATH, *, retention_days: int = 7) -> sqlite3.Connection:
    """Opens the queue database and ensures the schema is current."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA secure_delete = ON")
    conn.execute(_SCHEMA)
    conn.execute("DROP TABLE IF EXISTS karma")
    conn.execute("CREATE TABLE IF NOT EXISTS daily_attempts (day TEXT PRIMARY KEY, attempts INTEGER NOT NULL)")
    _migrate(conn)
    conn.execute("DELETE FROM drafts WHERE model != 'human'")
    conn.execute("UPDATE drafts SET post_author = ''")
    conn.commit()
    prune(conn, retention_days)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Adds columns a queue.db from an earlier version is missing."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
    if "posted_url" not in columns:
        conn.execute("ALTER TABLE drafts ADD COLUMN posted_url TEXT")
    if "source_hash" not in columns:
        conn.execute("ALTER TABLE drafts ADD COLUMN source_hash TEXT")


def has_draft(conn: sqlite3.Connection, post_id: str) -> bool:
    """True if this post already has a draft, so we never draft it twice."""
    row = conn.execute("SELECT 1 FROM drafts WHERE post_id = ?", (post_id,)).fetchone()
    return row is not None


def add_draft(
    conn: sqlite3.Connection,
    *,
    post_id: str,
    subreddit: str,
    post_title: str,
    post_url: str,
    post_author: str,
    comment: str,
    model: str,
    status: str = STATUS_PENDING,
    source_hash: str | None = None,
) -> Draft:
    """Inserts one pending draft and returns it."""
    now = _now()
    conn.execute(
        """
        INSERT INTO drafts (
            post_id, subreddit, post_title, post_url, post_author,
            comment, status, model, created_at, updated_at, source_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (post_id, subreddit, post_title, post_url, post_author, comment, status, model, now, now, source_hash),
    )
    conn.commit()
    return Draft(
        post_id=post_id,
        subreddit=subreddit,
        post_title=post_title,
        post_url=post_url,
        post_author=post_author,
        comment=comment,
        status=status,
        model=model,
        created_at=now,
        updated_at=now,
        source_hash=source_hash,
    )


def get_draft(conn: sqlite3.Connection, post_id: str) -> Draft | None:
    """One draft by post id, or None if it isn't queued."""
    row = conn.execute("SELECT * FROM drafts WHERE post_id = ?", (post_id,)).fetchone()
    return Draft(**dict(row)) if row is not None else None


def set_status(conn: sqlite3.Connection, post_id: str, status: str) -> None:
    """Moves a draft to a new status (e.g. pending -> approved) and stamps it."""
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {sorted(VALID_STATUSES)}")
    conn.execute(
        "UPDATE drafts SET status = ?, updated_at = ? WHERE post_id = ? AND status NOT IN (?, ?)",
        (status, _now(), post_id, STATUS_POSTED, STATUS_UNCERTAIN),
    )
    conn.commit()


def update_comment(conn: sqlite3.Connection, post_id: str, comment: str) -> None:
    """Replaces a draft's comment text (used when the reviewer edits it)."""
    conn.execute(
        "UPDATE drafts SET comment = ?, status = ?, updated_at = ? WHERE post_id = ? AND status NOT IN (?, ?)",
        (comment, STATUS_PENDING, _now(), post_id, STATUS_POSTED, STATUS_UNCERTAIN),
    )
    conn.commit()


def mark_posted(conn: sqlite3.Connection, post_id: str, posted_url: str) -> None:
    """Marks a draft as posted and records the live comment's permalink."""
    conn.execute(
        "UPDATE drafts SET status = ?, posted_url = ?, updated_at = ? WHERE post_id = ?",
        (STATUS_POSTED, posted_url, _now(), post_id),
    )
    conn.commit()


def list_drafts(conn: sqlite3.Connection, status: str | None = None) -> list[Draft]:
    """Every draft (newest first), optionally filtered to one status."""
    if status is None:
        rows = conn.execute("SELECT * FROM drafts ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM drafts WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    return [Draft(**dict(row)) for row in rows]


def count_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    """How many drafts sit in each status - a quick queue overview."""
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM drafts GROUP BY status").fetchall()
    return {row["status"]: row["n"] for row in rows}


def forget(conn: sqlite3.Connection, post_id: str) -> None:
    """Delete a source post's stored metadata and draft."""
    with conn:
        conn.execute("DELETE FROM drafts WHERE post_id = ?", (post_id,))


def prune(conn: sqlite3.Connection, retention_days: int = 7) -> int:
    if isinstance(retention_days, bool) or not 1 <= retention_days <= 30:
        raise ValueError("retention_days must be between 1 and 30")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat(timespec="seconds")
    stale = conn.execute("SELECT post_id FROM drafts WHERE created_at < ?", (cutoff,)).fetchall()
    with conn:
        conn.executemany("DELETE FROM drafts WHERE post_id = ?", [(r["post_id"],) for r in stale])
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        conn.execute("DELETE FROM daily_attempts WHERE day < ?", (yesterday,))
    return len(stale)


def reserve_publish(conn: sqlite3.Connection, draft: Draft, max_attempts: int) -> None:
    """Reserve an attempt atomically; uncertain failures cannot be blindly retried."""
    from difflib import SequenceMatcher

    day = datetime.now(timezone.utc).date().isoformat()
    normalized = " ".join(draft.comment.casefold().split())
    conn.execute("BEGIN IMMEDIATE")
    try:
        current = get_draft(conn, draft.post_id)
        if current is None or current.status != STATUS_APPROVED or current.comment != draft.comment:
            raise RuntimeError("Draft is no longer approved with the reviewed text")
        for previous in list_drafts(conn):
            if previous.status not in {STATUS_POSTED, STATUS_UNCERTAIN}:
                continue
            text = " ".join(previous.comment.casefold().split())
            if normalized == text or (
                min(len(text), len(normalized)) >= 20 and SequenceMatcher(None, normalized, text).ratio() >= 0.9
            ):
                raise RuntimeError("Duplicate or substantially similar comment; publishing blocked")
        row = conn.execute("SELECT attempts FROM daily_attempts WHERE day = ?", (day,)).fetchone()
        if row is not None and row["attempts"] >= max_attempts:
            raise RuntimeError("Daily publishing attempt limit reached (UTC)")
        conn.execute(
            "INSERT INTO daily_attempts VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET attempts = attempts + 1", (day,)
        )
        conn.execute(
            "UPDATE drafts SET status = ?, updated_at = ? WHERE post_id = ?", (STATUS_UNCERTAIN, _now(), draft.post_id)
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
