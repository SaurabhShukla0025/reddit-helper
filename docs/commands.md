# Commands

| Command | Behavior |
|---|---|
| setup --username NAME --community NAME | Initialize public details without fabricating permissions |
| readiness | Report missing local evidence without loading credentials or calling Reddit |
| privacy-review | Review the completed notice and record its hash |
| credentials set | Hidden local input saved with current-user Windows encryption |
| credentials clear | Remove encrypted local credentials; environment values remain |
| draft ID --text-file FILE | Verify selected source and queue your human-written reply |
| draft ID | Open the editor to write a reply |
| review ID | Verify source, show text and approve, reject or edit |
| post ID | Verify source, require approval and confirm exactly one publication |
| post ID --dry-run | Offline existence/status check; content remains hidden |
| cleanup | Prune local retention and remove legacy app logs |
| cleanup --sync | Also verify queued sources through the authorized API |
| cleanup --post-id ID | Delete one source's local data |
| cleanup --all | Delete all queue content; retain today's attempt counter |
| maintenance | Repeat local cleanup hourly until stopped |

Use plain submission IDs without t3_ or URLs. There is no fetch, match, karma,
batch limit, Gemini drafting or --yes command. Optional -v precedes the command.

Maintenance needs no API credentials and makes no network requests. It must remain
running, or be replaced by the Windows task installer or another OS schedule. Cleanup never
deletes published Reddit comments or user-created reply files/backups.
