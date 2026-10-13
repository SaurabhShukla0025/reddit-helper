# Configuration and permission records

`config.yaml` is a local, git-ignored file. All permission fields default to
empty/false. Setting them is a record of real authorization, not a bypass to
obtain authorization. Do not enable a feature outside the approved scope.

## Required policy records

| Setting | Meaning |
|---|---|
| `api_approval_reference` | Reddit approval/ticket covering the actual API use case |
| `app_registration_reference` | App/developer registration and required profile labeling |
| `dedicated_app_username` | Dedicated app account; must match credentials and live identity |
| `privacy_policy_reviewed` | Operator has customized and published/made available the notice as applicable |
| `data_security_reviewed` | Appropriate storage encryption/access controls and credential protection established |
| `deletion_contact` | Accessible real channel for requests, also included in the privacy notice |
| `external_ai_approval_reference` | Explicit authorization for sending Reddit text to the selected third-party AI service |
| `provider_data_use_reviewed` | Provider processing/retention/training conditions reviewed and permitted |
| `retention_days` | Local maximum age, 1-30 days; choose a shorter period if approval requires it |

Boolean values must be YAML `true`/`false`, not strings. API commands require the
first six records. Drafting and posting additionally require both external-AI
records. The operator must stop and clear permissions if approval is revoked.

## Community records

Each subreddit requires `access_reference` (permitted scope) and
`rules_reviewed_on` (YYYY-MM-DD, no future dates, no more than 30 days old).
Drafting/posting also require `comments_reference` (rules or moderator permission
covering the workflow) and `ai_comments_allowed: true`. Recheck rules whenever
they change; the 30-day guard is an additional local control, not Reddit's
mandated review interval. Example community names are not endorsements.

## Other settings

- `reddit`: client ID/secret, dedicated username/password, honest User-Agent.
- `fetch`: `new`, `rising`, or `hot`, and per-community limit.
- `gemini`: model, temperature (0-2), output token limit, hard request cap.
- `post`: load-control delay range and hard per-run post cap. `--limit` may lower
  either cap but cannot increase it. No noninteractive confirmation bypass.
- `match`: case-insensitive title/body keywords and exclusions, optional score,
  comment-count and age limits. Per-community settings inherit global fields.
  These filters are for relevance, not automatic maximization of karma.
- `guidelines`: verified community rules and useful-response guidance. Prompts
  cannot guarantee compliance, correctness, or moderator acceptance.

The Gemini model value is configurable; this change does not verify provider
model availability or pricing. The program refuses private, quarantined, NSFW,
deleted, and removed sources as an intentionally narrower supported scope.
