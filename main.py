"""Command-line entry point for Reddit Helper.

Usage:
    python main.py fetch          # log in and list recent posts (read-only)
    python main.py match          # list only the posts that pass your match rules
    python main.py match --all    # also show skipped posts and why
    python main.py draft          # draft comments for matched posts into the queue
    python main.py draft --limit N  # cap how many drafts this run creates
    python main.py drafts         # show what's waiting in the review queue
    python main.py review         # approve / reject / edit pending drafts
    python main.py post           # post approved comments to Reddit (asks first)
    python main.py karma          # read and record your posted comments' scores
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
import tempfile

from src import applog, karma, poster, review, store
from src.config import Config, load_config
from src.drafter import DraftError, draft_comment, make_client
from src.fetch import fetch_all
from src.match import MatchResult, match_all
from src.reddit_client import make_client as make_reddit, whoami

log = logging.getLogger(__name__)


def _sign_in(config: Config):
    reddit = make_reddit(config.reddit)
    try:
        me = whoami(reddit)
    except Exception as error:  # noqa: BLE001 - show the user a clear reason
        log.error("Reddit sign-in failed: %s", error)
        raise SystemExit(f"Could not sign in to Reddit: {error}")
    log.info("signed in as u/%s", me)
    return reddit, me


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


def cmd_match(args: list[str]) -> None:
    show_all = "--all" in args
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


def cmd_draft(args: list[str]) -> None:
    config = load_config()
    limit = _int_flag(args, "--limit", default=config.claude.max_drafts_per_run)

    reddit, me = _sign_in(config)
    client = make_client()
    conn = store.connect()
    guidelines = {sub.name: sub.guidelines for sub in config.subreddits}

    print(
        f"Signed in as u/{me}. Drafting with {config.claude.model} "
        f"(up to {limit} new draft(s) this run). Nothing is posted.\n"
    )

    results = match_all(fetch_all(reddit, config), config.subreddits)
    drafted = skipped_existing = skipped_by_model = errors = 0

    for name, verdicts in results.items():
        for verdict in (v for v in verdicts if v.matched):
            post = verdict.post
            if store.has_draft(conn, post.id):
                skipped_existing += 1
                continue
            if drafted >= limit:
                continue
            try:
                comment = draft_comment(client, post, guidelines.get(name, ""), config.claude)
            except DraftError as error:
                errors += 1
                print(f"  ! r/{name} {post.title!r}: {error}")
                continue
            if comment is None:
                skipped_by_model += 1
                continue
            store.add_draft(
                conn,
                post_id=post.id, subreddit=name, post_title=post.title,
                post_url=post.url, post_author=post.author,
                comment=comment, model=config.claude.model,
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


def cmd_drafts() -> None:
    conn = store.connect()
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
    conn = store.connect()
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


def cmd_post(args: list[str]) -> None:
    config = load_config()
    limit = _int_flag(args, "--limit", default=config.post.max_posts_per_run)
    dry_run = "--dry-run" in args
    assume_yes = "--yes" in args or "-y" in args

    conn = store.connect()
    approved = store.list_drafts(conn, status=store.STATUS_APPROVED)
    if not approved:
        print("No approved drafts to post. Approve some with: python main.py review")
        return
    batch = approved[:limit]

    print(f"{len(approved)} approved draft(s); will post up to {len(batch)} this run:\n")
    for draft in batch:
        print(f"  r/{draft.subreddit}  {draft.post_title}")
        print(f"    {draft.post_url}")
    print()

    if dry_run:  # no sign-in, no network - just show what would be posted
        print("Dry run - nothing was posted.")
        return

    reddit, me = _sign_in(config)
    if not assume_yes and not _confirm(
        f"Post {len(batch)} comment(s) to Reddit as u/{me}? This cannot be undone. [y/N]: "
    ):
        print("Aborted. Nothing was posted.")
        return

    print()
    run = poster.run_posts(conn, reddit, batch, delay=poster.delay_from(config.post))

    print(f"\nPosted {len(run.posted)}, failed {len(run.failed)}.")
    log.info("post run: %d posted, %d failed, stopped_early=%s",
             len(run.posted), len(run.failed), run.stopped_early)
    if run.stopped_early:
        print("Stopped early due to Reddit rate limiting; remaining approved drafts are untouched.")
    if run.posted:
        print("Karma tracking and logging come in step 6.")


def cmd_karma() -> None:
    config = load_config()
    conn = store.connect()
    posted = store.list_drafts(conn, status=store.STATUS_POSTED)
    if not posted:
        print("No posted comments yet. Post some with: python main.py post")
        return

    reddit, me = _sign_in(config)
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


def _int_flag(args: list[str], name: str, default: int) -> int:
    """Reads `--flag N` from args, falling back to `default`."""
    if name not in args:
        return default
    index = args.index(name)
    if index + 1 >= len(args):
        raise SystemExit(f"{name} needs a number, e.g. {name} 5")
    try:
        value = int(args[index + 1])
    except ValueError:
        raise SystemExit(f"{name} needs a number, e.g. {name} 5")
    if value < 1:
        raise SystemExit(f"{name} must be at least 1")
    return value


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else None
    applog.setup_logging(verbose="--verbose" in args or "-v" in args)
    if command:
        log.info("command: %s", " ".join(args))

    if command == "fetch":
        cmd_fetch()
    elif command == "match":
        cmd_match(args[1:])
    elif command == "draft":
        cmd_draft(args[1:])
    elif command == "drafts":
        cmd_drafts()
    elif command == "review":
        cmd_review()
    elif command == "post":
        cmd_post(args[1:])
    elif command == "karma":
        cmd_karma()
    else:
        print(
            "Usage: python main.py fetch | match [--all] | draft [--limit N] | "
            "drafts | review | post [--limit N] [--dry-run] [--yes] | karma\n"
            "  (add --verbose to echo the log to the console)"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
