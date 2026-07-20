# Collaboration authority operations

The governed collaboration boundary is a `v0.1.2` local synthetic backend capability.
It proves assigned-participant conversation, typed fact
proposal, assigned-advisor verification, and atomic confirmed-fact revision
publication. The PR C browser walkthrough is documented separately. PR B Skill
governance, external message transport, and live-provider execution retain their own
boundaries.

## Deterministic checks

Run the offline collaboration contract lane first:

```bash
make collaboration-check
```

This lane is intended to validate pure models and policy, application and adapter
contracts, HTTP/OpenAPI registration, architecture boundaries, documentation, and
release-surface wiring without a remote provider.

Use one focused disposable PostgreSQL suite when diagnosing a specific boundary:

```bash
make collaboration-db-check SUITE=repository
make collaboration-db-check SUITE=http
make collaboration-db-check SUITE=authority
```

- `repository` exercises the PostgreSQL adapter and runtime functions.
- `http` seeds the deterministic fixtures twice, then crosses real opaque-session,
  FastAPI, PostgreSQL, RLS, and transaction-local context paths.
- `authority` covers catalog/grants, tenancy, concurrency, rollback, downgrade,
  repository, and HTTP authority. Downgrade success and refusal scenarios require
  isolated fresh databases so one scenario's authority history cannot contaminate
  another.

The focused runner owns an isolated Compose project and volume and tears them down
on success or failure. Unknown suite names fail before Docker starts. These commands
are verification procedures; treat a gate as passed only after its actual process
exits successfully.

Run the complete database migration and regression proof with:

```bash
make db-check
```

The database runner orders its destructive proof before full collaboration seed:

```text
empty upgrade to 0007
  -> empty 0007 -> 0006 -> 0007
  -> existing 0006 -> 0005 -> 0006 regression
  -> empty full graph 0007 -> 0001 -> 0007
  -> 0007 -> 0001 -> identity-only seed -> 0007
  -> full demo seed twice
  -> database, HTTP, catalog, role, RLS, concurrency, and rollback suites
  -> expected with-collaboration-history downgrade refusal
```

Do not interpret the final refusal as a migration failure. Refusing to remove
collaboration authority history is the expected downgrade contract.

## Local stack and backend flow proof

Start the normal local stack with the existing command:

```bash
make demo
```

Migration remains seed-free. The one-shot `demo-seed` service creates the explicit
synthetic fixtures after migration. To repeat only the idempotent seed against a
running development stack:

```bash
docker compose run --rm demo-seed
```

The seed is allowed only in development/test with demo mode enabled. It creates one
primary collaboration Case plus active-task, stale-candidate, and expired-candidate
fixtures. Repeated seed must preserve the fixed IDs and must not mutate the existing
default `/demo` Case. Exact identities are documented in
[Collaboration and confirmed facts](../reference/collaboration-and-confirmed-facts.md#deterministic-demo-identities).

The complete Compose proof includes a backend collaboration flow but no new frontend
route in PR A:

```bash
make compose-proof
make down
docker compose ps --all
```

The backend proof must use real sessions and HTTP commands to append a message,
propose a typed candidate, confirm it as the assigned advisor, and reload the new
ConfirmedFact and Case revision. It also checks wrong-role, stale, expired, and
active-task failures. `docker compose ps --all` should show no project containers
after teardown. Do not claim success from health checks alone.

## Fixture inventory

| Fixture | Case ID | Expected authority state |
| --- | --- | --- |
| primary | `41000000-0000-0000-0000-000000000001` | revision 1, clean shared thread |
| active task | `41000000-0000-0000-0000-000000000002` | revision 1, exact `waiting_review` task blocks confirmation |
| stale candidate | `41000000-0000-0000-0000-000000000003` | candidate pinned to revision 1, Case current revision 2 |
| expired candidate | `41000000-0000-0000-0000-000000000004` | candidate expiry is already before database time |

All fixtures are visibly synthetic. They do not represent real student records,
production tenancy, or admissions outcomes.

## Runtime role checks

The expected database boundary is:

- `night_voyager_migrator` owns the six tables and restricted functions;
- `night_voyager_api` has no direct collaboration-table privilege and may execute
  only the four mutations and four read projections;
- `night_voyager_worker` has no collaboration table or function authority;
- `PUBLIC` has no table or function authority;
- the API cannot execute the legacy whole-revision writer;
- every collaboration table has enabled and forced RLS;
- transaction-local tenant, actor, and role settings are empty after commit or
  rollback when a pooled connection is reused.

Use `make db-check` or the `authority` focused suite to verify this catalog through
the real runtime roles. An owner-role query is not sufficient RLS evidence.

## Downgrade safety

Never run a generic downgrade against a retained demo volume. Collaboration rows and
their exact audit/idempotency history are durable authority, so `0007 -> 0006` must
refuse rather than delete them.

Downgrade proof uses separate disposable databases for:

1. an empty PR A boundary, which may round-trip `0007 -> 0006 -> 0007`;
2. unrelated earlier audit/idempotency history, which may also downgrade;
3. any of the six collaboration table histories, which must refuse;
4. an exact collaboration audit or idempotency discriminator without table rows,
   which must refuse.

On allowed downgrade, verify that `0006` restores its exact legacy writer function,
API grant, PlanningRun guard, planning-result persistence function, and migrator
bootstrap behavior. On refusal, verify that migration remains at `0007` and no
authority row is removed.

## Troubleshooting

Inspect bounded local logs only when a gate fails:

```bash
docker compose logs api worker postgres
```

Do not copy opaque session or CSRF values, database URLs, credentials, raw SQL,
tracebacks, local paths, message bodies, verification reasons, or unbounded provider
content into proof output. Public HTTP problems should contain only their bounded
status, code, and detail.

Diagnose failures by boundary:

- `resource_unavailable`: confirm the session is valid and the actor has the exact
  Case participant role; do not infer whether another tenant's resource exists.
- `case_revision_stale` or `memory_candidate_stale`: reload the current Case and
  create a new source message/candidate; never rebase the old candidate.
- `memory_candidate_expired` or `memory_candidate_terminal`: create a new candidate;
  expiry and terminal decisions are immutable.
- `active_task_blocks_revision`: finish or otherwise resolve the existing task
  through its established authority; collaboration does not cancel it.
- `idempotency_conflict`: retry only the original body with the original key, or use
  a new key for a genuinely new command.
- `persistence_unavailable`: inspect the first database or result-shape failure;
  repeated retries must not replace diagnosis.

Use the guarded retained-volume reset only when deleting local synthetic data is
intentional:

```bash
RESET_DEMO=1 make reset-demo
```

PR A stops at local backend authority proof. Do not use these operations to start PR
B or PR C, run a live provider, publish a release, deploy, or claim production
readiness.
