# Contribution Helper for Reddit ? implementation report

Updated 2026-10-12. This replaces the earlier approve-first report, which implied
that pacing and human approval were sufficient for compliant operation.

The CLI prepares useful contributions subject to documented permissions, required
app identity, disclosed AI processing, community rules, and human confirmation.
Automated karma farming is outside its purpose. Existing score inspection remains
available only within the approved use case; there is no voting functionality.

Live access defaults to blocked. Gemini processing has an additional independent
authorization gate. Permission references are operator attestations, not proof
or a grant of approval. Current API/developer policies may require a separate
agreement or Devvit architecture; local Python cannot bypass those requirements.

Implemented changes: hard request/post caps, removal of `--yes`, community and
identity checks, preserved disclosure, source fingerprint migration, source
verification before queue use and submission/retry, exact duplicate blocking,
local retention and per-post/all cleanup, and an operator privacy template.

Migration removes legacy rows without a fingerprint during source sync. Local
cleanup removes queue rows and related score history, not Reddit comments,
provider records, logs, or backups. SQLite secure deletion is enabled but the
application does not encrypt the database; OS storage protections are required.

Validation uses offline fake clients and SQLite tests, including blocked network
paths, source deletion/edit handling, retention, disclosure, and hard request caps.
Live Reddit/Gemini behavior and permission approval remain unverified. No
background deletion listener or scheduler is installed. Operate only within real
approval and keep rules, data handling, and deletion procedures current.
