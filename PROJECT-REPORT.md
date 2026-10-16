# Project Report — Reddit Contribution Helper

**Prepared for:** Technical Reviewer
**Prepared by:** Project owner (u/saurabhimapro, imaPRO) with AI pair-programming assistance
**Date:** 2026-10-16
**Repository:** https://github.com/SaurabhShukla0025/reddit-helper
**Status:** Two working implementations delivered; original automation goal determined **not viable** within platform rules.

---

## 1. Executive Summary

This project began as an **AI-assisted Reddit commenting system** intended to find relevant
posts, generate helpful comments, and publish them across multiple communities. During
development, Reddit's platform rules (tightened significantly in late 2025 / 2026) made the
original goal — **automated commenting across public communities the operator does not
moderate** — **impossible to build legitimately**, and Reddit **rejected** the API access
request for it.

The project was therefore **re-engineered twice**:

1. From an automated, AI-driven, multi-community pipeline → into a **compliant, single-community,
   human-written, approve-first assistant** (Python CLI).
2. Then **ported to Devvit** (Reddit's officially supported in-platform app framework) as a
   TypeScript app that runs inside a community the operator moderates.

Both implementations are **built, tested, and working**. The report below documents what was
built, every approach the owner attempted, and a clear feasibility verdict.

> ### ⚠️ Headline Finding
> **The originally intended system is NOT BUILDABLE.** Automated commenting across public
> communities the operator does not moderate — the core goal — cannot be built on *any*
> platform or with *any* tool within Reddit's rules. This was confirmed through extensive
> hands-on attempts and deep research (Section 3), not assumed. Every official path is closed
> to this use case, and every unofficial path is a Terms-of-Service violation that is actively
> detected and penalized by Reddit's 2026 enforcement systems.

**Bottom line:** The *legitimate* system is complete and functional. The *originally intended*
system (automated cross-community commenting for karma/growth) is **not buildable** on any
platform within Reddit's rules, and attempts to do so via unofficial means are non-viable due
to Terms-of-Service violations and active bot detection. This conclusion was reached only
**after** the owner exhausted the full range of available approaches.

---

## 2. Original Objective

Build a tool that would:

- Monitor a list of chosen subreddits for relevant posts.
- Use an LLM to draft context-aware, per-community comments from custom instructions.
- Publish those comments (semi- or fully-automatically), paced to avoid rate limits.
- Track resulting karma/engagement.

**Underlying business goal:** grow visibility/credibility for imaPRO.in on Reddit.

---

## 3. Owner's Efforts & Approaches Attempted (Engineering & Research Journey)

This project was **not abandoned at the first obstacle.** The owner pursued the goal
persistently and methodically, exhausting **every realistic avenue** — official, supported,
and unofficial — before concluding it is not buildable. This section documents that effort in
detail, because the thoroughness of the investigation is what makes the final verdict credible.

### 3.1 Effort summary

- **~6 development iterations** across two complete, separately-architected implementations.
- **Multiple Reddit API access attempts** (initial application + resubmission) with careful,
  policy-aware application wording.
- **A full second implementation** built from scratch on a different platform (Devvit/TypeScript)
  and **deployed + tested live**.
- **Every alternative channel investigated** — no-code (Zapier/Make), browser automation,
  computer-use agents, third-party tools, and "loophole"/grey-area methods.
- **Deep, repeated web research** into 2026 Reddit policy, enforcement, and bot detection.

### 3.2 Approaches, in order

| # | Approach (owner effort) | Outcome |
|---|----------|---------|
| 1 | **Built the full pipeline** (fetch → match → draft → review → post → karma) in Python, dependency-injected for fully offline tests | ✅ Built and tested (original design) |
| 2 | **Swapped the LLM engine Claude → Gemini** (free tier) to control cost, contained cleanly to the drafter | ✅ Implemented and verified working end-to-end |
| 3 | **Registered a Reddit API app and requested access**, with the use case described carefully to fit policy | ❌ **Rejected** by Reddit (Responsible Builder Policy; "not in compliance / lacks detail") |
| 4 | **Resubmitted** a narrower, read-only-leaning application | ❌ Low odds; self-service API access was closed (Nov 2025) |
| 5 | **Re-engineered the entire project for compliance** — removed AI, removed multi-community support, removed auto-posting; added a fail-closed policy/attestation layer | ✅ Completed (single-community, human-written, approve-first) |
| 6 | **Evaluated and then fully built a Devvit app** (Reddit's officially supported in-platform framework), porting the approve-first flow to TypeScript | ✅ Built; viable **only** for communities the operator moderates |
| 7 | **Deployed and playtested the Devvit app** in an owner-moderated test subreddit (r/saurabhhelpertest), including diagnosing and clearing its fail-closed settings gate | ✅ End-to-end comment publish **confirmed working** |
| 8 | **Investigated no-code automation** (Zapier / Make / Pipedream) for posting | ❌ Runs on the same gated API + cannot do the cross-community use case |
| 9 | **Investigated browser automation & AI computer-use agents** (e.g. Simular-style) for cross-community auto-posting | ❌ **Non-viable**: violates the User Agreement, bannable, defeated by 2026 bot detection |
| 10 | **Investigated grey-area / "loophole" methods and alternative AI tools/models** without platform limits | ❌ **Non-viable**: all rely on ToS circumvention; actively detected and penalized |
| 11 | **Conducted deep web research** on 2026 Reddit policy, Devvit mechanics, bot detection, and vendor "auto-comment" guides to validate the conclusion | ✅ Independently confirmed the feasibility verdict (Section 6) |

**Interpretation:** Items 1–7 represent substantial, successful engineering. Items 3–4 and 8–11
represent diligent exploration of *every* path to the original goal — each of which was ruled
out on solid, evidence-based grounds rather than given up on.

---

## 4. What Was Built (Deliverables)

### 4.1 Implementation A — Python CLI (`/`, `src/`)
A local, single-community, **human-written**, approve-first comment assistant.

- **Flow:** operator selects a post by ID → writes the reply themselves → reviews → explicitly
  confirms → one comment is published via PRAW.
- **No AI drafting** (removed for compliance). **Exactly one** approved community enforced.
- **Fail-closed compliance layer** (`policy.py`, `readiness.py`): blocks all live access until
  ~18 real authorization attestations are recorded.
- **Source re-verification** (`lifecycle.py`): the source post is re-checked before display and
  again before each submission; changed/removed/locked/out-of-scope posts are purged.
- **Secrets** read from environment variables / Windows DPAPI — never stored in the repo.
- **Local SQLite** queue with retention + secure delete (`store.py`).

### 4.2 Implementation B — Devvit App (`devvit/`)
A TypeScript app running **inside** Reddit via Devvit, delivering the same approve-first flow
for a community the operator **moderates**.

- **UI:** a post menu action ("Write a reply…") → write form → review form → explicit confirm.
- **Core logic** (`workflow.ts`): operator/community guards, source eligibility + hashing,
  duplicate/similar-text blocking, per-post lock, daily attempt limit, atomic Redis writes.
- **Fail-closed settings gate:** disabled until operation mode + permitted-use + community-scope
  references are recorded (verified during this project by the "disabled" guard behaving exactly
  as designed, then clearing once configured).
- **Deployed and playtested**: a real comment was published end-to-end as the app account.

### 4.3 Documentation & Supporting Material
- `README.md`, `REPORT.md`, `PRIVACY.md`, and `docs/` (getting-started, commands, configuration,
  architecture, operations, troubleshooting, approval-preparation, devvit-assessment).
- GitHub Actions CI; helper PowerShell scripts for local data protection and cleanup.

---

## 5. Technology & Quality

| Area | Detail |
|------|--------|
| **Languages** | Python 3.10+ (CLI), TypeScript (Devvit) |
| **Key libraries** | PRAW (Reddit), PyYAML, SQLite (stdlib); Devvit Web, Hono, Redis |
| **Architecture** | Dependency injection of all side effects → fully offline, deterministic tests |
| **Tests** | ~50 Python tests + ~29 Devvit test cases, all offline (no network/cost) |
| **Tooling/CI** | ruff (lint), mypy (types), pytest; GitHub Actions on Python 3.10 & 3.12 |
| **Security** | Secrets via env/DPAPI/Devvit secrets; no credentials committed; secure-delete retention |
| **Design principles** | Fail-closed, re-verify-before-act, human-in-the-loop, hard rate/duplicate limits |

**Engineering note for reviewer:** the dependency-injection design is the project's main
strength — it allowed a clean LLM swap (Claude→Gemini), a clean removal of the AI layer, and a
full platform port (Python→Devvit) while keeping the test suite intact.

---

## 6. Feasibility Analysis — Is the Original System Possible?

The central question: **can an automated system post comments across public communities the
operator does not moderate (e.g., for karma/growth)?**

> ## 🚫 VERDICT: NOT BUILDABLE
> **No — this system cannot be built on any platform, with any tool or AI model, within
> Reddit's rules.** This is a definitive conclusion reached after exhausting every approach
> in Section 3. It is a *platform policy* constraint, not a coding difficulty — so no amount
> of engineering effort, tooling, or prompting changes it. The only working systems are the
> *scoped, legitimate* variants in the table below.

| Method | Achieves the original goal? | Why |
|--------|------------------------------|-----|
| Official Reddit API | ❌ | Self-service access closed (Nov 2025); request rejected; policy forbids this use |
| Devvit | ❌ | Apps run only in communities whose **moderators install them** — not arbitrary public subs |
| Browser automation / computer-use agents | ❌ | Violates User Agreement ("automated access without permission"); bannable |
| Unofficial APIs / scrapers / bought accounts | ❌ | ToS violations; actively detected and removed |
| **AI drafts → human posts manually** | ✅ *(partial)* | Legitimate in any community, because a human performs the final post |
| **Automated bot in an owned community** | ✅ *(scoped)* | Legitimate via Devvit/approved API — limited to communities you moderate |
| **Open platforms (Lemmy, Stack Exchange)** | ✅ *(different platform)* | Open APIs that permit automated helpful contribution |

### Why it is not merely a technical limitation
Reddit tightened enforcement specifically against this pattern in 2026:
- **Nov 2025:** self-service Data API access closed; approval now required; Devvit pushed as the path.
- **Mar 2026:** automated accounts are **labeled**; suspected bots must pass **human verification**;
  content from unregistered automation is excluded/removed under **Rule 8**.
- **Detection:** platform fingerprinting + moderator vigilance + third-party AI-comment detectors.

The code was never the hard part; operating undetected against a platform actively enforcing
against this is not achievable, and doing so would be a ToS violation regardless.

### On "karma" as the objective
Karma does not convert to revenue, leads, or customers. Karma farmed on flagged/banned accounts
is a liability to the imaPRO brand, not an asset — so even a hypothetical working version would
not serve the underlying business goal.

---

## 7. Current Status

- ✅ Python CLI: complete, tested, committed.
- ✅ Devvit app: complete, tested, deployed to a playtest install, comment published successfully.
- ✅ Repository: reshape + Devvit app committed (`e2df6d4`) and pushed; no secrets committed.
- ⏸️ Reddit API approval: rejected; not a viable path for the original use case.
- 🔀 Original cross-community automated goal: **closed as not viable** (Section 6).

---

## 8. Risks & Limitations

- **Platform dependency:** both implementations depend on Reddit's evolving policy; the Devvit
  app is usable only where the operator is a moderator.
- **Single operator / single community** by design (compliance), which limits reach.
- **No AI drafting** in the shipped versions (removed to reduce approval risk).
- **Approval uncertainty:** even the compliant CLI requires real Reddit authorization to operate
  live, which is not guaranteed.

---

## 9. Recommendations / Next Steps

1. **Adopt the legitimate workflow for growth:** "AI drafts → human reviews → human posts" — gives
   speed and per-community tailoring across any subreddit, without ToS risk. *(Recommended.)*
2. **Run the Devvit app in owned communities** for genuine in-community automation.
3. **Consider open platforms** (Lemmy / Stack Exchange) if full automation is a hard requirement.
4. **Position the project as a portfolio piece:** the Claude→Gemini swap, the compliance
   re-engineering, and the Python→Devvit port form a strong narrative of adapting a design to
   real-world platform constraints.
5. **Do not pursue** unofficial/grey-area automation — it is non-viable and brand-damaging.

---

## 10. Conclusion

The project successfully produced **two working, well-tested implementations** of a responsible
Reddit contribution assistant and a thorough, evidence-based assessment of what is and is not
possible on the platform. The **original automated cross-community commenting goal is not
achievable** within Reddit's rules by any method. The engineering work — particularly the
dependency-injected architecture, the fail-closed compliance layer, and the clean platform port —
demonstrates sound design and the ability to re-scope a product responsibly when external
constraints require it.

---

## Appendix A — Repository Structure (abridged)

```
reddit-helper/
├─ main.py                      # Python CLI entry (argparse)
├─ src/                         # config, policy, readiness, credentials, lifecycle,
│                               # store, review, poster, reddit_client, applog
├─ tests/                       # offline test suite (~50 tests)
├─ devvit/                      # Devvit app (TypeScript)
│  ├─ devvit.json               # manifest: menu, forms, settings, permissions, triggers
│  ├─ src/                      # index.ts, workflow.ts, configuration.ts, redis-store.ts (+tests)
│  └─ scripts/                  # owner playtest configuration helper
├─ docs/                        # setup, commands, architecture, operations, approval prep
├─ README.md / REPORT.md / PRIVACY.md / PROJECT-REPORT.md
└─ .github/workflows/ci.yml     # ruff + mypy + pytest
```

## Appendix B — Git History

```
e2df6d4  Reshape to single-community human-written assistant; add Devvit app
11d0d37  Polish: argparse CLI, ruff + mypy in CI, default to gemini-flash-latest
a7dee1b  Add responsible-use compliance layer (policy, lifecycle, privacy)
08446f6  Switch draft engine from Claude to Gemini; add docs/ folder
c7d456a  Add GitHub Actions CI to run tests on push and PR
e2320b5  Initial commit: Reddit Helper (approve-first draft-and-post assistant)
```

## Appendix C — Key References

- Reddit Responsible Builder Policy (support.reddithelp.com)
- r/redditdev — Responsible Builder Policy announcement (Nov 11, 2025)
- TechCrunch — Reddit human-verification requirements for bots (Mar 2026)
- Devvit documentation — app accounts, `submitComment` (`runAs: 'APP'`), triggers/scheduler
- Reddit User Agreement — automated access provisions
