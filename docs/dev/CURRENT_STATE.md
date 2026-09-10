# Current Development State

Updated: 2026-09-10

## 1. Current state

- Branch: `2026_09_04`
- Implementation HEAD at handoff authoring: `78b0fafbd500ab00d42376a6fb92024504040646`
- Commit: `feat: add grounded multi-turn teacher assistant`
- Upstream: `origin/2026_09_04`
- Ahead/behind at the Step 8C3 checkpoint: ahead 17, behind 0
- Working tree immediately after the Step 8C3 commit: clean
- Push: not performed; all local checkpoints remain unpushed
- Production deployment: not performed by this checkpoint; repository state alone cannot verify external production state

Do not push until the user explicitly requests it.

Do not deploy to production until the user gives the exact approval: `운영 배포 진행`.

## 2. Product Contract

The Growth vNext Product Contract is:

`docs/growth_vnext/PRODUCT_CONTRACT_v0.2.md`

Read it before changing Growth, Reading AI, assistant grounding, canonical metrics, evidence, or report behavior. Contract statements override implementation convenience.

## 3. Completed checkpoints

These are the current post-rebase SHAs from `git log`:

- Step 1: `d270e7804d0e9c4ef3604c2da626db20d5855cdf` — `feat: add Growth vNext study domain foundation`
- Step 2: `c1912c10ce7937df535c94824a4276dce80201fe` — `feat: complete Growth vNext study input workflow`
- Step 3: `83ee8961711331130ea8e793da88225d54f42117` — `feat: complete Growth vNext study schedule and performance`
- Step 4: `de985702d723f6ac1b12806d059628a456616746` — `feat: add observed learning progress and completion forecast`
- Step 5: `c86deccee083cc965ff43b86bed2cdf3643dbc22` — `feat: add same-center peer comparisons`
- Step 6: `d422820f0116e1baab3ccc8a68b1122cc4adc51c` — `feat: add reading analysis and dedicated AI`
- Step 7: `3a5cf699d7746ee72461d727f7fa9757608a55a4` — `feat: connect canonical Growth evidence to overall AI`
- Step 8A: `2dee62ae161ec7d6a180751fa8e1a71b18392722` — `refactor: align Growth UI with canonical semantics`
- Step 8B: `ad3a3524ab8f40a585ced10b230d3951a60ca358` — `feat: redesign Growth report experience`
- Step 8C1: `96ef1e9fe88e75ce03af179d77271e1df93a409d` — `feat: add Growth entry points and center setup hub`
- Reading layout fix: `fa18c6d10bedd8196534a89b5f3a8c2f8231b0a2` — `fix: improve reading analysis stat layout`
- Step 8C2: `b052813b86db229329a4b2ba8240bbb8d800045a` — `feat: add global teacher assistant shell`
- Step 8C3: `78b0fafbd500ab00d42376a6fb92024504040646` — `feat: add grounded multi-turn teacher assistant`

Ancillary QA infrastructure commits remain in history but are not substituted for the functional checkpoint SHAs above.

## 4. Critical invariants

- Missing or unavailable data is not zero.
- Do not impute missing dates or pages.
- Attendance is not learning performance.
- `verified` means direct physical verification by a teacher.
- Do not hardcode subject or point rules that belong to configured/canonical data.
- Do not produce rank, percentile, TOP/BOTTOM, leaderboards, or ability/personality superiority claims.
- Peer references use canonical median and sample-size semantics.
- Do not remove statistical outliers unless the record is objectively invalid.
- Do not assume adjacent pages, interpolation, or continuous progress between observations.
- Raw Reading text is available only to Reading-specific AI boundaries.
- Global assistant and Overall Growth AI must not receive raw Reading text.
- AI failure must leave deterministic facts available.
- No hidden LLM retry.
- Growth AI and Reading AI generation require explicit user action.
- The LLM must not recalculate canonical metrics.
- Assistant v1 is READ + NAVIGATE only.
- There are no assistant WRITE tools.
- Disabling or failing the assistant must not break the main application.

## 5. Assistant architecture

### Browser

- Global drawer: `templates/assistant/`, `static/js/assistant.js`, `static/css/assistant.css`
- Browser conversation uses `sessionStorage`.
- Stored state is bound to a server-generated account/session scope; cookies or tokens are not exposed to JavaScript.
- Scope mismatch, including an empty legacy scope, discards stored assistant state.
- One conversation segment allows 10 free natural-language requests.
- Quick actions, guided deterministic steps, navigation, child-slot completion, and fuzzy confirmation do not consume the question limit.
- AI-generated responses can carry request-linked positive/negative feedback.

### LLM working context

- At most the latest 12 conversational user/assistant messages are sent.
- Structured state carries authoritative page context plus active child, subject, topic, and pending action.
- Deterministic onboarding, quick actions, confirmation, and navigation events are excluded from the 12-message budget.
- Browser transcript, bounded LLM context, and server audit history are separate structures.

### Runtime

- Free text is OpenAI-first; pending state is advisory and does not preempt general/help/new/safety requests.
- Explicit quick actions remain deterministic.
- The deterministic free-text exception is a simple fuzzy candidate confirmation/rejection.
- Exact, normalized exact, unique partial, ambiguous partial, and fuzzy nickname handling are implemented separately.
- Tool execution is capped at `MAX_TOOL_ROUNDS = 5` per user request.
- Every tool call in every round independently passes the Policy Gate.
- The next user request starts a new tool-round budget without clearing conversation state.

### Tools and evidence

- Tools expose canonical READ data, allowlisted NAVIGATE destinations, and teacher-help RAG only.
- No WRITE, generic ORM, free SQL, arbitrary URL, raw Reading, or AI-generation tool exists.
- Evidence chips distinguish canonical `data` sources from `help` sources.

### Safety

- Input/output harnesses cover prompt injection, internal/system disclosure, raw Reading, ranking, unavailable-as-zero claims, and unsupported capabilities.
- Tool registration, schema, role/resource permissions, destination permission, and forbidden capability checks are enforced server-side.
- Provider failure returns a bounded assistant error without breaking the main page.

### Audit

- `features/assistant/audit.py` writes append-only JSONL request, tool/Policy Gate, result/navigation/RAG, final response, latency, and feedback events.
- Audit records safe arguments and conversational state summaries under a request ID.
- It excludes API keys, cookies/tokens, system/developer prompts, hidden instructions, raw Reading content/AI input, raw OpenAI payloads, ORM/DB dumps, secret environment values, and sensitive exception stacks.

## 6. Assistant audit note

The append-only JSONL audit is sufficient for v1 observability and Step 8C3 acceptance. Do not assume it satisfies permanent production audit-retention requirements.

At the Step 9 release gate, review:

- Runtime filesystem persistence
- Rotation
- Retention
- File/directory access permissions
- Whether a database or external log sink is required

This is not a current Step 8C3 acceptance blocker.

## 7. Feature flags and commands

Environment variable names used by the assistant:

- `TEACHER_ASSISTANT_ENABLED`
- `TEACHER_ASSISTANT_PROVIDER`
- `TEACHER_ASSISTANT_MODEL`
- `TEACHER_ASSISTANT_LIVE`
- `TEACHER_ASSISTANT_AUDIT_PATH`
- `OPENAI_API_KEY` — secret value must never be printed or documented
- `GROWTH_AI_MODEL` — current provider fallback when the assistant-specific model is unset

Repository commands:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_assistant tests.test_assistant_tools tests.test_assistant_orchestration
.\scripts\qa.ps1 preview
.\scripts\qa.ps1 assistant
$env:TEACHER_ASSISTANT_LIVE='1'
$env:TEACHER_ASSISTANT_PROVIDER='openai'
$env:TEACHER_ASSISTANT_ENABLED='true'
.\venv\Scripts\python.exe scripts\qa\smoke_assistant_live.py
```

Do not place secret values in commands, logs, screenshots, or this document.

## 8. Known unresolved: REPORT-001 / REPORT-002

These remain Step 9 Contract Gate work.

### REPORT-001

- Historical report snapshot immutability is not yet fully guaranteed.
- Deterministic Growth GET paths can recalculate against live data.
- Peer or other-child changes can alter the current target packet/hash.
- A historical report must preserve its original target values, peer median, sample size, comparison date, difference, and evidence.
- Silent regeneration or silent mutation of historical report facts is forbidden.

### REPORT-002

- A historical correction to the target child's relevant source data must make the existing analysis stale.
- The existing report remains visible with a changed-record notice.
- Reanalysis must be explicit.
- Silent regeneration is forbidden.
- Revision counter, dirty flag, or input fingerprint remains an implementation decision.

## 9. Remaining roadmap

### Step 8D — Character + Final UX Polish

- Inventory actual character poses before integration.
- Connect the global assistant launcher/avatar.
- Cover greeting, guide/onboarding, thinking/working, success/help/error, and Growth AI processing stages.
- Finish visual polish without redesigning calculations or semantics.

### Step 9 — Integration / Contract Gate

- Full regression and browser integration
- Permissions and account/child context leakage
- Assistant tool grounding and multi-turn behavior
- Question limits, audit, feedback, RAG, and evidence
- Raw Reading and rank/unavailable invariants
- Mobile behavior
- REPORT-001 / REPORT-002
- Security and release blockers
- Production audit persistence decision

### Step 10 — Staging / Release Readiness

- Production-like PostgreSQL and migrations
- Environment/secrets checklist
- Staging and smoke verification
- Backup/rollback rehearsal
- Final release checklist

Production deployment happens only after the exact explicit approval `운영 배포 진행`.

## 10. Character status

Actual character artwork and pose inventory have not been integrated.

Current source-of-truth hooks:

- `features/assistant/character.py` resolves the generic `assistant/mark.svg` and optional `idle.webp`, `idle.png`, or `idle.webm`.
- `static/js/assistant.js` drives `idle`, `thinking`, and `error`.
- Provider/runtime responses currently add `working` and `help`.
- `guide` and `success` remain Step 8D states to design and integrate.
- If no asset exists, the character stage must remain hidden; blank placeholder space is forbidden.

## 11. Git safety

- No push without an explicit user request.
- No production deployment without the exact approval `운영 배포 진행`.
- Migrations must be additive and dialect-aware.
- Destructive schema changes are forbidden.
- Do not change Git author/name/email.
- Do not add `Co-authored-by` or Cursor/AI attribution trailers.

## 12. Codex first action

Before modifying code:

1. Read `docs/dev/CURRENT_STATE.md`.
2. Read `docs/growth_vnext/PRODUCT_CONTRACT_v0.2.md`.
3. Verify current HEAD and working-tree status.
4. Inspect the current relevant implementation.
5. Work only on the requested next milestone.
6. Do not reopen completed decisions without a concrete conflict.

The next milestone is Step 8D.
