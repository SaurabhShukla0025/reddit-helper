# Commands

`python main.py <command>`; add `--verbose` for operational log output.

| Command | Behavior |
|---|---|
| `fetch` | Approved API access: read eligible public posts |
| `match [--all]` | Fetch live, filter by relevance; optionally explain exclusions |
| `draft [--limit N]` | Approved external processing; hard cap counts declines/errors too |
| `drafts` | Verify existing sources before displaying pending content |
| `review` | Verify sources, then approve/reject/edit/skip/quit; disclosure is preserved |
| `post --dry-run` | Offline count only, no unverified source content or posting |
| `post [--limit N]` | Permission, identity and source checks; human confirmation; recheck on each submit/retry |
| `karma` | Read and record scores for retained, verified published contributions |
| `cleanup` | Enforce local retention without API access |
| `cleanup --sync` | With approved API access, remove stale/changed/unavailable sources |
| `cleanup --post-id ID` | Delete one post's local metadata, draft and score history |
| `cleanup --all` | Delete all queue data when stopping or handling revocation |

`post --yes` and `post -y` are rejected. Local cleanup does not remove published
Reddit comments, external provider data, logs, or backups. Manage those separately.
Queued content commands may now require live verification and credentials even
though they do not publish anything. Empty queues and local cleanup stay offline.
