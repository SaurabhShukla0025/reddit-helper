# Architecture

This page is for developers (or the curious). It explains how the code is
organized, how data flows, and the one design idea that matters most.

---

## The pipeline

Each command drives one stage. State is saved in a local database between
stages, so stages run independently and at different times.

```
config.yaml ─┐                                   GEMINI_API_KEY (env)
             │                                              │
             ▼                                              ▼
  fetch ──► match ──►  draft  ──► review ──►  post  ──►  karma
  (Reddit)  (pure)    (Gemini)   (you)       (Reddit)   (Reddit)
     │         │         │          │           │          │
     └─────────┴─────────┴──────────┴───────────┴──────────┘
                          │
                   queue.db (SQLite)        reddit-helper.log (audit log)
```

---

## Files and what each does

| File | Lines | Responsibility |
|------|-------|----------------|
| `main.py` | ~350 | The command-line entry point. Parses the command, prints output, and wires the real Reddit/Gemini/editor/sleep into the logic. |
| `src/config.py` | ~235 | Loads and validates `config.yaml` (credentials, match rules, Gemini + posting settings). Gives clear errors. |
| `src/reddit_client.py` | ~24 | Builds the authenticated Reddit (PRAW) client. |
| `src/fetch.py` | ~58 | Reads recent posts from a subreddit (read-only). |
| `src/match.py` | ~91 | Decides which posts pass your rules. **Pure logic** — no network. |
| `src/drafter.py` | ~103 | Builds the prompt and calls the Gemini API to write one comment. |
| `src/store.py` | ~210 | The SQLite "review queue": drafts, their status, posted links, and karma history. |
| `src/review.py` | ~104 | The approve/reject/edit loop. **I/O is injected**, so it's testable. |
| `src/poster.py` | ~150 | Posts approved comments, with human pacing and rate-limit backoff. |
| `src/karma.py` | ~92 | Reads and records posted comments' scores over time. |
| `src/applog.py` | ~38 | Sets up the rotating audit log (`reddit-helper.log`). |
| `tests/` | ~630 | Tests for every stage. **All run offline** (no network, no API cost). |

---

## The database (`queue.db`, SQLite)

Created automatically on first use. Git-ignored. Two tables:

**`drafts`** — one row per candidate post:

| Column | Meaning |
|--------|---------|
| `post_id` | Reddit post id (primary key — prevents drafting the same post twice) |
| `subreddit`, `post_title`, `post_url`, `post_author` | about the post |
| `comment` | the draft comment text |
| `status` | `pending` → `approved` / `rejected` → `posted` |
| `model` | which Gemini model wrote it |
| `created_at`, `updated_at` | timestamps |
| `posted_url` | link to the live comment, once posted |

**`karma`** — one row per score reading (a time series):

| Column | Meaning |
|--------|---------|
| `post_id` | which posted comment |
| `score` | its score at that moment |
| `checked_at` | when it was read |

### The draft's life (status lifecycle)

```
   draft        review            post
  ───────      ────────          ──────
  pending ───► approved ──────► posted
          └──► rejected  (end)
```

---

## The key design idea: injected side effects

The "side effects" — talking to Reddit, calling Gemini, and `sleep()`-ing
between posts — are **passed into** the core functions rather than called
directly inside them.

- In the **real app** (`main.py`), the real Reddit client, Gemini client, editor,
  and `time.sleep` are passed in.
- In the **tests**, fake versions are passed in instead.

Why this matters: it means the **entire pipeline is tested without any network,
without spending a cent on the Gemini API, and without actually waiting** for the
pacing delays. That's how the project has 45 fast, reliable tests.

For example, `poster.run_posts(...)` takes `submit`, `sleep`, and `delay` as
arguments; the tests pass a fake `submit` that returns a canned link and a
`sleep` that records calls instead of pausing.

---

## Safety and secrets (by design)

- **Approve-first:** only `post` writes to Reddit, and it asks for confirmation.
- **Read-only until posting:** `fetch`, `match`, `draft`, `review`, `karma` never
  change anything on Reddit.
- **Cost caps:** `max_drafts_per_run` and `max_posts_per_run`, plus `--limit`.
- **Pacing + backoff:** random human-like delays; stop if Reddit keeps
  rate-limiting.
- **Secrets stay out of git:** the Gemini key is an environment variable;
  `config.yaml`, `queue.db`, and `*.log` are all git-ignored.

---

## Tech stack

| Tool | Why |
|------|-----|
| **Python 3.10+** | Simple, great Reddit and AI libraries |
| **PRAW** | Official Reddit API wrapper (handles auth + endpoints) |
| **google-genai** | Official Gemini SDK — writes the drafts |
| **PyYAML** | Human-friendly config file format |
| **SQLite** (stdlib) | Durable state between commands, zero setup |
| **logging** (stdlib) | The audit log, no extra dependency |
| **pytest** | Runs the test suite |

See **[REPORT.md](../REPORT.md)** for the full project report and a reviewer's
checklist.
