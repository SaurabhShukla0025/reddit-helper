# Troubleshooting

**Live API access blocked:** Obtain actual approval and app registration, configure
a dedicated identity, customize the privacy notice, establish storage protections
and a deletion contact, and record the references. Do not toggle values simply
to bypass checks.

**Gemini drafting blocked:** The standard workflow does not presume permission
to share Reddit text with Google. Record explicit authorization and review the
provider's permitted data handling first. Without it, keep AI processing disabled.

**Community permission/rules error:** Verify allowed scope and current community
rules. AI replies may be prohibited. Record permitted commenting and a current
review date only after checking.

**Source verification failed:** No unverified queued content is shown or posted.
Resolve the network/API problem and rerun. The app does not treat unknown failures
as proof of deletion.

**Records disappeared during sync:** Edited/deleted/removed/protected/out-of-scope
sources and legacy drafts without fingerprints are removed locally. Retention
also removes expired records and score history. Regenerate only if currently
permitted and applicable; every replacement requires review.

**Missing disclosure:** Review adds the fixed disclosure and restores it after
edits. Posting refuses missing disclosure and returns the draft to pending.

**Rate limiting or posting error:** The poster backs off, retries once, then stops
if rate-limited again. Other errors leave drafts unposted. Do not use pacing,
new accounts, credential rotation, or repeated runs to evade restrictions.

**Deleting data:** Use local cleanup for requests or shutdown. Handle published
comments, provider copies, old logs, and backups separately. See [privacy](../PRIVACY.md).
