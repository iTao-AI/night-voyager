# Database roles and recovery

Fresh PostgreSQL volumes create separate bootstrap, migration, API, and worker
roles. Only the PostgreSQL container receives bootstrap credentials. Alembic
receives the migration URL; API and worker containers receive only their own
runtime URLs.

`night_voyager_migrator` owns schemas, tables, and restricted functions but is
`NOINHERIT NOBYPASSRLS`. `night_voyager_api` and `night_voyager_worker` are
non-owner runtime roles with no migration membership and no direct access to
`auth` tables. Only the API may execute the required authentication functions.

Use `make db-check` for a disposable fresh-volume `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006` migration,
explicit synthetic seed, catalog, role, RLS, downgrade/re-upgrade, and
connection-pool cleanup proof. The target uses
an isolated Compose project and removes its volumes on every exit. Do not run a
downgrade against a retained demo volume.

M3A grants runtime roles read access but no direct table-write privilege. The
API alone can execute narrow migrator-owned functions for Case revision CAS,
Case intake-to-planning transition, source/Evidence persistence and atomic PlanningRun result
persistence. Those functions use the transaction tenant context. Triggers
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
operations. The restored constraints prevent new mixed writes. A fresh
data-free graph proves `0006 -> 0001 -> 0006`.

The normal `make demo` path applies migrations, then runs the separate
`demo-seed` one-shot service before API/worker readiness. The schema migration
remains seed-free. To re-run only the explicit idempotent seed against a running
development stack, use `docker compose run --rm demo-seed`; it fails closed
unless demo mode is enabled outside production. `make compose-proof` uses a
fresh isolated volume and proves bootstrap, session mint, the M3B decision flow,
the governed mixed fixture-to-family-decision closure, the M4A
HTTP-to-worker-to-PlanningRun-to-SSE flow, and API/worker restart durability,
not health alone.
