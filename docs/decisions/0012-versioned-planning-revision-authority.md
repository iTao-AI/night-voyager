# ADR 0012: Versioned planning revision authority

## Status

Accepted and released in v0.1.4 as controlled provider-free evidence. PR 1,
PR 2, and PR 3 are implemented; strict live acceptance remains incomplete.
No provider, credential, live acceptance, tag, release, or deployment action
is authorized by this decision.

## Context

An advisor can already persist an exact `request_revision` review and confirm a
changed planning fact through the collaboration authority. Before migration
`0012`, the next planning task had no durable pointer to the run being revised.
A worker could therefore recover only by looking at current state, which is not
enough once the predecessor is deliberately made non-current.

The required authority chain is:

```text
request_revision review -> fact revision -> frozen task predecessor
  -> one task-owned successor -> deterministic old/new comparison
```

The old run must remain immutable audit history while losing current business
authority. HTTP and browser code must not submit a predecessor, output hash,
comparison, revision projection, or approval identity.

## Decision

1. Migration `0012` adds
   `student_case_revisions.revision_requested_by_review_id`,
   `student_case_revisions.superseded_planning_run_id`, and
   `agent_tasks.predecessor_planning_run_id`. Composite constraints bind every
   identity to the same organization, Case, and revision lineage.
2. Exact fact confirmation locks the Case before the current PlanningRun,
   validates the same-revision current `request_revision` review, publishes the
   new revision, and makes the predecessor non-current in one transaction.
3. A `waiting_review` predecessor task is exempt from the inherited active-task
   guard only when it produced the exact current run and that exact durable
   request review exists. All queued, leased, running, unrelated, or unreviewed
   tasks remain blocking. The predecessor task stays immutable
   `waiting_review` history.
4. Task creation copies the revision-owned predecessor into the task. The
   worker never infers predecessor from current PlanningRun. It loads only the
   claimed task's immutable predecessor.
5. Result persistence validates the task-owned predecessor, the non-current
   predecessor row, and the successor revision before insertion. Partial unique
   indexes and transactional checks enforce one predecessor -> at most one
   successor, including retry, lost-ack, and concurrent finalization paths.
6. The old run retained but non-authoritative remains immutable. Its routes, dimensions, and
   Evidence uses remain available only for bounded comparison reconstruction.
7. The comparison is deterministic and country-keyed. PostgreSQL loads exactly
   the predecessor and successor rows in original policy order; the domain
   layer reconstructs and validates both complete `PlanningResult` values,
   verifies their canonical SHA-256 values, and emits one closed
   `night-voyager.planning-revision-comparison.v1` projection.
8. Existing advisor-ledger and current-decision-brief routes keep V1 read routes
   as the default. One exact `contract_version=2` selects the V2 response.
   Missing, repeated, empty, or unknown negotiation values fail closed.
9. `GET /api/v1/cases/{case_id}/journey-status` returns only Case identity,
   current revision, durable phase, and the verified participant's active role.
   The journey-status is participant-safe recovery authority, not browser
   storage.
10. Migration `0012` adds the narrow API-only
    `app.read_connected_journey_fact_pending(uuid,uuid,text,uuid)` projection.
    It derives current revision internally and returns one boolean for an exact
    unexpired, unverified changed planning fact. It exposes no candidate,
    value, hash, message, actor, review, task, run, route, Evidence, or authority
    identity.
11. The pending-fact projection is migrator-owned `SECURITY DEFINER` with
    `search_path = pg_catalog, pg_temp`; `PUBLIC` and
    `night_voyager_worker` cannot execute it. The API and worker retain no
    direct table privilege on `app.memory_candidates` or
    `app.memory_candidate_verifications`.
12. `planning-revision worker` keeps the historical mixed-downgrade proof, but
    runs it in its own disposable database after the normal worker lane.
    `planning-revision all` runs authority, worker, isolated mixed downgrade,
    and projection serially.
13. Safe downgrade refuses before mutation when revision lineage exists.
    Without lineage it drops the new function, indexes, columns, constraints,
    and replacement bodies and restores the exact `0011` signatures and grants.

## Transaction and recovery order

```text
idempotency advisory lock
  -> idempotency record
  -> Case FOR UPDATE
  -> exact current-revision request review
  -> inherited active-task guard with the narrow reviewed-waiting exemption
  -> predecessor PlanningRun
  -> fact/revision/currentness writes
```

Task creation and finalization preserve the Case-to-PlanningRun ordering.
Same-key replay returns the original durable result; a changed payload is an
idempotency conflict. Rollback leaves task, run, review, revision, fact,
currentness, and idempotency state unchanged.

## Consequences

- `scripts/run_db_tests.sh planning-revision authority` proves migration,
  atomic publication, concurrency, rollback, RLS, grants, query bounds, and
  downgrade behavior.
- `scripts/run_db_tests.sh planning-revision worker` proves task-owned lineage,
  retry, reclaim, lost acknowledgement, and the separately isolated historical
  mixed downgrade.
- `scripts/run_db_tests.sh planning-revision projection` proves V1/V2
  negotiation, complete comparison hashes, every durable revision phase, and
  participant-safe HTTP/PostgreSQL reads.
- `scripts/run_db_tests.sh planning-revision all` runs the three authorities and
  the isolated downgrade lane serially.
- PR 3 browser journey is implemented provider-free. The backend status
  endpoint remains recovery authority, not permission for a browser to
  calculate phase or retain database identities.
- Migration `0012` remains the runtime lineage authority. Migration `0013` adds
  only the closed provider-free demo seed helper, with zero runtime grants.
  Its isolated `planning-revision-seed-migration` lane proves exact replay,
  drift refusal, downgrade, and re-upgrade. This forward migration does not
  change runtime lineage semantics or authority.

## Non-claims

This decision does not prove provider quality, live acceptance, production
readiness, admissions outcomes, real-user use, frontend completion, release
completion, or deployment.
