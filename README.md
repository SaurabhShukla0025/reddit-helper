# Contribution Helper for Reddit

A local Python CLI for preparing useful, accurate contributions in communities
that permit the workflow. It is not an automated karma-farming system.

**Live access is blocked by default.** Obtain explicit Reddit authorization for
API access, community scope, posting, and any third-party AI processing before
recording those permissions in configuration. A configuration value is an
operator attestation, not verification or a grant of permission. These controls
reduce risk; they do not certify compliance or guarantee Reddit approval.

## Setup

Use Python 3.10+, create a virtual environment, and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
Copy-Item config.example.yaml config.yaml
python -m pytest -q
```

Read [the operating requirements](docs/configuration.md) and
[the privacy notice](PRIVACY.md) before configuring live operation.
Do not put passwords or API keys in chat, issues, or commits.

## Workflow

```powershell
python main.py fetch
python main.py match --all
python main.py draft --limit 1
python main.py drafts
python main.py review
python main.py post --dry-run
python main.py post --limit 1
python main.py karma
python main.py cleanup --sync
```

Fetching and matching read Reddit live; they require approval too. Drafting sends
post titles and bodies to Gemini only after the additional external-processing
permission checks pass. The model may decline a post. Draft limits count every
request, including declines and errors; CLI limits cannot exceed configured caps.

Review shows disclosed AI drafts and supports approve, reject, edit, skip, and
quit. Editing preserves the disclosure. Posting requires human confirmation of
accuracy, relevance, disclosure, and current community rules. `--yes` is rejected.
Pauses control load; they must not conceal app identity or evade enforcement.

Source posts are checked before queued content is displayed or used, and again
before each submission/retry. Changed, removed, deleted, private, quarantined,
NSFW, and out-of-scope source records are purged. Locked/archived posts cannot
receive comments. Network verification errors block use rather than exposing
unverified content. Old queue rows lacking source fingerprints are purged during
synchronization; regenerate and review them only under an authorized workflow.
Exact duplicate comment text is blocked within retained posted records; human
review must also reject substantially similar or otherwise unwanted content.

`post --dry-run` stays offline and shows only a count: source content remains
hidden until live verification. It is not evidence that posting is authorized.
`karma` records comment scores for inspection, not karma optimization.

## Data cleanup

```powershell
python main.py cleanup                  # enforce configured retention locally
python main.py cleanup --sync           # verify sources with approved API access
python main.py cleanup --post-id abc123 # process a local data deletion request
python main.py cleanup --all            # remove all local queue data on shutdown
```

Cleanup deletes local records, not published Reddit comments. Retention defaults
to 30 days, may be shortened, and runs whenever the CLI opens the queue. The clock
uses original draft creation; updates do not extend retention. Run cleanup/sync
regularly while operating; no scheduler or background deletion listener is
installed. Handle deletion requests promptly, including backups and external
provider records. If permission is revoked, stop live use and run local cleanup.

## Files

- `main.py`: CLI, real clients, verification, confirmation, cleanup.
- `src/policy.py`: permission and disclosure checks.
- `src/lifecycle.py`: source fingerprints, revalidation, submission checks.
- `src/config.py`: settings and validation.
- `src/fetch.py`, `src/match.py`: eligible posts and topic rules.
- `src/drafter.py`, `src/review.py`: authorized AI drafting and human review.
- `src/poster.py`: submission orchestration, load pauses, rate-limit backoff.
- `src/store.py`, `src/karma.py`: local queue and score history.
- `src/applog.py`: rotating operational log.
- `tests/`: offline fake clients and SQLite regression tests.

[Documentation](docs/README.md) covers setup, commands, architecture, and limits.
