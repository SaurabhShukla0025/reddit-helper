# Implementation report

Updated 2026-10-14.

A separate Reddit-native Devvit Web version now exists in devvit/. Its native
post-menu writing/review forms publish one operator-confirmed reply as the app
account. Ordinary Reddit scope and Redis are its only requested capabilities.
Defaults disable live workflows until operating references and privacy details
are configured. Redis retention, atomic daily attempt limits, one-use review
tokens, source revalidation, deletion/edit triggers and local deletion actions
are implemented. Type checks, 42 offline tests and the production build pass.
The package lock pins the installed dependency tree. Runtime dependency audit
reports zero advisories; the official CLI's dev dependency advisories remain.
No upload, installation, account login, review submission or live publication
was performed. The Devvit privacy notice still needs a real contact/public URL.

The workflow now requires a manually selected post ID, a human-written reply,
review, and explicit confirmation for each single publication. The app supports
one approved community. Gemini drafting, post discovery/matching, score filters,
karma inspection, posting batches and automatic retries have been removed.

Approval checks remain fail-closed. Configuration records purpose, conditions,
community scope, app identity and optional expiry. Conditions are recorded for
operator review, not automatically interpreted. Approval remains Reddit's decision.
The Python component remains an external Python/PRAW CLI; no Reddit review was performed.
The documented Devvit assessment found support for the core workflow and no
substantiated platform gap. External operation now requires recorded Reddit
permission for this architecture in addition to general API authorization.

Credentials can come from environment variables or current-user Windows DPAPI
encrypted storage. Source authors are not retained.
Legacy non-human drafts and karma tables are removed on first queue access.
SQLite maintains atomic daily attempt counters across runs. Submission failures
reserve an attempt and leave the draft uncertain to prevent blind retry.
Duplicate/similarity checks operate only within retained local records.

Hourly local cleanup is available through the maintenance process and on queue
access. An hourly/logon Windows cleanup task is installed in this workspace,
and its initial run returned LastTaskResult=0. It requires the owning user to be
signed in. Existing config/queue file ACLs are restricted to the owner, SYSTEM
and administrators; disk encryption could not be verified. Console-only logging avoids new
persistent logs; cleanup removes legacy app log files. Source deletion checks
require cleanup --sync and authorization. Backup/reply-file cleanup remains manual.

Validation is offline. No live Reddit access, external API application, or approval
submission is performed. Offline readiness reports missing actual evidence;
privacy review records a hash that is invalidated by notice edits. Registration,
profile labeling, actual API/community permission, terms acceptance, deletion
contact, dedicated-account confirmation and storage review remain unresolved.
The user supplied developer username saurabhimapro, r/learnpython and a personal,
non-commercial purpose. None of these facts is treated as Reddit approval.


Owner playtest follow-up: the operator confirmed public readability of the notice
and reviewed test-community rules on 2026-10-14. A settings-format regression was
fixed by accepting the SDK's single-choice array values. Playtest prerequisites
use community settings, whose stored values can be verified; the portal global
settings value endpoint did not preserve the values reliably. Private version
0.0.2 was uploaded and installed only to r/saurabhhelpertest. No review submission
or test comment was published by the agent. The installer lists broad Reddit/
moderator capabilities, although the manifest uses user scope and application
code exposes no moderation actions; permission review remains a production task.
