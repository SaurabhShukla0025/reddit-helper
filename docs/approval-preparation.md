# Approval preparation — not a submitted application

Developer/operator username: saurabhimapro.
Purpose: personal, non-commercial contributions in r/learnpython.
Dedicated app account: unresolved; the developer username is not assumed dedicated.
Public deletion contact: missing.
Reddit approval, registration, profile label and community permission: not obtained.

A separate Devvit Web version is now built in devvit/ and passes local checks.
Use devvit/README.md for its registration, permitted playtest and review process.
The external API description below applies only to the Python CLI.

## Accurate behavior to describe

The current implementation is an external Python CLI. A human manually selects
a single submission, writes a reply, reviews it, and confirms that one publication.
It does not discover posts, generate AI replies, vote, send private messages,
track karma, or publish background batches. It rechecks sources, enforces a local
daily attempt cap, blocks similar replies within retained history, and prunes data.

It stores submission ID/title/community/URL/hash, human reply, status and timestamps,
and published comment URL; authors are not retained. No external AI provider receives
content. SQLite is not encrypted by the application. Credentials can be encrypted
for the current Windows user using DPAPI or injected through the environment.
Default queue retention is seven days; local cleanup is independent of Reddit API access.
No claim of global rate limiting, perfect spam detection, forensic erasure or automatic
Reddit deletion synchronization should be made.

## Route and evidence

Read devvit-assessment.md first. Core functionality appears supported by Devvit;
no valid external-platform exception has been established. Do not submit an external
application alleging an unsupported capability without real evidence.
The official [developer request form](https://support.reddithelp.com/hc/en-us/requests/new?tf_42139884615700=api_request_type_developer_clone&ticket_form_id=14868593862164)
asks for the platform gap, detailed behavior, source code and intended communities.
This document must not be submitted as if those missing facts were settled.

Before review, supply the actual app profile/registration and label evidence,
dedicated-account confirmation, completed public privacy notice, terms acceptance,
community access/reply permissions, verified storage protections, backup deletion
procedure, review demo and source link. Record Reddit's approved scope, conditions,
expiry and external architecture permission only after they are actually granted.
Do not duplicate requests or create accounts to evade decisions.
