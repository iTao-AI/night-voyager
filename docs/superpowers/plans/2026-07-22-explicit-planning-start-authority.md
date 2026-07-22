# Explicit Planning-Start Authority Implementation Plan

**Implementation status:** Implemented locally for authority review.

Tasks 1–6 have executable local evidence on the isolated implementation branch.
Independent authority review remains the closeout gate. PR 2 and PR 3 remain approved
but not implemented; no push, pull request, merge, release, or deployment is authorized
by this status.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` as the primary controller. If the implementation
> owner chooses isolated bounded lanes, use `superpowers:subagent-driven-development`
> instead, not in addition. Every behavioral slice follows test-first RED -> GREEN.

**Goal:** Make the first deterministic planning-task creation the atomic authority
that moves an assigned advisor's current Case from `intake` to `planning`, without
changing the existing task HTTP request/response contract or weakening Skill,
idempotency, tenant, revision, source-pack, and worker boundaries.

**Architecture:** Migration `0009_explicit_planning_start_authority.py` replaces only
the `app.create_agent_task(...)` function. It preserves the exact `0008` signature and
grant, locks the Case row, accepts `intake` only for
`generate_planning_run_v1`, and writes the Case transition, pinned `AgentTask`,
dispatch, first event, and idempotency result in one PostgreSQL transaction. The
existing FastAPI application service, repository call, worker, SSE, planning adapter,
and browser contracts remain consumers of the same public surface.

**Tech Stack:** Python 3.12, PostgreSQL 18.4, Alembic, SQLAlchemy async, asyncpg,
FastAPI, Pydantic, pytest, uv, Docker Compose, and the existing versioned-Skill and
durable AgentTask implementation.

## Global Constraints

- Start from clean `main` only after the approved design and three implementation
  plans are merged. Record the actual base SHA; do not reuse an older retained
  implementation worktree.
- PR 1 owns migration `0009`, explicit planning-start authority, its database and
  HTTP proof, ADR 0010, focused gate wiring, and affected references. It does not
  modify frontend files, BFF routes, session envelopes, DRA/MKE code, provider
  transport, dependency files, package versions, release records, or deployment.
- Do not edit historical migration `0008_versioned_skills.py`. Copy the exact prior
  `CREATE FUNCTION app.create_agent_task(...)` definition into `0009` as the
  downgrade definition and prove parity against a database actually downgraded to
  `0008`.
- Preserve the exact function signature:

  ```sql
  app.create_agent_task(
    uuid, uuid, uuid, uuid, text, integer, uuid, integer,
    text, jsonb, text, text
  )
  ```

- Preserve the existing API grant only to `night_voyager_api`; do not grant direct
  runtime DML or broaden `PUBLIC`, worker, or migrator authority.
- Keep idempotency replay before new-write validation. A same-key replay returns the
  original task and never repeats the Case transition. A changed request under the
  same key remains `NV008`.
- For new writes, acquire `FOR UPDATE` on the target Case. Accept:
  - `planning` for both existing operations under their existing evidence rules;
  - `intake` only for `generate_planning_run_v1`.
- Continue rejecting `generate_governed_mixed_planning_run_v1` from `intake`. This PR
  does not change the DRA promotion or governed-mixed sequence.
- The Case update happens only after actor, assignment, operation, revision,
  source-pack, active SkillVersion, complete manifest, pin, and effective-task checks
  succeed. The Case update and all task writes remain in the same transaction.
- No new public problem code, request field, response field, table, index, enum,
  queue, task operation, adapter, or event kind.
- Preserve `v0.1.2` release files and digests as immutable history. This is unreleased
  post-v0.1.2 work and does not select a future version.
- Use explicit path staging. Before every commit, compare
  `git diff --cached --name-only` with the Task allowlist and run
  `git diff --cached --check`.
- Before any Docker-heavy verification, run `make doctor MODE=dev` and record both
  host and Docker VM filesystem preflight. Use task-owned Compose project names,
  preserve retained data, run teardown, and record final container/project/image
  inventory. Broad prune or unrelated Docker cleanup requires separate authority.
- Keep all code, tests, docs, commit text, and output public-neutral. Never expose
  raw SQL errors, SQLSTATE, cookies, CSRF values, secrets, private paths, or private
  workflow metadata.

## Dependency and Ownership Map

This PR is serialized around one migration owner because the function definition,
downgrade copy, grant, migration runner, and concurrency/rollback proof are tightly
coupled. Optional bounded test lanes may inspect or add non-overlapping tests only;
they must not edit the migration or shared gate files.

```text
Task 1 contract RED
  -> Task 2 migration GREEN
  -> Task 3 authority/concurrency/rollback proof
  -> Task 4 downgrade and gate integration
  -> Task 5 docs and status
  -> Task 6 full verification and review handoff
```

Integration-owner files:

- `migrations/versions/0009_explicit_planning_start_authority.py`
- `scripts/run_db_tests.sh`
- `Makefile`
- `.github/workflows/ci.yml` only if an explicit new Make target must be routed
- shared architecture/security/release tests
- ADR/reference/index documents

No implementation lane may modify `0008_versioned_skills.py`.

---

### Task 1: Freeze the atomic planning-start contract

**Files:**

- Create: `tests/architecture/test_fact_to_plan_contract.py`
- Create: `tests/integration/tasks/test_planning_start_authority.py`
- Modify: `tests/integration/tasks/test_http_tasks.py`
- Reference only: `migrations/versions/0008_versioned_skills.py`
- Reference only: `src/night_voyager/interfaces/http/tasks.py`
- Reference only: `src/night_voyager/tasks/{models,application,postgres}.py`

**Contract:**

- The HTTP request remains `CreateAgentTaskRequest` with exact schema version,
  operation, expected Case revision, source pack, source-pack version, and policy.
- A new deterministic task on an assigned-advisor `intake` Case succeeds and returns
  the existing 202 projection.
- Confirmation alone leaves the Case in `intake` and creates no task.
- Successful first task creation leaves one `planning` Case, one pinned task, one
  dispatch row, one initial event, and one idempotency record.

- [x] **Step 1: Add architecture RED assertions**

  Assert that migration head is `0009`, only `0009` may replace the task function,
  the exact signature remains present, `FOR UPDATE` is required, the deterministic
  `intake` branch is explicit, the mixed operation cannot enter it, and the old
  migration remains unchanged relative to the PR base.

  ```python
  def test_0009_owns_only_the_explicit_first_planning_transition() -> None:
      migration = Path("migrations/versions/0009_explicit_planning_start_authority.py").read_text()
      assert 'revision = "0009"' in migration
      assert 'down_revision = "0008"' in migration
      assert "FOR UPDATE" in migration
      assert "p_operation='generate_planning_run_v1'" in migration
      assert "generate_governed_mixed_planning_run_v1" in migration
  ```

- [x] **Step 2: Add real PostgreSQL RED tests**

  Build an `intake` Case with exact revision/source/assignment/Skill seed. Call the
  existing SQL function as the API role and assert the desired atomic result. Add a
  companion test proving the Case is still `intake` before the call.

  ```python
  created = await api_connection.execute(
      text("SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,"
           "'generate_planning_run_v1',:revision,:pack,1,'m3a-policy-v1',"
           "CAST(:manifest AS jsonb),:request_hash,:key_hash)"),
      parameters,
  )
  assert created.mappings().one()["replayed"] is False
  assert await case_state(api_connection, case_id) == "planning"
  assert await task_authority_counts(api_connection, task_id) == (1, 1, 1, 1)
  ```

- [x] **Step 3: Add HTTP RED coverage**

  Use the existing opaque advisor session, CSRF, Origin, and idempotency headers.
  Prove response shape does not gain a transition flag or any new field.

- [x] **Step 4: Run RED**

  ```bash
  uv run pytest -q tests/architecture/test_fact_to_plan_contract.py
  make db-check
  ```

  Expected: architecture collection fails because `0009` is absent, and the
  PostgreSQL/HTTP cases fail with the existing stale-input conflict.

- [x] **Step 5: Commit tests only after the RED evidence is recorded**

  ```bash
  git add tests/architecture/test_fact_to_plan_contract.py \
    tests/integration/tasks/test_planning_start_authority.py \
    tests/integration/tasks/test_http_tasks.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "test: freeze explicit planning-start authority"
  ```

---

### Task 2: Implement migration 0009 as the single atomic authority gate

**Files:**

- Create: `migrations/versions/0009_explicit_planning_start_authority.py`
- Modify only if an executable head assertion requires it:
  `tests/architecture/test_fact_to_plan_contract.py`

**Implementation:**

- Export the new `CREATE_TASK_SQL`, exact `_0008_CREATE_TASK_SQL`, revoke/grant SQL,
  and `upgrade()` / `downgrade()` functions.
- In the new function, preserve all existing `0008` checks and introduce only:

  ```sql
  DECLARE starts_planning boolean := false;

  SELECT * INTO current_case
    FROM app.student_cases c
   WHERE c.organization_id=p_org AND c.id=p_case
   FOR UPDATE;

  IF NOT FOUND OR current_case.current_revision<>p_revision
     OR NOT EXISTS (
       SELECT 1 FROM app.source_packs s
        WHERE s.organization_id=p_org
          AND s.id=p_pack
          AND s.version=p_pack_version
     ) THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale';
  END IF;

  IF current_case.state='intake' AND p_operation='generate_planning_run_v1' THEN
    starts_planning := true;
  ELSIF current_case.state<>'planning' THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale';
  END IF;
  ```

- Keep the existing mixed-evidence predicate after the state decision. Before task
  insertion, perform the transition with an exact current-state/revision predicate:

  ```sql
  IF starts_planning THEN
    UPDATE app.student_cases
       SET state='planning', updated_at=clock_timestamp()
     WHERE organization_id=p_org AND id=p_case
       AND state='intake' AND current_revision=p_revision;
    IF NOT FOUND THEN
      RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale';
    END IF;
  END IF;
  ```

  Use the actual Case column set from the migration schema. Do not invent a
  `row_version` change if the table does not own that field.

- [x] **Step 1: Implement upgrade and downgrade**

  `upgrade()` drops the exact `0008` signature, creates the new function, revokes
  `PUBLIC`, and grants only `night_voyager_api`. `downgrade()` drops `0009`, restores
  the exact copied `0008` definition, applies the same revoke/grant boundary, and
  leaves all rows unchanged.

- [x] **Step 2: Run focused GREEN**

  ```bash
  uv run pytest -q tests/architecture/test_fact_to_plan_contract.py
  make db-check
  ```

  Expected: deterministic `intake` creation and existing `planning` paths pass;
  governed mixed from `intake` still fails.

- [x] **Step 3: Run static checks and commit**

  ```bash
  uv run ruff check migrations/versions/0009_explicit_planning_start_authority.py \
    tests/architecture/test_fact_to_plan_contract.py \
    tests/integration/tasks/test_planning_start_authority.py \
    tests/integration/tasks/test_http_tasks.py
  uv run pyright
  git add migrations/versions/0009_explicit_planning_start_authority.py \
    tests/architecture/test_fact_to_plan_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add atomic planning-start authority"
  ```

---

### Task 3: Prove authorization, concurrency, replay, and rollback

**Files:**

- Modify: `tests/integration/tasks/test_planning_start_authority.py`
- Modify: `tests/integration/tasks/test_http_tasks.py`
- Modify only when the existing helper belongs there:
  `tests/integration/tasks/test_postgres_tasks.py`
- Modify: `tests/integration/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_worker_authority.py`

**Required authority matrix:**

| Case | Expected result | Case state | New task authority |
| --- | --- | --- | --- |
| assigned advisor, deterministic, current `intake` | success | `planning` | exactly one complete set |
| same request/key replay | same task, `replayed=true` | `planning` | unchanged |
| same key, changed request | `NV008` / `idempotency_conflict` | unchanged | none |
| two first requests, different keys | one success, one effective conflict | `planning` | one set |
| parent/student/unassigned/cross-tenant | non-enumerating denial | `intake` | none |
| stale revision/source/manifest/pin | bounded conflict | `intake` | none |
| mixed operation from `intake` | governed boundary rejection | `intake` | none |
| deterministic from unsupported state | stale conflict | unchanged | none |
| injected write failure | exception | `intake` | zero residue |

- [x] **Step 1: Add authority-negative RED cases**

  Exercise runtime-equivalent roles, not database owner shortcuts. Count task,
  dispatch, event, idempotency, execution, and state rows after every failure.

- [x] **Step 2: Add two-connection concurrency RED**

  Hold the Case lock in connection A, start connection B with a different task/key,
  release A, and assert one success plus one existing bounded effective-task
  conflict. Prove one task/pin/dispatch/event/idempotency set and no execution before
  worker claim.

- [x] **Step 3: Add write-boundary rollback RED**

  Use transaction-local failing triggers or the repository's established injection
  pattern at each write boundary: Case update, task insert, dispatch insert, event
  append, idempotency insert. Each case must roll back the earlier Case transition.
  Drop every injected object inside `finally` / fixture teardown.

- [x] **Step 4: Prove worker consumes revision N+1**

  Confirm a `family.budget` fact, create the task from the resulting `intake`
  revision, claim it as the worker, and inspect the loaded
  `PersistedSyntheticSnapshotV1`. Assert the exact Case ID/revision and confirmed
  family budget, plus identical five-field task/execution Skill pins.

- [x] **Step 5: Run GREEN**

  ```bash
  make db-check
  uv run pytest -q -m "not database and not mke" \
    tests/unit/tasks tests/unit/test_api.py tests/architecture/test_fact_to_plan_contract.py
  ```

- [x] **Step 6: Commit**

  ```bash
  git add tests/integration/tasks/test_planning_start_authority.py \
    tests/integration/tasks/test_http_tasks.py \
    tests/integration/tasks/test_postgres_tasks.py \
    tests/integration/tasks/test_worker.py \
    tests/integration/tasks/test_worker_authority.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "test: prove planning-start transaction boundaries"
  ```

  Omit any unchanged path from the staging list.

---

### Task 4: Wire focused migration and release gates

**Files:**

- Modify: `scripts/run_db_tests.sh`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml` only if the new focused target is not already
  transitively exercised by `make check` / `make db-check`
- Modify: `scripts/verify_release.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `tests/security/test_m4a_catalog.py`
- Create: `tests/integration/tasks/test_planning_start_migration.py`

**Gate contract:**

- Replace hardcoded migration-head assertions from `0008` to `0009` where they mean
  current head; keep historical `0008` checks where they prove downgrade.
- Add one isolated `0009 -> 0008 -> 0009` lane that captures function definition,
  owner, ACL, and signature at each point.
- Add a focused `fact-to-plan-db-check` target only if it improves direct execution;
  it must call a real checked-in script and be included in `make db-check` or
  `make check`, not exist as an unused vanity target.

- [x] **Step 1: Write RED gate tests**

  Prove `make db-check` contains the exact new migration node and that the release
  verifier accepts exactly one Alembic head, `0009`. Mutation tests must fail if the
  focused downgrade/parity node is removed from the required command list.

- [x] **Step 2: Implement the isolated migration lane**

  Fresh database sequence:

  ```text
  upgrade 0008
  capture 0008 function/grant
  upgrade 0009
  prove intake first-task behavior
  downgrade 0008
  compare exact function/grant to the captured 0008 baseline
  upgrade 0009
  re-run focused authority assertions
  ```

- [x] **Step 3: Run gates**

  ```bash
  make db-check
  uv run pytest -q tests/unit/test_release_surface.py \
    tests/architecture/test_fact_to_plan_contract.py \
    tests/security/test_database_catalog.py tests/security/test_m4a_catalog.py
  uv run python scripts/verify_release.py --tree-mode development
  ```

- [x] **Step 4: Commit**

  ```bash
  git add scripts/run_db_tests.sh Makefile scripts/verify_release.py \
    tests/unit/test_release_surface.py tests/security/test_database_catalog.py \
    tests/security/test_m4a_catalog.py \
    tests/integration/tasks/test_planning_start_migration.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "test: integrate planning-start verification gates"
  ```

  Add `.github/workflows/ci.yml` only if it actually changed.

---

### Task 5: Record the explicit planning-start decision

**Files:**

- Create: `docs/decisions/0010-explicit-planning-start-authority.md`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/operations/worker-and-sse.md`
- Modify: `docs/superpowers/specs/2026-07-22-governed-fact-to-plan-closure-design.md`
- Modify: `docs/superpowers/plans/2026-07-22-explicit-planning-start-authority.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: `tests/architecture/test_documentation_governance.py`

**Documentation contract:**

- ADR 0010 explains why task creation, rather than confirmation or a separate state
  endpoint, owns the transition.
- References state that the public HTTP schema is unchanged and that deterministic
  first task creation may start `intake -> planning` atomically.
- Docs explicitly preserve mixed-from-intake rejection, no automatic planning, and
  no provider dependency.
- Status says PR 1 implemented only after executable evidence exists; PR 2 and PR 3
  remain approved but not implemented.

- [x] **Step 1: Add documentation RED assertions**

  Extend governance tests for ADR discoverability, migration-head truth, exact
  implementation status, and forbidden claims such as automatic planning or a new
  endpoint.

- [x] **Step 2: Run targeted documentation audit**

  Invoke GStack `document-release` against the affected contract. Use
  `document-generate` only if the audit finds a concrete missing document; do not
  generate empty Diataxis quadrants.

- [x] **Step 3: Update docs and run GREEN**

  ```bash
  uv run pytest -q tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  uv run python scripts/verify_release.py --tree-mode development
  git diff --check
  ```

- [x] **Step 4: Commit**

  ```bash
  git add docs/decisions/0010-explicit-planning-start-authority.md \
    docs/reference/agent-tasks-and-events.md docs/reference/http-api-v1.md \
    docs/operations/database-roles.md docs/operations/worker-and-sse.md \
    docs/superpowers/specs/2026-07-22-governed-fact-to-plan-closure-design.md \
    docs/superpowers/plans/2026-07-22-explicit-planning-start-authority.md \
    docs/README.md docs/superpowers/README.md \
    tests/architecture/test_documentation_governance.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "docs: record explicit planning-start authority"
  ```

---

### Task 6: Run full verification and prepare authority review

**Files:** None expected. If a gate reveals a defect, return to the responsible Task,
write a RED regression, fix it, and create a separate coherent follow-up commit.

- [x] **Step 1: Preflight**

  ```bash
  git status --short
  make doctor MODE=dev
  uv lock --check
  ```

  Record host and Docker VM filesystem evidence. Stop at the documented threshold;
  do not override or clean unrelated Docker resources.

- [x] **Step 2: Focused and static gates**

  ```bash
  uv run pytest -q tests/architecture/test_fact_to_plan_contract.py \
    tests/unit/test_release_surface.py
  uv run ruff check .
  uv run pyright
  make db-check
  ```

- [x] **Step 3: Full repository gates**

  ```bash
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  ```

  The required Compose flow remains local synthetic and provider-free. Use the
  repository's task-owned teardown; retain the approved data volume and unrelated
  resources.

- [x] **Step 4: Final diff and hygiene review**

  ```bash
  BASE=$(git merge-base HEAD origin/main)
  git diff --check "$BASE"..HEAD
  git diff --stat "$BASE"..HEAD
  git status --short
  uv run python scripts/verify_release.py --tree-mode development
  ```

  Review every changed file against this plan. Confirm no frontend, dependency,
  lockfile, version, release, DRA/MKE, live-provider, or unrelated migration diff.

- [x] **Step 5: Handoff**

  Keep the verified local branch/worktree clean for independent authority review.
  Report exact base/HEAD, ordered commits, RED -> GREEN evidence, migration and grant
  identity, full gate results, documentation impact, Docker inventory, and remaining
  risk. Do not push or create a PR without separate authorization.

## Acceptance Checklist

- [x] Existing task HTTP request and response shapes are unchanged.
- [x] Deterministic first task creation from current `intake` is atomic.
- [x] Confirmation alone does not create a task or enter `planning`.
- [x] Mixed planning from `intake` remains rejected.
- [x] Replay, conflict, authorization, concurrency, and rollback are proven against
  real PostgreSQL roles.
- [x] Worker input uses the exact new Case revision and confirmed fact.
- [x] Task and execution retain the complete five-field Skill pin.
- [x] `0009 -> 0008 -> 0009` restores function/grant parity without rewriting data.
- [x] Full local gates, teardown, hygiene, and documentation audit are green.
- [x] PR 2 and PR 3 remain unimplemented until this PR is merged and hosted-green.

## Not in Scope

- Browser handoff, localization, visual styling, or screenshot refresh.
- New public error codes, endpoints, task operations, workers, queues, or providers.
- DRA/MKE execution, live-provider proof, release, deployment, or production claims.
- Automatic planning during confirmation.
