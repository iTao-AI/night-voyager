# Database roles and recovery

Fresh PostgreSQL volumes create separate bootstrap, migration, API, and worker
roles. Only the PostgreSQL container receives bootstrap credentials. Alembic
receives the migration URL; API and worker containers receive only their own
runtime URLs.

`night_voyager_migrator` owns schemas, tables, and restricted functions but is
`NOINHERIT NOBYPASSRLS`. `night_voyager_api` and `night_voyager_worker` are
non-owner runtime roles with no migration membership and no direct access to
`auth` tables. Only the API may execute the required authentication functions.

Use `make db-check` for a disposable fresh-volume `0001 -> 0002` migration,
explicit M3A synthetic seed, catalog, role, RLS, `0002 -> 0001 -> 0002`, and
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

The normal `make demo` path applies migrations, then runs the separate
`demo-seed` one-shot service before API/worker readiness. The schema migration
remains seed-free. To re-run only the explicit idempotent seed against a running
development stack, use `docker compose run --rm demo-seed`; it fails closed
unless demo mode is enabled outside production. `make compose-proof` uses a
fresh isolated volume and proves bootstrap plus session mint, not health alone.
