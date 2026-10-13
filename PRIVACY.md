# Privacy notice ? operator customization required

This describes the local CLI's current behavior. Before live operation, add your
operator identity, real deletion contact, approved purpose/community scope,
retention period, storage protections, and the authorized provider's data-use
and retention terms. Do not claim that this template is a legal compliance
certification. `privacy_policy_reviewed` should remain false until this is done.

## Collection and purpose

The CLI reads submission IDs, titles, bodies, authors, community names, creation
times, scores, comment counts, and permalinks from permitted public communities.
Only sources eligible for the configured workflow are used. The purpose is
preparing relevant contributions for human review, not profiling people,
training models, advertising, or manipulating karma. There are no voting,
private-message, or account-creation features.

SQLite stores IDs, titles, authors, permalinks, community names, generated or
edited comments, status, model, timestamps, a source-text hash, published comment
links, and recorded comment scores. Source bodies are sent to the model but are
not stored as a separate database field. Generated drafts may contain portions
of source content and must be reviewed accordingly.

## External processing and publication

The draft command sends post titles/bodies, community names and guidelines to
Google Gemini only when explicit authorization is recorded. The CLI does not
train a model. It cannot independently guarantee the provider's retention or
training practices; the operator must verify that the authorized service/account
and any separate agreement permit the processing. Do not enable drafting if
those requirements cannot be met. Approved, disclosed comments are published
through Reddit's API only after human confirmation.

## Storage, retention, and requests

`config.yaml`, `queue.db`, and rotating logs live locally and are git-ignored.
Credentials are plaintext in config; Gemini credentials come from environment
variables. SQLite is NOT encrypted by this program. Use appropriate OS/disk
encryption, restricted filesystem access, and secure backups before attesting
to data security. Git ignore is not a security boundary.

Queue records expire after the configured 1-30 days from creation. Cleanup runs
on queue access; it does not execute while the app is idle. Run cleanup regularly.
Source verification removes local drafts/metadata and score history for deleted,
removed, edited, protected, or out-of-scope sources. Failed verification blocks
use until resolved. SQLite secure deletion is enabled; backups, filesystem
snapshots, disk remnants, old logs, and external copies need separate handling.

Provide your actual deletion contact in `policy.deletion_contact` and here.
Process requests with `cleanup --post-id ID`. Run `cleanup --all` when shutting
down or losing authorization, and handle logs/backups/provider records separately.
Local cleanup does not delete live comments; manage those on Reddit as needed.
Logs may include IDs, permalinks, subreddit names, counts, timestamps, error
messages, and historical metadata from older releases. Do not log secrets, and
review old logs during migration. Logs rotate by size rather than age; remove
unneeded logs and backups as part of the operator's retention procedure.
