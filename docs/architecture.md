# Architecture

`main.py` wires CLI I/O into configuration, policy gates, Reddit/Gemini clients,
a SQLite queue, review, checked submission, and score inspection.

`src/policy.py` checks operator records before live clients are constructed.
`src/lifecycle.py` compares current title/body hashes and removes records when
the source changes or becomes unavailable. It checks approval state, disclosure,
source eligibility, locked/archived state, and exact duplicates before posting.
`src/drafter.py` separately blocks model calls without external-processing records.
These checks cannot prove that references correspond to genuine Reddit approval.

The drafts table contains metadata, comment, status, model, timestamps, posted
URL, and `source_hash`. Migration adds missing columns. Legacy rows without a
fingerprint are deleted on synchronization instead of implicitly trusting old
approvals. Lifecycle: pending -> approved/rejected; approved -> posted.
The karma table stores score readings. Local deletion removes both tables' rows.
SQLite secure deletion is enabled; OS encryption and backup deletion remain
operator responsibilities. Retention is enforced at queue opening.

Human review adds/preserves an AI disclosure. The CLI has no confirmation bypass.
A checked submit wrapper revalidates immediately before each reply and retry.
The poster still exposes low-level injected functions for offline unit testing;
production operation must go through the guarded CLI, not custom scripts that
call network primitives directly.

No scheduler, background deletion listener, moderator-permission verification,
provider data-use verification, semantic spam detector, encrypted database
implementation, or remote approval validation is provided. Human review remains
necessary. Tests fake networks and sleeps and use real local SQLite.
