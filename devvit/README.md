# Contribution Helper

A personal, non-commercial contribution assistant for u/saurabhimapro.
Intended production community: r/learnpython, subject to its moderators' permission
and Reddit's review. The app is disabled by default.

## What a Redditor sees

1. Open a permitted post's menu and choose **Write a reply with Contribution Helper**.
2. Write your own reply and choose **Review reply**.
3. Read the exact reply, select **Publish this one reply**, and check the explicit
   confirmation box. Choose Continue to publish.
4. Edit, discard or cancel instead at any point.

A comment is published from the Reddit-managed **app account**, as the confirmation
form states. It never posts as the operator's personal account. Only the configured
operator saurabhimapro may write or publish; there is no background publishing.
One pending draft is stored at a time. Selecting another post replaces that pending
draft. A source must remain public, available, unchanged, unlocked and unarchived.

This is a community utility, not a moderation tool. It requests ordinary Reddit
scope and Redis storage. Its code makes no moderation, external HTTP, AI,
voting, message, advertising, karma-tracking or discovery calls. Reddit's installer
nonetheless lists broad Reddit/moderator capabilities for the SDK; this platform
permission surface must be assessed during review. The app does not expose those
moderation capabilities through any route.

## Development

Requires Node 24.18+:

```powershell
cd devvit
npm.cmd ci --ignore-scripts
npm.cmd run check
```

This runs TypeScript checks, offline safety tests and a production build.
The app uses official Devvit Web 0.14.8 with native Reddit menu/forms and Hono.
No website host or Python credentials are needed.

## Registration and permitted playtesting

1. Sign into the developer portal as saurabhimapro and register an app.
2. The wizard selected the app slug user-helper. Our devvit.json and package
   metadata now match it. Complete CLI authentication/initialization locally.
3. Publish the completed [privacy notice](PRIVACY.md) at an HTTPS URL and provide a
   real deletion contact. The operator supplied saurabhimapro@gmail.com;
   the operator supplied this public notice link:
   https://www.reddit.com/r/saurabhhelpertest/s/L7mpUwJldM.
   Its public readability must be confirmed in a signed-out browser.
4. Coordinate the actual community permission and use a permitted private
   development process/test community. Do not playtest in r/learnpython without
   the required permission. Playtest community must be public and eligible.
5. Run npm.cmd run login in your own terminal, then npm.cmd run dev -- YOUR_TEST_SUBREDDIT.
   This uploads and installs to Reddit and requires your authorization/account.
6. Set the installation's approved-community to that ONE test community, record the
   actual permitted-development and community references, privacy URL/contact,
   and rules-review date. Select playtest only for a permitted owner playtest.

Settings are records of permissions, not a grant of permission. The app never
enables itself. Publishing is available only to the configured operator and only
within the configured installation scope. Platform review and deployment controls
remain Reddit's responsibility.

For production, use the reviewed installation, restore the intended community to
learnpython, obtain actual permission, refresh the rules-review date, and record
the corresponding permission reference. The mode approved is an operator
attestation, not cryptographic verification of Reddit's approval.

## Submit for Reddit review

Before submission: finish public privacy/contact details, app registration, source
documentation, community permissions and permitted on-Reddit web/mobile testing.
Keep this app unlisted for its single-community use case unless Reddit instructs otherwise.

```powershell
npm.cmd run check
npm.cmd run publish
```

The publish script invokes the official CLI to submit this Devvit app for review.
It must be run by the operator after completing the prerequisites. The operator has initialized user-helper and installed its owner playtest in
r/saurabhhelpertest. Production review has not been submitted or granted.
A Devvit decision does not grant API access to the separate Python CLI.

## Safeguards and retention

Drafts expire after one hour. Minimal attempted/posted reply history expires within
seven days; the entire small history may expire earlier to avoid extending older
records. Expirations are enforced by Reddit-hosted Redis without a local scheduler.
UTC daily counters contain only a date and attempt count and expire after two days.
The installation has a hard cap of three publication attempts per UTC day, including
uncertain outcomes. Concurrent confirmations are protected by Redis WATCH/MULTI/EXEC.
After an ambiguous failure, check Reddit; the app does not retry automatically.

Duplicate and highly similar replies are blocked within retained history. These
are heuristics, not a spam guarantee. A small gap between source verification and
Reddit's submission remains unavoidable; Reddit also enforces posting restrictions.

Deletion/edit events purge the affected source's local draft/history. Sources are
also rechecked before review and immediately before publishing. Trigger delivery
and Devvit event behavior still require permitted on-platform validation.

Post menu: Delete my local reply data. Community menu: Delete all my local reply data.
Deletion remains available when posting is disabled. It never deletes live comments
or resets the daily counter. Deleting history also removes its duplicate-detection
records; daily limits and human review still apply. Handle support requests through
the configured public deletion contact.

## Validation and limitations

Local checks cover permissions, identity/scope, explicit confirmation, old tokens,
exact text, source changes, concurrency, uncertain outcomes, duplicates, retention,
deletion and Redis transaction failure. On-platform rendering, trigger delivery,
registration, labeling and live Reddit publication have not been tested.

npm audit --omit=dev reported zero advisories for runtime dependencies at build time.
The official Devvit CLI's development dependency tree reports unresolved advisories;
compatible npm audit fix did not remove them. Do not apply npm audit fix --force:
it proposes an incompatible CLI replacement. Track upstream updates and avoid
feeding untrusted files/configuration into development tools. The CLI is not part
of this app's runtime dependency declaration.


## Owner playtest configuration

All operating fields now use installation/community settings, because the portal's
global-settings value endpoint did not preserve the playtest values reliably.
Runtime reads only the installation's settings through the pinned official SDK
settings plugin; legacy app-wide settings cannot override community permissions.
Missing installation values keep the workflow disabled. Owner setup errors show
the running app version and mode to distinguish stale playtest sessions.
The single-choice mode is normalized from Reddit's native selection-array format.
The operator confirmed rules review on 2026-10-14 and public readability of the
privacy notice. The narrow helper scripts/configure-owner-playtest.mjs checks
registered owner/app and the exact existing saurabhhelpertest installation,
keeps the workflow disabled while saving prerequisites, enables playtest last,
and reads the settings back. It cannot request production approval or publish comments.


Installer observation: the 0.0.2 installation lists broad Reddit access and
moderator capabilities despite the manifest's user scope. These are host-granted
SDK capabilities, not evidence of production approval. Application code remains
restricted to the single configured community and operator and makes no moderation
calls. Do not describe platform permissions as narrower than the installer shows.
