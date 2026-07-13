# M4A Durable Agent Task, PostgreSQL Lease, Worker, and SSE Design

## Goal

M4A proves one bounded durable operation without remote credentials:

```text
assigned advisor mutation
  -> idempotent AgentTask create
  -> payload-free global dispatch claim
  -> tenant-scoped short transaction loads pinned input
  -> deterministic planning adapter outside the transaction
  -> existing M3A policy and PostgreSQL PlanningRun authority
  -> atomic task state plus AgentTaskEvent
  -> authorized SSE replay and reconnect
```

The only operation is
`generate_planning_run_v1(case_revision, source_pack_version, policy_version)`.
The local synthetic fixture ends in internal `waiting_review`, public
`needs_advisor_review`, and a current M3A `review_required` `PlanningRun`. It does
not approve the run, create a `DecisionBrief`, or make a family decision.

## Scope

M4A adds:

- pure task state, public projection, retry, and bounds policy;
- a Night Voyager-owned `PlanningAdapter` protocol and deterministic synthetic
  implementation that reuses the M3A fixture;
- durable `AgentTask`, `AgentExecution`, and `AgentTaskEvent` records;
- a payload-free internal dispatch record;
- PostgreSQL lease, monotonic generation fencing, heartbeat, reclaim, bounded
  retry, cancellation, and atomic finalization;
- a functional asyncio worker with short database transactions;
- assigned-advisor create, read, cancel, and SSE event endpoints;
- exact opaque-session, Origin, CSRF, idempotency, non-enumeration, and no-store
  boundaries;
- a separate task-ready synthetic Case;
- fresh PostgreSQL, bounded concurrency, restart, SSE replay, and Compose proof;
- public-neutral reference, operations, design, and bilingual entry-point updates.

M4B MKE consumption, DRA, OpenClaw, provider credentials, remote network calls,
M5 BFF/frontend wiring, `/demo` backend wiring, human-authority changes,
conversation/memory/Skill records, Redis, Celery, Temporal, Kafka, deployment,
release, and production claims remain outside M4A.

## Architecture

```text
FastAPI task routes       worker process
          |                    |
          v                    v
       TaskService       TaskWorker application service
          |                    |
          +------ task and adapter ports ------+
                                                |
                    pure task policy <----------+
                         |                      |
             PostgreSQL task adapter   deterministic planning adapter
                         |                      |
               existing M3A PlanningService and PostgreSQL authority
```

Pure task models, policy, and ports do not import FastAPI, SQLAlchemy, asyncpg,
Alembic, or concrete adapters. The adapter returns untrusted canonical JSON
bytes or a typed failure; it never returns an approved `PlanningResult`, grants
Evidence authority, or selects a tenant. The worker validates schema, pins,
bounds, and Evidence authority before using existing M3A deterministic policy.

Claim, input load, execution start, heartbeat, finalize/retry, and each SSE page
use separate short sessions and transactions. Adapter work and SSE sleep never
hold an application database transaction.

## Task state and public projection

Internal states are frozen:

```text
queued -> leased -> running -> waiting_review
                           -> succeeded
                           -> blocked
                           -> timed_out
                           -> failed
queued | leased | running -> cancelled
running -> queued only for an allowlisted retry with attempts remaining
```

The deterministic projection is:

| Internal condition | Public status |
|---|---|
| `queued`, `leased`, `running` | `preparing` |
| `waiting_review` | `needs_advisor_review` |
| current `succeeded` | `ready` |
| `blocked` | `needs_evidence` |
| explicit adapter deadline exceeded | `timed_out` |
| other terminal failure | `failed` |
| `cancelled` | `cancelled` |
| waiting/succeeded result no longer current | `outdated` |

Public responses never expose internal leased state, lease owner/generation,
database or worker errors, adapter payload, dispatch data, tenant/actor/session
IDs, raw Evidence, prompts, outputs, stack traces, or secrets.

## Deterministic planning adapter

`PlanningAdapter` consumes only pinned task identifiers and the approved fixture
profile. The deterministic implementation:

- references `fixtures/m3a/manifest.json` and its exact hash;
- changes only the synthetic organization and Case identifiers pinned by the
  separate task-ready seed;
- preserves source-pack, Evidence, cost, ranking, and policy facts;
- performs no network access and reads no provider credential;
- cannot emit `externally_verified`, approve Evidence, select a final route, or
  construct a `DecisionBrief`;
- supports constructor-injected typed outcomes for tests only.

`fixtures/m4a/manifest.json` uses stable eval ID `sse_idempotency_retry` and
references, rather than duplicates, the M3A policy fixture.

Validation bounds are exact: canonical UTF-8 JSON payload at most 1 MiB,
narrative at most 64 KiB, at most 20 Evidence refs, exact Australia/Japan/
Malaysia scope, schema version 1, task-pinned organization, Case revision,
source-pack version, and policy `m3a-policy-v1`.

Oversize, invalid schema, tenant/version mismatch, fallback output, or untrusted
Evidence represented as accepted is non-retryable. Missing required Evidence
maps to `blocked`; it never produces an invented success.

## Retry and runtime bounds

Runtime values are fixed:

- lease duration: 60 seconds;
- heartbeat interval: 15 seconds;
- idle poll interval: 1 second;
- SSE heartbeat comment: 15 seconds;
- maximum: three total attempts;
- replay page: at most 100 durable events.

Only normalized transient adapter unavailability, transport interruption, and
reclaimed expired leases are retryable. A retry creates a new `AgentExecution`,
increments `attempt_no` and lease generation, and retains prior durable events.
Authorization, tenant/version, schema, policy, fallback authority, oversize,
required-Evidence, and unknown failures are not blindly retried. Only an
explicit adapter deadline maps to `timed_out`; exhausted transient attempts map
to `failed` with a stable sanitized code.

## PostgreSQL authority

Migration `0004_agent_tasks_executions_events.py` extends the single graph
`0001 -> 0002 -> 0003 -> 0004` and creates three tenant tables:

1. `app.agent_tasks` stores the pinned operation, Case/source/policy versions,
   request hash, row version, internal state, current lease, attempt count,
   result `PlanningRun` reference, and sanitized terminal code.
2. `app.agent_executions` stores one normalized attempt per task/attempt number,
   lease generation, deterministic adapter identity/version, retry/fallback
   facts, hashes, result reference, bounded timing, and cost-status metadata.
3. `app.agent_task_events` stores immutable task-local sequence, stable event
   code, public status, optional result reference, and timestamp.

All three are tenant-keyed, migrator-owned, `ENABLE/FORCE RLS` protected, and
have explicit `USING/WITH CHECK` policies. Runtime roles have no direct M4A
`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, ownership, or `BYPASSRLS` authority.

The only global table is:

```text
internal.agent_task_dispatch(task_id, organization_id, available_at)
```

It has no Case, actor, request, Evidence, adapter, error, result, or raw payload.
API, worker, PUBLIC, and runtime roles have no direct schema/table access. Only
migrator-owned `SECURITY DEFINER` functions with fixed `search_path` and revoked
PUBLIC execute may use it. Global claim takes worker identity only and returns
only task ID, organization ID, and lease generation.

Narrow functions cover assigned-advisor idempotent create/cancel; worker claim,
start, heartbeat, retry/finalize, and reclaim; generation-fenced PlanningRun
persistence; and atomic task state/event creation. Lease owner plus monotonic
generation fences every worker write. Stale generations update zero rows and
their adapter output is discarded. Cancel-versus-complete and reclaim-versus-
finalize accept exactly one state/event transaction. Waiting and terminal states
hold no lease.

The existing `idempotency_records` authority is reused. Same actor, operation,
key, and request hash replays the original task; the same key with another hash
conflicts. A second effective task for the same Case, operation, and pins also
conflicts. Downgrade removes only M4A functions and storage, preserving M3B.

## HTTP v1 contract

| Method and path | Actor | Result |
|---|---|---|
| `POST /api/v1/cases/{case_id}/agent-tasks` | assigned advisor | idempotent create, `202` |
| `GET /api/v1/tasks/{task_id}` | assigned advisor | no-store public projection |
| `POST /api/v1/tasks/{task_id}/cancel` | assigned advisor | versioned idempotent cancel |
| `GET /api/v1/tasks/{task_id}/events` | assigned advisor | authorized SSE replay/resume |

Create accepts only schema version 1, operation `generate_planning_run_v1`,
expected Case revision, source-pack ID/version, and policy `m3a-policy-v1`.
It cannot select tenant, actor, adapter, injected failure, worker, lease, or
retry behavior. Errors use the existing non-enumerating RFC 9457-style problem
contract. Mutations and reads are `Cache-Control: no-store`; SSE also sets
`X-Accel-Buffering: no`.

`Last-Event-ID` is a non-negative task-local integer. Missing replays from the
first event; malformed/negative cursors are rejected; a cursor ahead of the
authoritative maximum returns a typed conflict. Each read returns at most 100
durable events. Durable IDs use `event_sequence`; 15-second heartbeats are SSE
comments and are never stored. Reconnect re-resolves session and assignment.
After a closing state and delivery of all durable events, the stream closes.

## Worker lifecycle

For each task the worker:

1. claims one payload-free dispatch row in a short transaction;
2. loads pinned tenant input in another short transaction;
3. records execution start through the fenced boundary;
4. runs the adapter outside a transaction;
5. heartbeats through an independent session when needed;
6. validates output and evaluates existing M3A policy;
7. finalizes or schedules an allowed retry in a short fenced transaction;
8. discards output after lease loss or cancellation.

The one-process Compose worker uses the non-owner worker URL. Its supervisor
continues after normalized transient claim/poll errors using stable sanitized
codes; authentication, schema, and programming errors remain visible.

## Synthetic seed and proof

Migration `0004` is seed-free. Explicit demo seeding adds a separate task-ready
synthetic Case and assigned advisor under the existing synthetic tenant. It
reuses the M3A source pack and does not mutate or reset the M3B golden Case,
review, Brief, family decision, receipt, or timeline.

Compose uses the deterministic adapter by default. The proof keeps all identity
and M3B probes, creates the M4A task through HTTP, observes the real worker reach
`needs_advisor_review` and a current `review_required` `PlanningRun`, replays and
reconnects SSE without duplicates, proves heartbeat comments are not rows,
proves task/result durability across API and worker restart, and tears down all
isolated containers and volumes.

Bounded local recovery evidence uses two workers and 100 tasks with no duplicate
accepted finalization, 25 authorized reconnecting clients, and a 100-plus-event
stream. These are deterministic local bounds, not throughput or availability
SLAs.

## Required evidence

Tests cover state/public projection and currentness; retry/bounds/pins; adapter
authority; forced RLS, grants, dispatch privacy, function search paths, and
downgrade/re-upgrade; real runtime roles and tenants; claim/reclaim/heartbeat/
generation/cancel races; short sessions; HTTP identity and idempotency; SSE
ordering, pagination, cursors, reconnect authorization, heartbeat, and restart;
and Compose teardown.

Fresh local gates are `make doctor MODE=dev`, `uv lock --check`, non-database
pytest, Ruff, Pyright, hashed build, unchanged frontend lint/typecheck/test/build,
`make db-check`, `make check`, `make proof`, `make compose-proof`, `make down`,
`docker compose ps --all`, and `git diff --check`. Hosted CI evidence requires a
later authorized push/PR and is not implied by local GREEN.

## Documentation and public claims

M4A updates the bilingual READMEs, docs index, HTTP and task/event references,
database-role and worker/SSE operations guides, affected design projections,
and Compose proof documentation.

The supported public statement is limited to a local synthetic deterministic
worker proof with PostgreSQL-backed leases and SSE replay. It does not prove
production throughput, distributed high availability, remote Agent integration,
real users, current study-abroad facts, or business outcomes. The fixture-only
M1 `/demo` remains disconnected.
