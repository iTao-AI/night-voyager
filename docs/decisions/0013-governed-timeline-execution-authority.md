# ADR 0013: Governed timeline execution authority

## Status

Accepted and implemented through merged PR A/B/C. The complete authority,
recovery/reassessment, presentation, and evaluator-first DX surface is included
in the v0.1.5 release candidate; publication remains separately gated.

## Context

The released workflow ends with immutable `FamilyDecision`, `DecisionReceipt`, and
`TimelinePlan` records. Those planning anchors do not record who reported progress,
which checkpoint an advisor verified, or why execution stopped for reassessment.
Reusing planning revision authority after a final decision would erase that boundary.

## Decision

1. Migration `0014` adds one execution per immutable `TimelinePlan`, ordered
   checkpoint snapshots, structured family attestations, advisor verifications,
   successor-safe reassessment requests, and immutable mutation receipts.
2. PostgreSQL owns Case selection, assignments, current date, row locks,
   transitions, idempotency, append-only history, and read-time risk. API and
   browser requests cannot supply `as_of`, tenant, actor, or role authority.
   Every mutation binds its public Case identity to the locked execution; an
   existing idempotency key resolves replay or request conflict before later
   new-request Case validation.
3. Family input is a structured attestation, not source `Evidence`. Only assigned
   advisor verification upgrades trust.
4. Every mutation returns a receipt. Clients must perform a separate fresh GET
   before rendering current state.
5. Current-action guidance is a synchronous deterministic projection. It creates
   no `AgentTask`, Skill, worker job, queue, scheduler, or SSE stream.
6. Reassessment records a future-successor-safe handoff but creates no successor
   Case, decision, timeline, execution, or other business row. A composite
   database anchor binds its predecessor Case, revision, decision, receipt,
   timeline, and execution identities, and the checkpoint remains execution-bound.
7. `0014 -> 0013` is allowed only with no execution history. Otherwise downgrade
   refuses before mutation.

## Consequences

The local `/demo/plan` route can start, attest, request an advisor update, verify,
advance, and complete the deterministic synthetic timeline. It renders blocked or
reassessment-required state without exposing a reassessment mutation in PR A.
Published v0.1.4 remains migration `0013`; the current development head is `0014`.

## Non-claims

This decision does not prove real application submission, document upload, live
provider execution, production tenancy, real-user adoption, admissions outcomes,
release completion, or deployment.
