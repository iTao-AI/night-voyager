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
an immutable `TimelineMutationReceiptV1`. Case identity is part of each stable
mutation request and PostgreSQL revalidates it against the locked execution.
After an execution is resolved, same-key replay or conflict is decided before
new-request Case validation. The required client order is:

```text
persist operation fingerprint and key
  -> POST mutation
  -> capture immutable receipt
  -> fresh execution GET
  -> render authoritative state
```

Browser `sessionStorage` is only a revalidated recovery hint. Its envelope contains
closed demo scenario, role, Case/timeline/execution/checkpoint identifiers, observed versions, the last
receipt identifier, and operation fingerprints/keys. It contains no CSRF token,
opaque session, tenant/actor authority, due date, mutable activity, or attestation
body.

## Reassessment boundary

Migration `0014` implements reassessment authority for blocked attestations and
database-observed elapsed deadlines. It records predecessor identities and
`pending_future_authorization`; one composite foreign key binds the predecessor
Case, revision, decision, decision receipt, timeline, and execution, while the
checkpoint remains bound to that execution. It creates no successor business
row. PR B exposes that UI and proves its terminal recovery boundary.

### Saved handoff summary

The current frontend consumes the existing saved `TimelineReassessment` and
validated context/view anchors. It shows the Case revision, saved checkpoint,
immutable due date, accountable family role, accepted trigger, known reason,
next advisor responsibility and two distinct server dates.

The checkpoint is selected by `reassessment.checkpoint_id`, independently of
`current_checkpoint`. A blocked reason is displayed only when the projected
attestation's ID equals `trigger_reference_id` and its execution/checkpoint IDs
match the saved reassessment, with blocked kind/status. Otherwise matching
attestation detail is explicitly unavailable. A deadline trigger reports saved
server acceptance; the browser neither recomputes it nor substitutes a local
date. `accepted_database_date` is the saved acceptance date; `observed_date` is
the current read's database-observed date.

Source identities and `pending_future_authorization` appear in a disclosure.
`accepted_trigger_projection_sha256` is a saved reference only; the browser does
not claim to revalidate the accepted trigger projection. User-initiated copy
exports the displayed facts, source identities, dates and Stop as plain text,
excluding actor IDs, session credentials and request headers. Clipboard failure
exposes a read-only selectable text area. Copy creates no canonical record and
sends no message. Unsettled, busy, changed-session or mismatched-context state
has no copyable handoff; new role, locale or summary clears previous copy
feedback/fallback.

Each settled frontend read retains its requested seeded scenario or connected
Case as client source metadata. Copy requires that source to match the current
request. Changing Happy/Blocked or the requested Case withdraws the old summary
until a fresh validated read supplies matching facts. This source marker is
kept in memory and grants no business authority.

## Closed synthetic identity

Migration `0015` is identity-only. It retains the generic demo principals and
adds distinct exact advisor/student/parent triads for `happy` and `blocked`.
The browser supplies only the closed scenario key; the server maps it to an
exact principal and the queryless BFF context validates the one assigned Case.
Same-scenario role rotation is allowed. Generic-to-scenario, Happy-to-Blocked,
unknown, ambiguous, or Case-selector attempts fail before the old session is
revoked. The browser holds one generation-scoped lock across the atomic
`POST /demo/sessions` rotation and the following context/read reconciliation;
an older generation cannot unlock a newer operation. Migration `0014` and all
timeline transitions remain unchanged.

## Presentation and proof boundary

`/demo/plan` localizes the closed milestone, checkpoint, risk, activity, and role
codes without changing them. Current authority appears before controls, the
approved four-step plan is read-only, and blocked advisor state exposes only the
reassessment stop. One live region and deterministic post-mutation focus are
accessibility projections, not business state.

The semantic Playwright assertions and browser-to-database receipt/GET proof are
the pass/fail authority. The four checked-in screenshots are review evidence and
use only visibly labelled synthetic data.

The [saved handoff acceptance record](../evidence/reassessment-handoff-summary.md)
separately classifies the new routed-fixture browser checks. They verify parser,
presentation and clipboard behavior, while reusing the existing projection
contract; they do not establish new HTTP/database or native recovery acceptance.
