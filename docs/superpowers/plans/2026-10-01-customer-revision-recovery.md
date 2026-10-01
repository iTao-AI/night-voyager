# Customer Revision and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scripted client revisions and family acceptance with explicit inputs, and add advisor-authorized fresh-task recovery for eligible terminal failures.

**Architecture:** Keep Browser -> BFF -> application/policy -> PostgreSQL authority. Reuse collaboration fact verification, immutable revisions, task creation, runtime Skill pins, and existing parent decision persistence. Recovery must validate and create atomically under the existing Case serialization boundary.

**Tech Stack:** Existing Next.js/React/TypeScript, FastAPI/Pydantic/SQLAlchemy, Alembic and PostgreSQL; no dependency additions.

**Spec:** [Approved design](../specs/2026-10-01-customer-revision-recovery.md).

## Global Constraints

- Controlled local synthetic pilot; deterministic adapters, no paid provider.
- One supported fact per revision: `student.preferred_countries` or `family.budget`.
- Existing country domain only: Australia/Japan/Malaysia; no new eligible routes.
- Preserve PostgreSQL authority, assigned advisor/parent roles, RLS, Origin/CSRF, immutable history, current revision and idempotency boundaries.
- Recoverable allowlist: `transient_unavailable`, `transport_interrupted`, `lease_expired`, `deadline_exceeded`; enable only codes with a current terminal producer.
- Cancellation, outdated results, unknown codes, `invalid_schema`, `pin_mismatch`, `fallback_authority`, and `policy_rejected` do not allow unchanged-input retry.
- Keep v1 field shapes and legacy reads compatible; eligible terminal v2 ledgers may expose `canonical_task_inputs` without a new schema version.
- Reassessment successor automation remains deferred.
- Local implementation, verification, docs, reviews and semantic commits only. No push, PR, merge, release, deploy, new dependencies, external tool installation, or permanent host configuration changes.
- The user additionally authorized existing-lock dependency synchronization in this worktree's isolated environment and task-owned Docker builds. Keep host caches task-local and do not modify the main checkout or shared configuration. Python verification must explicitly import this worktree's `src` and use its own interpreter.
- Required DB/Compose/concurrency gates are actual runtime gates; offline fixtures cannot replace them. Heavy builds and GUI work run sequentially.

## Review Focus

1. A reload or edited draft must not reuse an old mutation body/key against newer facts (Task 1 recovery tests).
2. Budget revisions must preserve the full existing budget shape and supported minor-unit conversion, including non-default authoritative values (Task 1 validation tests).
3. A new brief identity/version must discard old acknowledgments and explicit budget choices (Task 2 hook tests).
4. An ordinary task-create idempotency key must not replay as a recovery response; retry replay must remain tied to its exact failed source (Task 3 native DB tests).
5. Concurrent recovery, ordinary creation, or revision publication must not produce duplicate active tasks, deadlocks, or mutable failed history (Task 3 native concurrency tests).

## Status

In progress. Starting local HEAD: `539ca4eb0e8fe53d991581afe9f69846a523baf0`.
The design's older prepared baseline is historical; this HEAD is the explicitly delegated stack.
Tasks 1–3 and the scoped parent-session/initial-budget seed fixes are implemented and independently reviewed through `5d2ec2ca3ea4e0966b67e90868f8060eda657056`. Task 4 refreshed full native default/planning/journey/collaboration gates, 555 frontend tests/lint/typecheck, actual locked default build and bilingual country/budget recovery browser gates passed. Native budget proof includes real parent 503/same-tab recovery, actual proposal/revision, classifier/worker terminal producer, explicit retry/new task/SSE/fresh review and immutable receipt 300000–360000. The fresh-pilot-only initial budget lineage and shared participant reads preserve parent-only mutation authority. One fresh whole-branch review and owner acceptance remain pending; this is local work with no PR/release/deployment.

---

### Task 1: Supported revision form and actual advisor candidate

**Files:**
- Modify: `web/components/connected-demo/RevisionFactEditor.tsx`, `AdvisorLedger.tsx`, `ConnectedDemo.tsx`.
- Modify: `web/lib/connected-demo/revision.ts`, `use-connected-demo.ts`, `session-storage.ts` as required.
- Modify: `web/lib/presentation/catalog.ts`, existing `web/app/styles.css` as required for accessible bilingual inputs.
- Test: focused revision validation, hook/component recovery tests under `web/tests/unit/`; adapt existing scripted assertions and `web/e2e/planning-revision.spec.ts`.

**Interfaces:**
- Consumes: authoritative `CurrentFactsProjection`, `MemoryCandidateAdvisor`, existing collaboration API and budget validation/DTO shape.
- Produces: `RevisionIntent` in `revision.ts`, containing `expectedCaseRevision`, `factKey`, and validated proposed `value`; `submitRevision(intent: RevisionIntent): Promise<void>` and `confirmRevision(reason: string): Promise<void>` from the hook.
- The advisor confirms the actual single supported pending candidate and sees its value; ambiguity disables confirmation.

- [x] **Step 1: Add failing tests** for a non-default current country list, one chosen supported subset, budget revision values, duplicate/empty/unknown countries, unchanged values, stale revision, budget bounds, and edited-body idempotency. Assert proposal bodies contain the submitted fact/value and confirmation contains the entered reason.
- [x] **Step 2: Run focused Vitest tests** and record the expected behavior failures before implementation.
- [x] **Step 3: Implement the typed intent, form, and hook methods.** Initialize from authoritative facts; display current/proposed values. Reuse budget parsing, preserve authoritative budget fields, and validate material change. Persist one submitted body/key; edited values are a new intention. A stale server conflict reloads authority. Remove fixed target-country matching and update in-scope historical tests to express actual inputs.
- [x] **Step 4: Run focused tests, frontend typecheck and lint.** Passing means valid country/budget forms issue actual participant mutations, advisor confirmation consumes the actual candidate, invalid/stale forms fail closed, and unchanged journey tests remain green.
- [x] **Step 5: Review diff and commit** exact affected paths as `feat: support explicit client fact revisions`.

### Task 2: Explicit parent budget and trade-off acceptance

**Files:**
- Create: `web/lib/connected-demo/family-decision.ts` for draft parsing/validation.
- Modify: `web/components/connected-demo/FamilyDecisionBrief.tsx`, `ConnectedDemo.tsx`, `web/lib/connected-demo/use-connected-demo.ts`.
- Modify: presentation copy/styles and existing frontend fixtures/tests only where required.
- Test: `web/tests/unit/family-decision.test.ts`, related component/hook tests, existing planning journey E2E.

**Interfaces:**
- Consumes: current brief identity/version and `decision_requirements` (`eligible_route_id`, pinned cost, hard ceiling, currency, required trade-offs).
- Produces: `FamilyDecisionDraft` (min/max input strings and acknowledged trade-offs), a validator yielding the existing `FamilyDecisionBody`, hook-controlled draft/setter used by `FamilyDecisionAction`.
- Task 1 revision callbacks remain intact. Receipt renders existing immutable submitted values.

- [x] **Step 1: Add failing tests** for edited accepted minimum/maximum, separate unchecked trade-offs, missing acknowledgments, zero/unsafe/inverted/out-of-cost/over-ceiling intervals, and brief identity/version reset. Assert the API receives form values, current route/version, and only selected acknowledgments.
- [x] **Step 2: Run focused tests** and record expected failures.
- [x] **Step 3: Implement the draft and UI.** Explain suggested values, show independent required trade-off acknowledgments, and validate the actual form at submission. Keep final consent and parent role action explicit. Reset stale input when brief identity/version changes, preserving ambiguous network replay for the exact submitted body.
- [x] **Step 4: Run family/revision/hook tests, frontend typecheck and lint.** Passing means the submitted body matches explicit choices and receipt presentation preserves them.
- [x] **Step 5: Review diff and commit** exact paths as `feat: collect explicit family decision choices`.

### Task 3: Guarded advisor fresh-task recovery

**Files:**
- Modify: `src/night_voyager/tasks/{models,ports,application,postgres,policy}.py`, `src/night_voyager/interfaces/http/tasks.py`.
- Create: a forward migration after `0015`, an ADR after `0014`, and native recovery tests under `tests/integration/tasks/` and `tests/security/`.
- Modify: `src/night_voyager/connected_demo/{models,postgres}.py` and related unit/projection tests.
- Create: `web/app/api/demo/tasks/[taskId]/retry/route.ts`.
- Modify: connected contracts/API/hook/storage, ledger action, bilingual copy, relevant BFF tests.

**Interfaces:**
- Consumes: existing `TaskService.create`, `app.create_agent_task`, current canonical task pins, assigned advisor actor and Case lock authority.
- Produces: `RetryTaskCommand(task_id, expected_row_version, expected_case_revision)`; `TaskService.retry(context, command, idempotency_key)` returning the existing Task resource; repository retry method and guarded database operation.
- HTTP/BFF body: `{schema_version: 1, expected_row_version: positive integer, expected_case_revision: positive integer}`; `POST /api/v1/tasks/{task_id}/retry`, status `202` with existing projected task shape.
- V2 terminal ledger provides canonical inputs iff server policy says retry is eligible; v1 shapes remain unchanged. Browser method `retryTerminalTask()` consumes this authority and refreshes the ledger/adopts the fresh task.

- [x] **Step 1: Add failing pure/application/HTTP/frontend tests** for recognized terminal producers, hard/unknown/cancelled failures, stale row/revision, role denial, guarded payload, v1/v2 semantics, and exact consent-bound idempotency replay.
- [x] **Step 2: Run offline tests** to record expected behavior failures before implementation. Add native DB tests and run them against a task-owned PostgreSQL database when available; retain full Compose and existing broader authority gates for Task 4.
- [x] **Step 3: Implement atomic recovery.** Use a separate recovery idempotency namespace bound to source identity and expected versions. Under Case serialization, re-read current assigned case/revision and exact latest terminal source, reject accepted result/active successor, resolve canonical source/policy/current Skill, and reuse durable creation. Preserve the source task and all diagnostics. Define minimal grants/forced RLS-compatible function authority and safe forward migration/downgrade behavior; do not grant direct task writes.
- [x] **Step 4: Implement truthful server ledger policy and guarded UI/BFF action.** Strengthen phase/identity validation, preserve accepted bilingual failure explanations, add a fresh explicit advisor consent key, and reuse that exact key/body on ambiguous response. Adoption opens the existing task stream and returns to fresh advisor review.
- [x] **Step 5: Run offline coverage and static checks.** Native tests must cover same-key concurrent replay, different-key clicks, retry vs ordinary creation, retry vs revision/currentness changes, rollback, foreign/unassigned/parent actors, rejected failure codes, task-create key collision, current Skill pins, immutable old task, and fresh task -> worker -> advisor review.
- [x] **Step 6: Review diff and commit** exact paths as `feat: add guarded terminal task recovery`; keep full Compose and broader journey gates explicitly pending until Task 4.

### Task 4: Native acceptance, UI evidence, documentation and final candidate

**Files:**
- Modify: `docs/reference/http-api-v1.md`, `agent-tasks-and-events.md`, connected operation/design docs, `docs/README.md`, `docs/superpowers/README.md` as required.
- Create: `docs/operations/customer-revision-recovery.md` concise runnable role walkthrough and `docs/evidence/customer-revision-recovery.md` verified report.
- Modify: current plan status. Add only task-specific verifier/E2E adaptations needed to prove this feature.

**Interfaces:**
- Consumes: Tasks 1–3 actual contracts and commits; no additional feature scope.
- Produces: actual native DB/concurrency, Compose journey and Chinese/English desktop/mobile observations, documentation audit, final exact HEAD and clean resumable state.

- [x] **Step 1: Complete environment preflight.** Confirm Docker daemon and host/VM capacity, inventory shared resources, use a unique task-owned Compose project/ports, and serialize heavy operations. No broad pruning or permanent settings changes. Ask only for a concrete required host action if unavailable.
- [x] **Step 2: Run native PostgreSQL gates** with runtime-equivalent roles: recovery migration/authority/concurrency, existing planning-revision authority/worker/projection and collaboration concurrency, plus relevant family policy/old-version negatives. Verify current-source import and actual version before claims.
- [x] **Step 3: Run relevant broader checks** using existing dependencies: backend non-database tests, Ruff/Pyright, frontend tests/lint/typecheck/build, fixture/hygiene checks and Compose proof. Preserve any install-dependent gap explicitly.
- [x] **Step 4: Inspect real UI sequentially** in zh-CN/en at desktop and narrow/mobile widths. Demonstrate country and budget revision/comparison/renewed review, edited parent choices reflected in receipt, recoverable failure -> explicit advisor retry -> fresh task/review, and hard failure negative. Capture actual screenshots/observations. Hold/release task-owned `caffeinate` for long GUI work.
- [x] **Step 5: Apply `gstack-workflows:document-release` targeted important-feature audit.** Update exact contracts, runbook and discoverability; keep versioned release history immutable and clearly distinguish local implementation from hosted delivery.
- [ ] **Step 6: Run final branch review**, fix in-scope findings with regression coverage and scoped re-review, reconcile evidence/plan/index and inspect diff for unrelated edits/private paths/secrets/generated noise.
- [ ] **Step 7: Commit acceptance/documentation** as a semantic local commit, report READY only when required gates actually passed, and release task-owned processes/assertions/ephemeral resources. Retain the authorized branch/worktree; report exact HEAD and no PR.
