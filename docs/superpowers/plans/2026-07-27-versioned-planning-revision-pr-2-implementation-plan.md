# Versioned Planning Revision Authority PR 2 Implementation Plan

**Goal:** Add durable pre-final-decision planning lineage so an advisor-requested fact revision freezes one predecessor PlanningRun, creates at most one successor through the existing task worker, and exposes a deterministic old/new comparison.

**Architecture:** Migration `0012` extends existing Case revision and AgentTask rows with explicit predecessor authority. Fact confirmation records and invalidates the predecessor atomically; task creation copies that immutable identity; the worker consumes it instead of querying a current run; result persistence creates one exact successor. A pure comparison model and the existing connected read repository project the two retained runs without adding a second workflow.

**Tech Stack:** Python 3.12, Pydantic 2, SQLAlchemy 2, PostgreSQL 18, Alembic, FastAPI, pytest, existing durable AgentTask worker and connected-demo read models.

**Plan status:** Approved; implementation has not started.

## Global Constraints

- Base must contain merged PR 1 and migration head `0011`.
- New migration head is exactly `0012`.
- Do not rewrite migrations `0001` through `0011`.
- Scope is before any FamilyDecision, DecisionReceipt, or TimelinePlan exists.
- Reuse existing `request_revision`, collaboration candidate, fact verification, task, worker, advisor review, and family decision APIs.
- Do not accept caller-supplied predecessor identity.
- PostgreSQL owns fact revision, lineage, currentness, uniqueness, and authorization.
- The worker loads the predecessor from its claimed task; it never infers lineage from the current PlanningRun at execution time.
- Old runs and reviews remain immutable audit history but lose current business authority.
- Comparison is deterministic, country-keyed, closed, and role safe.
- Required CI remains offline and provider-free.
- Do not modify dependencies, lockfiles, Dockerfiles, Compose, DRA producer code, or published release artifacts.
- Every task uses RED before implementation, targeted GREEN after implementation, and a semantic local commit.
- If implementation needs a file outside the exact task lists or changes an approved contract, stop for authority review instead of silently expanding scope.

## Execution Preflight and Commit Protocol

Before Task 1, bind the authority-supplied merged PR 1 base and fail closed:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
: "${EXPECTED_BASE_SHA:?authority-approved merged PR 1 SHA required}"
test "$(git rev-parse HEAD)" = "$EXPECTED_BASE_SHA"
make doctor MODE=dev
uv sync --locked
test "$(uv run alembic heads | awk '{print $1}')" = "0011"
```

Record `EXPECTED_BASE_SHA` as `BASE_SHA`. Any dirty tree, base drift, or
migration-head mismatch stops before RED.

Before every task commit, run `git diff --check`, review the exact task paths,
stage only the listed paths, then run `git diff --cached --name-only`,
`git diff --cached --check`, and `git diff --cached`. After the final commit,
review `BASE_SHA..HEAD` and require a clean worktree. A RED run is valid only
when the intended assertion fails after successful collection; zero selection,
collection errors, and environment failures are stop conditions.

Before and after every Docker-backed gate, run the default
`make doctor MODE=dev` and record:

```bash
docker compose ls --all --format json
docker ps -a --no-trunc --format json
docker image ls --digests --no-trunc --format json
docker buildx du --format json
docker network ls --no-trunc --format json
docker volume ls --format json
```

Use one inline `COMPOSE_PROJECT_NAME` on every project-scoped command; do not
export it. Teardown with
`docker compose down --volumes --remove-orphans --rmi local`, verify the exact
project has no container, network, volume, or local image residue, then
separately verify the default Compose inventory. Preserve
`night-voyager_postgres-data`, shared images, and shared BuildKit cache.

---

### Task 1: Freeze revision-lineage and comparison domain contracts

**Files:**
- Create: `src/night_voyager/planning/revision.py`
- Modify: `src/night_voyager/planning/__init__.py`
- Create: `tests/unit/planning/test_revision.py`
- Modify: `tests/unit/tasks/test_application.py`
- Modify: `tests/architecture/test_m3a_contract.py`

**Interfaces:**
- Produces: `PlanningRevisionLineageV1`.
- Produces: `PlanningRevisionDelta`, `PlanningRevisionCountryComparisonV1`, `PlanningRevisionComparisonV1`.
- Produces: the closed `PreferredCountriesFactDeltaV1 | FamilyBudgetFactDeltaV1`
  discriminated union.
- Produces: `build_planning_revision_comparison(...)`.
- Preserves: HTTP task create body; predecessor is repository-owned.
- Supplies: the exact model consumed by the connected read model in Task 4.

- [ ] **Step 1: Add RED tests for closed lineage and comparison**

Add the exact lineage model:

```python
class PlanningRevisionLineageV1(FrozenModel):
    schema_version: Literal[1]
    case_id: UUID
    previous_revision: PositiveInt
    current_revision: PositiveInt
    request_revision_review_id: UUID
    predecessor_planning_run_id: UUID

    @model_validator(mode="after")
    def adjacent_revision(self) -> Self:
        if self.current_revision != self.previous_revision + 1:
            raise ValueError("planning_revision_not_adjacent")
        return self
```

Add comparison tests for:

- Malaysia removed;
- Australia and Japan unchanged or changed;
- lowered family budget with a blocked successor;
- canonical country order;
- unknown or duplicate countries;
- unchanged, malformed, or unsupported changed-fact values;
- mismatched predecessor/successor;
- blocked current run sets `approval_eligible=False`;
- caller cannot supply `approval_eligible`.
- known predecessor/current `PlanningResult` hashes;
- tampered run state, top-level reason, route, comparison dimension, and
  evidence-use row.

- [ ] **Step 2: Run model RED**

Run:

```bash
uv run pytest -q \
  tests/unit/planning/test_revision.py \
  tests/unit/tasks/test_application.py \
  -k "revision or predecessor or comparison"
```

Expected: test collection succeeds, then assertions fail because the revision
module and task-lineage models do not exist. If the new imports cannot collect,
add only the minimal empty module/export surface needed for collection, rerun,
and record the assertion RED; an import or collection error is not RED
evidence.

- [ ] **Step 3: Implement the pure comparison types**

Import `Annotated`, `Field`, `StringConstraints`, and the existing
`BudgetEnvelope`; then use closed enums and discriminated fact-delta models:

```python
class PlanningRevisionDelta(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


PlanningReasonCode = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_]{0,99}$",
    ),
]


class PreferredCountriesFactDeltaV1(FrozenModel):
    fact_key: Literal["student.preferred_countries"]
    previous_value: tuple[Country, ...]
    current_value: tuple[Country, ...]


class FamilyBudgetFactDeltaV1(FrozenModel):
    fact_key: Literal["family.budget"]
    previous_value: BudgetEnvelope
    current_value: BudgetEnvelope


PlanningRevisionFactDeltaV1 = Annotated[
    PreferredCountriesFactDeltaV1 | FamilyBudgetFactDeltaV1,
    Field(discriminator="fact_key"),
]


class PlanningRevisionCountryComparisonV1(FrozenModel):
    country: Country
    delta: PlanningRevisionDelta
    previous_outcome: RouteOutcome | None
    previous_reason_code: PlanningReasonCode | None
    current_outcome: RouteOutcome | None
    current_reason_code: PlanningReasonCode | None


class PlanningRevisionComparisonV1(FrozenModel):
    schema: Literal["night-voyager.planning-revision-comparison.v1"]
    case_id: UUID
    previous_revision: PositiveInt
    current_revision: PositiveInt
    previous_planning_run_id: UUID
    current_planning_run_id: UUID
    previous_output_sha256: Sha256
    current_output_sha256: Sha256
    changed_fact: PlanningRevisionFactDeltaV1
    countries: tuple[PlanningRevisionCountryComparisonV1, ...]
    current_run_state: Literal["review_required", "blocked"]
    approval_eligible: bool
```

Both fact-delta variants reject equal values. Preferred countries retain the
existing non-empty sorted-unique contract; budget values reuse `BudgetEnvelope`
and remain visible only in the assigned-advisor projection.

Define an internal `PersistedPlanningResultProjectionV1` that reconstructs the
complete predecessor or current `PlanningResult` from the run, route,
comparison-dimension, and evidence-use rows in the original policy order.
`build_planning_revision_comparison` accepts the typed changed-fact delta plus
two validated projections and their persisted `PlanningRun.output_sha256`
values. It validates each reconstructed `PlanningResult`, hashes its canonical
`model_dump(mode="json")` bytes with the existing planning hash algorithm, and
requires an exact match before deriving country deltas and
`approval_eligible`. HTTP callers and browsers cannot submit any projection
row or output hash.

Do not hash the public comparison or a route-only tuple as a substitute for the
persisted planning result. Add known-hash fixtures plus separate
counterfactuals for state, top-level reason, route, comparison dimension, and
evidence-use tampering while the stored hash remains unchanged.

- [ ] **Step 4: Bind task input semantics**

Keep `CreateTaskCommand` free of predecessor fields. Document and test that:

```python
assert "predecessor_planning_run_id" not in CreateTaskCommand.model_fields
```

Keep `WorkerTaskInput.supersedes_run_id` as the adapter-facing field for minimal
compatibility, but require it to be repository-populated from the task's durable
`predecessor_planning_run_id`.

- [ ] **Step 5: Run model GREEN**

Run:

```bash
uv run pytest -q \
  tests/unit/planning/test_revision.py \
  tests/unit/tasks/test_application.py \
  tests/architecture/test_m3a_contract.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit the domain contract**

```bash
git add \
  src/night_voyager/planning/revision.py \
  src/night_voyager/planning/__init__.py \
  tests/unit/planning/test_revision.py \
  tests/unit/tasks/test_application.py \
  tests/architecture/test_m3a_contract.py
git commit -m "feat: freeze planning revision lineage contracts"
```

### Task 2: Add migration `0012` and atomic revision authority

**Files:**
- Create: `migrations/versions/0012_versioned_planning_revision.py`
- Modify: `src/night_voyager/collaboration/postgres.py`
- Create: `tests/integration/planning/test_revision_migration.py`
- Create: `tests/integration/planning/test_revision_authority.py`
- Modify: `tests/integration/collaboration/test_postgres_collaboration.py`
- Modify: `tests/integration/collaboration/test_collaboration_concurrency.py`
- Modify: `tests/integration/collaboration/test_collaboration_rollback.py`
- Modify: `tests/integration/decision/test_postgres_decision.py`
- Modify: `tests/integration/decision/test_http_decision.py`
- Modify: `tests/security/test_collaboration_catalog.py`
- Modify: `tests/security/test_m3b_catalog.py`
- Modify: `tests/security/test_m3a_catalog.py`
- Modify: `tests/security/test_m4a_catalog.py`
- Modify: `tests/security/test_rls_isolation.py`
- Create: `tests/integration/planning/test_revision_query_plan.py`
- Modify: `tests/integration/tasks/test_planning_start_authority.py`
- Modify: `tests/integration/tasks/test_postgres_tasks.py`
- Modify: `tests/integration/tasks/test_worker_authority.py`
- Modify: `scripts/run_db_tests.sh`
- Modify: `scripts/run_collaboration_db_tests.sh`

**Interfaces:**
- Consumes: `request_revision` review and existing collaboration fact verification.
- Produces: revision columns `revision_requested_by_review_id` and `superseded_planning_run_id`.
- Produces: task column `predecessor_planning_run_id`.
- Produces: migration functions that create one atomic revision-lineage tuple.
- Produces: database uniqueness for one Case revision and one PlanningRun
  successor per predecessor.
- Preserves: initial-revision and non-revision fact confirmation behaviour.

- [ ] **Step 1: Add migration RED tests**

Require the three columns and closed nullability:

```python
def test_revision_lineage_columns_exist(catalog) -> None:
    assert {
        "revision_requested_by_review_id",
        "superseded_planning_run_id",
    } <= catalog.columns("app.student_case_revisions")
    assert {
        "predecessor_planning_run_id",
    } <= catalog.columns("app.agent_tasks")
```

Add real PostgreSQL scenarios:

1. request revision then confirm preferred countries;
2. confirm without request revision;
3. request review from an old run;
4. cross-Case predecessor;
5. concurrent confirmations;
6. rollback after fact insert, revision insert, predecessor invalidation, and
   idempotency write;
7. downgrade with lineage history.
8. a second revision or PlanningRun successor for one predecessor.
9. bounded query-plan access over multiple historical revisions, tasks, runs,
   reviews, and briefs.
10. same-key/same-payload and same-key/different-payload revision requests.
11. a two-connection, different-key request-revision race.
12. wrong caller predecessor at task finalization, same-task lost
    acknowledgement, and duplicate-successor persistence.
13. exact before/after catalog parity for refused downgrade plus a separate
    safe downgrade/re-upgrade round trip.

In the same test-first change, extend `scripts/run_db_tests.sh` with the closed
outer command:

```text
scripts/run_db_tests.sh planning-revision authority|worker|projection|all
```

Each inside suite must use
`PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database`
with these exact task-owned database paths:

- `authority`: `tests/integration/planning/test_revision_migration.py`,
  `tests/integration/planning/test_revision_authority.py`,
  `tests/integration/collaboration/test_postgres_collaboration.py`,
  `tests/integration/collaboration/test_collaboration_concurrency.py`,
  `tests/integration/collaboration/test_collaboration_rollback.py`,
  `tests/integration/decision/test_postgres_decision.py`,
  `tests/integration/decision/test_http_decision.py`,
  `tests/integration/tasks/test_planning_start_authority.py`,
  `tests/integration/tasks/test_postgres_tasks.py`,
  `tests/integration/tasks/test_worker_authority.py`,
  `tests/integration/planning/test_revision_query_plan.py`, and
  `tests/security/test_rls_isolation.py`.
- `worker`: `tests/integration/tasks/test_planning_start_authority.py`,
  `tests/integration/tasks/test_postgres_tasks.py`,
  `tests/integration/tasks/test_worker.py`,
  `tests/integration/tasks/test_worker_authority.py`, and
  `tests/integration/tasks/test_mixed_downgrade.py`.
- `projection`:
  `tests/integration/connected_demo/test_postgres_read_models.py`,
  `tests/integration/connected_demo/test_http_read_models.py`, and
  `tests/integration/planning/test_revision_query_plan.py`.

`all` runs the three suites serially. Unknown or missing submodes exit `2`
before Docker mutation and never fall through to the repository-wide database
suite. Static catalog tests remain outside these marked database lanes.

- [ ] **Step 2: Run database RED**

Run:

```bash
uv run pytest -q \
  tests/security/test_collaboration_catalog.py \
  tests/security/test_m3b_catalog.py
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-red-$$" \
  scripts/run_db_tests.sh planning-revision authority
```

Expected: successful collection followed by failures for missing migration,
columns, constraints, and function behaviour. Zero selected tests, collection
errors, and Docker/environment failures are not valid RED evidence.

- [ ] **Step 3: Implement migration `0012`**

The migration must:

- add the lineage columns and composite foreign keys;
- require both revision lineage columns together;
- require both null for initial revisions;
- add a unique successor constraint for each predecessor;
- add a partial unique index on non-null
  `planning_runs(organization_id,supersedes_run_id)`;
- add a partial unique index on
  `advisor_reviews(organization_id,planning_run_id)` where
  `action='request_revision'`;
- add the task predecessor foreign key;
- add `agent_tasks_case_revision_read_idx` on
  `(organization_id,case_id,case_revision,created_at DESC,id)`;
- add `advisor_reviews_case_revision_run_idx` on
  `(organization_id,case_id,case_revision,planning_run_id,review_version DESC)`;
- redefine and freeze every migration-owned SQL authority function touched by
  the flow: `review_planning_run`, fact confirmation, `create_agent_task`, task
  finalization, and PlanningRun persistence;
- preserve RLS, fixed search paths, and grants;
- deny worker and public direct execution of business transitions;
- fail downgrade when lineage history or revision tasks exist;
- restore exact `0011` function signatures and grants on safe downgrade.

Use a partial unique index equivalent to:

```sql
CREATE UNIQUE INDEX student_case_revisions_one_planning_successor
ON app.student_case_revisions(
  organization_id,
  case_id,
  superseded_planning_run_id
)
WHERE superseded_planning_run_id IS NOT NULL;
```

Also add:

```sql
CREATE UNIQUE INDEX planning_runs_one_successor
ON app.planning_runs(organization_id, supersedes_run_id)
WHERE supersedes_run_id IS NOT NULL;
```

Also add:

```sql
CREATE UNIQUE INDEX advisor_reviews_one_request_revision_per_run
ON app.advisor_reviews(organization_id, planning_run_id)
WHERE action = 'request_revision';
```

The request-review function locks Case then PlanningRun in that fixed order and
rechecks Case state, revision, and current-run identity. It uses the partial
unique index as the final authority; a losing different-key insert maps to one
stable public conflict rather than leaking `23505`.

The task finalizer locks the durable task row, requires any compatibility
caller parameter to be `IS NOT DISTINCT FROM
task.predecessor_planning_run_id`, and supplies only the task-owned value to
PlanningRun persistence. Freeze the exact signatures, fixed search paths, and
API/worker/PUBLIC ACL for all five functions. Safe downgrade must restore exact
`0011` bodies and grants and remove the two `0012` partial unique indexes.

Extend `scripts/run_db_tests.sh` so current-head assertions advance to `0012`
while the explicit historical `0009`, `0010`, and `0011` checkpoints remain.
Extend `scripts/run_collaboration_db_tests.sh` with one isolated
revision-migration/authority lane that starts from `0011`, exercises `0012`
upgrade, safe downgrade, refusal with lineage history, and returns to `0012`.
Keep the existing repository, HTTP, collaboration-authority, and historical
downgrade scenarios intact.

For refusal proof, snapshot and exact-compare the Alembic version, columns,
constraints, indexes, function definitions, ACL/search-path configuration,
RLS/trigger flags, and relevant rows before and after the refusal. Run safe
downgrade/re-upgrade in a separate empty-history database.

The real PostgreSQL query-plan regression must verify index-backed access for:

- current revision through the existing
  `student_case_revisions(organization_id,case_id,revision)` primary key;
- predecessor to the unique successor;
- Case plus revision to the exact task/current run;
- review and current brief to the exact current run.

Seed a fixed minimum cardinality across multiple Cases and revisions, then run
`ANALYZE`. First assert that the query returns exactly the predecessor/current
run ids. Check the natural `EXPLAIN (FORMAT JSON)` plan, then use
`SET LOCAL enable_seqscan=off` only to prove the named indexes are usable,
paired with exact catalog assertions. The test must not assert a wall-clock
latency SLA or treat a legal small-table sequential scan as a failure.

- [ ] **Step 4: Make request revision preserve the predecessor until confirmation**

Successful `request_revision`:

- inserts one immutable review;
- changes Case `advisor_review -> planning`;
- does not invalidate the predecessor;
- does not create a task;
- does not create a new revision.

It rejects decided/plan-ready state, stale revision/run, unassigned advisor,
and duplicate authority. Same-key/same-payload replays the original review;
same-key/different-payload returns the public idempotency conflict. In a
different-key race, at most one request review, audit row, and authority result
may survive.

- [ ] **Step 5: Make fact confirmation create lineage atomically**

For a Case in planning with a current predecessor and a valid
`request_revision` review, the confirmation transaction must:

```sql
INSERT INTO app.student_case_revisions(
  organization_id,
  case_id,
  revision,
  student_preferences,
  family_preferences,
  revision_requested_by_review_id,
  superseded_planning_run_id
) VALUES (...);

UPDATE app.planning_runs
SET is_current = false
WHERE organization_id = p_org
  AND id = predecessor.id
  AND is_current;
```

It then inserts complete fact refs, updates Case revision, writes audit and
idempotency rows, and returns one response. Injected failure at any step must
leave every table unchanged.

- [ ] **Step 6: Run authority GREEN**

Run:

```bash
make collaboration-db-check SUITE=authority
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-authority-$$" \
  scripts/run_db_tests.sh planning-revision authority
```

Expected: revision, concurrency, idempotency, RLS, rollback, and review paths pass.

- [ ] **Step 7: Commit migration authority**

```bash
git add \
  migrations/versions/0012_versioned_planning_revision.py \
  src/night_voyager/collaboration/postgres.py \
  tests/integration/planning/test_revision_migration.py \
  tests/integration/planning/test_revision_authority.py \
  tests/integration/planning/test_revision_query_plan.py \
  tests/integration/collaboration/test_postgres_collaboration.py \
  tests/integration/collaboration/test_collaboration_concurrency.py \
  tests/integration/collaboration/test_collaboration_rollback.py \
  tests/integration/decision/test_postgres_decision.py \
  tests/integration/decision/test_http_decision.py \
  tests/security/test_collaboration_catalog.py \
  tests/security/test_m3b_catalog.py \
  tests/security/test_m3a_catalog.py \
  tests/security/test_m4a_catalog.py \
  tests/security/test_rls_isolation.py \
  tests/integration/tasks/test_planning_start_authority.py \
  tests/integration/tasks/test_postgres_tasks.py \
  tests/integration/tasks/test_worker_authority.py \
  scripts/run_db_tests.sh \
  scripts/run_collaboration_db_tests.sh
git commit -m "feat: add atomic planning revision authority"
```

### Task 3: Freeze the predecessor in AgentTask and persist one successor

**Files:**
- Modify: `src/night_voyager/tasks/postgres.py`
- Modify: `tests/unit/tasks/test_postgres.py`
- Modify: `tests/unit/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_planning_start_authority.py`
- Modify: `tests/integration/tasks/test_postgres_tasks.py`
- Modify: `tests/integration/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_worker_authority.py`
- Modify: `tests/integration/tasks/test_mixed_downgrade.py`
- Modify: `tests/security/test_m4a_catalog.py`
- Modify: `tests/security/test_m3a_catalog.py`

**Interfaces:**
- Consumes: revision-owned `superseded_planning_run_id`.
- Produces: task-owned `predecessor_planning_run_id`.
- Supplies: `WorkerTaskInput.supersedes_run_id` from the task row.
- Produces: one successor `PlanningRun.supersedes_run_id`.

- [ ] **Step 1: Add worker-time inference RED regression**

Replace the current permissive test with one that makes the predecessor
non-current before worker load and requires:

```python
loaded = await repository.load(claim)
assert loaded.supersedes_run_id == PREDECESSOR_RUN_ID
assert "SELECT r.id FROM app.planning_runs" not in captured_worker_load_sql
```

Add real PostgreSQL tests that remove all current predecessor rows after task
creation and prove the task still loads the frozen predecessor.
Add a revision-task lease-expiry/reclaim scenario that proves the same task id
retains the same predecessor, only one execution wins, and only one successor
PlanningRun exists.

- [ ] **Step 2: Run task RED**

Run:

```bash
uv run pytest -q \
  tests/unit/tasks/test_postgres.py \
  tests/unit/tasks/test_worker.py \
  -k "predecessor or supersedes or revision"
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-worker-red-$$" \
  scripts/run_db_tests.sh planning-revision worker
```

Expected: failures because worker load still queries the current PlanningRun.

- [ ] **Step 3: Consume the migration-owned task predecessor**

Use the `0012` task-creation contract established in Task 2. The adapter must
prove that the function:

- locks the current Case revision;
- reads `superseded_planning_run_id`;
- validates state `planning`;
- inserts it into `agent_tasks.predecessor_planning_run_id`;
- never accepts it from HTTP;
- replays the exact stored task for same-key/same-payload.

Initial planning tasks store null.

- [ ] **Step 4: Load only the task-owned predecessor**

Change `PostgresWorkerTaskRepository.load` SQL to select:

```sql
t.predecessor_planning_run_id AS supersedes_run_id
```

Delete the scalar subquery that searches current runs.

- [ ] **Step 5: Persist through the migration-owned successor authority**

Call the `0012` finalizer/persistence contract from Task 2. A revision task
requires:

- predecessor matches task and revision lineage;
- predecessor is already non-current;
- no successor exists;
- new run revision is predecessor revision + 1.

Insert the new run with exact `supersedes_run_id`; do not issue a second
predecessor update.

Initial planning keeps the existing null-predecessor behaviour.
Add adapter-level wrong-predecessor, same-task lost-ack, lease
expiry/reclaim, and duplicate-successor regressions; none may bypass or
redefine migration-owned SQL.

- [ ] **Step 6: Run worker and database GREEN**

Run:

```bash
uv run pytest -q \
  tests/unit/tasks/test_postgres.py \
  tests/unit/tasks/test_worker.py
uv run pytest -q \
  tests/security/test_m4a_catalog.py \
  tests/security/test_m3a_catalog.py
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-worker-green-$$" \
  scripts/run_db_tests.sh planning-revision worker
```

Expected: initial and revision tasks, worker recovery, lease loss, lost acknowledgement,
and one-successor authority all pass.

- [ ] **Step 7: Commit task and worker lineage**

```bash
git add \
  src/night_voyager/tasks/postgres.py \
  tests/unit/tasks/test_postgres.py \
  tests/unit/tasks/test_worker.py \
  tests/integration/tasks/test_planning_start_authority.py \
  tests/integration/tasks/test_postgres_tasks.py \
  tests/integration/tasks/test_worker.py \
  tests/integration/tasks/test_worker_authority.py \
  tests/integration/tasks/test_mixed_downgrade.py \
  tests/security/test_m4a_catalog.py \
  tests/security/test_m3a_catalog.py
git commit -m "feat: persist planning task lineage"
```

### Task 4: Project the authoritative old/new comparison

**Files:**
- Modify: `src/night_voyager/planning/revision.py`
- Modify: `src/night_voyager/connected_demo/models.py`
- Modify: `src/night_voyager/connected_demo/postgres.py`
- Modify: `src/night_voyager/connected_demo/ports.py`
- Modify: `src/night_voyager/connected_demo/application.py`
- Modify: `src/night_voyager/interfaces/http/connected_demo.py`
- Modify: `tests/unit/connected_demo/test_models.py`
- Modify: `tests/unit/connected_demo/test_application.py`
- Modify: `tests/unit/planning/test_revision.py`
- Modify: `tests/integration/connected_demo/test_postgres_read_models.py`
- Modify: `tests/integration/connected_demo/test_http_read_models.py`
- Modify: `tests/integration/planning/test_revision_query_plan.py`
- Modify: `tests/architecture/test_m5_contract.py`

**Interfaces:**
- Consumes: `PlanningRevisionComparisonV1` and durable revision lineage.
- Produces: the exact snake-case `DemoPhaseV2` revision phase contract.
- Produces: `PublicPlanningRunProjectionV2` with
  `review_required | blocked`.
- Produces: `AdvisorLedgerV2` with current-revision task selection and optional comparison.
- Produces: participant-safe `ConnectedJourneyStatusV1` for reload and
  lost-ack recovery.
- Produces: a family-safe current-brief revision context derived from the exact
  current revision, PlanningRun, DecisionBrief, and advisor approval.
- Preserves: V1 as the default response for the existing advisor-ledger and
  current-decision-brief routes; `contract_version=2` explicitly selects V2.
- Adds: read-only `GET /api/v1/cases/{case_id}/journey-status`.
- Supplies: PR 3 frontend contracts.

- [ ] **Step 1: Add current-revision ledger RED tests**

Seed:

- revision 1 predecessor task/run;
- request-revision review;
- revision 2 successor task/run;
- the revision 1 task created later than another historical row.

Require the ledger to select revision 2 by authority, not timestamp:

```python
assert ledger.case_revision == 2
assert ledger.task.task_id == revision_2_task_id
assert ledger.planning_run.planning_run_id == revision_2_run_id
assert ledger.comparison.previous_planning_run_id == revision_1_run_id
assert current_brief.revision_context.current_case_revision == 2
assert current_brief.revision_context.planning_version == "revised"
assert (
    current_brief.revision_context.advisor_authorization
    == "renewed_for_current_revision"
)
```

Add blocked-run, missing route, duplicate country, and old-review counterfactuals.
Require the exact phase union from the approved design and reject unknown,
hyphenated, or stale-phase aliases.

Require both planning-output hashes to equal the canonical complete
`PlanningResult` reconstructed from the two retained runs. Add separate
correct-run-id counterfactuals for tampered run state, top-level reason, route,
comparison dimension, and evidence-use rows, plus a bounded-history case that
would expose an accidental full-history scan. Add
family-brief counterfactuals for an old advisor review, a review bound to the
wrong run, a stale Case revision, and any attempt to infer renewed authorization
from browser recovery metadata.

Require:

- default advisor-ledger/current-brief responses remain exact V1;
- `contract_version=2` returns only the exact V2 schema;
- missing, repeated, empty, or unknown negotiation values fail closed;
- every assigned advisor/student/parent receives only
  `ConnectedJourneyStatusV1`;
- unassigned and cross-tenant actors receive the existing role-safe 404;
- student/parent status contains no task, run, review, route, Evidence,
  candidate, or authority ids.

- [ ] **Step 2: Run read-model RED**

Run:

```bash
uv run pytest -q \
  tests/unit/connected_demo/test_models.py \
  tests/unit/connected_demo/test_application.py \
  tests/unit/planning/test_revision.py \
  -k "revision or comparison or current"
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-projection-red-$$" \
  scripts/run_db_tests.sh planning-revision projection
```

Expected: failures because `AdvisorLedgerV1` has no comparison and SQL selects the latest task overall.

- [ ] **Step 3: Add `AdvisorLedgerV2`**

Version the phase and planning-run projection first:

```python
class DemoPhaseV2(StrEnum):
    TASK_READY = "task_ready"
    ACTIVE_TASK = "active_task"
    REVIEW_REQUIRED = "review_required"
    REVISION_REQUESTED = "revision_requested"
    REVISION_FACT_PENDING = "revision_fact_pending"
    REPLAN_REQUIRED = "replan_required"
    REVISION_TASK_ACTIVE = "revision_task_active"
    REVISION_REVIEW_REQUIRED = "revision_review_required"
    REVISION_BLOCKED = "revision_blocked"
    FAMILY_REVIEW = "family_review"
    PLAN_READY = "plan_ready"
    TERMINAL_TASK_FAILURE = "terminal_task_failure"


class PublicPlanningRunProjectionV2(FrozenModel):
    planning_run_id: UUID
    state: Literal["review_required", "blocked"]
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"]
    source_snapshot_date: date


class FamilyRevisionContextV1(FrozenModel):
    schema: Literal["night-voyager.family-revision-context.v1"]
    current_case_revision: PositiveInt
    planning_version: Literal["initial", "revised"]
    advisor_authorization: Literal[
        "authorized_for_initial_revision",
        "renewed_for_current_revision",
    ]
```

Then version the ledger response:

```python
class AdvisorLedgerV2(FrozenModel):
    schema_version: Literal[2]
    proof_mode: Literal["synthetic-demo"]
    phase: DemoPhaseV2
    case_id: UUID
    case_revision: PositiveInt
    case_state: CaseState
    canonical_task_inputs: CanonicalDemoTaskInputs | None
    task: PublicTaskProjection | None
    planning_run: PublicPlanningRunProjectionV2 | None
    comparison: PlanningRevisionComparisonV1 | None
    routes: tuple[AdvisorRouteProjection, ...]
    evidence: tuple[EvidenceDisclosure, ...]
    review_inputs: AdvisorReviewInputs | None
    current_brief_id: UUID | None
    recovery: PublicRecoveryProjection | None
```

Keep strict phase validators. A comparison is required for every successor,
including a blocked revised run. Review inputs are required only for
`revision_review_required`; they are forbidden for `revision_blocked`.
Version the existing current-decision-brief response to include
`FamilyRevisionContextV1`. Keep V1 as the default on both existing routes and
return V2 only for one exact `contract_version=2` query value so PR 2 remains
compatible with the current V1 frontend and Compose proof.
`renewed_for_current_revision` is permitted only when the brief, current run,
current Case revision, and approving advisor review are the exact durable
chain. The browser cannot submit or derive this field.

Add the participant-safe recovery projection:

```python
class ConnectedJourneyStatusV1(FrozenModel):
    schema: Literal["night-voyager.connected-journey-status.v1"]
    case_id: UUID
    current_revision: PositiveInt
    phase: DemoPhaseV2
    active_role: Literal["advisor", "student", "parent"]
```

It is available only to assigned Case participants and contains no
advisor-only inputs, task/run/review ids, routes, Evidence, comparison, or
candidate data. Its phase and active role are derived from durable database
state, never from browser/session metadata.

- [ ] **Step 4: Make SQL revision-aware**

Change task selection from:

```sql
WHERE t.organization_id=:org AND t.case_id=:case
ORDER BY t.created_at DESC LIMIT 1
```

to an exact current-revision predicate:

```sql
WHERE t.organization_id=:org
  AND t.case_id=:case
  AND t.case_revision=:revision
ORDER BY t.created_at DESC, t.id
LIMIT 1
```

Load exactly the predecessor and current run plus all rows required to
reconstruct each complete `PlanningResult` in original policy order. Validate
and hash each internal `PersistedPlanningResultProjectionV1`, then call
`build_planning_revision_comparison` with the two verified projections and
persisted `PlanningRun.output_sha256` values. Do not hash a route-only tuple,
accept any projection row/hash from HTTP or browser input, scan complete Case
history, or expose the comparison to an unauthorized role.

Project the family revision context in the same bounded read transaction.
`planning_version="revised"` comes only from the current revision's durable
predecessor lineage. The renewed-authorization marker comes only from the
current approving review bound to that revision and run; timestamps, browser
recovery state, and the mere presence of a comparison are not authority.

Project `ConnectedJourneyStatusV1` through one bounded participant query. Its
query plan and role policy are tested for every durable phase and role.

Derive phase only from durable state:

```text
advisor_review + current initial run + no request review
  -> review_required
planning + request review + no new revision
  -> revision_requested
planning + request review + exact pending changed-fact candidate
  -> revision_fact_pending
planning + new revision + no task
  -> replan_required
planning + new revision + preparing task
  -> revision_task_active
advisor_review + successor reviewable
  -> revision_review_required
planning + successor blocked
  -> revision_blocked
family_review + current brief
  -> family_review
plan_ready + current decision/timeline
  -> plan_ready
```

Do not derive phase from timestamps or browser metadata.

- [ ] **Step 5: Run read-model GREEN**

Run:

```bash
uv run pytest -q \
  tests/unit/connected_demo/test_models.py \
  tests/unit/connected_demo/test_application.py \
  tests/unit/planning/test_revision.py \
  tests/architecture/test_m5_contract.py
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-projection-green-$$" \
  scripts/run_db_tests.sh planning-revision projection
```

Expected: initial and revision ledgers pass; old tasks and reviews never become current.

- [ ] **Step 6: Commit the projection**

```bash
git add \
  src/night_voyager/planning/revision.py \
  src/night_voyager/connected_demo/models.py \
  src/night_voyager/connected_demo/postgres.py \
  src/night_voyager/connected_demo/ports.py \
  src/night_voyager/connected_demo/application.py \
  src/night_voyager/interfaces/http/connected_demo.py \
  tests/unit/connected_demo/test_models.py \
  tests/unit/connected_demo/test_application.py \
  tests/unit/planning/test_revision.py \
  tests/integration/connected_demo/test_postgres_read_models.py \
  tests/integration/connected_demo/test_http_read_models.py \
  tests/integration/planning/test_revision_query_plan.py \
  tests/architecture/test_m5_contract.py
git commit -m "feat: project planning revision comparisons"
```

### Task 5: Document revision authority and run backend completion gates

**Files:**
- Create: `docs/decisions/0012-versioned-planning-revision-authority.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/operations/worker-and-sse.md`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/reference/collaboration-and-confirmed-facts.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md`
- Modify: `docs/superpowers/plans/2026-07-27-versioned-planning-revision-pr-2-implementation-plan.md`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: migration `0012`, durable task lineage, and comparison projection.
- Produces: current public authority documentation and final PR 2 evidence.
- Preserves: PR 3 as unimplemented and all release/live-provider non-claims.

- [ ] **Step 1: Add documentation RED assertions**

Require docs to state:

```text
request_revision review -> fact revision -> frozen task predecessor
worker never infers predecessor from current PlanningRun
one predecessor -> at most one successor
old run retained but non-authoritative
comparison is deterministic and country-keyed
V1 read routes remain default; contract_version=2 selects revision V2
journey-status is participant-safe recovery authority, not browser storage
PR 3 browser journey remains unimplemented
```

- [ ] **Step 2: Run documentation RED**

Run:

```bash
uv run pytest -q tests/architecture/test_documentation_governance.py
```

Expected: missing ADR/reference/status assertions fail.

- [ ] **Step 3: Publish backend authority documentation**

Document:

- transaction order;
- role and grant matrix;
- schema and downgrade guard;
- task/worker lineage;
- comparison contract;
- negotiated V1/V2 public HTTP shape and participant-safe journey status;
- failure and recovery taxonomy;
- explicit lack of browser journey and release.

Before the final documentation commit, run one targeted `document-release`
audit over reference, operations/how-to, ADR/explanation, README/docs-index
discoverability, exact commands, and the PR 3/non-release boundary. Record the
result in the PR `Documentation impact`. The operations documentation must also
expose `planning-revision authority|worker|projection|all`, with the exact
purpose of each focused mode.

- [ ] **Step 4: Run complete backend gates**

The task-level suites above are focused diagnostics. This block is the
authoritative final non-Compose evidence for PR 2:

```bash
uv lock --check
uv run ruff check .
uv run pyright
make db-check
make collaboration-db-check SUITE=authority
make check
make proof
uv run python scripts/verify_release.py --tree-mode development
git diff --check "$(git merge-base HEAD origin/main)"..HEAD
```

Expected: all commands exit zero.

- [ ] **Step 5: Run one normal task-scoped Compose proof**

After the formal host and Docker VM 8 GiB preflight:

```bash
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-$$" make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-$$" \
  docker compose --profile browser-proof \
  down --volumes --remove-orphans --rmi local
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-2-$$" docker compose ps --all
docker compose ps --all
```

Expected: backend revision regressions do not break existing connected,
collaboration, DRA, restart, SSE, or browser proofs; the exact task project and
default Compose inventories are empty after teardown. Record the global
pre/post inventories defined in the execution protocol and preserve
`night-voyager_postgres-data` plus shared images/cache.

- [ ] **Step 6: Verify boundaries and commit**

Confirm:

- migration `0011` and older migrations unchanged;
- dependencies, lockfiles, Dockerfiles, and Compose unchanged;
- no frontend runtime change;
- no provider, credential, tag, release, or deploy action.

Then commit:

```bash
git add \
  docs/decisions/0012-versioned-planning-revision-authority.md \
  docs/operations/database-roles.md \
  docs/operations/worker-and-sse.md \
  docs/reference/agent-tasks-and-events.md \
  docs/reference/collaboration-and-confirmed-facts.md \
  docs/reference/http-api-v1.md \
  docs/design/projection-matrix.md \
  docs/design/state-and-interaction-matrix.md \
  docs/superpowers/README.md \
  docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md \
  docs/superpowers/plans/2026-07-27-versioned-planning-revision-pr-2-implementation-plan.md \
  tests/architecture/test_documentation_governance.py \
  scripts/verify_release.py
git commit -m "docs: publish planning revision authority"
```

## PR 2 Completion Gate

Stop for authority review with:

- exact merged PR 1 base and migration head;
- exact final HEAD and ordered commits;
- changed-file list and diff stat;
- RED/GREEN evidence, including selected/passed/failed counts;
- migration, grants, RLS, downgrade, concurrency, rollback, and lost-ack evidence;
- predecessor/current/successor database rows;
- comparison canonical bytes;
- full gates with selected/passed/failed counts and Docker inventory; elapsed
  time is diagnostic only;
- explicit confirmation that frontend journey, provider, release, and deploy were not started.

Do not push or create a pull request until separate publication authorization.
