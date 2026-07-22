# Collaboration and confirmed-fact reference

Migration `0007` implements the PR A governed conversation and memory authority,
released in `v0.1.2` for the local synthetic pilot.
PR B Skill governance, PR C browser integration, external transports, and
live-provider execution are not implemented by migration `0007` itself. PR B and
PR C are released in v0.1.2; the post-v0.1.2 fact-to-plan browser composition reuses
their existing authority without changing this database contract.

## Authority model

PostgreSQL owns tenant isolation, Case assignment, source authorship, sequence
allocation, candidate currentness, expiry, terminal decisions, revision publication,
fact provenance, idempotency, and audit history. FastAPI and application services
provide strict DTOs and typed adapters; they do not calculate tenant or Case
authority.

The authority records are deliberately separate:

| Record | Meaning | Mutability |
| --- | --- | --- |
| `CollaborationThread` | The single always-active shared thread for one Case | immutable |
| `MessageEvent` | Assigned-participant communication; never a fact or command | append-only |
| `MemoryCandidate` | One source-author proposal pinned to one Case revision | immutable; status derived |
| `MemoryCandidateVerification` | One terminal assigned-advisor decision | immutable and unique per candidate |
| `ConfirmedFact` | Advisor-confirmed typed fact with source and supersession lineage | immutable and versioned |
| `CaseRevisionConfirmedFactRef` | Complete current ConfirmedFact set applied to a resulting Case revision | immutable |

The six exact PostgreSQL tables are:

```text
app.collaboration_threads
app.message_events
app.memory_candidates
app.memory_candidate_verifications
app.confirmed_facts
app.case_revision_confirmed_fact_refs
```

Each table is migrator-owned, tenant-keyed, `ENABLE ROW LEVEL SECURITY`,
`FORCE ROW LEVEL SECURITY`, and protected by an explicit tenant policy. Composite
foreign keys bind redundant parents through `organization_id`, `case_id`, and the
parent identity. Immutable triggers reject row update and delete. Runtime roles have
no direct `SELECT`, `INSERT`, `UPDATE`, `DELETE`, or `TRUNCATE` grant on these
tables.

## Closed fact contract

Only a student or parent may propose a fact from their own message. The role and
fact-key matrix is exact:

| Fact key | Source role | Strict value |
| --- | --- | --- |
| `student.intended_field` | student | non-empty safe string, at most 160 UTF-8 bytes |
| `student.preferred_countries` | student | non-empty sorted unique subset of `australia`, `japan`, `malaysia` |
| `student.intake` | student | valid calendar month in `YYYY-MM` |
| `family.risk_tolerance` | parent | `low`, `medium`, or `high` |
| `family.japan_risk_accepted` | parent | boolean |
| `family.budget` | parent | strict schema-version-1 CNY `program_total` `BudgetEnvelope` |

Message bodies are inert plain text of 1 to 4096 UTF-8 bytes. Verification reasons
are 1 to 512 UTF-8 bytes. Bounded strings reject control characters, credential or
secret material, local paths, any case-insensitive `file://` substring, URL
credentials, and executable or shell structure.
Fact strings and verification reasons also reject plain URLs. Ordinary preference
words do not grant authority and are not rejected merely as prompt-like language.

One message may create at most one candidate. A candidate expires exactly seven
days after creation according to the database clock. Its derived status uses this
precedence:

```text
confirmed or rejected
  -> stale when its pinned revision is not current
  -> expired when database time reaches expires_at
  -> pending
```

Terminal status therefore remains terminal even after the Case advances or the
expiry time passes. Candidates are never rebased, revived, or edited.

## Confirmation and rejection

Only an assigned advisor may verify a candidate. The command supplies the candidate,
expected current Case revision, `confirm|reject`, a bounded reason, and the normal
idempotency proof. It cannot supply tenant, role, subject identity, source message,
Case ID, expiry, fact version, or revision contents.

Verification serializes resources in this order:

```text
operation-scoped idempotency advisory lock
  -> idempotency ledger
  -> Case FOR UPDATE
  -> candidate FOR UPDATE
  -> current fact head
  -> current PlanningRun
  -> terminal checks and writes
```

Worker planning-result persistence uses the compatible prefix
`Case FOR UPDATE -> superseded PlanningRun update`. It cannot hold the current
PlanningRun while waiting for a Case lock already held by verification.

Rejection atomically writes the terminal verification, an
`memory_candidate_rejected` audit event, and the idempotency response. It creates no
ConfirmedFact or Case revision.

Confirmation requires all of the following:

- the candidate is not already terminal, stale, or expired;
- the expected revision equals the candidate revision and current Case revision;
- the Case state is `intake` or `planning`;
- the role, fact key, candidate value, and current revision projection remain valid;
- no Case task is `queued`, `leased`, `running`, or `waiting_review`;
- a `planning` Case has exactly one current PlanningRun, while an `intake` Case may
  have none.

A successful confirmation writes, in one transaction:

1. the terminal `memory_candidate_verifications` row;
2. the next immutable `confirmed_facts` version and supersession link;
3. a cloned `StudentCaseRevision` with exactly the selected field replaced;
4. one `case_revision_confirmed_fact_refs` row for every current confirmed fact;
5. the Case current-revision compare-and-swap;
6. the exact prior current PlanningRun's `is_current=false`, when present;
7. the `memory_candidate_confirmed` audit event;
8. the idempotency response.

Any failure rolls back the entire command. Confirmation does not advance Case state,
create a planning task, approve Evidence, review a PlanningRun, or make a family
decision.

## PostgreSQL function and grant surface

The API role may execute exactly these collaboration functions:

```text
app.create_collaboration_thread(...)
app.append_collaboration_message(...)
app.propose_memory_candidate(...)
app.verify_memory_candidate(...)
app.read_collaboration_thread(...)
app.read_collaboration_messages(...)
app.read_memory_candidates(...)
app.read_confirmed_facts(...)
```

All are migrator-owned `SECURITY DEFINER` functions with fixed
`search_path = pg_catalog, pg_temp`, trusted `ActorContext`, participant checks, and
revoked `PUBLIC` execution. The worker receives none. The migrator-only
`app.seed_demo_collaboration(...)` function is not granted to either runtime role.

The API grant on the legacy whole-revision writer
`app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)` is revoked in
`0007`. That function remains only for migrator-controlled bootstrap and test setup.
The collaboration confirmation function is the sole runtime revision publication
path introduced by PR A.

Idempotency reuses `app.idempotency_records` with these exact operation names:

```text
collaboration_thread_create
collaboration_message_append
memory_candidate_propose
memory_candidate_verify
```

The same actor, key, and canonical request hash replay the original response. Reusing
the key with a different canonical request fails with `idempotency_conflict`. Raw
keys, session values, and CSRF values are not persisted in the collaboration rows.

## HTTP API

All endpoints require a valid opaque session and return `Cache-Control: no-store`.
Mutations additionally require the exact configured `Origin`, the session-bound
`X-CSRF-Token`, and an `Idempotency-Key` of 1 to 200 characters. Request models are
strict schema-version-1 models with `extra="forbid"`. Tenant, actor, role, subject,
and authority fields are never accepted from request JSON.

| Method and path | Assigned actor | Request or result |
| --- | --- | --- |
| `POST /api/v1/cases/{case_id}/collaboration-thread` | advisor | `{schema_version: 1}`; creates or idempotently returns the Case's single thread |
| `GET /api/v1/cases/{case_id}/collaboration-thread` | advisor/student/parent | shared thread projection |
| `GET /api/v1/collaboration-threads/{thread_id}/messages` | advisor/student/parent | stable sequence page |
| `POST /api/v1/collaboration-threads/{thread_id}/messages` | advisor/student/parent | `{schema_version: 1, body}`; immutable message |
| `POST /api/v1/messages/{message_id}/memory-candidates` | source student/parent | `{schema_version: 1, case_revision, proposal}`; participant-safe proposal projection |
| `GET /api/v1/cases/{case_id}/memory-candidates` | advisor or source participant | advisor sees all; participant sees only their own proposals |
| `POST /api/v1/memory-candidates/{candidate_id}/verification-decisions` | advisor | `{schema_version: 1, expected_case_revision, decision, reason}`; terminal result |
| `GET /api/v1/cases/{case_id}/confirmed-facts` | advisor/student/parent | role-safe current page; advisor-only bounded history |

Message paging uses `after_sequence` default `0`, `limit` default `50`, and maximum
`100`. `next_after_sequence` is the stable cursor when another page may exist. A
thread is capped at 1000 events. Same-key replay remains available at capacity; a
different-key append returns `409 collaboration_thread_full`. Candidate limits
default to `50` and are capped at `100`. Confirmed-fact `limit` bounds only
advisor history: all current heads remain present, and `next_cursor` advances a
keyset page bound to the Case revision visible on the first read. History membership
is defined by successor verification revision at or below that immutable high-water
mark, preventing later commits from entering the cursor chain. Student and parent
responses contain only `{schema_version, current}` and never expose history or cursor
metadata.

### Controlled same-Case browser handoff

After advisor confirmation, `/demo/collaboration` may validate the current candidate,
confirmed facts, Case revision, advisor ledger, and Planning Skill inspector through
the existing `no-store` BFF reads. The handoff itself does not create a task, resolve
task inputs, open SSE, or change database authority. It keeps the same Case and
advisor session, replaces the strict `schema_version=2` journey envelope once, and
navigates to `/demo` once.

Validation failure preserves the original collaboration envelope. The destination
re-reads the same Case and consumes only `ledger.canonical_task_inputs`; active,
review, or terminal task identity is adopted only from the ledger. Confirmation
therefore remains separate from the explicit advisor task action.

### Role-safe projections

All assigned participants see the shared thread and its messages. Candidate and
confirmed-fact metadata remain narrower:

| Field group | Advisor | Student or parent |
| --- | --- | --- |
| Candidate fact, value, status, created/expiry time | all Case candidates | caller's own proposals only |
| Candidate/message/verification IDs and pinned revision | yes | no |
| Candidate subject identity, source sequence, hashes, decision reason | yes | no |
| Current confirmed fact value, version, confirmed-at, subject role | yes | yes |
| Historical or superseded fact values | yes | no |
| Fact/candidate/verification/message IDs and digest prefix | yes | no |
| Confirming advisor | identity and role | role label only |
| Verification reason and supersession link | yes | no |

### Closed public errors

Authorization and unknown resources use the same non-enumerating `404
resource_unavailable`. Collaboration-specific validation and conflicts use only:

```text
case_revision_stale
memory_candidate_stale
memory_candidate_expired
memory_candidate_terminal
collaboration_thread_full
active_task_blocks_revision
invalid_collaboration_message
unsupported_fact_key
unsafe_fact_value
idempotency_conflict
persistence_unavailable
```

The shared HTTP boundary may also return bounded authentication, Origin, CSRF,
idempotency-header, and request-validation problems. PostgreSQL SQLSTATE mapping is
operation-sensitive: `NV003` is Case or candidate staleness, `NV006` is the unsafe
contract fallback, `NV007` is non-enumerating authorization, `NV008` is idempotency
conflict, `NV012` maps by operation to append-only `collaboration_thread_full` or
candidate-only `memory_candidate_terminal`, `NV013` is expiry, and `NV014` is
active-task blocking. Unexpected `NV012` uses and unknown, permission, connection,
serialization, and result
shape failures become `503 persistence_unavailable`. Public problems never include
raw SQL messages, tracebacks, credentials, cookies, local paths, or unbounded input.

## Deterministic demo identities

The idempotent migrator-owned demo seed creates four independent collaboration
Cases. They use the synthetic organization and existing advisor/student/parent
principals without mutating the default `/demo` Case.

| Fixture | Case ID | Thread ID | Additional fixed identity | Purpose |
| --- | --- | --- | --- | --- |
| primary | `41000000-0000-0000-0000-000000000001` | `42000000-0000-0000-0000-000000000001` | none | clean collaboration authority path |
| active task | `41000000-0000-0000-0000-000000000002` | `42000000-0000-0000-0000-000000000002` | task `48000000-0000-0000-0000-000000000002` | exact legacy-unpinned `waiting_review` block |
| stale candidate | `41000000-0000-0000-0000-000000000003` | `42000000-0000-0000-0000-000000000003` | message `43000000-0000-0000-0000-000000000003`; candidate `45000000-0000-0000-0000-000000000003` | candidate pinned to revision 1 while Case is revision 2 |
| expired candidate | `41000000-0000-0000-0000-000000000004` | `42000000-0000-0000-0000-000000000004` | message `43000000-0000-0000-0000-000000000004`; candidate `45000000-0000-0000-0000-000000000004` | database-clock expiry path |

The active task is deliberately `waiting_review` so it remains historical
legacy-unpinned state for the deferred PR B migration while still blocking PR A
confirmation. Seed replay must match every fixed identity and fixture shape or fail
closed.

## Downgrade contract

`0007 -> 0006` is allowed only when all six collaboration tables are empty and
neither reused ledger contains an exact PR A discriminator. Unrelated audit or
idempotency history from earlier features does not block the downgrade.

Downgrade refuses before destructive DDL when any thread, message, candidate,
verification, fact, revision reference, `memory_candidate_confirmed|rejected` audit
event, or one of the four collaboration idempotency operations exists. A successful
empty-boundary downgrade removes PR A tables/functions/triggers, restores the exact
`0006` PlanningRun guard, and restores the API grant on the legacy bootstrap writer.
Use disposable databases for both success and refusal proof; do not downgrade a
retained demo volume.

See [Collaboration authority operations](../operations/collaboration-authority.md)
and [ADR 0008](../decisions/0008-governed-collaboration-and-memory-authority.md).
