# Reddit Helper — Project Report

**For:** Senior developer review
**Author:** thedevimapro@gmail.com
**Date:** 2026-10-10
**Version:** 0.1 (all 6 planned build steps complete)
**Status:** Feature-complete for the planned scope; not yet run against live Reddit/Gemini in production.

---

## 1. Executive summary

Reddit Helper is a **draft-and-approve** assistant (CLI, Python) that finds relevant
posts in chosen subreddits, uses the Gemini API to draft helpful comments that follow
each community's guidelines, lets a human approve/edit them, then posts the approved
ones to Reddit — paced like a human and rate-limit aware — and tracks the resulting
karma over time.

It is deliberately **not** an unattended bot: nothing is posted without explicit
human approval, and posting is the only action that writes to Reddit.

- ~1,450 lines of source across 11 modules; ~630 lines of tests.
- **45 tests, all passing, all offline** (no network, no API spend, no real waiting).
- 3 runtime dependencies: `praw`, `google-genai`, `PyYAML`.

---

## 2. Objectives & scope

**In scope (delivered):** a 6-stage pipeline, each stage a separate CLI command:

| # | Stage | Command | Writes to Reddit? | Cost |
|---|-------|---------|-------------------|------|
| 1 | Authenticate + fetch recent posts | `fetch` | No (read) | Free |
| 2 | Match posts against per-subreddit rules | `match` | No | Free |
| 3 | Draft comments via Gemini into a queue | `draft` | No | **Gemini API** |
| 4 | Human approve / reject / edit | `review` | No | Free |
| 5 | Post approved comments, paced + rate-limit aware | `post` | **Yes (confirmed)** | Free |
| 6 | Track comment karma + audit logging | `karma` | No (read) | Free |

**Out of scope (intentionally):** web UI/API, multi-account orchestration, scheduling,
analytics dashboards, OAuth flow (uses script-app password auth).

---

## 3. Architecture & design

### 3.1 Component overview

```
                         config.yaml                 GEMINI_API_KEY (env)
                              |                               |
                              v                               v
 main.py (CLI dispatch) --> src/config.py            src/drafter.py --> Gemini API
     |                                                    ^
     |  fetch/match           src/reddit_client.py        | draft
     +---------------------> src/fetch.py --> Reddit API   |
     |                        src/match.py (pure logic)    |
     |  draft/review/post ------------------------------> src/store.py (SQLite: queue.db)
     |                        src/review.py (approve/edit)     ^
     |                        src/poster.py --> Reddit API ----+ post
     |  karma                 src/karma.py  --> Reddit API ----+ record
     +---------------------> src/applog.py --> reddit-helper.log (rotating audit log)
```

### 3.2 Data flow

`fetch` → `match` → `draft` (pending) → `review` (approved/rejected/edited) →
`post` (posted) → `karma` (scores over time). State persists in a single SQLite
file between commands, so each stage can be run independently and later.

### 3.3 Module responsibilities & size

| Module | LOC | Responsibility |
|--------|-----|----------------|
| `main.py` | 346 | CLI dispatch, user I/O, wiring real side effects into the logic |
| `src/config.py` | 235 | Load + validate `config.yaml` (creds, rules, Gemini, posting) |
| `src/store.py` | 207 | SQLite store: drafts, status lifecycle, karma history, migration |
| `src/poster.py` | 147 | Post comments; pacing + rate-limit backoff |
| `src/review.py` | 104 | Approve/reject/edit loop (I/O injected) |
| `src/drafter.py` | 103 | Build prompt + call Gemini; lazy SDK import |
| `src/karma.py` | 92 | Read + record comment scores; build report |
| `src/match.py` | 91 | Filter posts by rules (pure logic) |
| `src/fetch.py` | 58 | Read recent posts via PRAW |
| `src/applog.py` | 38 | Rotating audit log setup |
| `src/reddit_client.py` | 24 | Build authenticated PRAW client |

**Key architectural principle — dependency injection of side effects.** Every network
call, the Gemini call, and `time.sleep()` are passed into the core functions
(`run_review`, `run_posts`, `check_karma`, `draft_comment`). Production code (`main.py`)
injects the real implementations; tests inject fakes. This is why the entire pipeline
is unit-testable with no network, no API cost, and no real waiting.

---

## 4. Tech stack & rationale

| Technology | Why chosen |
|------------|-----------|
| **Python 3.10+** (tested on 3.12) | Rich ecosystem for both Reddit and Gemini; fast to iterate |
| **PRAW** (`>=7.7,<8`) | Official Reddit API wrapper; handles auth, endpoints, rate-limit surfaces |
| **google-genai** (`>=1.0`) | Official Gemini SDK; chosen over local templates for draft quality |
| **PyYAML** (`>=6,<7`) | Human-friendly config incl. multi-line per-subreddit guidelines |
| **SQLite** (stdlib) | Durable cross-command state with zero setup; one git-ignored file |
| **logging** (stdlib) | Audit trail without a heavy dependency; rotating file handler |
| **pytest** (dev) | Standard, low-friction test runner |

Default Gemini model: `gemini-3.8-flash` (configurable). API key is read from the
`GEMINI_API_KEY` environment variable and **never** stored in a file.

---

## 5. Data model (SQLite — `queue.db`)

**`drafts`** — one row per candidate post:
`post_id` (PK, Reddit submission id — enforces no double-drafting), `subreddit`,
`post_title`, `post_url`, `post_author`, `comment`, `status`, `model`,
`created_at`, `updated_at`, `posted_url`.

Status lifecycle: `pending → approved | rejected → posted`.

**`karma`** — time series, one row per reading:
`id` (PK), `post_id`, `score`, `checked_at`; indexed on `(post_id, checked_at)`.

Schema is created on connect; a lightweight `_migrate()` adds missing columns
(`posted_url`) so an older `queue.db` upgrades in place.

---

## 6. Key design decisions

1. **Approve-first, human-in-the-loop.** Posting requires explicit confirmation;
   `--dry-run` previews without login; `--yes` is the explicit non-interactive opt-out.
2. **One slice at a time, read-only until posting.** Only `post` writes to Reddit.
3. **Side-effect injection** for full offline testability (see §3.3).
4. **Cost & safety caps:** `max_drafts_per_run` and `max_posts_per_run`, plus `--limit`;
   the model may return `SKIP` to decline low-value posts (no wasted output tokens).
5. **Human-like pacing + rate-limit backoff** in the poster; a second rate-limit stops
   the run rather than hammering Reddit.
6. **Secrets out of source:** Gemini key in env; `config.yaml`, `queue.db`, and
   `*.log` are git-ignored.

---

## 7. Security & privacy

- **Credentials:** Reddit creds live in git-ignored `config.yaml`; Gemini key in env only.
- **Config validation** rejects leftover example placeholders and missing fields.
- **Data sent off-machine:** post title + body + subreddit guidelines are sent to the
  Gemini API during `draft`. This should be understood/consented (public Reddit data).
- **Auth method:** Reddit "script" app password auth (see §9 limitations).
- **Honest User-Agent** is required and documented, per Reddit policy.

---

## 8. Testing & quality

- **45 tests, all offline.** Coverage spans: config parsing/validation, match-rule
  gates (keywords, score/comment/age bounds, case-insensitivity), the queue
  (CRUD, status transitions, reconnect persistence, duplicate rejection), the review
  loop (approve/reject/edit/skip/quit), posting (pacing, rate-limit retry/stop, error
  isolation, PRAW error parsing), and karma (record/history, report math, skip paths).
- **Approach:** pure logic + injected fakes; a real in-memory SQLite DB (`:memory:`)
  for store/review/poster/karma tests.
- **Not present:** no CI pipeline, no coverage measurement, no linter/formatter config,
  no type-checker in the loop (type hints are used but not enforced).

---

## 9. Limitations & known issues

- **Not a git repository.** No version history yet — recommend `git init` + first commit.
- **Reddit auth is password-based** (script app). No OAuth refresh-token flow; accounts
  with 2FA need the `password:otp` form, which is awkward for automation.
- **No live end-to-end run** against real Reddit/Gemini has been performed/verified.
- **No retry/backoff on the Gemini call** itself (relies on SDK defaults).
- **Single-user, single-machine**; `queue.db`/log live in the project root.
- **Karma history is manual/polled** — no scheduler; the user must re-run `karma`.

---

## 10. Suggested future work

- `git init`, add CI (run `pytest` on push), add `ruff`/`black` + `mypy`.
- OAuth auth flow to replace password auth.
- Scheduled `karma` runs (cron / Task Scheduler) for a real time series.
- Richer reporting/export; optional dedup against already-answered threads.
- Packaging (`pyproject.toml`, console entry point) instead of `python main.py`.

---

## 11. How to run

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml   # then fill in Reddit creds + subreddits
$env:GEMINI_API_KEY = "your-key"    # for `draft`

python main.py fetch        # read-only
python main.py match
python main.py draft --limit 1
python main.py review
python main.py post --dry-run
python main.py karma

python -m pytest             # 45 tests
```

---

## 12. Review checklist — areas where senior feedback is most useful

- [ ] CLI arg handling in `main.py` is hand-rolled — move to `argparse`/`click`?
- [ ] Is SQLite-in-project-root the right place, or should state go under a data dir?
- [ ] Error handling around the Gemini call (retries, partial failures, budget).
- [ ] Rate-limit parsing in `poster._parse_wait` is regex on message text — fragile?
- [ ] Prompt design in `drafter.SYSTEM_PROMPT` — quality/guardrails for `SKIP`.
- [ ] Secrets handling and whether sending post content to Gemini needs explicit consent.
- [ ] Test strategy: enough, or add an integration test behind a flag?
