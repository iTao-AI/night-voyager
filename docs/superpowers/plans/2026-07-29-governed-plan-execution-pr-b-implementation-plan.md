# Governed Plan Execution PR B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose and prove the blocked/reassessment terminal path, lost-acknowledgement reconciliation, stale-tab and role/session recovery, and complete `zh-CN`/`en` browser-to-database governed execution journeys.

**Architecture:** Build on the complete merged PR A `0014` authority. PR B adds only the authority-approved identity migration `0015`; it does not change the `0014` timeline schema or backend transitions. PR B expands the strict browser state machine, recovery controller, blocked/reassessment presentation, deterministic fixture/proof, and operations documentation over the existing receipt-then-GET API. PostgreSQL remains the only state authority; browser storage holds revalidated identities and stable idempotency slots only.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, Playwright 1.58, existing FastAPI/PostgreSQL timeline-execution contracts, pytest, Ruff, Pyright, Docker Compose.

**Plan status:** Implemented, reviewed, and merged. PR C is also reviewed and
merged; the complete surface is included in the v0.1.5 release candidate.
Publication remains separately gated.

## Global Constraints

- Base is the reviewed and merged PR A at migration head `0014`.
- Migration `0014` is immutable after PR A merge. The approved identity-only `0015` extends the exact demo principal allowlist and same-scenario session rotation; it does not change timeline transition semantics.
- No `AgentTask`, Skill, worker, event, SSE, provider, model, queue, scheduler, successor business row, or second idempotency ledger.
- The existing synchronous current-action projection remains provider-free and non-authoritative.
- A blocked or PostgreSQL-overdue checkpoint may reach exactly one durable `reassessment_required` request and then stops.
- No successor Case revision, PlanningRun, AdvisorReview, FamilyDecision, DecisionReceipt, TimelinePlan, execution, or task is created.
- A lost response is recovered only by replaying the exact prior request body with the same idempotency key. Recovery never creates a new key automatically.
- Every local identity is revalidated through the server context and execution GET before use.
- Reload obtains a fresh CSRF value through the existing opaque-session bootstrap path. CSRF and session values are never stored in the plan-execution envelope.
- A shared-cookie role rotation or revocation closes in-flight work and produces bounded `session_changed`; it never mutates with stale authority.
- Exact `zh-CN` and `en` journeys are required.
- Functional acceptance covers 1440 and 390 CSS pixels. The full 768/320/200% and cross-route presentation closure remains PR C.
- Do not modify dependencies, lockfiles, Dockerfiles, Compose policy, version/release artifacts, DRA status, or public release history.
- Every task uses RED → GREEN, exact review, semantic commit, and clean handoff.

## File Map and Ownership

Primary paths:

- `web/lib/plan-execution/contracts.ts`: final strict receipt, context, execution, handoff, and Problem decoders.
- `web/lib/plan-execution/api.ts`: exact BFF transport calls.
- `web/lib/plan-execution/idempotency.ts`: request fingerprints and stable operation slots.
- `web/lib/plan-execution/session-storage.ts`: closed `PlanExecutionEnvelopeV1`.
- `web/lib/plan-execution/reducer.ts`: UI/recovery states only.
- `web/lib/plan-execution/use-plan-execution.ts`: bounded orchestration and abort generation.
- `web/components/plan-execution/**`: blocked, waiting, recovery, activity, and terminal handoff presentation.
- `web/e2e/plan-execution.spec.ts`: complete bilingual Happy/Blocked proof.
- `scripts/seed_demo.py`: deterministic Happy and Blocked scenario anchors.
- `scripts/verify_timeline_execution.py`: exact database closure verifier.
- `scripts/verify_compose.sh`: provider-free proof lane and teardown.
- `tests/integration/timeline_execution/test_journey.py`: real database proof/counterfactuals.
- `tests/architecture/test_plan_execution_journey.py` and `tests/architecture/test_compose_contract.py`: harness authority.
- current operations/reference/docs surfaces named in Task 5.

Bounded compatibility paths are authorized only for fresh mechanical RED:

- existing plan-execution tests and BFF handler tests;
- existing demo session, bootstrap, connected-demo handoff, portfolio route, catalog, Compose, documentation, and release-surface tests;
- `scripts/run_db_tests.sh` only when the new read-only verifier lane must be enumerated;
- seed replay/parity and historical-head calls only to pass the existing `--without-planning-revision`/new scenario exclusions without weakening historical authority.

A need to edit migrations other than approved new `0015`, `src/night_voyager/timeline_execution/**`, FastAPI route semantics, dependency manifests, Dockerfiles, or Compose policy is a substantive blocker requiring authority review.

## Execution Preflight and Commit Protocol

```bash
git status --short --branch
test -z "$(git status --porcelain)"
: "${EXPECTED_BASE_SHA:?reviewed PR A merge SHA required}"
test "$(git rev-parse HEAD)" = "$EXPECTED_BASE_SHA"
make doctor MODE=dev
uv sync --locked
npm --prefix web ci
test "$(uv run alembic heads | awk '{print $1}')" = "0015"
```

Record `BASE_SHA`. Use the same RED, GREEN, diff, commit, Docker inventory, exact teardown, and no-prune contract as PR A.

---

### Task 1: Freeze the final recovery and reconciliation state machine

**Files:**

- Modify: `web/lib/plan-execution/contracts.ts`
- Modify: `web/lib/plan-execution/api.ts`
- Modify: `web/lib/plan-execution/idempotency.ts`
- Modify: `web/lib/plan-execution/session-storage.ts`
- Modify: `web/lib/plan-execution/reducer.ts`
- Modify: `web/lib/plan-execution/use-plan-execution.ts`
- Modify: `web/tests/unit/plan-execution-contracts.test.ts`
- Modify: `web/tests/unit/plan-execution-reducer.test.ts`
- Modify: `web/tests/unit/plan-execution-recovery.test.tsx`
- Create: `web/tests/unit/plan-execution-idempotency.test.ts`

**Final reducer states:**

```text
loading
ready_to_start
checkpoint_active
mutation_in_flight
awaiting_advisor
execution_completed
reassessment_required
session_changed
recoverable_error
```

`mutation_in_flight` carries operation and safe prior display state, not authority rows. The controller records `{fingerprint,idempotencyKey}` before POST, captures the immutable receipt before navigation/focus, performs a fresh GET, and clears the slot only after receipt/result identity and GET authority reconcile.

Lost acknowledgement flow:

```text
known exact body + stable slot
  -> explicit user recovery
  -> same POST body + same Idempotency-Key
  -> exact original TimelineMutationReceiptV1
  -> fresh GET
```

If a stored slot has no reconstructable exact body, recovery fails closed and performs no mutation. A new user action after a confirmed fresh state may create a new key; an automatic retry may not.

Session generation rules:

- every bootstrap/role rotation increments an in-memory controller generation;
- all pending fetches and mutation continuations bind that generation;
- a 401, `session_changed`, or generation mismatch aborts and ignores later completion;
- recovery bootstrap returns fresh CSRF to memory only;
- same-Case role rotation may retain revalidated Case/execution identity;
- cross-Case or ambiguous context clears the envelope and exposes no mutation.

- [x] **Step 1: Add RED for lost acknowledgement, exact replay, two tabs, session change, and abort generation**

Cover stable key reuse, different-body conflict, absent exact body, receipt-before-GET order, later state change after accepted mutation, double click, stale execution/checkpoint versions, role rotation during request, revoked cookie, delayed old-generation response, malformed storage, cross-Case storage, and exactly one active recovery envelope.

- [x] **Step 2: Run RED**

```bash
npm --prefix web run test -- --run \
  web/tests/unit/plan-execution-contracts.test.ts \
  web/tests/unit/plan-execution-idempotency.test.ts \
  web/tests/unit/plan-execution-reducer.test.ts \
  web/tests/unit/plan-execution-recovery.test.tsx
```

- [x] **Step 3: Implement the minimal final controller state machine**

Use `AbortController` and an integer in-memory generation. Do not use `BroadcastChannel`, localStorage authority, timers as state authority, background retry, or EventSource.

- [x] **Step 4: Run GREEN and commit**

```bash
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test -- --run \
  web/tests/unit/plan-execution-contracts.test.ts \
  web/tests/unit/plan-execution-idempotency.test.ts \
  web/tests/unit/plan-execution-reducer.test.ts \
  web/tests/unit/plan-execution-recovery.test.tsx
npm --prefix web run test
npm --prefix web run build
git add web/lib/plan-execution web/tests/unit/plan-execution-*.test*
git commit -m "feat: close timeline execution recovery"
```

### Task 2: Expose blocked, overdue, reassessment, and terminal handoff UI

**Files:**

- Modify: `web/components/plan-execution/PlanExecutionWorkspace.tsx`
- Modify: `web/components/plan-execution/CurrentCheckpoint.tsx`
- Modify: `web/components/plan-execution/CheckpointAttestationForm.tsx`
- Modify: `web/components/plan-execution/AdvisorVerificationPanel.tsx`
- Modify: `web/components/plan-execution/ExecutionActivity.tsx`
- Create: `web/components/plan-execution/ReassessmentHandoff.tsx`
- Create: `web/components/plan-execution/ExecutionRecoveryNotice.tsx`
- Modify: `web/lib/presentation/catalog.ts`
- Modify: `web/tests/unit/plan-execution-ui.test.tsx`
- Create: `web/tests/unit/plan-execution-presentation.test.ts`

**State/action matrix:**

| Durable state | Family presentation/action | Advisor presentation/action |
| --- | --- | --- |
| active + in_progress | accountable role: progress/completion/blocked attestation; other family role: waiting | current owner and risk, no family mutation |
| active + awaiting_advisor | submitted attestation/receipt and waiting | `verify` and `request_update` |
| active + blocked | blocker, owner, stop consequence | `request_reassessment` |
| completed | verified history, no mutation | verified history, no mutation |
| reassessment_required | stop reason and no resume | exact predecessor handoff and no successor action |
| session_changed | last valid safe content plus reconnect | same |
| projection unavailable | last valid safe content only when internally consistent | retry/reconnect |

Overdue advisor action is visible only when the server returns `risk_state=overdue`; the browser never calculates authority from local time. Reassessment confirmation states that it stops execution and does not create a new plan.

Every state has:

1. what is happening now;
2. what the current user should do;
3. who acts next.

Attestation forms expose only closed radio/select values. No text area, file input, URL input, or arbitrary string field exists.

- [x] **Step 1: Add semantic, role, focus, and bilingual RED**

Cover all matrix rows, wrong-role absence, exact closed form values, advisor verify/request-update, blocked and overdue confirmation, receipt focus destination, deduplicated live-region announcements, terminal later-mutation absence, no fake resume CTA, long Chinese/English copy, and no raw UUID/hash/row-version default content.

- [x] **Step 2: Run RED**

```bash
npm --prefix web run test -- --run \
  web/tests/unit/plan-execution-ui.test.tsx \
  web/tests/unit/plan-execution-presentation.test.ts
```

- [x] **Step 3: Implement the complete functional state presentation**

Keep data fetching and mutation orchestration in the hook. Components receive strict DTOs and callbacks only.

- [x] **Step 4: Run GREEN and commit**

```bash
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
git add web/components/plan-execution web/lib/presentation/catalog.ts \
  web/tests/unit/plan-execution-ui.test.tsx \
  web/tests/unit/plan-execution-presentation.test.ts
git commit -m "feat: add governed reassessment handoff"
```

### Task 3: Build deterministic Happy and Blocked fixtures and database verifier

**Files:**

- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `scripts/seed_demo.py`
- Modify: `scripts/verify_timeline_execution.py`
- Create: `tests/integration/timeline_execution/test_journey.py`
- Modify: `tests/integration/timeline_execution/test_seed.py`
- Modify only after RED: bounded seed replay/parity/current-count compatibility paths.

**Fixture contract:**

- Happy scenario begins with final immutable plan and no execution.
- Blocked scenario begins with a separate final immutable plan and no execution.
- Both have exact assigned advisor/student/parent actors.
- Neither contains attestations, verifications, receipts, reassessment, successor rows, or execution tasks at seed time.
- Re-running seed compares complete bounded rows and never mutates a terminal execution.

**Verifier inputs:**

A private proof JSON contains only:

```text
schema_version
locale
scenario
case_id
timeline_plan_id
execution_id
accepted receipt ids
checkpoint ids
reassessment_request_id|null
```

It contains no session, CSRF, idempotency key, raw request, actor secret, database URL, or content-bearing payload.

The database verifier proves:

- exact anchor and ordered checkpoints;
- Happy path progress/completion/request-update/verify/final completion;
- Blocked path one blocked attestation and one reassessment request;
- byte-identical receipt replay and one central idempotency row per accepted operation;
- exact actor/role ownership;
- exact observed-date/trigger projection for overdue counterfactual;
- no later mutation after reassessment;
- zero successor planning/decision/timeline/execution/task rows.

- [x] **Step 1: Add seed replay, verifier, and counterfactual RED**

- [x] **Step 2: Run RED**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-b-db-red-$$" \
  scripts/run_db_tests.sh timeline-execution journey
```

- [x] **Step 3: Implement deterministic scenario additions and verifier**

Use fixed synthetic UUIDs in `demo_seed.py`. Historical-head seed calls explicitly disable the new scenario rather than invoking `0014` functions before they exist.

- [x] **Step 4: Run GREEN and commit**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-b-db-green-$$" \
  scripts/run_db_tests.sh timeline-execution journey
uv run ruff check src/night_voyager/identity/demo_seed.py \
  scripts/seed_demo.py scripts/verify_timeline_execution.py \
  tests/integration/timeline_execution
uv run pyright scripts/verify_timeline_execution.py \
  tests/integration/timeline_execution
git add src/night_voyager/identity/demo_seed.py scripts/seed_demo.py \
  scripts/verify_timeline_execution.py tests/integration/timeline_execution
# Add only individually reviewed RED-proven compatibility paths.
git commit -m "test: freeze governed execution journeys"
```

### Task 4: Add complete bilingual browser-to-database proof

**Files:**

- Create: `web/e2e/plan-execution.spec.ts`
- Modify: `scripts/verify_compose.sh`
- Modify: `scripts/verify_timeline_execution.py`
- Modify: `tests/architecture/test_compose_contract.py`
- Create: `tests/architecture/test_plan_execution_journey.py`

**Happy path for each locale:**

1. bootstrap server-owned Case context;
2. start execution as assigned family;
3. observe current checkpoint, owner, due date, risk, and deterministic current action;
4. submit progress then completion and capture immutable receipts;
5. rotate to advisor, request update once, rotate back, submit completion again;
6. verify documents, application, and visa;
7. rotate to parent for arrival completion;
8. rotate to advisor, verify arrival, and observe `completed`;
9. reload and prove exact terminal activity/history.

**Blocked path for each locale:**

1. bootstrap the isolated blocked Case;
2. start execution and submit one blocked attestation;
3. rotate to advisor and create one reassessment request;
4. observe `reassessment_required` and exact successor-safe handoff;
5. attempt the former attestation and verification calls with fresh versions and prove closed rejection;
6. prove no successor business rows.

**Recovery counterfactuals:**

- drop one mutation response after PostgreSQL commit and replay exact body/key;
- stale second tab submits old versions and receives closed refresh;
- rotate/revoke the shared session while a read is in flight and prove `session_changed`;
- reload with valid envelope and fresh CSRF;
- malformed/cross-Case envelope causes zero mutation;
- activity 65-plus discloses latest 64 and exact total.

- [x] **Step 1: Add harness architecture RED**

Require exact locales, scenarios, role sequence, receipt replay, stale-tab rejection, session-generation closure, browser proof JSON schema, database verifier, phase markers, and teardown.

- [x] **Step 2: Run focused static GREEN after implementing harness shape**

```bash
uv run pytest -q \
  tests/architecture/test_compose_contract.py \
  tests/architecture/test_plan_execution_journey.py
uv run ruff check scripts/verify_timeline_execution.py \
  tests/architecture/test_plan_execution_journey.py
uv run pyright scripts/verify_timeline_execution.py
sh -n scripts/verify_compose.sh
```

- [x] **Step 3: Run one normal task-scoped Compose proof**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-b-proof-$$" \
  make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-b-proof-$$" \
  make down
```

Expected: all prior lanes and exact `zh-CN`/`en` Happy/Blocked execution lanes pass; task/default project and container readbacks are empty.

- [x] **Step 4: Commit**

```bash
git add web/e2e/plan-execution.spec.ts scripts/verify_compose.sh \
  scripts/verify_timeline_execution.py \
  tests/architecture/test_compose_contract.py \
  tests/architecture/test_plan_execution_journey.py
git commit -m "test: prove governed plan execution recovery"
```

### Task 5: Close operations, error catalog, and PR B verification

**Files:**

- Modify: `docs/operations/timeline-execution.md`
- Create: `docs/operations/plan-execution-walkthrough.md`
- Modify: `docs/reference/timeline-execution-contract.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: governed-plan-execution spec and PR A/B plan statuses.
- Modify: `scripts/verify_release.py`
- Modify only after RED: documentation/release/presentation compatibility tests.

Document exact Happy/Blocked commands and outcomes, recovery actions per public problem code, append-only latest-64 limitation, PostgreSQL observed-date boundary, session/stale-tab behavior, handoff non-successor boundary, expected proof phases, cleanup, and non-claims.

- [x] **Step 1: Add documentation/release RED and update current-development surfaces**

- [x] **Step 2: Run a targeted documentation coverage audit**

Close confirmed tutorial/how-to, reference, operations, and explanation gaps without changing released artifacts.

- [x] **Step 3: Run final PR B gates**

```bash
uv lock --check
uv run ruff check .
uv run pyright
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
make db-check
make check
make proof
uv run python scripts/verify_release.py --tree-mode development
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-b-final-$$" \
  make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-b-final-$$" \
  make down
git diff --check
git diff "$BASE_SHA"..HEAD --check
git status --short
```

- [x] **Step 4: Commit documentation**

```bash
git add docs README.md README_CN.md scripts/verify_release.py
# Add only individually reviewed RED-proven compatibility paths.
git commit -m "docs: publish governed execution recovery"
```

- [x] **Step 5: Freeze PR B exit evidence**

Return commit list, exact diff/stat, RED→GREEN evidence, Happy/Blocked browser/database identities, receipt replay proof, session/stale-tab evidence, Docker inventories, documentation impact, rollback boundary, and remaining PR C/release work. Require clean worktree/staging/untracked.

**Rollback:** Revert PR B web, fixture, proof, and documentation commits. Downgrade
`0015 -> 0014` only on an empty PR B identity boundary; if any 0015-only
principal or session history exists, the migration refuses before catalog or row
mutation. PR A schema/API/minimal vertical remains complete, and immutable
execution/reassessment history remains readable.

**Exit evidence:** Blocked/reassessment, recovery, and bilingual provider-free browser-to-database closure are GREEN. Professional cross-route presentation, version bump, release, provider execution, deploy, and successor workflow are not claimed.
