"""Human-selected, human-written, individually confirmed contributions."""

from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import subprocess
import tempfile
import time
from contextlib import closing
from pathlib import Path

import yaml

from src import applog, credentials, lifecycle, policy, poster, readiness, review, store
from src.config import CONFIG_PATH, Config, _policy_config, load_config
from src.reddit_client import make_client as make_reddit
from src.reddit_client import whoami


def _sign_in(config: Config):
    policy.require_api(config)
    reddit = make_reddit(config.reddit)
    try:
        me = whoami(reddit)
    except Exception:
        raise SystemExit("Reddit sign-in failed; check credentials and authorization") from None
    if me.casefold() != config.policy.dedicated_app_username.casefold():
        raise SystemExit("Authenticated account does not match the dedicated app account")
    return reddit, me


def _queue():
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    retention = _policy_config(
        {"retention_days": ((data or {}).get("policy") or {}).get("retention_days", 7)}
    ).retention_days
    return store.connect(retention_days=retention)


def _post_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9]{1,12}", value):
        raise argparse.ArgumentTypeError("Use the submission ID, e.g. abc123, without t3_ or a URL")
    return value


def _confirm(question: str) -> bool:
    try:
        return input(question).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _edit_in_editor(current: str) -> str:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(current)
        path = handle.name
    try:
        subprocess.run([*shlex.split(editor, posix=os.name != "nt"), path], check=True)
        return Path(path).read_text(encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        raise SystemExit("Could not open editor; use --text-file instead") from None
    finally:
        Path(path).unlink(missing_ok=True)


def cmd_draft(post_id: str, text_file: str | None = None) -> None:
    config = load_config()
    reddit, _ = _sign_in(config)
    with closing(_queue()) as conn:
        if store.has_draft(conn, post_id):
            raise SystemExit("This post is already queued. Review or delete its local draft first.")
        try:
            source = reddit.submission(id=post_id)
            community = source.subreddit.display_name
            policy.require_post(config, community)
            if not lifecycle.available(source) or source.locked or source.archived:
                raise SystemExit("Post is unavailable or cannot receive replies")
            title, body = source.title, source.selftext or ""
        except SystemExit:
            raise
        except Exception:
            raise SystemExit("Could not verify the selected post; no draft created") from None
        print(f"r/{community}: {title}\n{body}\n\nCommunity guidelines: {config.subreddits[0].guidelines}")
        comment = Path(text_file).read_text(encoding="utf-8") if text_file else _edit_in_editor("")
        comment = comment.strip()
        if not comment or len(comment) > 10000:
            raise SystemExit("Write a non-empty reply of at most 10,000 characters")
        store.add_draft(
            conn,
            post_id=post_id,
            subreddit=community,
            post_title=title,
            post_url=f"https://www.reddit.com/r/{community}/comments/{post_id}/",
            post_author="",
            comment=comment,
            model="human",
            source_hash=lifecycle.fingerprint(title, body),
        )
        print(f"Human-written draft saved. Review with: python main.py review {post_id}")


def _verified_draft(conn, reddit, config, post_id):
    store.prune(conn, config.policy.retention_days)
    draft = store.get_draft(conn, post_id)
    if draft is None:
        raise SystemExit("No local draft for this post")
    if draft.model != "human":
        raise SystemExit("Legacy AI draft is blocked. Delete it and create a new human-written reply.")
    if lifecycle.verified_source(conn, reddit, draft, config) is None:
        raise SystemExit("Source changed or became unavailable; local draft removed")
    return draft


def cmd_review(post_id: str) -> None:
    config = load_config()
    reddit, _ = _sign_in(config)
    with closing(_queue()) as conn:
        draft = _verified_draft(conn, reddit, config, post_id)
        if draft.status in {store.STATUS_POSTED, store.STATUS_UNCERTAIN}:
            raise SystemExit("This draft is posted or has an uncertain submission. Check Reddit; do not retry blindly")
        print(review.render_draft(draft, 1, 1))
        print(f"Community guidelines: {config.subreddits[0].guidelines}")
        try:
            action = input("[a]pprove, [r]eject, [e]dit, or Enter to leave pending: ").strip().lower()
        except EOFError:
            action = ""
        if action == "e":
            comment = _edit_in_editor(draft.comment).strip()
            if not comment or len(comment) > 10000:
                raise SystemExit("Reply must contain 1-10,000 characters")
            store.update_comment(conn, post_id, comment)
            print("Edited draft saved as pending. Review again before publishing.")
        elif action in {"a", "r"}:
            if action == "a":
                policy.require_post(config, draft.subreddit)
            store.set_status(conn, post_id, store.STATUS_APPROVED if action == "a" else store.STATUS_REJECTED)
            print("Approved." if action == "a" else "Rejected.")


def cmd_post(post_id: str, dry_run: bool = False) -> None:
    if dry_run:
        with closing(_queue()) as conn:
            draft = store.get_draft(conn, post_id)
            print(
                "Dry run: approved record exists."
                if draft and draft.status == store.STATUS_APPROVED
                else "Dry run: no approved record."
            )
        return
    config = load_config()
    reddit, me = _sign_in(config)
    with closing(_queue()) as conn:
        draft = _verified_draft(conn, reddit, config, post_id)
        policy.require_post(config, draft.subreddit)
        if draft.status != store.STATUS_APPROVED:
            raise SystemExit("Review and approve this draft first")
        print(review.render_draft(draft, 1, 1))
        print(f"Community guidelines: {config.subreddits[0].guidelines}")
        if not _confirm(f"Confirm accuracy, relevance and current rules. Publish this ONE reply as u/{me}? [y/N]: "):
            print("Cancelled. Nothing was posted.")
            return
        try:
            url = lifecycle.submit_checked(conn, reddit, draft, draft.comment, config, poster.submit_comment)
        except Exception as error:
            raise SystemExit(str(error)) from None
        print(f"Published: {url}")


def cmd_cleanup(sync=False, post_id=None, all_=False) -> None:
    with closing(_queue()) as conn:
        if all_:
            for draft in store.list_drafts(conn):
                store.forget(conn, draft.post_id)
        elif post_id:
            store.forget(conn, post_id)
        elif sync:
            config = load_config()
            reddit, _ = _sign_in(config)
            lifecycle.refresh(conn, reddit, store.list_drafts(conn), config)
    applog.cleanup_logs()
    print("Local retention/deletion cleanup complete. Published comments are unchanged.")


def cmd_maintenance(interval: int = 3600) -> None:
    print("Local retention cleanup is running. Leave this process running; Ctrl+C stops it.")
    try:
        while True:
            cmd_cleanup()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Maintenance stopped.")


def _build_parser():
    parser = argparse.ArgumentParser(description="Select a post, write a reply, review, then publish one comment.")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="record public details without enabling live access")
    setup.add_argument("--username", required=True)
    setup.add_argument("--community", required=True)
    sub.add_parser("readiness", help="offline report of missing approval and operating evidence")
    sub.add_parser("privacy-review", help="review and attest to the exact completed privacy notice")
    secrets = sub.add_parser("credentials", help="manage current-user Windows encrypted credentials")
    secrets.add_argument("action", choices=("set", "clear"))
    draft = sub.add_parser("draft", help="write a human reply for a manually selected post")
    draft.add_argument("post_id", type=_post_id)
    draft.add_argument("--text-file", help="UTF-8 file containing your human-written reply")
    for command in ("review", "post"):
        child = sub.add_parser(command)
        child.add_argument("post_id", type=_post_id)
        if command == "post":
            child.add_argument("--dry-run", action="store_true", help="offline record check; hides source content")
    clean = sub.add_parser("cleanup", help="local retention and deletion requests")
    group = clean.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true")
    group.add_argument("--post-id", type=_post_id)
    group.add_argument("--all", action="store_true")
    sub.add_parser("maintenance", help="run hourly local retention cleanup until stopped")
    return parser


def main():
    args = _build_parser().parse_args()
    # Cleanup/maintenance never open persistent logging files.
    if args.command not in {"cleanup", "maintenance"}:
        applog.setup_logging(verbose=args.verbose)
    logging.getLogger(__name__).info("command: %s", args.command)
    if args.command == "setup":
        readiness.initialize(args.username, args.community)
    elif args.command == "readiness":
        if not readiness.report():
            raise SystemExit(1)
    elif args.command == "privacy-review":
        readiness.review_privacy()
    elif args.command == "credentials":
        if args.action == "set":
            credentials.save_interactive()
        else:
            credentials.SECRET_PATH.unlink(missing_ok=True)
            print("Encrypted local credentials cleared; environment values are unchanged.")
    elif args.command == "draft":
        cmd_draft(args.post_id, args.text_file)
    elif args.command == "review":
        cmd_review(args.post_id)
    elif args.command == "post":
        cmd_post(args.post_id, args.dry_run)
    elif args.command == "cleanup":
        cmd_cleanup(args.sync, args.post_id, args.all)
    elif args.command == "maintenance":
        cmd_maintenance()


if __name__ == "__main__":
    main()
