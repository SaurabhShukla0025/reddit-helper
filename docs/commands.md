# Commands

Everything is run as `python main.py <command>`. Here is each one, what it does,
and what you'll see.

> Add `--verbose` (or `-v`) to any command to also print the log lines to the
> screen. Everything is logged to `reddit-helper.log` regardless.

---

## `fetch` — see recent posts (read-only)

```
python main.py fetch
```
Logs into Reddit and lists recent posts from each subreddit in your config.
Nothing is posted. Good for checking your login works.

**Example output:**
```
Signed in as u/yourname. Reading new posts (read-only).

r/learnpython - 10 posts
  [  12   3c] How do I fix this TypeError?
        https://reddit.com/r/learnpython/comments/...
  ...
```
(`12` is the score, `3c` is the comment count.)

---

## `match` — see which posts are worth replying to (read-only)

```
python main.py match          # only the posts that pass your rules
python main.py match --all    # also show the SKIPPED posts and why
```
Applies your [match rules](configuration.md#match-rules) to the fetched posts and
shows which ones qualify for a draft. Still nothing is posted.

**Example output:**
```
r/learnpython - 2 of 10 matched
  + [  12   3c] How do I fix this TypeError?  (keyword 'typeerror')
        https://reddit.com/...
```
With `--all`, skipped posts appear with a `-` and the reason (e.g. `no keyword
match`, `score 1 < min 2`, `age 70.0h > max 48h`).

---

## `draft` — write draft comments with AI 🤖 (uses the Gemini API)

```
python main.py draft            # draft for matched posts, up to the per-run cap
python main.py draft --limit 3  # draft at most 3 this run
```
For each matched post that isn't already in the queue, Gemini writes a comment
that follows that subreddit's guidelines, and saves it as **pending** in the
review queue. **This is the only command that calls an external AI** — Gemini has
a free tier, so it's usually free (heavy use may use paid quota). The AI may
**decline** a post it can't usefully answer.

**Example output:**
```
Signed in as u/yourname. Drafting with gemini-3.8-flash (up to 3 new draft(s) this run). Nothing is posted.

  + r/learnpython queued: How do I fix this TypeError?

1 new draft(s) queued. Skipped 0 already queued, 1 the model declined, 0 error(s).
Review them with: python main.py drafts
```

**Usage control:** limited by `gemini.max_drafts_per_run` in your config and the
`--limit` flag. It never re-drafts a post that's already in the queue.

---

## `drafts` — see what's waiting in the queue (read-only)

```
python main.py drafts
```
Lists every **pending** draft with its full comment text, and a summary of the
queue (how many pending / approved / etc.).

---

## `review` — approve, edit, or reject each draft

```
python main.py review
```
Walks through each pending draft one at a time and asks what to do:

| Key | Action |
|-----|--------|
| `a` | **approve** — mark it ready to post |
| `r` | **reject** — discard it |
| `e` | **edit** — open the comment in your text editor to change it, then decide |
| `s` | **skip** — leave it pending, decide later |
| `q` | **quit** — stop reviewing |

Editing opens your editor (`$EDITOR`/`$VISUAL`, or Notepad on Windows). Approved
drafts move to the **approved** status and wait for posting. Nothing is posted
here.

---

## `post` — post approved comments to Reddit ✍️ (asks first)

```
python main.py post --dry-run   # preview what WOULD be posted; posts nothing, no login
python main.py post             # confirm, then post the approved comments
python main.py post --limit 1   # post at most one this run
python main.py post --yes       # skip the confirmation prompt (careful!)
```
This is the **only** command that writes to Reddit. It:
- shows exactly which approved comments it will post,
- **asks you to confirm** (unless `--dry-run` or `--yes`),
- posts them one by one, **pausing a random human-like interval** between each
  (set by the `post:` config),
- **backs off** if Reddit rate-limits you (and stops if it keeps happening),
- marks each posted draft and records the live comment's link.

> **Tip:** `--limit 1` posts a single comment with **no pacing delay**, which is
> the easiest way to try posting for real.

---

## `karma` — track your posted comments' scores (read-only)

```
python main.py karma            # read & record current scores
python main.py karma --verbose  # also echo the log to the screen
```
Reads each posted comment's current score from Reddit (free), saves a snapshot,
and shows the latest score and the change since the first reading. Run it now and
then to build a history.

**Example output:**
```
  r/learnpython score    7: How do I fix this TypeError?

Karma so far:
  r/learnpython  score     7  (+5 since first)  How do I fix this TypeError?

Total karma across 1 comment(s): 7
```

---

## Quick reference

| Command | Touches Reddit? | Costs money? |
|---------|-----------------|--------------|
| `fetch` | read | no |
| `match` | — | no |
| `draft` | — | free tier (Gemini API) |
| `drafts` | — | no |
| `review` | — | no |
| `post` | **writes (after you confirm)** | no |
| `karma` | read | no |
