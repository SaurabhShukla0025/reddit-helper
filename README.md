# Contribution Helper for Reddit

The Reddit-native version is now built in [devvit/](devvit/README.md). It uses
Reddit post menus and forms for writing, reviewing and confirming one reply.
Its local tests and production build pass; registration, permitted on-platform
testing, public privacy/contact details and Reddit review are still required.
The Python CLI described below remains separately blocked pending its own permission.

A local Python CLI for human-written replies in one approved community.
You choose a post, write a reply, review it, and explicitly publish that one comment.
There is no post discovery, Gemini processing, karma tracking, voting, private
messaging, batch publishing, or automatic submission retry.

**Live access is blocked until real Reddit authorization is recorded.**
Configuration records operator attestations; it does not grant or verify approval.
Reddit directs developers to Devvit first. This external CLI is not a Devvit app:
assess Devvit and document a real unsupported capability before requesting an
external API exception. This implementation cannot guarantee approval.

## Setup

Use Python 3.10+:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
Copy-Item config.example.yaml config.yaml
python -m pytest -q
```

Record real approval, app registration/label, dedicated app account, permitted
purpose, community scope, posting permission, conditions and expiry in config.
Complete [PRIVACY.md](PRIVACY.md) with your real identity and deletion contact.
Choose retention and daily limits consistent with approval. Never fabricate permissions.

Credentials come from REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_PASSWORD
environment variables. Inject them through your trusted credential manager or
session; do not save secrets in config, shell history, chat, or the repository.
On Windows, `python main.py credentials set` can save credentials using
current-user DPAPI encryption. The app does not encrypt SQLite.

Run `python main.py readiness` for an offline report of missing evidence.
Complete the privacy notice and run `python main.py privacy-review` to record
review of its exact bytes; later edits invalidate that review.
See [operating procedures](docs/operations.md) and the
[Devvit assessment](docs/devvit-assessment.md). Core functionality appears
supported by Devvit; no external platform exception has been established.

## Workflow

Select a submission in the approved community yourself. Copy its submission ID
from its URL, e.g. abc123 in /comments/abc123/.

```powershell
python main.py draft abc123 --text-file my-reply.txt
python main.py review abc123
python main.py post abc123
```

Omit --text-file to write in your editor. Review allows approve/reject/edit.
An edit returns the draft to pending. Publishing shows the exact reply and asks
for one explicit confirmation. There is no --yes or batch selection.
Write the reply yourself; there is no AI integration or AI-disclosure injection.

Before queued content is displayed or published, the source is checked.
Changed, removed, deleted, NSFW, protected or out-of-scope sources are purged.
Locked/archived posts cannot receive replies; verification errors block use.
Exact and highly similar text are blocked against retained posted/uncertain drafts.
These checks are heuristics, so review must also reject spam and unwanted replies.

Daily publish attempts use persistent UTC counters, including failed or uncertain
submissions. Concurrent reservations are serialized. An uncertain submission
cannot be approved or republished: check Reddit and resolve it manually.
Removing queue records does not reset today's attempt count. Do not delete or
replace the database to bypass limits. Limits apply to this local database,
not other machines or directly published comments.

## Automatic local cleanup

```powershell
python main.py maintenance
```

Leave this separate process running for hourly local retention cleanup; Ctrl+C
stops it. Cleanup also runs on every queue access. The maintenance process itself
is not installed as a service; the separate Windows task handles scheduled cleanup.
The Windows installer `scripts/install-cleanup-task.ps1` provides an hourly/logon
task using pythonw. It runs only while its owning user is signed in and catches
up when available. A task is installed and verified in this workspace.
Use `scripts/protect-local-data.ps1` to restrict existing application data files
to the owning Windows user, SYSTEM and administrators; repeat for new files.
Disk encryption requires a separate verified OS configuration.

```powershell
python main.py cleanup --sync
python main.py cleanup --post-id abc123
python main.py cleanup --all
```

Source deletion checks require approved API access and --sync; local maintenance
does not call Reddit. Backups and user-created reply files require operator cleanup.
New versions use console-only logs; cleanup removes the four legacy app log files.
Local cleanup never removes comments already published on Reddit.

## Migration

Replace legacy configuration with the new example, retaining only real permissions.
On first queue access, legacy non-human drafts and karma history are removed,
and stored author names are cleared. Legacy AI drafts cannot be published.
Retained human drafts without source fingerprints are removed during verification.
Local deletion commands work without API credentials or authorization.

[Documentation](docs/README.md) describes configuration, commands and limits.
