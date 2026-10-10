# Reddit Helper (approve-first)

[![CI](https://github.com/SaurabhShukla0025/reddit-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/SaurabhShukla0025/reddit-helper/actions/workflows/ci.yml)

A small Python tool that finds relevant Reddit posts in the communities you list
and **drafts** comments following per-community guidelines. You review and approve
before anything is posted. It uses Reddit's official API (PRAW), stays within the
free rate limit, and paces posting like a human.

This is a draft-and-approve assistant, not an unattended bot. It never posts
without your approval, and it is meant for genuinely useful comments that follow
each subreddit's rules.

## What it does (and the build order)

1. **Authenticate + fetch** (done): log in with your Reddit app credentials and
   list new/rising posts from your chosen subreddits. Read-only.
2. **Match worthwhile posts by your rules** (done): filter the fetched posts by
   keywords, score, comment count and age. Still read-only.
3. **Draft comments into a review queue** (done): for each matched post, the
   Claude API drafts a comment following that subreddit's guidelines and stores
   it as `pending` in a local SQLite queue. The model can decline low-value
   posts. Nothing is posted — drafts only.
4. **You approve/edit** (done): walk the pending drafts one by one and approve,
   reject, or edit each in your editor. Approved drafts wait in the queue for
   posting. Still read-only toward Reddit.
5. **Post approved comments, paced and rate-limit aware** (done): post the
   approved drafts to Reddit, pausing a human-like interval between each and
   backing off when Reddit rate-limits. Posting asks for confirmation first and
   supports a dry run. This is the only step that writes to Reddit.
6. **Track karma and log everything** (done): read the score of each comment
   you've posted and record it over time, so you can see how your comments do.
   Every run also writes to an audit log. Reading scores uses Reddit's free API.

All six steps are implemented. The only step that posts to Reddit is step 5, and
only when you confirm.

## Setup

1. **Install Python 3.10+.** Check with `python --version`. If missing, install from
   python.org and re-open your terminal.

2. **Create a virtual environment and install dependencies:**
   ```
   cd C:\Users\imapro\reddit-helper
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Create your Reddit app** (one time, free):
   - Log in to Reddit, open https://www.reddit.com/prefs/apps
   - "create another app" -> type **script** -> redirect uri `http://localhost:8080`
   - Copy the **client id** (under the app name) and the **secret**.

4. **Add your credentials:** copy `config.example.yaml` to `config.yaml` and fill in
   the `reddit:` section and your `subreddits:`. `config.yaml` is git-ignored, so
   your secret never gets committed.

5. **Run the read-only commands:**
   ```
   python main.py fetch        # list recent posts from your subreddits
   python main.py match         # list only posts that pass your match rules
   python main.py match --all   # also show skipped posts and the reason
   ```
   Both are read-only. Nothing is posted.

6. **Draft comments (step 3) — needs a Claude API key:**
   ```
   # PowerShell: set your key for this terminal session
   $env:ANTHROPIC_API_KEY = "sk-ant-..."

   python main.py draft           # draft comments for matched posts into the queue
   python main.py draft --limit 3  # cap how many drafts this run creates
   python main.py drafts          # show what's waiting in the review queue
   ```
   `draft` calls the Claude API (which costs money per draft — hence the
   `max_drafts_per_run` cap in `config.yaml` and the `--limit` flag). It only
   drafts posts that aren't already queued, and the model may decline posts it
   can't usefully answer. Still nothing is posted; drafts wait in the queue for
   your approval (step 4). Get a key at https://console.anthropic.com/.

7. **Approve or edit drafts (step 4):**
   ```
   python main.py review
   ```
   Walks each pending draft and asks what to do: `[a]pprove`, `[r]eject`,
   `[e]dit`, `[s]kip` (decide later), or `[q]uit`. Editing opens the comment in
   your editor (`$EDITOR`/`$VISUAL`, or Notepad on Windows). Approved drafts move
   to the `approved` status and wait for posting (step 5). Nothing is posted yet.

8. **Post approved comments (step 5) — writes to Reddit:**
   ```
   python main.py post --dry-run   # show what would be posted; posts nothing
   python main.py post             # ask for confirmation, then post
   python main.py post --limit 1    # post at most one this run
   python main.py post --yes        # skip the confirmation prompt (careful)
   ```
   This is the only command that writes to Reddit. It posts the `approved`
   drafts, pausing a random human-like interval between each (see the `post:`
   settings in `config.yaml`) and backing off if Reddit rate-limits. It asks you
   to confirm first (unless `--dry-run` or `--yes`), marks each posted draft and
   records the live comment's permalink. A single post (`--limit 1`) has no
   pacing delay, which is the easiest way to try it.

9. **Track karma (step 6):**
   ```
   python main.py karma            # read & record scores for your posted comments
   python main.py karma --verbose   # also echo the log to the console
   ```
   Reads each posted comment's current score via the free Reddit API, records a
   snapshot, and prints the latest score plus the change since the first
   reading. Run it now and then (or on a schedule) to build a history. Every
   command also appends to the audit log at `reddit-helper.log` (git-ignored);
   add `--verbose` to any command to echo those log lines to the console.

## Match rules

Each subreddit decides which posts are worth a draft. Set a global `match:`
block in `config.yaml` and override any field per subreddit (see
`config.example.yaml`). A post matches only when every gate passes:

- `keywords` — title/body must contain at least one (empty = any post)
- `exclude` — skip if the title/body contains any of these
- `min_score` / `max_score` — score bounds
- `min_comments` / `max_comments` — comment-count bounds (cap it to get in early)
- `max_age_hours` — skip posts older than this

Keyword and exclude matching is case-insensitive and checks both the title and
the post body.

## Running the tests

```
pip install -r requirements-dev.txt
python -m pytest
```

## Files

- `config.yaml` — your credentials, subreddits, guidelines, match rules and Claude/posting settings (you create it)
- `queue.db` — the SQLite queue of drafts, their status and karma history (created on first `draft`; git-ignored)
- `reddit-helper.log` — the rotating audit log of what the tool did (git-ignored)
- `main.py` — the command-line entry point (`fetch`, `match`, `draft`, `drafts`, `review`, `post`, `karma`)
- `src/config.py` — loads and validates the config, incl. match rules, Claude and posting settings
- `src/reddit_client.py` — logs in to the Reddit API
- `src/fetch.py` — reads recent posts (read-only)
- `src/match.py` — filters posts against each subreddit's rules (pure logic)
- `src/drafter.py` — drafts a comment for one post via the Claude API
- `src/store.py` — the SQLite store (drafts, status, posted permalink, karma history)
- `src/review.py` — the approve/reject/edit loop over pending drafts (pure of I/O)
- `src/poster.py` — posts approved comments, paced and rate-limit aware (I/O injected)
- `src/karma.py` — reads and records posted comments' scores over time (I/O injected)
- `src/applog.py` — sets up the rotating audit log
- `tests/` — tests for every stage: matching, drafting, queue, review, posting, karma (no network)
