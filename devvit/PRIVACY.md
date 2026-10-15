# Contribution Helper privacy notice — complete before launch

Operator: u/saurabhimapro
Deletion contact: saurabhimapro@gmail.com
Current development community: r/saurabhhelpertest
Intended production community: r/learnpython, subject to permission and review
Purpose: personal, non-commercial, human-written contributions
Current status: Devvit owner playtest installed in r/saurabhhelpertest.
Production use has not been approved by Reddit.

This notice applies only to the Devvit app, not the separate Python CLI.

The operator selects a post and writes a reply. The app reads only the selected
source's title/body, ID, community and availability metadata and verifies source
author availability. Source author identifiers are not retained. The app checks
the current user identity to limit usage to its operator; it does not profile users
or match them with off-platform identities.

Reddit-hosted Redis stores one draft (random review token, source ID/hash,
human-written reply, deadline) and a short history of attempts/posted replies
(source ID/hash, reply, token, status, timestamp and comment URL when known).
Storage is isolated by Reddit installation. No source body/title is retained.
Daily attempt counters have only a UTC date and count. No external provider receives
content; the app has no external HTTP permission, analytics, AI or training pipeline.

Drafts expire after one hour. Attempt/posted history expires within seven days;
older records are not extended by later activity, and history may be deleted early.
Daily counters expire after two days. Reddit provides hosting and underlying storage;
this app does not claim to independently encrypt or erase Reddit's infrastructure.

Reddit source deletion/edit events purge the affected draft/history. Sources are
rechecked before display/publication. These event integrations require permitted
on-platform testing; this local build alone does not prove event delivery.

The operator can use the post-menu deletion action for one source or the
community-menu deletion action for all local reply data. These actions remain
available when posting is disabled. They do not delete published Reddit comments
or reset daily counters. Published content is managed on Reddit separately.

Publication occurs only after a separate explicit confirmation and uses the app's
Reddit-managed account. The reply becomes public Reddit content. Operators must
handle deletion requests promptly through the public contact, disable operation
on revocation, purge local app data, and handle any separately created exports.
The app creates no external backups/exports and logs no reply content or credentials.

Privacy/contact settings and review references are operator records, not proof of
authorization. Production use requires the applicable Reddit review and community
permission. For deletion requests, email the operator above and identify the
relevant Reddit post URL or ID; do not send passwords or authentication tokens.
