# Architecture

main.py receives an explicit submission ID, loads approved single-community
configuration, verifies the selected source and queues the operator's reply.
review handles display and human review. Editing invalidates approval.
policy gates all live access and posting. reddit_client builds the PRAW client
using injected environment credentials.

lifecycle revalidates sources before display and publication. store reserves
publication under a SQLite write lock, checks retained duplicate/similar comments,
increments the UTC daily attempt counter, and marks the draft uncertain BEFORE
the network call. Success records the permalink and posted status. Network
failures cannot trigger automatic retries or reapproval of uncertain drafts.

store also migrates legacy schemas, removes non-human drafts/karma data, clears
authors and enforces retention. Daily counters have no source or author identifiers.
main maintenance runs local cleanup hourly. It is not a deletion-event listener,
does not call Reddit, and is not installed as a persistent OS service.

The database is local and unencrypted. Backups, other machines and provider-side
published content lie outside this application's local cleanup and limits.
