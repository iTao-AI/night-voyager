# ADR 0001: Identity, session, and RLS boundary

Status: Accepted

Night Voyager establishes tenant identity through a restricted authentication
bootstrap, then applies `ActorContext` inside the same database transaction as
tenant queries. Tenant tables in `app` use enabled and forced PostgreSQL row
security. Runtime roles are non-owner, non-member, and `NOBYPASSRLS`.

Authentication tables in `auth` are the narrow exception to tenant RLS. Runtime
roles receive no direct table privileges; the API can call small
`SECURITY DEFINER` functions that accept token digests and return only identity
scalars. Those functions use fully qualified names, a trusted fixed
`search_path`, revoked public execution, and an explicit API grant. The worker
has no authentication-function grant.

Sessions and CSRF values are 32-byte opaque tokens. Only keyed SHA-256 digests
are persisted. Identity is transaction-local through `set_config(..., true)`,
so pooled connections cannot retain tenant authority after commit or rollback.

This boundary intentionally excludes public accounts, passwords, OAuth,
frontend integration, domain workflow tables, background tasks, and production
tenancy operations.
