# Connected same-Case plan execution continuation v1

Status: Approved
Implementation: Merged on the current default branch in PR #103; local synthetic and provider-free; not included in stable v0.1.5; not deployed

## Problem

The connected synthetic advisor-to-family journey preserves fact revision, renewed review, family decision, DecisionReceipt, and TimelinePlan on one current StudentCase. At plan_ready, however, the browser links to /demo/plan, whose happy and blocked paths are independently seeded scenarios. That boundary is honest, but it prevents a user from verifying that the exact current Case decision becomes the authority for execution and blocked reassessment.

## Goal

Add one participant-safe, case-scoped continuation from the current connected Case into the existing governed timeline execution flow. The continuation must preserve the exact current case revision, decision, decision receipt, and timeline plan through start, reload, role handoff, checkpoint activity, and reassessment.

## Non-goals

- No new business state table, migration, RLS or permission relaxation, mutation schema, domain transition, queue, scheduler, worker job, or second orchestration framework.
- No automatic successor Case, planning revision, TimelinePlan, or execution.
- No provider or model call, new dependency, real student data, deployment, tag, Release, or package publication.
- No merging or rewriting of the independently seeded happy and blocked scenarios.
- No visual redesign. Only necessary navigation, copy, documentation, and affected current deterministic evidence may change.

## Authority boundary

PostgreSQL remains the only business authority for StudentCase, current revision, FamilyDecision, DecisionReceipt, TimelinePlan, execution, checkpoint, attestation, verification, and reassessment.

The browser supplies only the public case_id route identity. The server derives all current revision, decision, receipt, timeline, execution, participant, and role identities. Client storage, query parameters, display state, and mutation bodies do not become business truth.

All writes continue through the existing timeline execution service and database mutation functions. The continuation introduces no alternative mutation path or frontend-only execution state.

## Read contract

Add:

GET /api/v1/cases/{case_id}/plan-execution-context

The endpoint is owned by the existing timeline_execution module and returns the strict product contract night-voyager.connected-plan-execution-context.v1:

- schema_version = 1
- journey = connected-advisor-family
- case_id
- case_revision
- decision_id
- decision_receipt_id
- timeline_plan_id
- execution_id or null
- active_role
- assignment_status = assigned

A projection is available only when the authenticated actor is an assigned participant for the requested Case and the server can derive exactly one internally consistent current revision, decision, receipt, and timeline. An optional execution must belong to that exact timeline.

Missing, multiple, noncurrent, foreign, cross-Case, role-mismatched, or contradictory identities fail closed with a bounded non-enumerating problem response. The response does not disclose whether another Case or identity exists.

Implement the projection in PostgresTimelineExecutionRepository with existing row-level security and existing SELECT grants. Do not add a migration or SECURITY DEFINER function. If those existing boundaries cannot safely produce the contract, stop instead of broadening authority.

## Browser continuation

Add the strict BFF mirror:

GET /api/demo/cases/{caseId}/plan-execution-context

At connected plan_ready, offer a primary action to continue the current plan execution. The destination carries only the current case_id.

The plan execution route supports two mutually exclusive authority sources:

1. connected mode: exact case-scoped context and connected demo principals;
2. seeded mode: the existing happy or blocked scenario and plan_execution_* principals.

Unknown, mixed, or contradictory route identities fail closed.

Parameterize the existing plan execution API/controller only at the context/session authority seam. Reuse the existing reducer, receipts, idempotency, stale-authority refresh, receipt-then-GET reconciliation, reload recovery, role checks, and presentation components. Do not duplicate the execution state machine.

Persisted recovery metadata must identify the authority kind and exact case or scenario. It must never restore a connected Case into a seeded scenario or a seeded scenario into a connected Case.

## Compatibility and public truth

CurrentDecisionBriefV2 and all existing mutation endpoints remain compatible. Existing /demo/plan happy and blocked scenarios remain available and explicitly independent.

Update current README/docs/navigation to explain the new same-Case continuation and the retained independent recovery scenarios. Historical Release records and tagged evidence remain immutable.

Refresh only current deterministic screenshots or manifests whose visible source changed. Semantic database/browser assertions remain acceptance authority; screenshots remain review evidence.

## Acceptance

The implementation is accepted only when:

1. the same connected Case proceeds from confirmed fact revision through renewed review, family decision, exact receipt/timeline, execution start, reload, role handoff, blocked checkpoint, and reassessment;
2. case revision, decision, receipt, timeline, and execution identities remain exact at every boundary;
3. lost acknowledgements replay the same mutation and fresh read, without duplicate business rows;
4. family roles can start/attest, the assigned advisor can verify/reassess, and cross-role/cross-Case access fails closed;
5. reassessment records the exact predecessor chain and stops at pending_future_authorization;
6. independent happy/blocked scenarios and all existing authority, security, consumer, frontend, and packaging gates remain green;
7. public docs and affected deterministic evidence describe the implemented synthetic/local behavior without production, user, or outcome claims.
