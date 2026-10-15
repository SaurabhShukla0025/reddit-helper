# Operating procedures

## Public identity and privacy

Developer/operator: u/saurabhimapro. Intended community: r/learnpython.
The purpose is personal, non-commercial, human-written contributions.
A dedicated app-account confirmation and public deletion contact are still required.
Do not mark a personal/mixed-use account as dedicated.

Complete PRIVACY.md with the real deletion contact, approved purpose/scope,
retention and verified storage practices. Record the same identity/contact in config.
Run python main.py privacy-review, read the exact notice and confirm locally.
It records the file hash and review flag. Changing the notice invalidates review.

## Credentials and storage

On Windows run python main.py credentials set in your own terminal; input is hidden.
It saves only a current-user DPAPI-encrypted .credentials.bin, never plaintext.
There is no insecure fallback. Environment-injected values override stored values.
Run credentials clear to remove that file. This does not revoke Reddit tokens.

DPAPI protects the saved credential file for the Windows account, not a compromised
session. SQLite, config, reply files and terminal transcripts are not encrypted by
this program. Verify OS/disk encryption and restricted file access before recording
storage_security_reference or data_security_reviewed. Record actual findings,
not a generic statement that protections are enabled.
Microsoft documents [current-user DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
Never send credentials in chat.

## Automatic cleanup

scripts/install-cleanup-task.ps1 installs a project-specific Windows Scheduled Task.
It runs local cleanup hourly and at logon, uses pythonw to avoid visible windows,
and runs with limited privileges as the current logged-in user. It does not store
a Windows password or make Reddit API calls. It cannot run while that user is
signed out; catch-up is enabled. Verify Task Scheduler LastTaskResult and record
the actual task name in cleanup_schedule_reference. Other operating systems can
use maintenance or their own scheduler.

The installer refuses to replace an existing task. .cleanup-task.json is an
installation receipt, not proof that later runs succeeded. Inspect Task Scheduler
for current enabled state and last result.

## Deletion requests and backups

The app does not create backups automatically. If no backup copies exist, document
that fact after checking. If copies do exist, inventory their paths/access controls,
maximum retention, responsible operator and how per-source deletion reaches every copy.
Run cleanup --post-id ID for local deletion. Remove that source from operator-managed
backups, snapshots, exported replies and retained terminal transcripts promptly.
Use cleanup --all on revocation/shutdown and revoke or clear credentials separately.
These external copies cannot be safely deleted automatically by this app.

A reply file passed through --text-file remains operator-owned. Remove it according
to the same retention/deletion procedure. The app never silently deletes arbitrary
input files or external directories. Record this procedure and your actual inventory
in backup_deletion_procedure_reference.

## Registration and permissions

Create the developer profile/app through Reddit and obtain the required label.
Accept the applicable developer/API terms and record the actual date. Retain written
approval and community permission. Do not apply for moderator-only access for this
ordinary contribution workflow. Use readiness to check missing local evidence,
without accessing Reddit or displaying secrets.


## Recorded local setup (2026-10-14)

The project-specific hourly/logon cleanup task was installed and its first run
returned result 0. Existing config.yaml and queue.db ACLs were restricted to the
owning Windows user, SYSTEM and administrators. Disk-encryption status could not
be verified because Windows denied the BitLocker query; it remains pending.
The public deletion contact and dedicated-account status are also pending.
Review evidence and all actual permissions remain unset.
