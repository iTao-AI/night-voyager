# Timeline execution contract

Migration `0014` adds a separate execution authority after an immutable
`TimelinePlan`. Planning records remain unchanged.

## Authority chain

```text
FamilyDecision + DecisionReceipt + TimelinePlan
  -> TimelineExecution
  -> ordered TimelineCheckpoint snapshots
  -> family CheckpointAttestation
  -> advisor CheckpointVerification
  -> next checkpoint or completed
  -> optional reassessment-required handoff
```

PostgreSQL owns the selected Case, assigned participants, canonical milestone
order, accountable roles, observed date, risk state, locking, version checks,
idempotency, receipts, and transitions. `StudentCase.state` remains `plan_ready`.

## Checkpoints and roles

| Ordinal | Milestone | Accountable family role |
| --- | --- | --- |
| 1 | `documents` | `student` |
| 2 | `application` | `student` |
| 3 | `visa` | `student` |
| 4 | `arrival` | `parent` |

A currently assigned student or parent may start. Only the accountable role may
submit a structured `progress`, `completion`, or `blocked` attestation. Attestation
is not source `Evidence`; it accepts no URL, upload, filename, free-form narrative,
external account, or source locator. Only the assigned advisor may `verify`,
`request_update`, or create the reassessment handoff.

## State and read projection

Execution states are `active`, `reassessment_required`, and `completed`.
Checkpoint states are `pending`, `in_progress`, `awaiting_advisor`, `verified`,
and `blocked`. Risk is projected as `on_track`, `due_soon`, or `overdue` from
PostgreSQL `CURRENT_DATE`; callers cannot submit `as_of`.

The read projection includes the execution, ordered checkpoints, at most one
current checkpoint, latest attestation and verification, optional reassessment,
database-observed date, and a bounded 64-item activity page with exact total and
truncation flag. Current action is derived synchronously from that projection and
is not durable work.

## Mutation and recovery contract

Every mutation uses the existing `app.idempotency_records` authority and returns
an immutable `TimelineMutationReceiptV1`. The required client order is:

```text
persist operation fingerprint and key
  -> POST mutation
  -> capture immutable receipt
  -> fresh execution GET
  -> render authoritative state
```

Browser `sessionStorage` is only a revalidated recovery hint. Its envelope contains
role, Case/timeline/execution/checkpoint identifiers, observed versions, the last
receipt identifier, and operation fingerprints/keys. It contains no CSRF token,
opaque session, tenant/actor authority, due date, mutable activity, or attestation
body.

## Reassessment boundary

Migration `0014` implements reassessment authority for blocked attestations and
database-observed elapsed deadlines. It records predecessor identities and
`pending_future_authorization`; it creates no successor business row. PR A renders
the stop safely but exposes no reassessment action. PR B owns that UI and recovery
proof.
