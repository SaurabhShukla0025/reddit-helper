# Devvit assessment — 2026-10-14

Developer/operator: u/saurabhimapro.
Intended use: personal, non-commercial, human-written contributions in r/learnpython.
This is not a moderation tool. Moderator-only access must not be requested for it.

## Findings

The current workflow selects one submission, displays its content, accepts a
human-written reply, shows a review step, and explicitly publishes one comment.
Reddit documents getPostById and submitComment in its
[Devvit Reddit API](https://developers.reddit.com/docs/capabilities/server/reddit-api).
It also documents user input and chained review steps through
[forms](https://developers.reddit.com/docs/capabilities/client/forms).
Devvit handles app API authentication.

Inference: these documented primitives appear sufficient for the core workflow.
No substantiated unsupported Devvit capability has been identified. Local Python
implementation preference is not evidence of a platform limitation.

## Decision

The recommended production route is a Devvit implementation with app review and
permission/installation in the intended community. The existing Python CLI remains
a local reference implementation; it must not use live APIs unless Reddit explicitly
permits this external architecture.

The [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
directs developers to Devvit and provides an external request route for unsupported
use cases. Do not claim that Devvit cannot support this app or use moderator-only
authorization for ordinary contributions.

## Remaining platform work

A Devvit Web port has now been created in devvit/ and builds locally. It has not
been uploaded, installed, approved, or tested in r/learnpython. Before deploying,
confirm registration, deletion contact, community agreement and exact
distribution/identity requirements with Reddit.
Preserve source checks, explicit single-comment consent, duplicate safeguards,
small persistent limits, short retention and deletion support in the port.
Review the [launch guidance](https://developers.reddit.com/docs/guides/launch/launch-guide)
and test on web/mobile before requesting review.

External API access should be requested only if a real unsupported requirement
is discovered or Reddit expressly permits the external CLI. Record that permission
in external_api_exception_reference; a local assessment alone is not an exception.
