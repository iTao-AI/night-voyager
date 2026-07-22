# Governed Fact-to-Plan Walkthrough Implementation Plan

**Implementation status:** Approved plan. Implementation has not started.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` as the primary controller. If the implementation
> owner chooses isolated bounded lanes, use `superpowers:subagent-driven-development`
> instead, not in addition. Every browser, recovery, and proof slice follows
> test-first RED -> GREEN.

**Goal:** Continue the advisor-confirmed Case from `/demo/collaboration` into the
existing `/demo` task, SSE, advisor-review, family-decision, receipt, and timeline
workflow without creating a second planning UI or treating browser storage as
business authority.

**Architecture:** The collaboration client performs a no-store authority reload,
replaces the existing strict `schema_version=2` collaboration envelope with the
existing advisor-family envelope for the same Case and advisor session, then
navigates to `/demo`. The destination re-reads `advisor-ledger`, creates the task
only after an explicit advisor action, and reuses the current reducer, idempotency,
SSE, inspector, review, role-rotation, and family-decision implementation. No new
BFF route or backend mutation is introduced.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Vitest, Testing Library,
Playwright/Chromium, existing transport-only BFF utilities, FastAPI/PostgreSQL from
PR 1, Docker Compose, and the current warm-paper design system.

## Global Constraints

- Start only after PR 1 is merged to clean `main`, its exact merge-SHA hosted
  `python`, `frontend`, and `compose` checks are green, and migration `0009` is the
  sole head. Record the actual base SHA.
- PR 2 owns same-Case journey handoff, current fact/revision presentation, functional
  Chromium proof, and affected runbooks/design matrices. It does not change a
  migration, backend function, API/BFF route, dependency, lockfile, task operation,
  worker, provider, package version, release record, or deployment.
- The handoff never creates a task. It validates current server authority, replaces
  the same-tab envelope, and navigates. Task creation remains the existing explicit
  `/demo` action.
- Reuse exact `schema_version=2`; do not add optional fields or a third journey.
  Successful conversion replaces one full discriminated-union member with the other.
- Keep the same opaque advisor cookie and CSRF value. Do not bootstrap, mint, revoke,
  infer, or client-switch role during handoff.
- Re-read candidate, current confirmed facts, advisor ledger, and Skill inspector
  through existing no-store BFF methods. Never copy task inputs, revision, source,
  policy, Skill pin, route, evidence, or decision facts from collaboration storage.
- The new transient reducer state is exactly `handoff_validating`. It is never
  persisted. Reload before storage replacement returns to `replan_required`.
- If a current same-revision task exists, adopt its identity only from
  `advisor-ledger`. Never send a task POST during handoff.
- A validation failure leaves the collaboration envelope intact and renders a
  closed recovery category. A successful replacement followed by interrupted
  navigation must be recoverable by `/demo` without substituting the default Case.
- Preserve one active EventSource per task, monotonic cursor, exact mutation replay,
  stale reload, session-recovery precedence, and all role-rotation behavior.
- Preserve standalone `/demo` and standalone `/demo/collaboration` behavior. The
  complete path is additive, not a redirect or replacement.
- User-visible copy in this PR may clarify the functional handoff in existing English
  style, but PR 3 owns bilingual catalog and visual refinement. Do not duplicate the
  future locale implementation here.
- Use explicit staging and run `git diff --cached --check` before every commit.
- Before Docker/Chromium proof, run `make doctor MODE=dev`; record host and Docker VM
  capacity, use a task-owned Compose project, preserve retained data, run teardown,
  and record final inventory. No broad prune or unrelated cleanup.
- Keep public output synthetic and neutral. Do not expose internal UUIDs, raw JSON,
  hashes, cookies, CSRF, tracebacks, private paths, or private workflow metadata.

## Dependency and Ownership Map

```text
Task 1 envelope/reducer contracts
  -> Task 2 authority validation and conversion hook
  -> Task 3 destination recovery and current-fact presentation
  -> Task 4 full browser-to-database golden flow
  -> Task 5 docs and plan status
  -> Task 6 full verification and review handoff
```

The integration owner exclusively owns shared recovery and browser composition:

- `web/lib/connected-demo/session-storage.ts`
- `web/lib/connected-demo/use-connected-demo.ts`
- `web/lib/collaboration-demo/use-collaboration-demo.ts`
- `web/lib/collaboration-demo/reducer.ts`
- `web/components/collaboration-demo/CollaborationDemo.tsx`
- Playwright configuration, Compose proof orchestration, shared docs, and screenshots

Optional bounded test work may operate on one non-overlapping test file at a time,
but integration into shared hooks remains serialized.

---

### Task 1: Freeze exact journey conversion and transient state contracts

**Files:**

- Modify: `web/lib/connected-demo/session-storage.ts`
- Modify: `web/lib/collaboration-demo/reducer.ts`
- Modify: `web/tests/unit/collaboration-session.test.ts`
- Modify: `web/tests/unit/collaboration-reducer.test.ts`
- Modify: `web/tests/unit/connected-demo-recovery.test.tsx`
- Modify: `web/tests/unit/collaboration-recovery.test.tsx`

**Interfaces:**

- Add a pure conversion function; do not let a component construct raw storage:

  ```typescript
  export function continueCollaborationAsAdvisorFamily(
    current: CollaborationJourneyEnvelopeV2,
    taskId: string | null,
  ): AdvisorFamilyJourneyEnvelopeV2;
  ```

- The function requires `role === "advisor"` and `phase === "replan_required"`,
  preserves `csrf` and `caseId`, accepts only a validated nullable UUID task ID,
  returns `journey: "advisor-family"`, `briefId: null`, `cursor: 0`, and empty
  advisor-family mutations.
- Extend `CollaborationState` with transient `handoff_validating`; do not add it to
  `CollaborationPersistedPhase` or `COLLABORATION_PHASES`.
- Add reducer events `HANDOFF_VALIDATE` and `HANDOFF_FAILED` only if the existing
  generic failure event cannot preserve the required resume phase. Prefer the
  smallest event surface that keeps `replan_required` recoverable.

- [ ] **Step 1: Write conversion RED tests**

  Cover exact valid conversion and reject parent role, every non-terminal phase,
  partial/malformed IDs, extra fields, altered CSRF/Case, carried collaboration
  mutations, non-zero cursor, and non-null brief ID. Prove the original envelope is
  not mutated.

  ```typescript
  expect(continueCollaborationAsAdvisorFamily(collaborationEnvelope, null)).toEqual({
    schema_version: 2,
    journey: "advisor-family",
    role: "advisor",
    csrf: collaborationEnvelope.csrf,
    caseId: collaborationEnvelope.caseId,
    taskId: null,
    briefId: null,
    cursor: 0,
    mutations: {},
  });
  ```

- [ ] **Step 2: Write reducer RED tests**

  Assert `replan_required -> handoff_validating`; failure returns a closed
  recoverable state whose retry performs a read-only validation; reload hydration
  cannot persist `handoff_validating`.

- [ ] **Step 3: Run RED**

  ```bash
  npm --prefix web run test -- collaboration-session collaboration-reducer \
    collaboration-recovery connected-demo-recovery
  npm --prefix web run typecheck
  ```

  Expected: missing conversion function/state and type errors.

- [ ] **Step 4: Implement minimal GREEN**

  Keep the storage key `night-voyager:m5` and both existing envelope schemas
  unchanged. Export the pure conversion and transient reducer state only.

- [ ] **Step 5: Verify and commit**

  ```bash
  npm --prefix web run test -- collaboration-session collaboration-reducer \
    collaboration-recovery connected-demo-recovery
  npm --prefix web run lint
  npm --prefix web run typecheck
  git add web/lib/connected-demo/session-storage.ts \
    web/lib/collaboration-demo/reducer.ts \
    web/tests/unit/collaboration-session.test.ts \
    web/tests/unit/collaboration-reducer.test.ts \
    web/tests/unit/connected-demo-recovery.test.tsx \
    web/tests/unit/collaboration-recovery.test.tsx
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: freeze same-Case journey handoff"
  ```

---

### Task 2: Validate current authority before navigation

**Files:**

- Modify: `web/lib/collaboration-demo/use-collaboration-demo.ts`
- Modify: `web/components/collaboration-demo/CollaborationDemo.tsx`
- Modify: `web/tests/unit/use-collaboration-demo.test.tsx`
- Modify: `web/tests/unit/collaboration-demo.test.tsx`
- Modify: `web/tests/unit/collaboration-recovery.test.tsx`

**Hook surface:**

Add `continueToPlanning(): Promise<void>` to the hook return. For testability, keep
navigation behind one injected or module-owned bounded function rather than spreading
`window.location` writes through the hook.

Required algorithm:

```text
load exact collaboration envelope
require advisor + replan_required + candidateId
dispatch HANDOFF_VALIDATE
GET current advisor candidates
GET current confirmed facts
GET advisor ledger
GET planning Skill inspector
validate same Case and current result revision
validate exact candidate terminal state and matching fact provenance
validate ledger task phase/task identity when present
build exact advisor-family envelope
replace storage once
navigate /demo
```

Validation rules:

- candidate is the stored candidate and remains `confirmed`;
- confirmed fact is current, advisor-safe, and names the same source candidate;
- `ledger.case_id === stored.caseId`;
- `ledger.case_revision === context.caseRevision === fact/current result revision`;
- ledger is one of `task-ready`, `active-task`, `review-required`,
  `terminal-task-failure`, `family-review`, or `plan-ready` with its existing strict
  projection validator;
- task ID is null for `task-ready`, `family-review`, and `plan-ready`; it comes
  exactly from `ledger.task.task_id` for `active-task`, `review-required`, and
  `terminal-task-failure`;
- do not treat inspector data as authority for conversion; it is refreshed only for
  visible proof.

- [ ] **Step 1: Write hook RED tests**

  Cover the valid task-ready path, concurrent active-task adoption, review-required
  and terminal-task adoption, family-review and plan-ready conversion with a null
  task ID, no task POST, exact read order, one storage replacement, one navigation,
  unchanged CSRF/Case, empty mutation map, and cursor reset.

- [ ] **Step 2: Add failure RED matrix**

  Candidate missing/stale/wrong, fact missing/mismatched, revision drift, Case drift,
  wrong role, expired session, unavailable ledger, malformed projection, and unknown
  failure must leave the collaboration envelope byte-identical. Retry invokes only
  authority reads, never a mutation.

- [ ] **Step 3: Add component RED tests**

  Replace the old link with one primary button. During `handoff_validating`, show a
  disabled, live-region status and no second action. Keep the current confirmed fact
  visible. Focus the new phase heading after transition or failure.

- [ ] **Step 4: Run RED**

  ```bash
  npm --prefix web run test -- use-collaboration-demo collaboration-demo \
    collaboration-recovery collaboration-session
  ```

- [ ] **Step 5: Implement and run GREEN**

  ```bash
  npm --prefix web run test -- use-collaboration-demo collaboration-demo \
    collaboration-recovery collaboration-session
  npm --prefix web run lint
  npm --prefix web run typecheck
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add web/lib/collaboration-demo/use-collaboration-demo.ts \
    web/components/collaboration-demo/CollaborationDemo.tsx \
    web/tests/unit/use-collaboration-demo.test.tsx \
    web/tests/unit/collaboration-demo.test.tsx \
    web/tests/unit/collaboration-recovery.test.tsx
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add governed planning handoff"
  ```

---

### Task 3: Make `/demo` recover the continued Case and show current authority

**Files:**

- Modify: `web/lib/connected-demo/use-connected-demo.ts`
- Modify: `web/components/connected-demo/ConnectedDemo.tsx`
- Modify: `web/components/connected-demo/AdvisorLedger.tsx`
- Modify: `web/components/collaboration-demo/ConfirmedFactSummary.tsx`
- Create: `web/components/connected-demo/CurrentConfirmedFacts.tsx`
- Modify: `web/tests/unit/connected-demo-recovery.test.tsx`
- Modify: `web/tests/unit/connected-demo-ui.test.tsx`
- Modify: `web/tests/unit/connected-demo-inspector.test.tsx`
- Modify: `web/tests/unit/connected-demo-test-data.ts`

**Destination contract:**

- `recover()` already prefers a valid advisor-family envelope. Strengthen tests so
  `metadata.caseId` always drives `advisorLedger`, confirmed-facts, inspector, task,
  SSE, review, brief, and role-rotation reads; constant `CASE_ID` remains only the
  new standalone bootstrap seed.
- A valid continued Case is never replaced by the default Case after reload,
  recoverable error, task acceptance, EventSource refresh, advisor review, or parent
  rotation.
- Add one bounded advisor-only confirmed-facts read using the existing
  `createCollaborationDemoApi().confirmedFacts(caseId, "advisor")` method. Match facts
  to the ledger Case revision and render public fact key/value/version/revision only.
- `AdvisorLedger` displays localized-later public labels for Case revision and current
  fact summary; this PR keeps existing English presentation and excludes internal IDs,
  raw candidate/message bodies, actor IDs, request hashes, and history.

- [ ] **Step 1: Write destination RED tests**

  Build a non-default Case envelope. Assert every API call uses that Case and no call
  uses the default fixture. Cover task-ready, active task, review required, terminal,
  current brief, reload, and interrupted navigation.

- [ ] **Step 2: Write fact-presentation RED tests**

  Assert the current `family.budget`, fact version, and Case revision render; internal
  UUIDs and raw JSON do not. Missing facts render a bounded empty state, not a stale
  previous projection.

- [ ] **Step 3: Preserve inspector and SSE invariants**

  Assert handoff itself has zero task POST and zero EventSource. Explicit task create
  opens exactly one `/events?after=0`; recovery uses the stored task/cursor; inspector
  is `not_created` before creation and `matched` only after server proof.

- [ ] **Step 4: Implement and run GREEN**

  ```bash
  npm --prefix web run test -- connected-demo-recovery connected-demo-ui \
    connected-demo-inspector connected-demo-presentation
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add web/lib/connected-demo/use-connected-demo.ts \
    web/components/connected-demo/ConnectedDemo.tsx \
    web/components/connected-demo/AdvisorLedger.tsx \
    web/components/connected-demo/CurrentConfirmedFacts.tsx \
    web/components/collaboration-demo/ConfirmedFactSummary.tsx \
    web/tests/unit/connected-demo-recovery.test.tsx \
    web/tests/unit/connected-demo-ui.test.tsx \
    web/tests/unit/connected-demo-inspector.test.tsx \
    web/tests/unit/connected-demo-test-data.ts
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: recover the confirmed Case in planning"
  ```

---

### Task 4: Prove one browser-to-database authority chain

**Files:**

- Create: `web/e2e/fact-to-plan.spec.ts`
- Modify: `web/playwright.compose.config.ts`
- Modify: `scripts/verify_compose.sh`
- Create: `scripts/verify_fact_to_plan_flow.py`
- Create: `tests/integration/connected_demo/test_fact_to_plan_flow.py`
- Modify: `tests/architecture/test_compose_contract.py`
- Modify: `tests/architecture/test_fact_to_plan_contract.py`

**Golden flow:**

1. Fresh synthetic database at migration `0009`.
2. Parent appends the bounded budget message.
3. Parent explicitly proposes the typed budget candidate.
4. Real parent revoke/bootstrap/advisor mint.
5. Advisor confirms candidate; browser proves fact version and revision `N+1`.
6. Handoff performs reads only and navigates with the same Case/advisor session.
7. Advisor explicitly creates the task; database proves `intake -> planning` and
   exact five-field Skill pin.
8. Worker executes revision `N+1`; browser follows native SSE and reconnect.
9. Advisor approves the current PlanningRun.
10. Real advisor revoke/bootstrap/parent mint.
11. Family confirms; database proves receipt and timeline for the same Case.

- [ ] **Step 1: Write browser RED**

  Use role/name selectors, not CSS implementation selectors. Capture all mutation
  requests and prove no task request occurs before the explicit destination action.
  Assert one EventSource and monotonic durable cursor.

- [ ] **Step 2: Write database verifier RED**

  Accept only the browser-observed Case/task identifiers through bounded command
  arguments or an owned proof file. Query PostgreSQL as an approved proof role and
  assert exact Case, revision, confirmed fact, candidate, task, dispatch/event,
  execution, Skill pin, PlanningRun, review, brief, decision, receipt, and timeline
  relationships. Never print raw cookies, CSRF, or source contents.

- [ ] **Step 3: Wire the real Compose lane**

  Add `fact-to-plan.spec.ts` to `testMatch`. Run the database verifier after the
  browser flow. Preserve current connected and collaboration specs as independent
  compatibility lanes.

- [ ] **Step 4: Add recovery and responsive cases**

  Cover reload before validation, after envelope replacement, during task streaming,
  during review, and after parent rotation. Exercise 1440, 768, and 390 px, keyboard
  focus, landmarks, 44 px action target, and no horizontal overflow. PR 3 later owns
  visual polish and bilingual screenshots.

- [ ] **Step 5: Run focused and full browser GREEN**

  ```bash
  npm --prefix web run test
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  make doctor MODE=dev
  make compose-proof
  make down
  docker compose ps --all
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add web/e2e/fact-to-plan.spec.ts web/playwright.compose.config.ts \
    scripts/verify_compose.sh scripts/verify_fact_to_plan_flow.py \
    tests/integration/connected_demo/test_fact_to_plan_flow.py \
    tests/architecture/test_compose_contract.py \
    tests/architecture/test_fact_to_plan_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "test: prove the governed fact-to-plan flow"
  ```

---

### Task 5: Update functional documentation and implementation status

**Files:**

- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/operations/collaboration-walkthrough.md`
- Modify: `docs/operations/connected-demo.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/route-map.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `docs/reference/collaboration-and-confirmed-facts.md`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/reference/versioned-skills-and-runtime-pins.md`
- Modify: `docs/superpowers/specs/2026-07-22-governed-fact-to-plan-closure-design.md`
- Modify: `docs/superpowers/plans/2026-07-22-governed-fact-to-plan-walkthrough.md`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `tests/unit/test_release_surface.py`

**Documentation truth:**

- `/demo/collaboration` now has an explicit same-Case handoff but still creates no
  task itself.
- `/demo` owns the explicit task action and all subsequent planning/decision states.
- The flow is local synthetic and provider-free. PR 3 presentation work remains
  approved but not implemented.
- Existing v0.1.2 release docs/screenshots remain immutable history until PR 3
  creates new current screenshots; do not rewrite tagged records.

- [ ] **Step 1: Add documentation RED assertions**

  Test route/state/storyboard consistency, same-Case wording, no automatic planning,
  no new BFF, functional plan status, and PR 3 still pending.

- [ ] **Step 2: Run GStack `document-release`**

  Audit reference, operations/how-to, explanation, and evaluator entry points. Use
  `document-generate` only for a verified in-scope gap.

- [ ] **Step 3: Update docs and run GREEN**

  ```bash
  uv run pytest -q tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py tests/architecture/test_fact_to_plan_contract.py
  uv run python scripts/verify_release.py --tree-mode development
  git diff --check
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add README.md README_CN.md docs/README.md docs/superpowers/README.md \
    docs/operations/collaboration-walkthrough.md docs/operations/connected-demo.md \
    docs/design/demo-storyboard.md docs/design/route-map.md \
    docs/design/state-and-interaction-matrix.md docs/design/projection-matrix.md \
    docs/reference/collaboration-and-confirmed-facts.md \
    docs/reference/agent-tasks-and-events.md \
    docs/reference/versioned-skills-and-runtime-pins.md \
    docs/superpowers/specs/2026-07-22-governed-fact-to-plan-closure-design.md \
    docs/superpowers/plans/2026-07-22-governed-fact-to-plan-walkthrough.md \
    tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "docs: complete the fact-to-plan walkthrough proof"
  ```

---

### Task 6: Run full verification and prepare authority review

**Files:** None expected.

- [ ] **Step 1: Preflight and deterministic gates**

  ```bash
  git status --short
  make doctor MODE=dev
  uv lock --check
  npm --prefix web ci
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  ```

- [ ] **Step 2: Full backend and database gates**

  ```bash
  make check
  make proof
  ```

- [ ] **Step 3: Fresh Compose/Chromium proof and teardown**

  ```bash
  make compose-proof
  make down
  docker compose ps --all
  ```

  Record the task-owned project/image/cache/volume inventory before and after. Do
  not prune unrelated resources.

- [ ] **Step 4: Final review**

  ```bash
  BASE=$(git merge-base HEAD origin/main)
  git diff --check "$BASE"..HEAD
  git diff --stat "$BASE"..HEAD
  uv run python scripts/verify_release.py --tree-mode development
  git status --short
  ```

  Confirm no migration, backend authority, BFF route, dependency, lockfile, version,
  release, provider, DRA, or MKE diff.

- [ ] **Step 5: Handoff**

  Keep a clean local branch/worktree for independent authority review. Report exact
  base/HEAD, ordered commits, focused RED -> GREEN, one continuous browser-to-database
  proof, default-route compatibility, documentation impact, Docker inventory, and
  remaining PR 3 scope. Do not push or create a PR without separate authorization.

## Acceptance Checklist

- [ ] Handoff validates current candidate, fact, revision, ledger, and Case identity.
- [ ] Handoff sends zero task mutations and performs one exact storage replacement.
- [ ] `/demo` recovers the same non-default Case and never substitutes the seed Case.
- [ ] Task inputs come only from destination `advisor-ledger`.
- [ ] Concurrent current task identity is adopted only from the ledger.
- [ ] Existing one-EventSource, cursor, retry, review, role, and decision contracts
  remain green.
- [ ] Real Chromium and PostgreSQL prove the full confirmed-fact-to-receipt chain.
- [ ] Standalone `/demo` and `/demo/collaboration` remain independently usable.
- [ ] PR 3 remains presentation-only and unimplemented until this PR is merged.

## Not in Scope

- Migration/backend/API/BFF changes, automatic task creation, new EventSource, or
  a second planning state machine.
- Localization framework, Chinese copy catalog, visual redesign, or screenshot
  replacement; those belong to PR 3.
- DRA/MKE/live-provider execution, release, deployment, or production claims.
