# Troubleshooting & Glossary

Common problems and their fixes, followed by plain-English definitions of the
words used in this project.

---

## Troubleshooting

### "No config found at ... config.yaml"
You haven't created your config yet. Copy the example and fill it in:
```powershell
copy config.example.yaml config.yaml
```
See [Configuration](configuration.md).

### "config.yaml still has example placeholders"
You left the `YOUR_CLIENT_ID` / `YOUR_...` placeholders in. Replace them with
your real Reddit values.

### "config.yaml is missing reddit values: ..."
One of `client_id`, `client_secret`, `username`, `password`, or `user_agent` is
blank. Fill them all in under the `reddit:` section.

### "Could not sign in to Reddit: received 401 ..."
Your Reddit credentials are wrong. Check:
- the **client id** and **secret** are copied correctly (no extra spaces),
- the app type is **script** (not "web app" or "installed app"),
- the **username/password** are correct,
- if your account has **2FA**, the password must be `password:123456` (password
  + colon + current 6-digit code).

### "No Gemini API key found"
The `draft` command needs your Google key. Set it for the session:
```powershell
$env:GEMINI_API_KEY = "your-key..."
```
Get a free one at [Google AI Studio](https://aistudio.google.com/apikey).

### "The 'google-genai' package is not installed"
You skipped installing dependencies (or aren't in the virtual environment):
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

### `draft` says "the model declined this post"
That's normal — the AI decided the post wasn't something it could usefully reply
to, so it skipped it instead of writing filler. Nothing was charged for output.

### `post` says "rate limited ... stopping"
Reddit is asking you to slow down (common on new accounts). The tool waited and
tried again, and stopped to avoid hammering Reddit. Your approved drafts are
untouched — try again later, or post fewer at a time (`--limit 1`).

### Posting a comment fails with "post may be locked or removed"
The target post was deleted, locked, or archived since it was drafted. That draft
is marked as failed and the tool moves on; the others still post.

### The Reddit "Responsible Builder Policy" notice when creating the app
That's just an informational link, not an error — continue creating the app. This
tool is built to follow those rules (approve-first, paced, honest User-Agent, no
spam).

### I want to see more detail about what happened
Add `--verbose` to any command to print the log to the screen, or open the full
history in `reddit-helper.log`.

---

## Glossary

Plain-English definitions of terms used here.

| Term | Meaning |
|------|---------|
| **Subreddit** | A community on Reddit, like `r/learnpython`. |
| **Post** | A submission in a subreddit (the thing you reply to). |
| **Comment** | A reply to a post. This tool drafts and posts comments. |
| **Karma** | A comment's score (upvotes minus downvotes). Step 6 tracks it. |
| **Draft** | An AI-written comment waiting for your approval. |
| **The queue** | The list of drafts and their status, stored in `queue.db`. |
| **Pending / approved / rejected / posted** | The four states a draft moves through. |
| **Match rules** | The filters that decide which posts are worth a draft. |
| **Guidelines** | Your notes about a subreddit's rules/tone that the AI follows. |
| **PRAW** | The official Python library for talking to Reddit's API. |
| **Gemini / Google** | The AI (and the company) that writes the drafts. |
| **API** | A way for programs to talk to a service (Reddit's API, Gemini's API). |
| **API key** | A secret password that lets the tool use a service (your Gemini key). |
| **Environment variable** | A value set in your terminal (like `GEMINI_API_KEY`) that programs can read, without saving it in a file. |
| **Rate limit** | A cap on how fast you can act, enforced by Reddit. The tool paces itself to stay under it. |
| **User-Agent** | A short honest label identifying your app, required by Reddit. |
| **Dry run** | A preview that shows what *would* happen without doing it (`post --dry-run`). |
| **Virtual environment (`.venv`)** | An isolated box for this project's Python libraries. |
| **SQLite** | A tiny database kept in a single file (`queue.db`) — no server needed. |
| **CLI** | Command-Line Interface — you run it by typing commands in a terminal. |

Still stuck? See [Getting Started](getting-started.md) to re-check the setup, or
[Commands](commands.md) for exactly what each command does.
