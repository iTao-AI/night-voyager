# ADR 0009: Govern versioned Skills and pin planning runtime

- Status: Accepted
- Date: 2026-07-18
- Implementation status: Implemented by migration `0008` and the PR B backend
  boundary; unreleased after `v0.1.1`

## Context

Night Voyager already owns Case revisions, accepted Evidence, deterministic planning,
human review, family decisions, and durable AgentTask execution. Before PR B, the two
planning operations selected checked-in adapters but did not preserve which governed
capability version authorized a task or execution. The synthetic operation also loaded
the fixture Case rather than the exact persisted revision requested by the task.

A mutable prompt record or display-only catalog would not close either gap. Database
content must not become executable code, an evaluation pass must not become activation
authority, and a later activation must not silently change queued or running work.

## Decision

PostgreSQL is the governance and provenance authority for version records, evaluation
evidence, activation history, and runtime pins. Checked-in Python remains executable
authority. Migration `0008` adds exactly five migrator-owned, tenant-keyed tables:

- `skill_definitions`;
- `skill_versions`;
- `skill_change_candidates`;
- `skill_evaluation_results`;
- `skill_activation_events`.

All five tables have enabled and forced row-level security, one tenant `USING` and
`WITH CHECK` policy, immutable-row protection, and no runtime direct DML or `TRUNCATE`
grant. Runtime roles receive narrow `SECURITY DEFINER` functions only; `PUBLIC`
receives none.

The catalog is closed to exactly six Skill keys. Only
`study-destination-compare` has `binding_kind=planning_runtime`; the remaining five
are `catalog_only` and are never activated, rolled back, or task-pinned in v1. The
designated owner is an existing organization advisor membership, not a new role.

`fixtures/skills/runtime-manifest-v1.json` and
`fixtures/skills/eval-manifest-v1.json` are packaged into the wheel and loaded only
through `importlib.resources`. The strict runtime registry supports the six `1.0.0`
catalog entries plus the reviewed `study-destination-compare@1.0.1` compatibility
entry. Database rows contain immutable identities and hashes, never executable code,
prompt text, import paths, shell commands, package URLs, or arbitrary tool names.

Deterministic evaluation invokes checked-in pure product policies. The browser submits
neither result status nor assertion output. Each registered version also stores the
migrator-owned expected evaluation projection produced by the packaged evaluator.
The API mutation persists a result only when its complete canonical projection is
identical, so an API-role caller cannot invent assertion IDs, observations, status,
failed IDs, or an output hash. A passing evaluation is immutable evidence; promotion
still requires the designated owner and expected active version/sequence.
Activation and rollback append events and never rewrite version or evaluation history.

Every new planning AgentTask resolves the current runtime Skill inside the same
transaction that owns idempotency replay, effective-task uniqueness, task insert, and
dispatch insert. The task stores this exact five-field pin:

- `skill_definition_id`;
- `skill_version_id`;
- `skill_activation_event_id`;
- `skill_activation_sequence`;
- `runtime_binding_sha256`.

Claim copies the same five fields to AgentExecution. The effective-task index includes
the complete pin, so a later activation may authorize new work while old work keeps its
original identity. Idempotent replay returns the original task and pin.

After claim and load, but before start, the worker resolves the configured router leaf
and validates the persisted key/version, five-field pin, complete packaged manifest,
operation binding, and selected leaf. The exact top-level binding is
`planning_adapter_router@v1`:

```text
generate_planning_run_v1
  -> deterministic_planning@m4a-v1

generate_governed_mixed_planning_run_v1
  -> governed_mixed_planning@dra-mixed-v1
```

Invalid or unsupported pins fail through the fenced, non-retryable
`skill_pin_invalid` path before `start_agent_task` or adapter invocation. Successful
execution hashes the canonical object `{request, five_field_pin}`; the selected leaf
remains a separate audit fact.

The worker-only persisted snapshot projection loads the exact organization, Case, and
revision. Both planning operations consume those persisted student/family facts.
`preferred_countries` is a non-empty sorted unique subset of Australia, Japan, and
Malaysia, and only selected route, cost, ranking, Evidence-link, and eligibility rows
may become product results.

The canonical explicit seed creates six definitions, six `1.0.0` versions, six seed
evaluations, and one `study-destination-compare@1.0.0` seed activation. Migration
`0008` remains seed-free. Supported `1.0.1` registration is an explicit migrator-owned
maintenance action and is not part of migration, default seed, browser, or Compose
bootstrap.

Upgrade cancels only active legacy-unpinned `queued|leased|running` tasks with
`legacy_unpinned`; `waiting_review` and terminal history remain visible as
`legacy_unpinned`. Downgrade to `0007` is allowed only for the exact canonical seed
with no task or execution pin. Any non-seed governance history or active/terminal pin
refuses downgrade before history is removed.

## Consequences

- Catalog governance cannot masquerade as executable runtime support.
- Evaluation evidence, owner activation, task identity, execution identity, and the
  actual adapter leaf remain separate and auditable.
- Activation and rollback affect future task creation only.
- PostgreSQL still owns tenant, idempotency, CAS, lease, and persistence authority;
  checked-in code owns executable compatibility.
- Persisted Case revisions, rather than fixture Case values, determine both planning
  operations and selected-country product projections.
- The capability is an unreleased local synthetic backend proof after `v0.1.1`; it is
  not a production deployment, live-provider proof, or real-user claim.

## Deferred and rejected alternatives

PR C's `/demo/collaboration` walkthrough and technical inspector UI remain deferred.
There is no Skill management UI, dynamic plugin loader, database prompt registry, new
queue, new worker, provider transport, live-provider proof, release, or deployment in
this decision. Catalog-only Skills require a later explicit runtime design before they
can execute.
