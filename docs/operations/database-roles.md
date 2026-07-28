# Database roles and recovery

Fresh PostgreSQL volumes create separate bootstrap, migration, API, and worker
roles. Only the PostgreSQL container receives bootstrap credentials. Alembic
receives the migration URL; API and worker containers receive only their own
runtime URLs.

`night_voyager_migrator` owns schemas, tables, and restricted functions but is
`NOINHERIT NOBYPASSRLS`. `night_voyager_api` and `night_voyager_worker` are
non-owner runtime roles with no migration membership and no direct access to
`auth` tables. Only the API may execute the required authentication functions.

Use `make db-check` for a disposable fresh-volume `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007 -> 0008 -> 0009 -> 0010 -> 0011 -> 0012 -> 0013` migration,
explicit synthetic seed, catalog, role, RLS, downgrade/re-upgrade, and
connection-pool cleanup proof. The target uses
an isolated Compose project and removes its volumes on every exit. Do not run a
downgrade against a retained demo volume.

M3A grants runtime roles read access but no direct table-write privilege. The
API alone can execute narrow migrator-owned functions for Case revision CAS,
source/Evidence persistence and atomic PlanningRun result persistence. M3A originally
granted a standalone Case intake-to-planning function, but migration `0009` removes
that API grant at the current head. Those functions use the transaction tenant context. Triggers
enforce allowed run transitions, terminal output immutability, exact source
hashes and same-pack Evidence links. The worker has no M3A mutation function.
Publishing a current `review_required` result also performs the revision-pinned
Case handoff to `advisor_review`; blocked, failed, stale and non-current runs do not.

M3B adds exactly eight migrator-owned forced-RLS tables. The API can execute
only narrow review/decision functions; the worker has no M3B mutation authority.
Downgrade removes only M3B structures and restores a valid M3A Case state.

M4A adds exactly three migrator-owned forced-RLS application tables:
`agent_tasks`, `agent_executions`, and `agent_task_events`. The API can select
task/event projections and execute only assigned-advisor create/cancel
functions. The worker can select task pins and execute only claim, start,
heartbeat, failure/retry, and generation-fenced finalization functions. Neither
runtime role has direct M4A write privilege.

`internal.agent_task_dispatch` contains only task ID, organization ID, and
availability time. Runtime roles and `PUBLIC` cannot access its schema or table;
migrator-owned fixed-search-path functions are the only boundary. Global claim
returns only task ID, organization ID, and lease generation. Migration `0004`
is seed-free and downgrade preserves all M3B structures.

Migration `0005` adds exactly two forced-RLS immutable ledgers for DRA
candidates and terminal external-evidence verification. It is seed-free. The
API role can select those ledgers and execute only candidate import and atomic
verify/promote functions; it has no direct DML. The worker has neither table
access nor function execution. Downgrade removes only the two ledgers, their
functions/policies/triggers, and derived promoted revisions while preserving
the `0004` task and existing synthetic demo structures.

Migration `0006` adds no table. It extends the existing task operation and
adapter-pair constraints, adds the worker-only
`load_governed_mixed_planning_snapshot` function, and keeps API/worker direct
DML prohibited. The API can create the additive mixed task only through the
existing assigned-advisor task function. The worker can load only the exact
current Case/revision, promoted pack, and policy snapshot through the narrow
function; the API and `PUBLIC` cannot execute it. Downgrade to `0005` preserves
terminal mixed audit rows, atomically cancels queued, leased, or running mixed
tasks with the public code `migration_downgrade`, removes their dispatch rows,
and prevents the restored `0005` claim function from selecting mixed
operations. The restored constraints prevent new mixed writes.

Migration `0007` adds exactly six migrator-owned, tenant-keyed, forced-RLS,
immutable collaboration tables. Neither runtime role has direct table access.
`night_voyager_api` may execute only the four closed collaboration mutations and
four role-safe read projections; `night_voyager_worker` and `PUBLIC` have no
collaboration function authority. The API can no longer execute the legacy
`publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)` writer. Confirmed
facts can publish a revision only through the assigned-advisor
`verify_memory_candidate(...)` transaction.
Planning-result persistence takes the compatible Case-before-PlanningRun lock
order; an allowed downgrade restores the exact `0006` function body as well as the
legacy writer grant and PlanningRun guard.

Migration `0008` adds exactly five migrator-owned, tenant-keyed, forced-RLS,
immutable Skill tables: `skill_definitions`, `skill_versions`,
`skill_change_candidates`, `skill_evaluation_results`, and
`skill_activation_events`. Neither runtime role has direct table access or DML.
`night_voyager_api` may execute the four lifecycle mutations and four advisor/owner
read projections. `night_voyager_worker` may execute only the existing task lifecycle
functions plus `load_agent_task_skill_pin(...)` and
`load_persisted_synthetic_planning_snapshot(...)`; it has no candidate, evaluation,
activation, rollback, or catalog authority. `PUBLIC` receives no Skill function
authority.

`agent_tasks` and `agent_executions` each retain the immutable five-field Skill pin.
Composite foreign keys prove definition/version/activation/digest equality and claim
copies the exact task pin into the execution. The API resolves a new task's active pin
inside the task creation transaction. The worker validates the execution pin through
its narrow projection before start.

Migration `0008` is seed-free. The explicit demo seed creates exactly six
definitions, six `1.0.0` versions, six seed evaluations, and one runtime activation
before any task-ready Case seed. An allowed downgrade requires that exact canonical
seed and no task/execution pin; registered non-seed versions, governance history, or
active/terminal pins refuse before history is removed. The current fresh data-free
graph proves `0008 -> 0001 -> 0008`, including all earlier migrations.

Migration `0009` adds no table, role, RLS policy, HTTP contract, or worker function. It
replaces only the existing task-creation function so a valid first deterministic task
may atomically own `intake -> planning` together with its complete task, dispatch,
event, Skill pin, and idempotency writes. The function remains migrator-owned with
`EXECUTE` granted only to `night_voyager_api`; `night_voyager_worker` and `PUBLIC`
cannot execute it, and neither runtime role receives direct task DML. Migration `0009`
also revokes `transition_case(uuid,uuid,text,text)` from the API, so `PUBLIC`, API, and
worker cannot submit a standalone planning transition at head. Task creation takes a
same-key transaction advisory lock before replay lookup.

Migration `0010` adds no table, role, or RLS policy. It closes new DRA candidate
imports to the exact v0.1.6 producer tuple while keeping historical v0.1.3 rows
readable, and adds the tenant-scoped `project_dra_live_outcome` function. Only
`night_voyager_api` may execute that bounded read projection. The API receives
no new table DML, and `night_voyager_worker` and `PUBLIC` receive no new
authority. All affected ledgers retain forced RLS.

The isolated `0010 -> 0009 -> 0010` lane proves producer validation, historical
readability, function owner/signature/ACL, API/worker parity, and clean
re-upgrade. Downgrade refuses before mutation when v0.1.6 history exists; with
no incompatible live history it removes only the additive function and
restores the previous import boundary.

Migration `0011` preserves the exact legacy release-referenced import signature
and adds a distinct strict commit-referenced
`app.import_dra_research_candidate(...)` overload. Catalog and privilege checks
bind each function by `oidvectortypes(p.proargtypes)`, never by `proname`
cardinality. The API has `EXECUTE=true` for both exact import signatures and the
exact `app.verify_and_promote_dra_candidate(...)` signature; the worker and
`PUBLIC` have `EXECUTE=false` for all three. Runtime roles retain no direct
candidate-ledger DML and both ledgers retain forced RLS.

The strict branch stores the exact post-release producer commit,
`generic-strict-citation@1`, `dra.strict-citation-profile.v1`, request identity,
and observed profile manifest. It cannot be inferred from a legacy row or mixed
with the v1 identity. Downgrade to `0010` takes an exclusive ledger lock and
refuses before mutation when any commit-referenced strict history exists.
Empty-history and legacy-only databases may downgrade safely and re-upgrade
without changing historical rows.

Migration `0012` adds versioned planning lineage without adding a runtime role
or direct table grant. Exact `request_revision` review authority is copied into
the next Case revision together with the now-non-current predecessor
PlanningRun; the next task copies that immutable predecessor and the worker
consumes only the task-owned identity. Partial unique indexes and replacement
function bodies enforce one predecessor -> at most one successor. The old run
and predecessor task remain immutable history but are non-authoritative.

The API alone may execute
`app.read_connected_journey_fact_pending(uuid,uuid,text,uuid)`. This narrow
`SECURITY DEFINER` projection uses fixed
`search_path = pg_catalog, pg_temp`, verifies the exact Case participant, loads
the current revision internally, and returns one boolean. `PUBLIC` and the
worker cannot execute it. Neither runtime role receives direct access to
`memory_candidates` or `memory_candidate_verifications`.

A safe `0012 -> 0011` downgrade requires no planning-revision lineage. It drops
the narrow projection and restores the exact `0011` function signatures and
grants. When lineage exists, downgrade refuses before any schema or authority
mutation and preserves rows, functions, and ACLs.

Migration `0012` remains the runtime lineage authority. Migration `0013` adds
only the closed provider-free demo seed helper
`app.seed_demo_planning_revision_fact(...)`; it adds no runtime tables,
policies, roles, or grants. The helper is migrator-owned, uses a fixed search
path, and has zero runtime grants: `PUBLIC`, API, and worker cannot execute it.
It atomically creates or exact-compares the five collaboration authority rows
needed by each synthetic planning-revision fixture. A safe `0013 -> 0012`
downgrade drops only that exact helper and leaves business data unchanged.

The isolated `planning-revision-seed-migration` database lane proves the helper
catalog and ACL, first create, exact replay, drift and collision refusal,
transactional rollback, downgrade, and re-upgrade. Historical-head seed calls
explicitly exclude planning-revision fixtures; current-head demo and journey
lanes retain the complete deterministic fixture.

Use the focused planning-revision modes:

```bash
scripts/run_db_tests.sh planning-revision authority
scripts/run_db_tests.sh planning-revision worker
scripts/run_db_tests.sh planning-revision projection
scripts/run_db_tests.sh planning-revision all
```

`authority` proves atomic revision publication, grants/RLS, concurrency,
rollback, query bounds, and downgrade parity. `worker` proves task-owned
predecessor loading, successor uniqueness, reclaim, and lost-ack behavior, then
runs the historical mixed-downgrade proof in a separate disposable database.
`projection` proves complete old/new hashes, V1/V2 negotiation, and
participant-safe phases. `all` runs those authorities and the isolated
mixed-downgrade lane serially. Every outer command owns and tears down its
Compose projects and volumes.

Run the focused strict migration mode with:

```bash
scripts/run_db_tests.sh dra-strict-migration
```

The `dra-strict-migration` mode uses one disposable task-owned Compose project,
upgrades from the historical `0009` seed through current head `0011`, and runs
only the existing live-migration compatibility test, strict migration
upgrade/downgrade tests, and DRA RLS isolation checks. It is not a provider,
credential, candidate-freeze, or release command.

Use `make fact-to-plan-db-check` for the isolated `0009 -> 0008 -> 0009` parity lane.
It proves the exact `0008` task function definition, owner, signature, ACL, runtime
privileges, and legacy API transition grant are restored on downgrade without rewriting
existing Case/task rows. Re-upgrade removes the transition grant again and re-proves the
`0009` planning-start authority. `make db-check` includes this lane before the shared
database suite.

Use `make collaboration-check` for the deterministic offline contracts and
`make collaboration-db-check SUITE=repository|http|authority` for focused disposable
PostgreSQL proof. The `authority` suite runs empty, unrelated-history, table-history,
audit-history, and idempotency-history downgrade scenarios in separate projects.
An empty or unrelated boundary may restore `0006`; any exact PR A authority history
must refuse before removing data. See [collaboration authority operations](collaboration-authority.md).

Use `make skills-check` for deterministic offline contracts and
`make skills-db-check SUITE=catalog|worker|lifecycle` for focused disposable Skill
proof. The suites cover catalog/grants/downgrade, task/execution/worker pins, and the
owner-controlled lifecycle respectively. See [Skill governance operations](skill-governance.md).

The normal `make demo` path applies migrations, then runs the separate
`demo-seed` one-shot service before API/worker readiness. Skill registry/evaluation
seed and runtime activation precede task-ready Case seed. The schema migration
remains seed-free. To re-run only the explicit idempotent seed against a running
development stack, use `docker compose run --rm demo-seed`; it fails closed
unless demo mode is enabled outside production. `make compose-proof` uses a
fresh isolated volume and proves bootstrap, session mint, the M3B decision flow,
the governed mixed fixture-to-family-decision closure, the governed collaboration
message-to-confirmed-fact flow and restart durability, the M4A
HTTP-to-worker-to-PlanningRun-to-SSE flow, and API/worker restart durability,
not health alone.
