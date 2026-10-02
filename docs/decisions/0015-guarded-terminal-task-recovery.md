# ADR 0015: Guarded terminal task recovery

Status: Accepted

Implementation status: Local implementation, Task 4 native/Compose/bilingual
browser acceptance, final branch review and owner acceptance are complete.
Scoped review resolved the final copy/document findings. No hosted delivery or
provider action is implied by this decision.

## Context

Bounded worker retries can end in a recoverable failure. An advisor needs an
explicit fresh-task action that preserves the failed task as audit history and
cannot reuse stale browser authority, silently change source pins, or approve a
new result automatically.

## Decision

1. The retry command carries only source Task identity, expected row version and
   expected Case revision. Trusted ActorContext supplies organization and advisor.
   The existing Origin, CSRF and assigned-advisor guards apply to the new HTTP/BFF
   mutation; its 202 response is the existing public Task resource.
2. Migration `0016` serializes retry under the Case row, rechecks current revision,
   exact latest source, assignment after lock acquisition, no accepted result and
   no successor. Only `failed` with `transient_unavailable`,
   `transport_interrupted` or `lease_expired`, and `timed_out` with
   `deadline_exceeded`, qualify. Hard, unknown, cancelled and outdated outcomes
   expose no action.
3. A separate `agent_task_retry` idempotency namespace binds source and both
   versions. Its exact replay returns the same successor after creation while
   current assignment and revision still apply. Ordinary create keys cannot stand
   in for retry consent. A composite source foreign key and partial unique index
   enforce at most one successor within the same organization and Case.
4. Retry takes its outer advisory lock, derived inner creation advisory lock,
   Skill definition SHARE lock, then Case UPDATE lock. It reuses the actual
   lineage-aware `create_agent_task` authority and its locks. Current packaged
   Skill validation occurs in the application and is revalidated atomically by
   creation. Case serialization prevents two current live tasks even when active
   Skill pins or operations differ.
5. Source operation, source-pack ID/version and policy remain exact. Eligible
   governed mixed tasks retain their approved promoted pack and mixed operation.
   This does not expand the existing synthetic-only connected demo ledger,
   `CanonicalDemoTaskInputs` or `EvidenceDisclosure` shapes. Mixed recovery is
   supported through the existing Task API authority.
6. The source Task, events and AgentExecution diagnostics are immutable. The new
   task records `retried_from_task_id`, starts a fresh bounded execution and must
   return through a fresh advisor review before family authority is issued.
7. V1 keeps its terminal response shape with null canonical inputs and truthful
   recovery policy. V2 exposes terminal canonical inputs iff server eligibility
   allows recovery. Phase/identity validation rejects invented authority. The
   browser requires explicit advisor consent, saves the exact body and fresh key
   for each failed source, and replays that submitted intent after network loss or
   same-tab reload. It refreshes the authoritative ledger before adopting the new
   Task and existing SSE stream.
8. Only API execution grants are added for retry and eligibility functions.
   Functions use SECURITY DEFINER with `pg_catalog, pg_temp` search path; existing
   forced RLS and direct-write denial remain. Downgrade is allowed before recovery
   history exists and refuses once a successor or retry idempotency record exists.

## Consequences

Recovery does not change a failed task's diagnostics or reuse its attempt budget.
Stale ledger affordances may be rejected at POST time. An ambiguous response needs
exact-key replay, while a changed body or new key is a new command subject to all
current guards. The dedicated native runner supplements the full Task 4 gates;
published release records remain immutable history.
