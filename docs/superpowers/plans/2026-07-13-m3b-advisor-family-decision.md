# M3B Advisor and Family Decision Implementation Plan

**Implementation status:** Complete. The unchecked tasks below preserve the historical
implementation recipe rather than current progress.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the immutable advisor-review, family-safe brief, explicit family decision, receipt, and deterministic timeline backend flow.

**Architecture:** Pure frozen Pydantic contracts and deterministic policy remain independent of frameworks. Application ports orchestrate PostgreSQL adapters; migration `0003` provides forced-RLS storage and narrow transactional authority functions. FastAPI resolves the existing opaque session into transaction-local actor context before calling the application service.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, SQLAlchemy async, Alembic, PostgreSQL 18, pytest, Ruff, Pyright.

## Global Constraints

- Preserve immutable M3A `PlanningRun.review_required` output and its provenance triggers.
- Exact migration graph `0001 -> 0002 -> 0003`, one head, and exactly eight M3B tables.
- No new dependencies, participant-management API, share token, frontend integration, remote provider, or production claim.
- Every behavioral or security slice records a real failing test before implementation.
- All records, docs, fixtures, commands, and commits remain public-neutral and synthetic-proof precise.

---

### Task 1: Pure decision contracts and deterministic policy

**Files:**
- Create: `src/night_voyager/decision/models.py`
- Create: `src/night_voyager/decision/policy.py`
- Create: `src/night_voyager/decision/hashing.py`
- Modify: `src/night_voyager/planning/models.py`
- Test: `tests/unit/decision/test_policy.py`

**Interfaces:**
- Consumes: M3A `Country`, `RouteOutcome`, `CaseState`, budget and route facts.
- Produces: versioned review/brief/decision DTOs, `canonical_request_sha256()`, `build_family_safe_brief()`, `validate_family_decision()`, and `build_timeline_plan()`.

- [ ] Write focused tests for role/participant authorization, eligible/blocked routes, risk acceptance, currentness pins, projection exclusion, Australia budget/trade-off validation, deterministic dates, transitions, and canonical hashes.
- [ ] Run `uv run pytest tests/unit/decision/test_policy.py -q` and record the expected import/behavior failures.
- [ ] Implement frozen exact-version models and pure functions with no framework/database imports.
- [ ] Re-run the focused test and `tests/unit/planning`; record GREEN.
- [ ] Commit exact pure-layer paths as one coherent change.

### Task 2: Migration `0003` authority boundary

**Files:**
- Create: `migrations/versions/0003_advisor_family_decision.py`
- Create: `tests/security/test_m3b_catalog.py`
- Create: `tests/architecture/test_m3b_contract.py`
- Modify: `tests/architecture/test_m3a_contract.py`

**Interfaces:**
- Consumes: M2 transaction-local context and M3A current Case/run/source/evidence/cost rows.
- Produces: eight named tenant tables plus narrow `review_planning_run`, `decide_family_brief`, and read functions with typed `NV003/NV006/NV007/NV008` failures.

- [ ] Add static architecture/catalog tests for the exact graph, tables, FKs, RLS, policies, grants, search paths, append-only guards, and downgrade scope.
- [ ] Run those tests and record RED because `0003` is absent.
- [ ] Implement seed-free DDL, Case-state extension, unique-current constraints, immutable triggers, narrow functions, grants, and downgrade restoration.
- [ ] Re-run architecture/security tests and record GREEN.
- [ ] Commit migration and static authority proof.

### Task 3: Application ports and PostgreSQL adapter

**Files:**
- Create: `src/night_voyager/decision/ports.py`
- Create: `src/night_voyager/decision/application.py`
- Create: `src/night_voyager/decision/postgres.py`
- Create: `src/night_voyager/decision/errors.py`
- Test: `tests/unit/decision/test_application.py`
- Test: `tests/integration/decision/test_postgres_decision.py`

**Interfaces:**
- Consumes: pure commands and transaction-local `ActorContext`.
- Produces: `DecisionService.review()`, `get_brief()`, `decide_direct()`, and `decide_as_advisor()` with typed stale/policy/idempotency errors.

- [ ] Write fake-port application tests and real-role PostgreSQL tests for assignments, tenants, context cleanup, append-only rows, stale/current conflicts, idempotency, concurrency, rollback, and downgrade/re-upgrade.
- [ ] Run focused tests and record RED for missing service/functions.
- [ ] Implement minimal service and SQLAlchemy adapter mapping typed SQLSTATEs without broad table writes.
- [ ] Re-run focused unit and disposable PostgreSQL integration suites; record GREEN.
- [ ] Commit application/database adapter and runtime proof.

### Task 4: Explicit synthetic participant seed

**Files:**
- Modify: `scripts/seed_demo.py`
- Modify: `src/night_voyager/identity/demo_seed.py`
- Test: `tests/unit/identity/test_seed_demo.py`
- Test: `tests/integration/decision/test_postgres_decision.py`

**Interfaces:**
- Consumes: the three existing synthetic demo principals and stable synthetic Case.
- Produces: an explicit idempotent seed assigning advisor, student, and parent; no participant HTTP API.

- [ ] Add failing validation/idempotency tests.
- [ ] Run them and record RED.
- [ ] Extend explicit development/test-only seed through a narrow idempotent database function.
- [ ] Re-run focused tests and record GREEN.
- [ ] Commit seed support separately.

### Task 5: HTTP v1 endpoints and problem contract

**Files:**
- Create: `src/night_voyager/interfaces/http/decision.py`
- Modify: `src/night_voyager/interfaces/http/dependencies.py`
- Modify: `src/night_voyager/api.py`
- Create: `tests/integration/decision/test_http_decision.py`
- Modify: `tests/unit/test_api.py`

**Interfaces:**
- Consumes: existing session cookie, Origin/CSRF helpers, session resolver, and `DecisionService`.
- Produces: the four frozen `/api/v1` routes, `Idempotency-Key`, no-store responses, and RFC 9457-style problem documents.

- [ ] Add real FastAPI/PostgreSQL tests for approve/reject/revise, brief read, direct/advisor-recorded decision, roles, assignment, session, Origin, CSRF, non-enumeration, stale and idempotency recovery.
- [ ] Run focused HTTP tests and record RED for absent routes.
- [ ] Implement exact request/response DTOs, transaction-local context, status mapping, and headers.
- [ ] Re-run HTTP and identity regression tests; record GREEN.
- [ ] Commit HTTP contract implementation.

### Task 6: Demo/Compose proof and documentation

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/reference/domain-and-source-manifests.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `scripts/verify_compose.sh`
- Modify: `Makefile`
- Test: `tests/architecture/test_compose_contract.py`

**Interfaces:**
- Consumes: complete M3B API and explicit synthetic seed.
- Produces: fresh-volume `0001 -> 0002 -> 0003` golden advisor-to-parent proof and precise public documentation.

- [ ] Add failing architecture/proof assertions for advisor approval, parent read/Australia decision, persistent receipt/timeline, Malaysia visibility/ineligibility, and empty teardown.
- [ ] Run focused proof tests and record RED.
- [ ] Implement proof commands and update bilingual/reference/operations/design docs, explicitly keeping `/demo` disconnected.
- [ ] Re-run focused proof and docs hygiene checks; record GREEN.
- [ ] Commit proof and documentation.

### Task 7: Fresh closeout and local branch completion

**Files:**
- Review: every path changed from `2d46bcdaccd5ec382feac8910e14d6c984332e36`.

**Interfaces:**
- Consumes: all prior task commits.
- Produces: clean local branch evidence suitable for authority review.

- [ ] Run focused unit/integration/security/architecture suites and `uv run pytest -q -m "not database"`.
- [ ] Run Ruff, Pyright, hashed wheel build, frontend lint/typecheck/test/build, `make db-check`, `make doctor MODE=dev`, `make check`, `make proof`, and `make compose-proof`.
- [ ] Run `make down`, verify `docker compose ps --all` is empty, then run `git diff --check`.
- [ ] Inspect the complete base diff for scope, generated noise, secrets, private paths, public claims, migration graph, functions, grants, RLS, and frontend disconnection.
- [ ] Make any required focused fix through RED→GREEN, create the final intentional local commit, and verify the worktree is clean without push/PR/merge/tag/release/deploy.
