# Privacy notice — complete before live use

Operator: u/saurabhimapro (public developer/operator identity)
Deletion contact: saurabhimapro@gmail.com
Intended purpose: personal, non-commercial, human-written contributions
Intended community: r/learnpython
Approved scope/permission: [REQUIRED: actual Reddit approval and community permission]
Retention period and storage protections: [REQUIRED]

This template is not a compliance certification. Keep privacy_policy_reviewed
false until these details and your actual operating practices are documented.

The operator manually chooses one submission. The app reads its ID, title, body,
availability and community through the approved Reddit API. The source author is
checked for deletion/availability but is not stored or displayed by this app.
It does not collect score histories, discover users, infer sensitive traits,
train models or send content to an external AI service.

SQLite stores source ID, title, community, URL, source hash, the human-written
reply, review status, timestamps and the published comment URL. Compatibility
columns retain an empty author and a human authorship marker. Daily publishing
counters contain only UTC dates and attempt counts. Reddit receives the published
reply. There are no advertising, private-message or voting features.

Queue retention defaults to seven days and can be configured from one to thirty
days according to authorization. It is measured from creation, not last edit.
Queue access and the running maintenance process prune expired records.
The process checks hourly; it does not run while stopped. An installed Windows
task can also run hourly and at logon while its owning user is signed in, with
catch-up enabled. Source deletion
synchronization requires a separately initiated approved API call (cleanup --sync).
Daily counters older than yesterday are deleted during cleanup.

Cleanup removes local records and legacy app logs. New operational logs go only
to the console. Terminal transcripts, backups, filesystem snapshots, editor
temporary-file remnants and human-created reply files require separate operator
handling. Generated drafts and score history from older versions are removed
on database migration. Published Reddit comments require separate management.

Use restricted filesystem access and OS/disk encryption: this program does not
encrypt its database. Credentials may be stored using current-user Windows DPAPI encryption or injected
through environment variables. The encrypted credential file does not encrypt the
queue, backups or operator-created reply files. Avoid persistent plaintext secrets.
SQLite secure deletion is enabled but is not a guarantee of forensic erasure.

Handle deletion requests promptly with cleanup --post-id ID. On authorization
revocation, stop live use and run cleanup --all; remove backups and other retained
copies. Approval attestations are not proof of authorization.
