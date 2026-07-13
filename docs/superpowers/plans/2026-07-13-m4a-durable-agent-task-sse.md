# M4A Durable Agent Task, Lease, Worker, and SSE Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` task-by-task. Each
> behavioral, security, and concurrency slice follows test-first RED -> GREEN.

**Goal:** Add one deterministic, durable planning operation with PostgreSQL
lease/fencing, a functional worker, and authorized SSE replay.

**Architecture:** HTTP and worker adapters depend on application ports and pure
task/planning policy. PostgreSQL owns durable task, execution, event, lease, and
PlanningRun authority. External adapter work and SSE waits remain outside short
transactions.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI/Starlette, SQLAlchemy async,
asyncpg, Alembic, PostgreSQL 18, pytest, Docker Compose.

## Global constraints

- Preserve M2/M3A/M3B identity, RLS, Evidence, PlanningRun, AdvisorReview, and
  FamilyDecision authority.
- Use graph `0001 -> 0002 -> 0003 -> 0004`, three forced-RLS M4A app tables, and
  one payload-free internal dispatch table.
- Support only `generate_planning_run_v1` and `m3a-policy-v1`.
- Use lease 60 seconds, heartbeat 15 seconds, poll 1 second, SSE heartbeat 15
  seconds, three total attempts, and replay pages of at most 100 durable events.
- Bound payload to 1 MiB, narrative to 64 KiB, Evidence refs to 20, and countries
  to Australia, Japan, and Malaysia.
- Grant no direct runtime M4A DML or internal dispatch access, and no worker M3B
  mutation authority.
- Add no dependency, remote provider, credential, MKE/DRA/OpenClaw, BFF/frontend
  wiring, release, deployment, or production claim.

### Task 1: Freeze public contracts and architecture regressions

- Add architecture tests for exact public records, migration/storage, dispatch
  privacy, pure dependency direction, four HTTP routes, and M4B/M5 exclusions.
- Observe missing-record/implementation RED.
- Add this spec, plan, and ADR with public-neutral content.
- Make the record subset GREEN while keeping later implementation tests explicit.
- Commit the docs/static contract slice.

### Task 2: Add pure task policy and deterministic planning adapter

- Test exhaustive internal/public states, currentness, retry classification,
  attempt limits, payload/narrative/Evidence/country/schema/pin bounds, manifest
  drift, and adapter authority.
- Observe import/behavior RED.
- Implement `tasks/models.py`, `tasks/policy.py`, `tasks/ports.py`, adapter
  protocols, deterministic fixture adapter, and `fixtures/m4a/manifest.json`.
- Re-run focused M4A and existing M3A regressions, Ruff, and Pyright.
- Commit the pure/adapter slice.

### Task 3: Add migration 0004 and database authority

- Test graph/schema/storage, forced RLS, ownership, grants, payload-free dispatch,
  fixed SECURITY DEFINER search paths, downgrade, and release catalog counts.
- Add real runtime-role RED for idempotent create/conflict, two tenants, direct
  DML denial, claim uniqueness, generation fencing, heartbeat, reclaim, retry,
  cancellation, and contiguous events.
- Implement seed-free DDL and narrow assigned-advisor/worker functions.
- Verify repeated upgrade, `0004 -> 0003 -> 0004`, role isolation, and pool cleanup.
- Commit migration and database authority evidence.

### Task 4: Add application service and HTTP create/read/cancel

- Test fake-port services and real FastAPI/PostgreSQL session, assignment, role,
  Origin, CSRF, idempotency, pins, non-enumeration, and no-store behavior.
- Observe missing service/routes RED.
- Implement task errors, application service, PostgreSQL adapter, and the three
  non-streaming endpoints with exact request DTOs and SQLSTATE mapping.
- Re-run task HTTP, identity, and M3B HTTP regressions.
- Commit application/HTTP support.

### Task 5: Implement fenced worker execution and recovery

- Test adapter execution outside sessions, independent heartbeat, lease-loss
  discard, and lease-free waiting state.
- Add real two-worker claim, reclaim, stale finalize, cancel/complete,
  reclaim/finalize, restart, three-attempt exhaustion, and 100-task capacity RED.
- Implement `TaskWorker.run_once()` and bounded `run_forever()` plus the Compose
  worker entry point.
- Re-run worker/database and Compose contract tests.
- Commit worker/lease/recovery support.

### Task 6: Add authorized SSE replay and reconnect

- Test first replay, pagination, ordered IDs, malformed/negative/ahead cursors,
  cross-tenant and reconnect authorization, comments, terminal close, 25 clients,
  and 100-plus-event pagination.
- Observe missing stream behavior RED.
- Implement page-scoped reads and SSE framing without holding sessions while
  sleeping or yielding.
- Re-run SSE, HTTP, pool-cleanup, and restart tests.
- Commit SSE replay/reconnect support.

### Task 7: Add explicit seed, Compose proof, and documentation

- Test the separate task-ready synthetic Case and M4A manifest/proof contracts.
- Extend only explicit demo seed; keep migration 0004 seed-free and production
  fail-closed.
- Add bounded real HTTP -> worker -> PlanningRun -> SSE proof, restart durability,
  retained M3B probes, and isolated teardown.
- Update bilingual entry points, references, operations, and design projections
  with exact proof/non-proof boundaries and disconnected fixture-only `/demo`.
- Re-run focused proof and public-hygiene tests and commit.

### Task 8: Fresh closeout and local branch completion

- Run all focused M4A suites and fresh non-database pytest.
- Run lock, Ruff, Pyright, hashed build, frontend, PostgreSQL, proof, and Compose
  gates serially where they share Docker/ports.
- Tear down and verify no project containers/volumes remain.
- Inspect the complete base diff for scope, graph, RLS/grants, dispatch privacy,
  payload leakage, private paths, secrets, generated noise, dependency drift,
  and M4B/M5 artifacts.
- Fix findings through focused RED -> GREEN, rerun affected/full gates, create
  intentional local commits, confirm a clean worktree, and stop without push,
  PR, merge, tag, release, deployment, or branch/worktree cleanup.
