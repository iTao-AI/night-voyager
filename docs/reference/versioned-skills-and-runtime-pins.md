# Versioned Skills and runtime pins

PR B implements the local synthetic Skill governance boundary released in `v0.1.2`.
PostgreSQL owns immutable governance and provenance records. Packaged,
checked-in Python owns executable compatibility. A database row, passing evaluation,
or browser response cannot become executable authority by itself.

## Closed catalog

| Skill key | Binding kind | v1 runtime status |
| --- | --- | --- |
| `student-profile-intake` | `catalog_only` | governed contract only |
| `study-destination-compare` | `planning_runtime` | pinned by both planning operations |
| `evidence-research` | `catalog_only` | governed contract only |
| `document-evidence-retrieval` | `catalog_only` | governed contract only |
| `family-decision-brief` | `catalog_only` | governed contract only |
| `application-timeline-guard` | `catalog_only` | governed contract only |

`catalog_only` means versioned and deterministically evaluated, not executable. It
cannot have activation events, rollback events, or AgentTask pins. Only
`study-destination-compare` is `planning_runtime` in v1.

## Packaged manifests

The wheel contains these server-owned resources:

- `night_voyager/skills/data/runtime-manifest-v1.json` from
  `fixtures/skills/runtime-manifest-v1.json`;
- `night_voyager/skills/data/eval-manifest-v1.json` from
  `fixtures/skills/eval-manifest-v1.json`.

Production code loads both with `importlib.resources`; there is no current working
directory or operator-supplied fallback. The runtime manifest contains seven exact
entries: one `1.0.0` entry for each of the six keys plus the supported
`study-destination-compare@1.0.1` compatibility entry. The evaluation manifest has
the same seven key/version identities.

The only executable binding is the complete map below. Its canonical projection
participates in `runtime_binding_sha256`.

```text
planning_adapter_router@v1
  generate_planning_run_v1
    -> deterministic_planning@m4a-v1
  generate_governed_mixed_planning_run_v1
    -> governed_mixed_planning@dra-mixed-v1
```

`1.0.0` and `1.0.1` may share the same executable binding digest while remaining
different semantic versions. Runtime selection therefore uses the exact trusted
Skill key/version pair, never a UUID or digest alone.

## Relational authority

Migration `0008` adds exactly five forced-RLS, tenant-keyed, immutable tables:

1. `app.skill_definitions` owns the stable key, designated owner advisor, and binding
   kind.
2. `app.skill_versions` owns immutable contracts, digests, tools, data scopes,
   policies, dataset identity, packaged manifest identity, the migrator-owned trusted
   expected evaluation projection, and optional supersession.
3. `app.skill_change_candidates` records a base/proposed version and bounded
   provenance.
4. `app.skill_evaluation_results` records one server-produced deterministic result
   for a candidate/version/evaluator/dataset identity.
5. `app.skill_activation_events` appends `seed|promote|rollback` history and monotonic
   activation sequence.

Runtime roles have no direct table access or DML. API functions enforce organization
advisor visibility, designated-owner mutations, idempotency, evaluation identity,
scope bounds, and activation CAS. Worker functions expose only an already-created
task pin and exact persisted planning snapshot.

## Candidate, evaluation, activation, and rollback

The server resolves the complete packaged entry for candidate creation. HTTP accepts
only proposed semantic version, closed provenance, bounded reason, and optional
reference. It does not accept executable bindings, contracts, tools, scopes, hashes,
evaluator output, or activation identity.

Evaluation runs the checked-in deterministic evaluator and persists its canonical
assertions and output hash only when the entire result equals the immutable trusted
projection registered for that exact version. Missing, empty, extra, duplicate, or
reordered assertions; changed observations; forged status/failed IDs; and changed
canonical output hashes fail before any evaluation or activation side effect. A
passing result is evidence, not activation authority. Promotion requires the
designated owner, `planning_runtime`, a passing exact result, the expected active
semantic version and activation sequence, and no scope expansion.

Rollback appends a new event. Its target must be a previously activated version that
is still supported by packaged runtime, and its expected active version/sequence must
match. Neither promote nor rollback deletes versions, evaluations, candidates, or
activation history.

## Canonical seed and registration

The explicit default seed creates exactly:

- six definitions;
- six `1.0.0` versions;
- six passing deterministic seed evaluations;
- one `study-destination-compare@1.0.0` seed activation.

On a fresh database already at migration `0008`, the default seed also creates the
fixed collaboration active-task negative fixture in `waiting_review` with all five
fields bound to that canonical activation. On the `0007 -> 0008` upgrade path, an
existing exact PR A `waiting_review` fixture is retained as `legacy_unpinned`; the
seed does not backfill or reinterpret its history.

`1.0.1` is packaged but is absent from the default database seed. The separate
migrator-owned registration command loads its exact packaged runtime tuple and trusted
packaged-evaluator projection before a lifecycle candidate can reference it. Migration
`0008` itself inserts no seed data.

## AgentTask and AgentExecution pin

Every newly created planning task has this exact five-field pin:

```text
skill_definition_id
skill_version_id
skill_activation_event_id
skill_activation_sequence
runtime_binding_sha256
```

Composite foreign keys prove definition/version/activation/digest equality. The
effective-task partial unique index contains the complete pin. Claim copies all five
fields to the new execution, whose relational constraint and immutable guard require
equality with the task.

Task replay returns the original task and pin even after a new activation. A task
created after activation receives the new pin; rollback affects only subsequently
created tasks. The trusted worker projection additionally returns the immutable Skill
key and semantic version needed to select the packaged entry.

Upgrade treats pre-`0008` history explicitly. Active `queued|leased|running` rows
without a pin are cancelled with `legacy_unpinned`. Historical `waiting_review` and
terminal rows are retained and inspector-projected with
`pin_status=legacy_unpinned`.

This preservation rule applies only to an existing upgrade-path task. It does not
authorize a fresh-head default seed to create new legacy-unpinned task history.

## Worker validation

The worker order is fixed:

```text
claim
-> load request, execution pin, trusted Skill key/version, and claimed leaf
-> resolve the configured router leaf
-> validate the exact packaged manifest and five-field pin
-> require claimed leaf = router leaf = packaged leaf
-> start with sha256({request, five_field_pin})
-> invoke the resolved adapter
-> validate and persist the bounded result
```

Missing, mismatched, catalog-only, unsupported, stale, or malformed pins fail through
the fenced non-retryable `skill_pin_invalid` path before start or adapter execution.
They are removed from dispatch eligibility and do not enter a reclaim/retry loop.

## Persisted Case revision materialization

Both planning operations read the exact organization, Case, revision, source pack,
source-pack version, and policy through worker-only projections. Persisted budget,
intake, Japan-risk acceptance, and preferred countries reach the actual adapter.
Missing, stale, cross-tenant, malformed, unsupported-country, or pin-mismatched
revisions fail closed before adapter execution.

`preferred_countries` is a non-empty, sorted, unique subset of
`australia|japan|malaysia`. Only selected routes, costs, rankings, route-to-Evidence
links, and advisor eligibility may be persisted as product results. Baseline Evidence
may remain an input record without becoming an unselected-country result.

## HTTP and inspector

The exact seven endpoints and request bodies are documented in
[HTTP API v1](http-api-v1.md#versioned-skill-governance). All are advisor-only;
mutations additionally require the designated owner. The Case inspector is one
server-owned composite projection with
`pin_status=not_created|matched|legacy_unpinned`. The browser does not join catalog,
activation, task, and execution records into an authority claim.

During the controlled same-Case handoff, the collaboration page re-reads this
inspector only to validate current authority. The handoff itself never resolves a
Skill pin, creates a task, or transports pin fields. `/demo` re-reads its advisor
ledger, and task creation atomically persists the exact active five-field pin through
the existing backend authority.

## Downgrade

`0008 -> 0007` succeeds only for the exact reproducible canonical seed with no task
or execution pin. An explicitly registered non-seed version, non-seed candidate or
evaluation, promote/rollback event, or active/terminal pin refuses downgrade before
history is removed. An allowed downgrade restores the exact `0007` task/claim
functions, effective-task index, grants, and task behavior.

## Public boundary

This is a local synthetic backend proof released in `v0.1.2`. PR C's
`/demo/collaboration` walkthrough includes the read-only technical inspector UI. No live
provider, external message transport, dynamic plugin loader, production deployment,
production tenancy, or real-user evidence is claimed.
