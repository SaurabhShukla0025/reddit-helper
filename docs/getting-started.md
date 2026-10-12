# Getting Started

This guide takes you from nothing to a working setup. Follow it top to bottom.
No prior experience assumed.

---

## Step 1 — Install Python

You need **Python 3.10 or newer**.

- Check if you have it:
  ```
  python --version
  ```
  If it prints `Python 3.10` (or higher), you're good.
- If not, download it from [python.org](https://www.python.org/downloads/),
  install, and **re-open your terminal**.

---

## Step 2 — Get the project and install its dependencies

Open a terminal in the project folder and run these once:

```powershell
cd C:\Users\imapro\reddit-helper

python -m venv .venv            # create an isolated environment
.venv\Scripts\activate          # turn it on (you'll see (.venv) in the prompt)
pip install -r requirements.txt # install the libraries it needs
```

> **What is a virtual environment (`.venv`)?** A private box for this project's
> libraries, so they don't clash with other Python projects. You "activate" it
> each time you work on the project.

To run the tests (optional, proves everything works):
```powershell
pip install -r requirements-dev.txt
python -m pytest
```
You should see something like `45 passed`.

---

## Step 3 — Create your Reddit app (free, ~3 minutes)

The tool logs into Reddit through a "script app" that you create once.

1. Log in at [reddit.com](https://www.reddit.com) with the account you want to
   post from.
2. Go to **https://www.reddit.com/prefs/apps**
3. Scroll down, click **"create another app..."** (or "are you a developer?
   create an app...").
4. Fill the form:
   - **name:** `reddit-helper` (anything)
   - **type:** choose **`script`** ← important
   - **redirect uri:** `http://localhost:8080`
   - leave the other fields blank
5. Click **create app**.
6. Copy these two values:
   - **client id** — the short code just **under the app's name**
   - **secret** — the longer value labeled "secret"

> You may see a notice linking to Reddit's *Responsible Builder Policy*. That's
> informational — just continue. (This tool is built to follow those rules: it's
> approve-first, paced, and uses an honest User-Agent.)

---

## Step 4 — Get a Gemini API key (only needed for the `draft` step)

Drafting comments uses Google's Gemini AI, which has a **free tier** (a free key
with a generous free quota — great for a personal tool).

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and create a key.
2. Set it in your terminal (for the current session):
   ```powershell
   $env:GEMINI_API_KEY = "your-key..."
   ```

> The key is read from this **environment variable**, never saved in a file —
> so your secret can't accidentally get shared.

---

## Step 5 — Create your `config.yaml`

The project ships with an example config. Copy it and fill in your details:

```powershell
copy config.example.yaml config.yaml
```

Open `config.yaml` and:
- Paste your **client id**, **secret**, Reddit **username** and **password** into
  the `reddit:` section.
- Put your real username in the `user_agent` line too.
- List the **subreddits** you want to work in, each with its own guidelines and
  matching rules.

See **[Configuration](configuration.md)** for what every field means.

> `config.yaml` is **git-ignored** — it never gets committed, so your password
> and secret stay private.

---

## Step 6 — Run it for the first time

Start with the safe, read-only commands:

```powershell
python main.py fetch     # lists recent posts from your subreddits
python main.py match     # shows which posts pass your rules
```

If `fetch` prints `Signed in as u/yourname` and lists posts, **your setup works.** 🎉

Then try the full flow:
```powershell
python main.py draft --limit 1   # AI drafts ONE comment (uses the Gemini API)
python main.py drafts            # see what's waiting
python main.py review            # approve / edit / reject it
python main.py post --dry-run    # preview what WOULD be posted (posts nothing)
python main.py post --limit 1    # actually post it (asks you to confirm first)
python main.py karma             # later: track your comment's score
```

Full details for each command: **[Commands](commands.md)**.

---

## A note on two-factor authentication (2FA)

If your Reddit account has 2FA turned on, the password field must be your
password **and** the 6-digit code joined by a colon: `yourpassword:123456`.
This is awkward (the code changes every 30s), so it's easiest to use an account
without 2FA for testing.
