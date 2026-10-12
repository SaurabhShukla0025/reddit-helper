# Reddit Helper — Documentation

Welcome! This folder explains the whole project in plain language, so **anyone**
— even if you've never used it before — can understand what it is, set it up,
and run it.

## What is Reddit Helper, in one sentence?

A small program that **finds relevant Reddit posts, writes helpful draft comments
with AI, lets you approve or edit each one, and then posts the approved ones for
you** — slowly and safely, like a human would. **It never posts anything without
your approval.**

> It is a *draft-and-approve assistant*, **not** an unattended bot. It is meant
> for writing genuinely useful comments that follow each community's rules.

## The big picture

The tool works in six stages. You run one command for each stage:

```
  1. fetch     →  2. match    →  3. draft    →  4. review   →  5. post     →  6. karma
  ─────────       ─────────       ─────────      ─────────      ─────────      ─────────
  read recent     keep only       AI writes      you approve    post the       track how
  posts from      the posts       a comment      / edit /       approved       your posted
  your chosen     worth           for each       reject each    comments to    comments
  subreddits      replying to     good post      draft          Reddit         score over time
  (read-only)     (read-only)     (Gemini API)   (you decide)   (asks first)   (read-only)
```

Everything is saved in between, so you can do step 3 today and step 5 tomorrow.

## Table of contents

Read these in order if you're new:

1. **[Getting Started](getting-started.md)** — install it, get your Reddit and
   Gemini keys, fill in the config, and run it for the first time.
2. **[Commands](commands.md)** — every command, what it does, and example output.
3. **[Configuration](configuration.md)** — a full reference for `config.yaml`
   (every setting explained).
4. **[Architecture](architecture.md)** — how the code is organized and how data
   flows (for developers / the curious).
5. **[Troubleshooting & Glossary](troubleshooting.md)** — fixes for common
   errors, plus plain-English definitions of the words used here.

## Is it safe? Does it cost money?

- **Reddit API** — free. Reading posts and posting comments costs nothing.
- **Gemini API** — has a **free tier**, and **only** the `draft` command uses it.
  There are built-in caps so you stay within your quota.
- **Posting** is the only action that changes anything on Reddit, and it always
  **asks you to confirm first**.

See [Getting Started](getting-started.md) to begin.
