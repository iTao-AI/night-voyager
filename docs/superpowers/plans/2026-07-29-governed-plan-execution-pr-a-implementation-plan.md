# Governed Plan Execution PR A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add migration `0014`, the complete governed timeline-execution authority, strict HTTP/BFF contracts, and a minimal bilingual `/demo/plan` vertical that can start, attest, verify, and complete one immutable `TimelinePlan`.

**Architecture:** `TimelinePlan`, `FamilyDecision`, and `DecisionReceipt` remain immutable planning anchors. A new `timeline_execution` domain owns structured family attestations, advisor verification, immutable mutation receipts, deterministic current-action guidance, and a PostgreSQL-authoritative execution ledger. PostgreSQL owns Case selection, assignment, observed date, lock order, transitions, idempotency, and append-only history; FastAPI and the Next.js BFF are strict transport layers; the browser is a recoverable projection and never mints authority.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, SQLAlchemy async sessions, PostgreSQL 18, Alembic, Next.js 16, React 19, TypeScript, Vitest, Playwright 1.58, pytest, Ruff, Pyright, Docker Compose.

**Plan status:** Implemented, reviewed, and merged; included in the v0.1.5
release candidate. Publication remains separately gated.

## Global Constraints

- Start from the branch containing the approved governed-plan-execution spec at exact reviewed HEAD.
- The pre-implementation migration head is `0013`; this PR adds exactly `0014_timeline_execution_authority.py`. There is no `0015`.
- `StudentCase.state` remains `plan_ready`; execution state is separate.
- One and only one execution may exist for one `TimelinePlan`.
- The execution snapshot must copy the canonical milestones `documents`, `application`, `visa`, `arrival`, in that order, with exact due dates and server-owned accountable roles `student`, `student`, `student`, `parent`.
- A currently assigned student or parent may start execution. Only the exact accountable family role may attest. Only a currently assigned advisor may verify or request reassessment.
- Family input is structured attestation, not source Evidence. No URL, file, upload, free-form narrative, external account identifier, or source locator is accepted.
- Advisor verification is the only trust upgrade.
- Current-action guidance is synchronous, deterministic, non-authoritative, provider-free, and has no durable table, `AgentTask`, Skill, worker, event, queue, scheduler, or SSE stream.
- PostgreSQL supplies the observed date for both read-time risk and accepted `deadline_elapsed` authority. API and browser requests contain no authoritative `as_of`.
- Every mutation returns an immutable `TimelineMutationReceiptV1`; the client obtains current state through a separate fresh GET.
- The existing `app.idempotency_records` remains the sole idempotency authority. It points to an immutable timeline receipt; the receipt table is not a competing key ledger.
- Reassessment database authority is complete in `0014`, but the minimal PR A UI does not expose blocked/reassessment actions. PR B exposes and proves those paths without changing migration `0014`.
- All unavailable and unauthorized results are non-enumerating.
- Required gates are provider-free and credential-free. No third DRA provider attempt is permitted.
- Do not modify dependencies, lockfiles, Dockerfiles, Compose image policy, `VERSION`, release notes, published `v0.1.0`–`v0.1.4` artifacts, or the strict DRA live-acceptance status.
- Every task uses valid RED collection, minimal GREEN implementation, exact diff review, and one semantic local commit.

## File Map and Ownership

Primary implementation paths:

- `src/night_voyager/timeline_execution/models.py`: closed domain and public DTOs.
- `src/night_voyager/timeline_execution/policy.py`: pure snapshot, risk, transition, and current-action projection.
- `src/night_voyager/timeline_execution/hashing.py`: canonical stable request and receipt bytes.
- `src/night_voyager/timeline_execution/errors.py`: closed domain errors.
- `src/night_voyager/timeline_execution/ports.py`: repository protocol and commands.
- `src/night_voyager/timeline_execution/application.py`: role-scoped orchestration.
- `src/night_voyager/timeline_execution/postgres.py`: approved `0014` function adapter and strict projection decoder.
- `src/night_voyager/interfaces/http/timeline_execution.py`: strict FastAPI routes and Problem JSON mapping.
- `migrations/versions/0014_timeline_execution_authority.py`: complete schema, functions, RLS, grants, indexes, upgrade/downgrade.
- `web/lib/plan-execution/**`: strict browser contracts, API, recovery envelope, reducer, and hook.
- `web/components/plan-execution/**`: minimal semantic workspace.
- `web/app/demo/plan/page.tsx`: dedicated execution route.
- `web/app/api/demo/**`: transport-only execution BFF routes.
- `scripts/seed_demo.py`: deterministic finalized execution scenario.
- `scripts/verify_timeline_execution.py`: bounded provider-free database verifier.
- `tests/unit/timeline_execution/**`, `tests/integration/timeline_execution/**`, `tests/security/test_timeline_execution_catalog.py`, `tests/architecture/test_timeline_execution_contract.py`, and matching web tests.

The following compatibility paths are pre-authorized only when a fresh targeted or full-gate RED proves mechanical current-head, seed-count, catalog, runner, or release-surface drift:

- `scripts/run_db_tests.sh`
- `scripts/verify_release.py`
- `tests/architecture/test_bootstrap_contract.py`
- `tests/architecture/test_collaboration_contract.py`
- `tests/architecture/test_documentation_governance.py`
- `tests/architecture/test_m4a_contract.py`
- `tests/architecture/test_m5_contract.py`
- `tests/architecture/test_portfolio_presentation_contract.py`
- `tests/architecture/test_v0_1_4_release_contract.py`
- `tests/integration/planning/test_postgres_planning.py`
- `tests/integration/skills/test_skill_migration_parity.py`
- `tests/integration/tasks/test_mixed_downgrade.py`
- `tests/security/test_collaboration_catalog.py`
- `tests/unit/test_release_surface.py`
- existing BFF/session/presentation tests whose closed inventories must include `/demo/plan`.

Compatibility fixes may update stale current-head assertions, deterministic fixture counts, route inventories, or isolate historical migration lanes. They may not add another migration, broaden grants, weaken RLS/downgrade refusal, change existing journey semantics, or rewrite immutable release evidence.

## Execution Preflight and Commit Protocol

Before Task 1:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
: "${EXPECTED_BASE_SHA:?approved spec HEAD required}"
test "$(git rev-parse HEAD)" = "$EXPECTED_BASE_SHA"
make doctor MODE=dev
uv sync --locked
npm --prefix web ci
test "$(uv run alembic heads | awk '{print $1}')" = "0013"
```

Record `EXPECTED_BASE_SHA` as `BASE_SHA`.

For each task:

1. Add the listed test and run the exact RED command.
2. Confirm tests collect and fail for the intended missing contract.
3. Implement only the listed contract.
4. Run targeted GREEN plus applicable Ruff, Pyright, lint, typecheck, and build.
5. Run `git diff --check`, review the exact task diff, stage only reviewed paths, review `git diff --cached`, commit, and require a clean worktree.

Collection errors, zero selected tests, registry/network failures, Docker failures, and unrelated failures are stop conditions, not RED evidence.

For every Docker-backed lane, record host and Docker VM available space and before/after Compose project, container, image, cache, network, and volume inventories. Use one task-owned `COMPOSE_PROJECT_NAME`; run exact teardown; retain `night-voyager_postgres-data`, shared images, and shared cache; do not prune or change daemon/proxy/source configuration.

---

### Task 1: Freeze the closed timeline-execution domain

**Files:**

- Create: `src/night_voyager/timeline_execution/__init__.py`
- Create: `src/night_voyager/timeline_execution/errors.py`
- Create: `src/night_voyager/timeline_execution/hashing.py`
- Create: `src/night_voyager/timeline_execution/models.py`
- Create: `src/night_voyager/timeline_execution/policy.py`
- Create: `tests/unit/timeline_execution/__init__.py`
- Create: `tests/unit/timeline_execution/test_models.py`
- Create: `tests/unit/timeline_execution/test_policy.py`
- Create: `tests/unit/timeline_execution/test_hashing.py`

**Interfaces:**

```python
class TimelineExecutionState(StrEnum):
    ACTIVE = "active"
    REASSESSMENT_REQUIRED = "reassessment_required"
    COMPLETED = "completed"

class TimelineCheckpointState(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_ADVISOR = "awaiting_advisor"
    VERIFIED = "verified"
    BLOCKED = "blocked"

class TimelineRiskState(StrEnum):
    ON_TRACK = "on_track"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"

class CheckpointAttestationKind(StrEnum):
    PROGRESS = "progress"
    COMPLETION = "completion"
    BLOCKED = "blocked"

class CheckpointStatusCode(StrEnum):
    WORK_IN_PROGRESS = "work_in_progress"
    READY_FOR_ADVISOR = "ready_for_advisor"
    WORK_BLOCKED = "work_blocked"

class CheckpointAttestationCode(StrEnum):
    DOCUMENTS_STATUS_CONFIRMED = "documents_status_confirmed"
    APPLICATION_STATUS_CONFIRMED = "application_status_confirmed"
    VISA_STATUS_CONFIRMED = "visa_status_confirmed"
    ARRIVAL_STATUS_CONFIRMED = "arrival_status_confirmed"

class CheckpointAttestationReasonCode(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    MISSING_REQUIRED_INPUT = "missing_required_input"
    EXTERNAL_DEPENDENCY_UNAVAILABLE = "external_dependency_unavailable"
    DEADLINE_AT_RISK = "deadline_at_risk"

class CheckpointVerificationAction(StrEnum):
    VERIFY = "verify"
    REQUEST_UPDATE = "request_update"

class CheckpointVerificationReasonCode(StrEnum):
    ATTESTATION_VERIFIED = "attestation_verified"
    STATUS_UPDATE_REQUIRED = "status_update_required"
    STATUS_INCONSISTENT = "status_inconsistent"

class ReassessmentTrigger(StrEnum):
    BLOCKED_ATTESTATION = "blocked_attestation"
    DEADLINE_ELAPSED = "deadline_elapsed"

class TimelineCurrentActionCode(StrEnum):
    CHECKPOINT_ATTESTATION_REQUIRED = "checkpoint_attestation_required"
    ADVISOR_VERIFICATION_REQUIRED = "advisor_verification_required"
    EXECUTION_COMPLETED = "execution_completed"
    REASSESSMENT_HANDOFF_REQUIRED = "reassessment_handoff_required"

class TimelineRiskCode(StrEnum):
    CHECKPOINT_DUE_SOON = "checkpoint_due_soon"
    CHECKPOINT_OVERDUE = "checkpoint_overdue"
    CHECKPOINT_BLOCKED = "checkpoint_blocked"
```

`TimelineChecklistCode` is the exact eight-value union:

```text
documents_confirm_status
documents_prepare_required_items
application_confirm_status
application_review_deadline
visa_confirm_status
visa_review_deadline
arrival_confirm_status
arrival_review_deadline
```

Public frozen Pydantic models use `extra="forbid"`:

```python
TimelineExecutionV1
TimelineCheckpointV1
TimelineCheckpointAttestationV1
TimelineCheckpointVerificationV1
TimelineReassessmentRequestV1
TimelineMutationReceiptV1
TimelineActivityItemV1
TimelineCurrentActionV1
TimelineExecutionViewV1
PlanExecutionContextV1
```

`TimelineCurrentActionV1` is exact:

```text
schema_version=1
code
owner_role: advisor|student|parent|none
checkpoint_id|null
execution_version
checkpoint_version|null
```

`PlanExecutionContextV1` is exact:

```text
schema_version=1
scenario=governed-plan-execution-v1
case_id
case_revision
decision_id
decision_receipt_id
timeline_plan_id
execution_id|null
active_role: advisor|student|parent
assignment_status=assigned
```

`TimelineActivityItemV1.kind` is the closed union
`attestation_recorded|verification_recorded|reassessment_recorded|mutation_receipt_recorded`.
Items are ordered by `created_at DESC, durable_id DESC`.
`TimelineExecutionViewV1` returns `activity` with at most 64 items,
`activity_total` as the exact O(history) count, and
`activity_truncated = activity_total > len(activity)`. This release exposes no
activity pagination, export, or delete contract.

`TimelineMutationReceiptV1` contains:

```text
schema_version=1
receipt_id
operation
result_kind
result_id
execution_id
checkpoint_id|null
before_execution_version|null
after_execution_version
before_checkpoint_version|null
after_checkpoint_version|null
created_at
```

It contains no `replayed` field, raw key hash, request hash, tenant, session, CSRF, or actor secret; same-key/same-request replay therefore returns byte-identical canonical JSON.

Attestation combinations are exact:

- `progress` → `work_in_progress`, milestone-matching attestation code, `not_applicable`;
- `completion` → `ready_for_advisor`, milestone-matching attestation code, `not_applicable`;
- `blocked` → `work_blocked`, milestone-matching attestation code, and one of `missing_required_input`, `external_dependency_unavailable`, `deadline_at_risk`.

Verification combinations are exact:

- `verify` → `attestation_verified`;
- `request_update` → `status_update_required` or `status_inconsistent`.

Policy signatures:

```python
def snapshot_timeline_plan(plan: TimelinePlan) -> tuple[CheckpointSeed, ...]: ...
def derive_risk_state(*, checkpoint_state: TimelineCheckpointState,
                      due_date: date, observed_date: date) -> TimelineRiskState: ...
def derive_current_action(view: TimelineExecutionViewV1) -> TimelineCurrentActionV1: ...
def validate_attestation_codes(*, milestone_key: str,
                               kind: CheckpointAttestationKind,
                               status_code: CheckpointStatusCode,
                               attestation_code: CheckpointAttestationCode,
                               reason_code: CheckpointAttestationReasonCode) -> None: ...
def validate_verification_codes(*, action: CheckpointVerificationAction,
                                reason_code: CheckpointVerificationReasonCode) -> None: ...
```

Risk is exact:

- verified checkpoints are `on_track`;
- an unverified checkpoint is `overdue` when `observed_date > due_date`;
- an unverified checkpoint is `due_soon` when `0 <= (due_date - observed_date).days <= 14`;
- every other checkpoint is `on_track`.

`derive_current_action` fails on contradictory authority rows. It maps `active/in_progress` to `checkpoint_attestation_required`, `active/awaiting_advisor` to `advisor_verification_required`, `completed` to `execution_completed`, and `reassessment_required` to `reassessment_handoff_required`.

- [x] **Step 1: Write strict model, code-union, policy, and canonical-byte tests**

Test unknown/extra fields, naive timestamps, non-positive versions, malformed UUIDs, every forbidden narrative/URL/file key, invalid code combinations, reordered/duplicate/missing milestones, browser-supplied role drift, due-soon boundaries at 14/15 days, overdue boundary, contradictory current checkpoints, and byte-identical receipt round-trip.

- [x] **Step 2: Run RED**

```bash
uv run pytest -q tests/unit/timeline_execution
```

Expected: collection succeeds and fails because the package and contracts do not exist.

- [x] **Step 3: Implement the minimal frozen models, canonical hashing, and pure policy**

Use aware UTC timestamps. Do not read the wall clock inside models or policy. Do not import FastAPI, SQLAlchemy, web/session code, Agent tasks, or provider code.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest -q tests/unit/timeline_execution
uv run ruff check src/night_voyager/timeline_execution tests/unit/timeline_execution
uv run pyright src/night_voyager/timeline_execution tests/unit/timeline_execution
```

- [x] **Step 5: Commit**

```bash
git add src/night_voyager/timeline_execution tests/unit/timeline_execution
git commit -m "feat: define governed timeline execution contracts"
```

### Task 2: Add application ports and role-scoped orchestration

**Files:**

- Create: `src/night_voyager/timeline_execution/ports.py`
- Create: `src/night_voyager/timeline_execution/application.py`
- Create: `src/night_voyager/timeline_execution/fakes.py`
- Create: `tests/unit/timeline_execution/test_application.py`
- Modify: `src/night_voyager/timeline_execution/__init__.py`

**Interfaces:**

```python
class TimelineExecutionRepository(Protocol):
    async def context(self, actor: ActorContext,
                      scenario: Literal["governed-plan-execution-v1"]
                      ) -> PlanExecutionContextV1 | None: ...
    async def read(self, actor: ActorContext,
                   case_id: UUID) -> TimelineExecutionViewV1 | None: ...
    async def start(self, actor: ActorContext,
                    command: StartTimelineExecutionCommand,
                    idempotency_key: str) -> TimelineMutationReceiptV1: ...
    async def attest(self, actor: ActorContext,
                     command: AttestTimelineCheckpointCommand,
                     idempotency_key: str) -> TimelineMutationReceiptV1: ...
    async def verify(self, actor: ActorContext,
                     command: VerifyTimelineCheckpointCommand,
                     idempotency_key: str) -> TimelineMutationReceiptV1: ...
    async def reassess(self, actor: ActorContext,
                       command: RequestTimelineReassessmentCommand,
                       idempotency_key: str) -> TimelineMutationReceiptV1: ...
```

`TimelineExecutionService` exposes matching `context`, `read`, `start`, `attest`, `verify`, and `reassess` methods. The service performs closed DTO/code validation and role prechecks; PostgreSQL revalidates all authority.

Commands contain only trusted `ActorContext`, path identities, positive expected versions, the strict public body, and server-generated durable IDs. They contain no client time, tenant field, actor field, milestone copy, responsible role, or mutable execution projection.

Error types:

```python
TimelineExecutionUnavailableError
TimelineExecutionConflictError(code: str)
TimelineExecutionProjectionError
```

- [x] **Step 1: Add RED service tests**

Cover scenario-key closure, assigned family start, wrong-role precheck, accountable-role attestation, advisor-only verification/reassessment, forbidden client authority fields, repository unavailable/conflict/projection mapping, and exact receipt passthrough without a synthesized mutable view.

- [x] **Step 2: Run RED**

```bash
uv run pytest -q tests/unit/timeline_execution/test_application.py
```

- [x] **Step 3: Implement ports, service, and deterministic fakes**

Fakes record call count and exact command bytes for provider-free unit proof. They do not contain production fallback state.

- [x] **Step 4: Run GREEN and commit**

```bash
uv run pytest -q tests/unit/timeline_execution
uv run ruff check src/night_voyager/timeline_execution tests/unit/timeline_execution
uv run pyright src/night_voyager/timeline_execution tests/unit/timeline_execution
git add src/night_voyager/timeline_execution tests/unit/timeline_execution
git commit -m "feat: add governed execution application boundary"
```

### Task 3: Create migration `0014`, tables, RLS, indexes, and downgrade authority

**Files:**

- Create: `migrations/versions/0014_timeline_execution_authority.py`
- Create: `tests/integration/timeline_execution/__init__.py`
- Create: `tests/integration/timeline_execution/test_migration.py`
- Create: `tests/integration/timeline_execution/test_downgrade.py`
- Create: `tests/integration/timeline_execution/test_query_plan.py`
- Create: `tests/security/test_timeline_execution_catalog.py`
- Modify: `scripts/run_db_tests.sh`
- Modify only after RED: listed compatibility paths.

**Schema:**

Create exactly:

```text
app.timeline_executions
app.timeline_checkpoints
app.timeline_checkpoint_attestations
app.timeline_checkpoint_verifications
app.timeline_reassessment_requests
app.timeline_mutation_receipts
```

Required database rules:

- composite foreign keys bind organization, Case, current revision, family decision, decision receipt, timeline, execution, checkpoint, attestation, and verification identities;
- `timeline_executions.timeline_plan_id` is unique;
- checkpoint milestone key and ordinal are independently unique per execution;
- all row versions are positive;
- all state/code columns use closed `CHECK` constraints identical to Task 1;
- attestations, verifications, reassessments, and receipts reject update/delete through immutable triggers;
- all tables enable and force RLS;
- runtime roles have no direct insert/update/delete grant;
- API role receives only narrow function execution and role-safe reads;
- worker receives no new authority;
- activity indexes start with `(organization_id, execution_id, created_at DESC, durable_id DESC)`;
- reassessment is unique per execution;
- the central `app.idempotency_records.response_type` is one of the four exact timeline receipt result types and `response_id` points to an immutable receipt identity by function validation.

The migration file also declares exact function signatures for Task 4:

```text
app.read_plan_execution_context(uuid,uuid,text,text)
app.read_timeline_execution(uuid,uuid,text,uuid)
app.start_timeline_execution(uuid,uuid,text,uuid,uuid,uuid,text,text)
app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text)
app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text)
app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text)
```

The exact parameter names and order are frozen by migration architecture tests. Server-generated UUID arguments are execution/attestation/verification/reassessment/receipt identities; the browser never supplies them.

- [x] **Step 1: Add migration, catalog, RLS, query-plan, and downgrade RED**

Cover fresh upgrade, `0013 -> 0014`, exact current head, owners/search paths/grants, forced RLS, direct-DML denial, runtime role matrix, all constraints, append-only triggers, empty downgrade parity, history refusal before mutation, re-upgrade, 0/1/64/65-plus mixed activity, equal-timestamp tie order, exact total, and JSON `EXPLAIN` index use.

- [x] **Step 2: Add a closed isolated database lane**

`scripts/run_db_tests.sh timeline-execution migration` runs only the new migration/catalog/query-plan tests in a disposable project. Unknown or missing submodes exit `2` before Docker mutation. Historical migration lanes remain isolated and unchanged.

- [x] **Step 3: Run RED**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-migration-red-$$" \
  scripts/run_db_tests.sh timeline-execution migration
```

- [x] **Step 4: Implement DDL, RLS, indexes, immutable triggers, function declarations, and downgrade**

`0014 -> 0013` takes the documented locks, checks all six history tables while RLS is safely controlled, refuses before mutation when any history exists, and restores exact `0013` catalog/grants when empty.

- [x] **Step 5: Run GREEN and commit**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-migration-green-$$" \
  scripts/run_db_tests.sh timeline-execution migration
uv run ruff check migrations/versions/0014_timeline_execution_authority.py \
  tests/integration/timeline_execution tests/security/test_timeline_execution_catalog.py
uv run pyright tests/integration/timeline_execution
git add migrations/versions/0014_timeline_execution_authority.py \
  scripts/run_db_tests.sh tests/integration/timeline_execution \
  tests/security/test_timeline_execution_catalog.py
# Add only individually reviewed RED-proven compatibility paths.
git commit -m "feat: add timeline execution migration authority"
```

### Task 4: Implement PostgreSQL mutations, projections, receipts, and repository

**Files:**

- Modify: `migrations/versions/0014_timeline_execution_authority.py`
- Create: `src/night_voyager/timeline_execution/postgres.py`
- Create: `tests/unit/timeline_execution/test_postgres.py`
- Create: `tests/integration/timeline_execution/test_authority.py`
- Create: `tests/integration/timeline_execution/test_repository.py`
- Modify: `tests/integration/timeline_execution/test_query_plan.py`
- Modify: `scripts/run_db_tests.sh`

**Database transition contract:**

Every mutation function:

1. validates non-null, closed role/operation, UUID and positive version arguments;
2. calls the existing trusted actor-context assertion;
3. resolves assigned Case and immutable timeline anchor without enumeration;
4. locks execution then current checkpoint in fixed order;
5. reads `app.idempotency_records` by organization, actor, operation, key hash;
6. returns the exact stored immutable receipt for same-key/same-request replay before later-state validation;
7. rejects same-key/different-request with the idempotency SQLSTATE;
8. validates current state and expected versions;
9. writes one business audit row, one immutable receipt, and one central idempotency row atomically.

Start copies canonical milestones and roles inside PostgreSQL from `timeline_plans.milestones`; no caller milestone JSON is accepted. First checkpoint is `in_progress`; later checkpoints are `pending`.

Attestation transitions:

- progress appends history and leaves `in_progress`;
- completion appends history and changes current checkpoint to `awaiting_advisor`;
- blocked appends history and changes current checkpoint to `blocked`.

Verification transitions:

- verify requires the latest completion attestation, marks the checkpoint verified, and activates the next checkpoint;
- verifying `arrival` marks execution completed atomically;
- request_update preserves history and returns the same checkpoint to `in_progress`.

Reassessment transitions are already complete in PR A backend authority:

- `blocked_attestation` binds the current blocked attestation;
- `deadline_elapsed` derives observed date and overdue proof using PostgreSQL `CURRENT_DATE`;
- accepted mutation marks execution `reassessment_required`, writes exact predecessor handoff fields and `successor_status='pending_future_authorization'`;
- it creates no successor Case revision, PlanningRun, AdvisorReview, FamilyDecision, DecisionReceipt, TimelinePlan, execution, task, or event.

Read projections use PostgreSQL `CURRENT_DATE` once per statement, expose it as `observed_date`, derive risk from it, and return one context/current checkpoint or fail on zero/ambiguous cardinality. Each activity source is locally limited before `UNION ALL`; global latest is 64; total is exact.

**Repository interface:**

`PostgresTimelineExecutionRepository` calls only the frozen functions, decodes exact DTOs, rejects malformed/duplicate/contradictory rows, maps approved SQLSTATEs to closed errors, and never repairs state in Python.

- [x] **Step 1: Add transition, receipt, concurrency, repository, and negative RED**

Cover all roles, multiple actors sharing one role, cross-tenant and cross-Case attempts, snapshot mismatch, duplicate start, all code combinations, latest-attestation binding, row-version conflicts, two-tab races, same-key replay after later transitions, lost acknowledgement, different-body conflict, fixed lock order, final completion, both reassessment triggers, database-owned date, exact handoff, no successor rows, pool rollback, and strict projection decode.

- [x] **Step 2: Run RED**

```bash
uv run pytest -q tests/unit/timeline_execution/test_postgres.py
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-authority-red-$$" \
  scripts/run_db_tests.sh timeline-execution authority
```

- [x] **Step 3: Implement SQL bodies and repository**

Use one `CURRENT_DATE` observation per read or reassessment statement. The stable client request hash excludes that date and all generated IDs; the accepted reassessment row separately stores `accepted_database_date` and the authoritative trigger projection hash.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest -q tests/unit/timeline_execution
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-authority-green-$$" \
  scripts/run_db_tests.sh timeline-execution authority
uv run ruff check src/night_voyager/timeline_execution \
  migrations/versions/0014_timeline_execution_authority.py \
  tests/unit/timeline_execution tests/integration/timeline_execution
uv run pyright src/night_voyager/timeline_execution \
  tests/unit/timeline_execution tests/integration/timeline_execution
```

- [x] **Step 5: Commit**

```bash
git add migrations/versions/0014_timeline_execution_authority.py \
  src/night_voyager/timeline_execution tests/unit/timeline_execution \
  tests/integration/timeline_execution scripts/run_db_tests.sh
git commit -m "feat: enforce governed timeline execution authority"
```

### Task 5: Publish strict FastAPI and transport-only BFF contracts

**Files:**

- Create: `src/night_voyager/interfaces/http/timeline_execution.py`
- Modify: `src/night_voyager/api.py`
- Create: `tests/integration/timeline_execution/test_http.py`
- Create: `tests/architecture/test_timeline_execution_contract.py`
- Create: `web/app/api/demo/plan-execution-context/route.ts`
- Create: `web/app/api/demo/timeline-plans/[timelinePlanId]/executions/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/timeline-execution/route.ts`
- Create: `web/app/api/demo/timeline-executions/[executionId]/checkpoint-attestations/route.ts`
- Create: `web/app/api/demo/timeline-executions/[executionId]/checkpoint-verifications/route.ts`
- Create: `web/app/api/demo/timeline-executions/[executionId]/reassessments/route.ts`
- Modify: `scripts/run_db_tests.sh`
- Modify: `web/tests/unit/demo-bff-handlers.test.ts`
- Create: `web/tests/unit/plan-execution-bff.test.ts`

**HTTP contracts:**

```text
GET  /api/v1/plan-execution-context?scenario=governed-plan-execution-v1
POST /api/v1/timeline-plans/{timeline_plan_id}/executions
GET  /api/v1/cases/{case_id}/timeline-execution
POST /api/v1/timeline-executions/{execution_id}/checkpoint-attestations
POST /api/v1/timeline-executions/{execution_id}/checkpoint-verifications
POST /api/v1/timeline-executions/{execution_id}/reassessments
```

The public BFF context route contains no arbitrary Case selector and always forwards the fixed closed scenario key. All mutation bodies use `extra="forbid"`, exact `schema_version=1`, positive expected versions, and closed enums. Start accepts no milestones or actor/tenant fields. Mutations require session, exact Origin, CSRF, bounded `Idempotency-Key`, and JSON content type.

Mutation success is exactly `TimelineMutationReceiptV1`. The client must issue a fresh execution GET. Receipt replay has byte-identical body and status.

Public codes:

```text
resource_unavailable
plan_execution_context_unavailable
invalid_idempotency_key
idempotency_conflict
stale_execution_version
stale_checkpoint_version
checkpoint_not_current
checkpoint_attestation_conflict
advisor_verification_required
reassessment_required
execution_completed
session_changed
execution_projection_unavailable
request_validation_failed
```

Add every route to the API path classifier so framework validation also emits Problem JSON. Authorization failures remain 404/non-enumerating. BFF handlers forward only Cookie and, for mutations, Content-Type, Origin, CSRF, and Idempotency-Key through the existing bounded transport.

- [x] **Step 1: Add FastAPI and BFF RED**

Cover exact routes, scenario closure, strict body shape, UUIDs, authentication, Origin, CSRF, idempotency, wrong role, cross-Case, stale versions, replay bytes, response cap, upstream timeout/unavailable, no authority derivation in BFF, and no task/SSE route.

- [x] **Step 2: Run RED**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-http-red-$$" \
  scripts/run_db_tests.sh timeline-execution http
uv run pytest -q tests/architecture/test_timeline_execution_contract.py
npm --prefix web run test -- --run \
  tests/unit/demo-bff-handlers.test.ts \
  tests/unit/plan-execution-bff.test.ts
```

- [x] **Step 3: Implement router, app wiring, BFF handlers, and exact error mapping**

Do not duplicate identity/session helpers. Do not return a mutable execution view from mutations.

- [x] **Step 4: Run GREEN and commit**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-http-green-$$" \
  scripts/run_db_tests.sh timeline-execution http
uv run pytest -q tests/architecture/test_timeline_execution_contract.py
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test -- --run \
  tests/unit/demo-bff-handlers.test.ts \
  tests/unit/plan-execution-bff.test.ts
uv run ruff check src/night_voyager/interfaces/http/timeline_execution.py \
  src/night_voyager/api.py tests/integration/timeline_execution
uv run pyright src/night_voyager/interfaces/http/timeline_execution.py \
  tests/integration/timeline_execution
git add src/night_voyager/interfaces/http/timeline_execution.py \
  src/night_voyager/api.py tests/integration/timeline_execution \
  tests/architecture/test_timeline_execution_contract.py \
  web/app/api/demo web/tests/unit/demo-bff-handlers.test.ts \
  web/tests/unit/plan-execution-bff.test.ts scripts/run_db_tests.sh
git commit -m "feat: expose governed timeline execution APIs"
```

### Task 6: Add deterministic scenario, strict client state, and minimal `/demo/plan`

**Files:**

- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `scripts/seed_demo.py`
- Modify: `scripts/run_db_tests.sh`
- Create: `scripts/verify_timeline_execution.py`
- Create: `tests/integration/timeline_execution/test_seed.py`
- Create: `web/lib/plan-execution/contracts.ts`
- Create: `web/lib/plan-execution/api.ts`
- Create: `web/lib/plan-execution/idempotency.ts`
- Create: `web/lib/plan-execution/session-storage.ts`
- Create: `web/lib/plan-execution/reducer.ts`
- Create: `web/lib/plan-execution/use-plan-execution.ts`
- Create: `web/app/demo/plan/page.tsx`
- Create: `web/components/plan-execution/PlanExecutionWorkspace.tsx`
- Create: `web/components/plan-execution/CurrentCheckpoint.tsx`
- Create: `web/components/plan-execution/CheckpointAttestationForm.tsx`
- Create: `web/components/plan-execution/AdvisorVerificationPanel.tsx`
- Create: `web/components/plan-execution/ExecutionActivity.tsx`
- Modify: `web/lib/presentation/catalog.ts`
- Create: `web/tests/unit/plan-execution-contracts.test.ts`
- Create: `web/tests/unit/plan-execution-reducer.test.ts`
- Create: `web/tests/unit/plan-execution-recovery.test.tsx`
- Create: `web/tests/unit/plan-execution-ui.test.tsx`
- Modify only after RED: listed seed/session/presentation compatibility paths.

**Scenario contract:**

`governed-plan-execution-v1` maps to one deterministic synthetic `plan_ready` Case with exact assigned advisor/student/parent, final decision, receipt, timeline, and no execution. Seed replay compares the complete bounded fixture byte-for-byte and fails on missing or drifted child authority.

**Recovery envelope:**

```ts
interface PlanExecutionEnvelopeV1 {
  schema_version: 1;
  journey: "plan-execution";
  role: "advisor" | "student" | "parent";
  caseId: string;
  timelinePlanId: string;
  executionId: string | null;
  executionVersion: number | null;
  checkpointId: string | null;
  checkpointVersion: number | null;
  lastReceiptId: string | null;
  mutations: Partial<Record<
    "start" | "attest" | "verify" | "reassess",
    { fingerprint: string; idempotencyKey: string }
  >>;
}
```

It stores no CSRF, session, actor, tenant, due date, role authority, mutable activity, or attestation body. Every identity is revalidated through context and execution GET before use.

Reducer states:

```text
loading
ready_to_start
checkpoint_active
awaiting_advisor
execution_completed
reassessment_required
session_changed
recoverable_error
```

PR A UI exposes start, progress, completion, advisor verify, advisor request-update, and final completion. It renders blocked/reassessment responses safely but does not expose blocked attestation or reassessment actions until PR B.

Mutation flow is always:

```text
persist operation fingerprint/key
POST mutation
capture immutable receipt
fresh GET
render authoritative state
```

- [x] **Step 1: Add deterministic seed, strict parser, reducer, recovery, and semantic UI RED**

Test zero/ambiguous scenario, seed replay, malformed/extra client fields, storage replacement count, no CSRF persistence, start-to-completion role matrix, receipt-before-GET ordering, duplicate click, reload, wrong role, optional guidance fallback, exact `zh-CN`/`en` catalog, current action first in DOM, and no raw hashes/row versions by default.

- [x] **Step 2: Run RED**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-seed-red-$$" \
  scripts/run_db_tests.sh timeline-execution seed
npm --prefix web run test -- --run \
  tests/unit/plan-execution-contracts.test.ts \
  tests/unit/plan-execution-reducer.test.ts \
  tests/unit/plan-execution-recovery.test.tsx \
  tests/unit/plan-execution-ui.test.tsx
```

- [x] **Step 3: Implement the seed, verifier, strict client, and minimal semantic workspace**

Use existing `PresentationShell` and catalog infrastructure. Keep API orchestration in the hook and pure display in components. Do not add route-level tabs or a generic dashboard.

- [x] **Step 4: Run GREEN and commit**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-seed-green-$$" \
  scripts/run_db_tests.sh timeline-execution seed
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
uv run ruff check src/night_voyager/identity/demo_seed.py \
  scripts/seed_demo.py scripts/verify_timeline_execution.py \
  tests/integration/timeline_execution
uv run pyright scripts/verify_timeline_execution.py \
  tests/integration/timeline_execution
git add src/night_voyager/identity/demo_seed.py scripts/seed_demo.py \
  scripts/verify_timeline_execution.py tests/integration/timeline_execution \
  web/lib/plan-execution web/app/demo/plan \
  web/components/plan-execution web/lib/presentation/catalog.ts \
  web/tests/unit/plan-execution-*.test*
# Add only individually reviewed RED-proven compatibility paths.
git commit -m "feat: add the minimal governed execution journey"
```

### Task 7: Close PR A documentation and exact-head verification

**Files:**

- Create: `docs/decisions/0013-governed-timeline-execution-authority.md`
- Create: `docs/reference/timeline-execution-contract.md`
- Create: `docs/operations/timeline-execution.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/superpowers/specs/2026-07-29-governed-plan-execution-and-reassessment-design.md`
- Modify: `docs/superpowers/plans/2026-07-29-governed-plan-execution-pr-a-implementation-plan.md`
- Modify: `scripts/verify_release.py`
- Modify only after RED: listed documentation/release compatibility paths.

Documentation must distinguish immutable planning from execution authority, family attestation from Evidence, advisor verification from attestation, synchronous guidance from AgentTask, PostgreSQL date authority, receipt-then-GET reconciliation, reassessment backend availability versus PR B UI/proof deferral, migration `0014`, released `v0.1.4@0013`, and all non-claims.

- [x] **Step 1: Add documentation/release RED**

```bash
uv run pytest -q \
  tests/architecture/test_documentation_governance.py \
  tests/architecture/test_timeline_execution_contract.py \
  tests/unit/test_release_surface.py
uv run python scripts/verify_release.py --tree-mode development
```

- [x] **Step 2: Update current-development documentation and run a targeted documentation coverage audit**

Close only confirmed reference, how-to/operations, explanation/ADR, and index gaps. Published release notes and verification guides remain byte-identical.

- [x] **Step 3: Run final PR A gates**

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

COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-final-$$" \
  make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-a-final-$$" \
  make down

git diff --check
git diff "$BASE_SHA"..HEAD --check
git status --short
```

The normal Compose proof must keep all prior journeys green and add a provider-free execution authority/minimal-browser lane. Record exact teardown and retained shared state.

Local follow-up verification passed the full default `make db-check`, authoritative
`make check`, independent `make proof`, development release verifier, and one normal
task-scoped `make compose-proof`. The Compose proof covered the complete existing
journey set and the minimal bilingual execution journey through terminal completion,
followed by exact task-resource teardown. Exact-final-HEAD hosted `python`,
`frontend`, and normal `compose` checks remain mandatory before publication or merge.

- [x] **Step 4: Commit documentation**

```bash
git add docs README.md README_CN.md scripts/verify_release.py
# Add only individually reviewed RED-proven compatibility paths.
git commit -m "docs: publish governed timeline execution authority"
```

- [x] **Step 5: Freeze PR A exit evidence**

Return exact commit list, changed files/stat, RED→GREEN commands, migration/grant/RLS/query-plan proof, normal Compose proof, Docker inventories, documentation impact, rollback boundary, remaining PR B/C work, and non-claims. Worktree, staging, and untracked state must be clean.

**Rollback:** Web, BFF, and API entry points can be reverted while audit rows remain readable. Empty `0014` history permits exact downgrade to `0013`; any execution history causes pre-mutation refusal and must be retained until a separately approved data migration exists.

**Exit evidence:** The complete backend authority and minimal start-to-completion vertical are provider-free and GREEN. Blocked/reassessment UI, full recovery matrix, professional presentation closure, version bump, release, provider execution, push, PR, merge, tag, and deploy are not claimed.
