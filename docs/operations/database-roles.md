# Database roles and recovery

Fresh PostgreSQL volumes create separate bootstrap, migration, API, and worker
roles. Only the PostgreSQL container receives bootstrap credentials. Alembic
receives the migration URL; API and worker containers receive only their own
runtime URLs.

`night_voyager_migrator` owns schemas, tables, and restricted functions but is
`NOINHERIT NOBYPASSRLS`. `night_voyager_api` and `night_voyager_worker` are
non-owner runtime roles with no migration membership and no direct access to
`auth` tables. Only the API may execute the required authentication functions.

Use `make db-check` for a disposable fresh-volume migration, seed, catalog,
role, RLS, downgrade/upgrade, and connection-pool cleanup proof. The target uses
an isolated Compose project and removes its volumes on every exit. Do not run a
downgrade against a retained demo volume.
