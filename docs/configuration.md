# Configuration

All settings live in **`config.yaml`** (you create it by copying
`config.example.yaml`). This page explains every field.

> `config.yaml` is git-ignored, so your credentials never get committed. The
> Gemini API key is **not** in this file — it's read from the
> `GEMINI_API_KEY` environment variable.

The file has five sections: `reddit`, `fetch`, `gemini`, `post`, and
`subreddits` (plus an optional global `match` block).

---

## `reddit` — your login (required)

```yaml
reddit:
  client_id: "paste_client_id_here"
  client_secret: "paste_secret_here"
  username: "your_reddit_username"      # no "u/" prefix
  password: "your_reddit_password"
  user_agent: "reddit-helper/0.1 by u/your_reddit_username"
```

| Field | What it is |
|-------|-----------|
| `client_id` | The short code under your app's name at reddit.com/prefs/apps |
| `client_secret` | The longer "secret" value from the same page |
| `username` / `password` | Your normal Reddit login |
| `user_agent` | A short, **honest** label Reddit requires — put your real username in it |

If any of these are missing or still contain the example placeholders, the tool
stops with a clear message.

---

## `fetch` — how many posts to read

```yaml
fetch:
  listing: "new"   # new | rising | hot
  limit: 10
```

| Field | Meaning | Default |
|-------|---------|---------|
| `listing` | Which Reddit listing to read: `new`, `rising`, or `hot` | `new` |
| `limit` | How many posts to read per subreddit | `10` |

---

## `gemini` — the AI that drafts comments (optional)

```yaml
gemini:
  model: "gemini-3.8-flash"   # cheaper option: "gemini-3.5-flash-lite"
  temperature: 0.7
  max_tokens: 1024
  max_drafts_per_run: 10
```

| Field | Meaning | Default |
|-------|---------|---------|
| `model` | Which Gemini model writes the drafts (`gemini-3.5-flash-lite` is cheaper) | `gemini-3.8-flash` |
| `temperature` | How varied the wording is: `0` = focused/consistent, up to `2` = more creative | `0.7` |
| `max_tokens` | Max length of each draft (comments are short) | `1024` |
| `max_drafts_per_run` | **Safety cap:** most drafts one `draft` run will create | `10` |

> Gemini has a **free tier**, so drafting is usually free. `max_drafts_per_run`
> still caps how many API calls one run makes; the `--limit` flag on `draft` can
> lower it further for a single run.

---

## `post` — pacing and safety for posting (optional)

```yaml
post:
  min_delay_seconds: 300   # 5 minutes
  max_delay_seconds: 900   # 15 minutes
  max_posts_per_run: 5
```

| Field | Meaning | Default |
|-------|---------|---------|
| `min_delay_seconds` | Shortest pause between posts | `300` |
| `max_delay_seconds` | Longest pause (a random time in the range is used) | `900` |
| `max_posts_per_run` | **Safety cap:** most comments one `post` run will post | `5` |

> Posting pauses a **random** amount of time between `min` and `max` before each
> post, so it behaves like a human, not a bot. A single post (`--limit 1`) has
> no delay.

---

## `subreddits` — the communities you work in (required)

A list. Each entry has a **name**, optional **guidelines**, and optional
per-subreddit **match rules**.

```yaml
subreddits:
  - name: "learnpython"
    guidelines: >
      Answer only beginner questions you can help with. Be concrete, give a
      short code example. No self-promotion. Match the friendly, patient tone.
    match:
      keywords: ["how do i", "error", "typeerror", "beginner", "help"]
      exclude: ["hiring", "job"]
      max_comments: 5
```

| Field | Meaning |
|-------|---------|
| `name` | The subreddit name (without `r/`) |
| `guidelines` | Plain-English notes the **AI follows** when drafting a comment here |
| `match` | Rules for which posts qualify (see below). Optional — falls back to the global defaults |

> The **guidelines** are important: they're how you tell the AI the rules and
> tone of each community (e.g. "no self-promotion, give a short code example").

---

## Match rules

Match rules decide **which posts are worth drafting a comment for**. You can set
**global defaults** (a top-level `match:` block) and **override** any of them per
subreddit. A post qualifies only when **every** rule below passes.

```yaml
match:
  keywords: []        # match only posts whose title/body contain ANY of these (empty = any post)
  exclude: []         # skip posts whose title/body contain ANY of these
  min_score: 0        # skip posts below this score
  max_score: null     # skip posts above this score (null = no limit)
  min_comments: 0     # skip posts with fewer comments than this
  max_comments: null  # skip posts with more comments than this (null = no limit)
  max_age_hours: 48   # skip posts older than this many hours (null = no limit)
```

| Rule | What it does |
|------|--------------|
| `keywords` | Post's title or body must contain **at least one** of these words. Empty list = no keyword filter (any post passes this gate). |
| `exclude` | If the title/body contains **any** of these, the post is skipped. |
| `min_score` / `max_score` | Keep posts within this score (upvote) range. |
| `min_comments` / `max_comments` | Keep posts within this comment-count range. Capping `max_comments` lets you reply early, before a thread is answered. |
| `max_age_hours` | Skip posts older than this. |

Keyword and exclude matching is **case-insensitive** and checks **both** the
title and the post body.

**How global + per-subreddit combine:** a subreddit's `match:` block only
changes the fields it names; everything it doesn't mention is inherited from the
global defaults. For example, if the global default is `max_age_hours: 48` and a
subreddit only sets `keywords`, that subreddit still uses `max_age_hours: 48`.
