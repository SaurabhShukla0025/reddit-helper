"""Command-line entry point for Reddit Helper.

Commands (run `python main.py <command> --help` for each one's options):
    fetch     log in and list recent posts (read-only)
    match     list the posts that pass your match rules (read-only)
    draft     draft comments for matched posts into the queue
    drafts    show what's waiting in the review queue
    review    approve / reject / edit pending drafts
    post      post approved comments to Reddit (asks first)
    karma     read and record your posted comments' scores
    cleanup   retention cleanup and data-deletion requests

Add --verbose (-v) to any command to echo the activity log to the console.
"""
from __future__ import annotations

import argparse
import logging
import os
import shlex
import subprocess
import tempfile

from src import applog, karma, lifecycle, policy, poster, review, store
from src.config import Config, load_config
from src.drafter import draft_comment, make_client
from src.fetch import fetch_all
from src.match import MatchResult, match_all
from src.reddit_client import make_client as make_reddit
from src.reddit_client import whoami

log = logging.getLogger(__name__)


def _sign_in(config: Config):
    policy.require_api(config)
    reddit = make_reddit(config.reddit)
    try:
        me = whoami(reddit)
    except Exception as error:  # noqa: BLE001 - show the user a clear reason
        log.error("Reddit sign-in failed: %s", error)
        raise SystemExit(f"Could not sign in to Reddit: {error}")
    log.info("signed in as u/%s", me)
    if me.casefold() != config.policy.dedicated_app_username.casefold():
        raise SystemExit("Authenticated account does not match the dedicated app account")
    return reddit, me


def _queue():
    """Local cleanup commands work without credentials or API approval."""
    import yaml

    from src.config import CONFIG_PATH, _policy_config
    settings = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    retention = _policy_config((settings or {}).get("policy") or {}).retention_days
    return store.connect(retention_days=retention)


def _refresh_queue(conn, config, reddit):
    before = store.list_drafts(conn)
    valid = lifecycle.refresh(conn, reddit, before, config)
    if len(valid) != len(before):
        print(f"Removed {len(before) - len(valid)} stale, changed, legacy, or out-of-scope record(s).")


def cmd_cleanup(sync: bool = False, post_id: str | None = None, all_: bool = False) -> None:
    conn = _queue()
    if post_id is not None:
        store.forget(conn, post_id)
        print("Removed the specified post's local draft, metadata, and score history.")
    elif all_:
        for draft in store.list_drafts(conn):
            store.forget(conn, draft.post_id)
        print("Removed all locally queued content and score history.")
    elif sync:
        config = load_config()
        reddit, _ = _sign_in(config)
        _refresh_queue(conn, config, reddit)
    else:
        print("Retention cleanup complete. Use --sync to check Reddit deletions, "
              "--post-id ID for a deletion request, or --all when stopping the app.")
    conn.close()


def cmd_fetch() -> None:
    config = load_config()
    reddit, me = _sign_in(config)
    print(f"Signed in as u/{me}. Reading {config.listing} posts (read-only).\n")

    for name, posts in fetch_all(reddit, config).items():
        print(f"r/{name} - {len(posts)} posts")
        for post in posts:
            print(f"  [{post.score:>4}  {post.num_comments:>3}c] {post.title}")
            print(f"        {post.url}")
        print()


def cmd_match(show_all: bool = False) -> None:
    config = load_config()
    reddit, me = _sign_in(config)
    print(f"Signed in as u/{me}. Matching {config.listing} posts (read-only).\n")

    results = match_all(fetch_all(reddit, config), config.subreddits)
    total_matched = 0
    for name, verdicts in results.items():
        matched = [v for v in verdicts if v.matched]
        total_matched += len(matched)
        print(f"r/{name} - {len(matched)} of {len(verdicts)} matched")
        for verdict in matched:
            _print_verdict(verdict, prefix="  + ")
        if show_all:
            for verdict in (v for v in verdicts if not v.matched):
                _print_verdict(verdict, prefix="  - ")
        print()

    print(f"{total_matched} post(s) matched across {len(results)} subreddit(s).")


def cmd_draft(limit: int | None = None) -> None:
    config = load_config()
    cap = config.gemini.max_drafts_per_run
    limit = cap if limit is None else min(limit, cap)
    # _sign_in enforces require_api; here add the draft-specific gates.
    policy.require_external_ai(config.policy)
    for sub in config.subreddits:
        policy.require_community(sub, comments=True)

    reddit, me = _sign_in(config)
    client = make_client()
    conn = _queue()
    _refresh_queue(conn, config, reddit)
    guidelines = {sub.name: sub.guidelines for sub in config.subreddits}

    print(
        f"Signed in as u/{me}. Drafting with {config.gemini.model} "
        f"(up to {limit} new draft(s) this run). Nothing is posted.\n"
    )

    results = match_all(fetch_all(reddit, config), config.subreddits)
    drafted = skipped_existing = skipped_by_model = errors = attempts = 0

    for name, verdicts in results.items():
        for verdict in (v for v in verdicts if v.matched):
            post = verdict.post
            if store.has_draft(conn, post.id):
                skipped_existing += 1
                continue
            if attempts >= limit:
                continue
            attempts += 1
            try:
                comment = draft_comment(client, post, guidelines.get(name, ""), config.gemini, policy=config.policy)
            except Exception:
                errors += 1
                print(f"  ! r/{name}: drafting failed; no comment queued.")
                continue
            if comment is None:
                skipped_by_model += 1
                continue
            store.add_draft(
                conn,
                post_id=post.id, subreddit=name, post_title=post.title,
                post_url=post.url, post_author=post.author,
                comment=comment, model=config.gemini.model,
                source_hash=lifecycle.fingerprint(post.title, post.selftext),
            )
            drafted += 1
            print(f"  + r/{name} queued: {post.title}")

    print(
        f"\n{drafted} new draft(s) queued. "
        f"Skipped {skipped_existing} already queued, "
        f"{skipped_by_model} the model declined, {errors} error(s)."
    )
    log.info(
        "draft run: %d queued, %d already queued, %d declined, %d error(s)",
        drafted, skipped_existing, skipped_by_model, errors,
    )
    print("Review them with: python main.py drafts")
    conn.close()


def cmd_drafts() -> None:
    conn = _queue()
    if store.list_drafts(conn):
        config = load_config()
        reddit, _ = _sign_in(config)
        _refresh_queue(conn, config, reddit)
    pending = store.list_drafts(conn, status=store.STATUS_PENDING)
    counts = store.count_by_status(conn)

    if not pending:
        print("No pending drafts. Run: python main.py draft")
    else:
        print(f"{len(pending)} draft(s) awaiting review:\n")
        for draft in pending:
            print(f"r/{draft.subreddit}  {draft.post_title}")
            print(f"  {draft.post_url}")
            for line in draft.comment.splitlines():
                print(f"  | {line}")
            print()

    if counts:
        summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
        print(f"Queue: {summary}.")
    if pending:
        print("Approve, reject or edit them with: python main.py review")


def cmd_review() -> None:
    conn = _queue()
    if store.list_drafts(conn):
        config = load_config()
        reddit, _ = _sign_in(config)
        _refresh_queue(conn, config, reddit)
    pending = store.list_drafts(conn, status=store.STATUS_PENDING)
    if not pending:
        print("No pending drafts to review. Run: python main.py draft")
        return

    print(f"Reviewing {len(pending)} pending draft(s). Nothing is posted here.")
    print("For each: [a]pprove  [r]eject  [e]dit  [s]kip  [q]uit\n")

    summary = review.run_review(conn, _prompt_action, _edit_in_editor)

    print(
        f"\nDone. {summary.approved} approved, {summary.rejected} rejected, "
        f"{summary.edited} edit(s), {summary.skipped} skipped, "
        f"{summary.remaining} still pending."
    )
    if summary.approved:
        print("Approved drafts are ready to post - that's step 5.")


def cmd_post(limit: int | None = None, dry_run: bool = False, yes: bool = False) -> None:
    if yes:
        raise SystemExit("--yes is no longer supported; live posting requires human confirmation")
    config = load_config()
    cap = config.post.max_posts_per_run
    limit = cap if limit is None else min(limit, cap)

    conn = _queue()
    approved = store.list_drafts(conn, status=store.STATUS_APPROVED)
    if not approved:
        print("No approved drafts to post. Approve some with: python main.py review")
        return
    batch = approved[:limit]
    if dry_run:
        print(f"Dry run: {len(batch)} approved record(s) selected; no network or posting. "
              "Content is hidden until source verification. Live permission checks still apply.")
        return
    for draft in batch:
        policy.require_post(config, draft.subreddit)
    reddit, me = _sign_in(config)
    _refresh_queue(conn, config, reddit)
    batch = store.list_drafts(conn, store.STATUS_APPROVED)[:limit]
    if not batch:
        print("No current approved drafts remain after source verification.")
        return
    for draft in batch:
        policy.require_post(config, draft.subreddit)
        if not draft.comment.rstrip().endswith(policy.AI_DISCLOSURE):
            store.set_status(conn, draft.post_id, store.STATUS_PENDING)
            raise SystemExit("Draft lacks AI disclosure; returned to review. "
                             "Add the required disclosure and approve again.")

    print(f"{len(approved)} approved draft(s); will post up to {len(batch)} this run:\n")
    for draft in batch:
        print(f"  r/{draft.subreddit}  {draft.post_title}")
        print(f"    {draft.post_url}")
        print(draft.comment)
    print()

    if not _confirm(
        f"Have you checked accuracy, current community rules, relevance, and disclosure "
        f"for these {len(batch)} comment(s)? Publish as u/{me}? [y/N]: "
    ):
        print("Aborted. Nothing was posted.")
        return

    print()
    by_id = {d.post_id: d for d in batch}
    def submit_checked(client, post_id, body):
        return lifecycle.submit_checked(conn, client, by_id[post_id], body, config, poster.submit_comment)
    run = poster.run_posts(conn, reddit, batch, delay=poster.delay_from(config.post), submit=submit_checked)

    print(f"\nPosted {len(run.posted)}, failed {len(run.failed)}.")
    log.info("post run: %d posted, %d failed, stopped_early=%s",
             len(run.posted), len(run.failed), run.stopped_early)
    if run.stopped_early:
        print("Stopped early due to Reddit rate limiting; remaining approved drafts are untouched.")
    if run.posted:
        print("Published comment scores can be inspected with: python main.py karma")


def cmd_karma() -> None:
    config = load_config()
    conn = _queue()
    posted = store.list_drafts(conn, status=store.STATUS_POSTED)
    if not posted:
        print("No posted comments yet. Post some with: python main.py post")
        return

    reddit, me = _sign_in(config)
    _refresh_queue(conn, config, reddit)
    posted = store.list_drafts(conn, status=store.STATUS_POSTED)
    print(f"Signed in as u/{me}. Reading scores for {len(posted)} posted comment(s)...\n")
    karma.check_karma(conn, reddit, posted, out=print)

    reports = karma.report(conn, posted)
    if reports:
        print("\nKarma so far:")
        for item in reports:
            trend = f"{item.delta:+d} since first" if item.samples > 1 else "first reading"
            print(f"  r/{item.subreddit}  score {item.latest_score:>5}  ({trend})  {item.post_title}")
        print(f"\nTotal karma across {len(reports)} comment(s): {karma.total_karma(reports)}")
    log.info("karma check complete for %d comment(s)", len(posted))


def _confirm(question: str) -> bool:
    """Yes only on an explicit y/yes; EOF (piped empty input) means no."""
    try:
        return input(question).strip().lower() in ("y", "yes")
    except EOFError:
        return False


_ACTIONS = {
    "a": review.APPROVE, "r": review.REJECT, "e": review.EDIT,
    "s": review.SKIP, "q": review.QUIT,
}


def _prompt_action(_draft) -> str:
    """Reads a single-letter action from stdin, re-asking until it's valid."""
    while True:
        choice = input("  action [a/r/e/s/q]: ").strip().lower()
        if choice in _ACTIONS:
            return _ACTIONS[choice]
        print("  Please enter one of: a, r, e, s, q")


def _edit_in_editor(current: str) -> str:
    """Opens the current comment in the user's editor and returns the result.

    Uses $EDITOR (or $VISUAL), falling back to notepad on Windows / vi elsewhere.
    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        editor = "notepad" if os.name == "nt" else "vi"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(current)
        path = handle.name
    try:
        subprocess.run([*shlex.split(editor, posix=(os.name != "nt")), path], check=True)
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, subprocess.SubprocessError) as error:
        print(f"  Could not open editor ({error}); keeping the current comment.")
        return current
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _print_verdict(verdict: MatchResult, prefix: str) -> None:
    post = verdict.post
    print(f"{prefix}[{post.score:>4} {post.num_comments:>3}c] {post.title}  ({verdict.reason})")
    print(f"        {post.url}")


def _positive_int(text: str) -> int:
    """An argparse type that accepts only whole numbers >= 1."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number")
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _build_parser() -> argparse.ArgumentParser:
    """The command-line interface: subcommands, flags, and auto-generated help."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true",
                        help="echo the activity log to the console")

    parser = argparse.ArgumentParser(
        prog="python main.py", parents=[common],
        description="Approve-first Reddit contribution assistant (read -> match -> "
                    "draft -> review -> post -> karma).",
    )
    sub = parser.add_subparsers(dest="command", metavar="command", required=True)

    sub.add_parser("fetch", parents=[common], help="list recent posts (read-only)")

    p_match = sub.add_parser("match", parents=[common], help="list posts that pass your rules (read-only)")
    p_match.add_argument("--all", action="store_true", help="also show skipped posts and why")

    p_draft = sub.add_parser("draft", parents=[common], help="draft comments into the review queue")
    p_draft.add_argument("--limit", type=_positive_int, metavar="N", help="cap new drafts this run")

    sub.add_parser("drafts", parents=[common], help="show the review queue")
    sub.add_parser("review", parents=[common], help="approve / reject / edit pending drafts")

    p_post = sub.add_parser("post", parents=[common], help="post approved comments to Reddit (asks first)")
    p_post.add_argument("--limit", type=_positive_int, metavar="N", help="post at most N this run")
    p_post.add_argument("--dry-run", action="store_true", help="preview only; posts nothing, no login")
    p_post.add_argument("--yes", "-y", action="store_true", help=argparse.SUPPRESS)

    sub.add_parser("karma", parents=[common], help="read and record posted comments' scores")

    p_clean = sub.add_parser("cleanup", parents=[common], help="retention cleanup and deletion requests")
    group = p_clean.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true", help="check Reddit for deleted/changed sources")
    group.add_argument("--post-id", metavar="ID", help="delete one post's local data")
    group.add_argument("--all", action="store_true", help="delete all local data (e.g. when stopping)")

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    applog.setup_logging(verbose=args.verbose)
    log.info("command: %s", args.command)

    if args.command == "fetch":
        cmd_fetch()
    elif args.command == "match":
        cmd_match(show_all=args.all)
    elif args.command == "draft":
        cmd_draft(limit=args.limit)
    elif args.command == "drafts":
        cmd_drafts()
    elif args.command == "review":
        cmd_review()
    elif args.command == "post":
        cmd_post(limit=args.limit, dry_run=args.dry_run, yes=args.yes)
    elif args.command == "karma":
        cmd_karma()
    elif args.command == "cleanup":
        cmd_cleanup(sync=args.sync, post_id=args.post_id, all_=args.all)


if __name__ == "__main__":
    main()
