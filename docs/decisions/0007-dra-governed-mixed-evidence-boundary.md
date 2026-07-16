# ADR 0007: Govern DRA candidate evidence and atomic promotion

- Status: Accepted
- Date: 2026-07-15

## Context

DRA can provide research material, but an external provider cannot own Night
Voyager evidence authority. Provider output may contain useful source links
while also carrying untrusted narrative, mutable state, or claims outside the
approved planning policy.

## Decision

DRA remains an optional research provider behind product-owned contracts. A
strict v1 projection imports only immutable `UNTRUSTED_CANDIDATE` rows. Import
has no source-pack, Evidence, PlanningRun, AgentTask, review, Brief, receipt,
timeline, or Case-transition side effect.

An assigned advisor may make one terminal verification decision. Human
verification and approve-time promotion execute in one PostgreSQL transaction
and create one immutable audit row. Approval has one external allowlist:

```text
australia_program_fit -> program_fit -> externally_verified
```

Approval creates one derived source-pack revision and one external Evidence;
all other accepted facts are exact copies of the synthetic baseline. Rejection
creates neither. Callers cannot provide authority, promoted identities,
baseline pins, tenant claims, roles, or credentials.

Delivery is split into two ordered pull requests. PR 1 establishes candidate
import, verification/promotion authority, API, and proof. PR 2 adds
`generate_governed_mixed_planning_run_v1` only after the merged PR 1 boundary.
It uses a worker-only PostgreSQL snapshot function and the existing AgentTask
queue, lease, retry, fencing, event, SSE, AdvisorReview, and family-decision
authorities. The existing all-synthetic planning function and `/demo` remain
unchanged.

## Consequences

- Provider output cannot promote itself or bypass `ActorContext` and forced RLS.
- The database is the atomic authority boundary for approval and rollback.
- Live provider proof requires separate authorization and is not a CI gate.
- Mixed planning admits external authority only for `australia_program_fit`;
  every other accepted fact must exactly match the synthetic baseline.
- Migration `0006` adds no table and grants the mixed snapshot function only to
  the worker role.
- Generic persisted planning, a separate promotion queue/table, and automatic
  advisor approval are rejected designs.
