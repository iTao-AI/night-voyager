# Skill governance operations

This runbook verifies the unreleased PR B Skill boundary locally. It uses packaged
manifests, deterministic evaluators, disposable PostgreSQL projects, and synthetic
data only. It does not call a live provider or authorize release or deployment.

## Offline contract lane

Run the fast deterministic lane first:

```bash
make doctor MODE=dev
uv lock --check
make skills-check
```

`make skills-check` covers strict models, both packaged manifests, deterministic
evaluation, the exact six-key catalog, canonical seed projection, architecture/docs
routing, release identity, and static database catalog contracts. It does not start
Docker or a live provider.

## Disposable PostgreSQL lanes

Run one isolated suite at a time:

```bash
make skills-db-check SUITE=catalog
make skills-db-check SUITE=worker
make skills-db-check SUITE=lifecycle
```

The runner accepts only `catalog`, `worker`, or `lifecycle`. Unknown or empty values
fail before Docker starts. Every accepted suite owns a unique Compose project and
volume, runs database-marked tests with runtime-equivalent roles, and removes its
containers, network, and volume on every exit.

- `catalog` proves migration `0008`, exactly five forced-RLS tables, immutable
  ledgers, composite lineage, grants, canonical seed, persisted snapshot projection,
  and allowed/refused downgrade paths.
- `worker` proves task creation and replay pins, claim-time execution copies, exact
  router/manifest leaf validation, canonical input hash, selected-country result
  persistence, invalid-pin terminal failure, and existing task/SSE compatibility.
- `lifecycle` proves designated-owner authority, strict HTTP DTOs, deterministic
  evaluation, concurrency, CAS, activation, rollback, runtime-role separation,
  explicit `1.0.1` registration, and non-seed downgrade refusal.

Use the full database gate after the focused suites:

```bash
make db-check
```

Do not run downgrade proof against a retained demo volume.

## Explicit supported-version registration

The default seed inserts only the six canonical `1.0.0` versions. To exercise the
reviewed compatibility lifecycle, use migration credentials and explicitly register
the packaged tuple:

```bash
uv run --no-editable python scripts/register_skill_version.py \
  --skill-key study-destination-compare --version 1.0.1
```

The command loads the packaged registry, inserts only the exact supported immutable
tuple, is idempotent for an exact match, and fails closed on mismatch. It is not run
by Alembic, the default seed, Compose bootstrap, FastAPI, or the browser.

## Runtime lifecycle

The API exposes catalog reads to organization advisors. Candidate creation,
evaluation, activation, and rollback additionally require the designated owner.
Mutations use the existing opaque session, exact Origin, session-bound CSRF token,
and `Idempotency-Key`; all responses are `Cache-Control: no-store`.

Operational order for a new version is:

```text
explicitly register supported packaged version
-> create change candidate from the current active version
-> compute and record deterministic evaluation
-> promote with expected active version and sequence
-> create a new planning task
-> retain prior task/execution pins unchanged
```

Rollback appends another activation event targeting a previously activated packaged
version. It requires the expected active version and sequence. A catalog-only Skill
cannot be activated or rolled back.

The closed Skill-domain problems are:

```text
resource_unavailable
skill_version_unavailable
skill_candidate_stale
skill_candidate_terminal
skill_evaluation_failed
skill_activation_stale
skill_scope_expansion
skill_rollback_unsupported
skill_pin_invalid
idempotency_conflict
persistence_unavailable
```

Unknown database, permission, connection, serialization, and result-shape errors
remain `persistence_unavailable`; raw SQL or tracebacks are never public.

## Worker checks

For each claim the worker loads the copied execution pin, trusted Skill key/version,
and claimed adapter leaf. Before start it resolves the configured router leaf and
requires exact equality with the packaged operation binding and complete
`runtime_binding_sha256`. A valid execution hashes `{request, five_field_pin}`.

`skill_pin_invalid` is non-retryable. The worker records the bounded failure through
the current lease owner/generation, removes dispatch eligibility, and does not start
the execution, invoke an adapter, or leave the task reclaimable.

Both planning operations materialize the exact persisted Case revision. When a Case
selects a country subset, inspect the resulting PlanningRun to confirm that routes,
costs, rankings, route-to-Evidence links, and advisor eligibility contain no
unselected country.

## Downgrade and recovery

An allowed `0008 -> 0007` downgrade requires the exact canonical seed and no task or
execution pin. Any registered `1.0.1`, non-seed governance event, or active/terminal
pin must refuse before data or provenance is removed. Use only the disposable
`catalog`/`lifecycle` lanes to exercise these scenarios.

Active legacy-unpinned `queued|leased|running` tasks encountered during upgrade are
cancelled with `legacy_unpinned`. Existing `waiting_review` and terminal history is
retained and remains inspector-visible as `legacy_unpinned`.

## Full local closeout

After focused checks, run the repository gates specified by the implementation plan.
At minimum, preserve the existing `python`, `frontend`, and `compose` hosted context
names and verify teardown:

```bash
make check
make proof
make compose-proof
make down
docker compose ps --all
```

See [Versioned Skills and runtime pins](../reference/versioned-skills-and-runtime-pins.md)
for the exact catalog, manifests, pin, worker, and downgrade contracts. PR C's
browser walkthrough and technical inspector remain deferred.
