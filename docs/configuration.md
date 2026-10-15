# Configuration

Use config.example.yaml as the current schema. Legacy fetch/match/gemini settings
and plaintext credential settings are rejected; migrate before live use.

reddit contains username and user_agent only. The credential environment variables
are REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_PASSWORD. Use a trusted
credential manager; environment variables are not an encrypted secret vault.

policy records actual approval reference, app registration reference, dedicated
username, approved purpose, approval conditions, optional approval_expires_on
(YYYY-MM-DD), privacy/security review attestations, deletion contact and retention.
Expiry dates permit use through that date. Approval conditions must be enforced by
the operator; arbitrary conditions are not parsed by this CLI.

subreddits must contain exactly one community, access_reference,
comments_reference, rules_reviewed_on and guidelines. Rules review expires after
30 days. All defaults intentionally block live access.

retention_days is an integer from 1 to 30, default 7. max_posts_per_day is an
integer from 1 to 10, default 3; set it lower if approval requires that.
The cap counts attempts in UTC and persists across runs, including uncertain
network outcomes. It is local to this database and is not a global account limit.


Additional evidence fields: operator_identity, app_profile_label_reference,
terms_accepted_on, devvit_assessment_reference, external_api_exception_reference,
storage_security_reference, backup_deletion_procedure_reference,
cleanup_schedule_reference and privacy_notice_sha256. These are operator records,
not verification of external authorization. Blank values block live access.
The external API exception must be actual Reddit permission for this architecture.
No unsupported Devvit capability has been substantiated.

privacy-review records review of the completed PRIVACY.md bytes. A placeholder,
a changed notice, or a missing operator/contact in the notice blocks live access.
Encrypted Windows credentials are optional; environment values take precedence.
