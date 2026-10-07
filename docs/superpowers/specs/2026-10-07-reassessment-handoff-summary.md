# Reassessment handoff summary

Status: implemented locally; frontend and fixture/browser acceptance passed;
final branch review pending. Hosted delivery is separate.

The saved reassessment becomes a readable, bilingual handoff for an advisor who
must judge changed circumstances and obtain any future authorization. This is a
read-only consumer of `PlanExecutionContext` and `TimelineExecutionView`.

## Scope and authority

- Show the saved Case revision, matched milestone, due date, trigger, known
  reason, checkpoint responsibility, next advisor responsibility and dates.
- Match the checkpoint by `reassessment.checkpoint_id`. A blocker reason is
  available only when the projected attestation matches the trigger reference,
  execution and checkpoint, and represents a blocked attestation.
- Missing detail remains explicitly unavailable. Deadline acceptance is a saved
  server fact; the browser does not recalculate it using a local clock.
- Distinguish `accepted_database_date` from the view's `observed_date`. The saved
  projection digest is a reference, not a browser verification claim.
- Collapse technical source identities. User-initiated copy exports the same
  facts and identities as plain text. Clipboard failure exposes selectable text.
  Export excludes actor identities, credentials and request headers.
- Loading, mutation, authority/context change or session loss removes the old
  copyable summary. A completed asynchronous clipboard operation cannot attach
  stale success/failure UI to a different summary.
- Preserve the Stop and `pending_future_authorization`. The summary grants no
  successor, recovery or replanning permission and sends no external messages.

No database, worker, RLS, Case, consent, receipt, intake, evidence or backend
contract changes are included. No dependencies or lockfile changes are needed.
The current published release boundary remains unchanged.

## Observable acceptance

1. Accepted blocked and deadline projections show their available facts in both
   languages. Reference/checkpoint mismatches and missing attestations never
   become a claimed blocker reason.
2. The saved checkpoint wins even if `current_checkpoint` differs. Context and
   view anchors must agree before the summary can be copied.
3. Actual browser fixtures cover Chinese and English at 1440 and 390 pixels,
   readable layout, copy, clipboard failure and context/session changes.
4. Export includes saved/view dates and source anchors, with no actor IDs or
   request credentials. A new render never exposes a stale fallback.
5. Relevant frontend tests, lint, typecheck, build, diff and documentation review
   pass. Existing HTTP/database projection evidence is inspected and reused;
   fixture browser checks are not classified as new native business validation.

## Delivery

One isolated local branch starts at `0017d364995ca59e9b71cad48433d9e485fb6c3a`.
The delivery owner may decide in-scope implementation details, verify and commit
locally. Hosted delivery and heavy native recovery acceptance remain separately
authorized. See the [implementation plan](../plans/2026-10-07-reassessment-handoff-summary.md).
