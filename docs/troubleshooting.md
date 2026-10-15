# Troubleshooting

Live access blocked: record only real authorization covering this app and community.
Configuration flags do not grant access. Check registration, dedicated identity,
purpose, privacy/security review, community references and expiry.

Legacy configuration: replace it using config.example.yaml and move secrets out
of config. Local cleanup requires no credentials and works with legacy retention
settings. Legacy AI drafts are removed during migration.

Source verification failed: wait until verification succeeds. Deleted, changed
or protected sources remove the local draft; write and review a fresh reply only
if the source is still eligible.

Daily limit reached: wait for the next UTC day. Do not delete the database or use
other accounts to bypass it.

Uncertain submission: check the app account's comments on Reddit. Do not blindly
retry; the draft cannot be approved or posted again through this CLI.

Maintenance stopped: restart python main.py maintenance, or configure your OS
scheduler to run python main.py cleanup hourly. The Windows installer provides a
project-specific task; check its current enabled state and LastTaskResult. This
workspace has a verified task installed, but it requires the owning user to be signed in.

Privacy notice: complete the operator identity, actual deletion contact, approved
purpose/community, retention and storage practices before live use.
