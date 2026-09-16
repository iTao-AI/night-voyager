# Configurable budget intake and explainable planning outcomes

Design and implementation plan, 2026-09-16. Copy this document to `docs/superpowers/plans/2026-09-16-configurable-budget-intake.md` before implementation.

## Outcome

A family can enter its preferred and maximum program budget in the existing collaboration journey. The advisor sees exactly what was submitted, explicitly confirms it, and starts planning from the persisted confirmed fact. A restrictive budget produces an understandable outcome from the planner rather than a misleading generic technical failure. The current default journey continues to work.

This is a local synthetic workflow with editable inputs. A structured budget form does not claim natural-language extraction or live policy research. The scope ends at a verified local implementation.

## Current implementation and scope

Baseline: `ecd1ed3188c402e9de4ba181bfb9936470b50277`.

- `web/lib/collaboration-demo/use-collaboration-demo.ts` currently fixes the parent message, budget, and candidate request to CNY 300,000 / 400,000.
- `web/lib/connected-demo/session-storage.ts` persists recovery metadata and mutation fingerprints, but not a configurable budget intent.
- `BudgetEnvelope` and collaboration `family.budget` proposals already support the required domain values; reuse them.
- `PlanningRevisionComparisonV1` already supports budget deltas, but the connected revision journey deliberately assigns `revision_requested` to the student. This phase does not generalize that journey or change role authority.
- The initial blocked planner result can be hidden behind `terminal_task_failure`. Inspect and reuse the persisted result for explanation; do not fabricate an explanation from form values.

Change the existing `/demo/collaboration` workflow, its recovery and local presentation, and only the read-model support required to explain its actual outcome. Retain the existing country-preference revision workflow. No new model/provider, general chat, database migration, role system, HTTP endpoint, or evaluation platform is needed.

## User experience

1. In the parent input step, show `期望预算（元）` and `最高预算（元）`, with the existing default 300000 / 400000. Label these as total program costs. Show the retained budget elasticity explicitly; this slice retains the existing 10% value and does not silently change it.
2. Offer two small fill-only examples: `常规预算` (300000 / 400000) and `紧预算` (100000 / 120000). Selecting an example only edits the draft and makes no request. The user can enter other valid whole-yuan values.
3. Show a compact readable summary before `提交预算说明`. A valid input requires positive decimal whole-yuan integers, preferred <= maximum, and safe integer conversion to minor units. Reject blank, negative, exponent notation, decimals, NaN/Infinity, and unsafe integers with local, specific feedback; send zero mutation requests on invalid input.
4. Once the first submission is in flight or accepted, lock the submitted intent for that journey. Message and candidate must refer to the same amounts and case revision. The separate existing candidate creation and advisor confirmation actions remain explicit.
5. The advisor sees the submitted amounts, their source message, and the pending confirmation. Do not imply a budget is confirmed before the advisor action succeeds.
6. The handoff uses the same Case and persisted confirmed fact. Its outcome must reflect the selected budget. On a restrictive outcome, lead with a plain-language statement such as `当前条件下没有可直接确认的路线`, then show persisted route reasons where available. Keep budget constraints distinguishable from technical timeout or transport errors.
7. Keep the present visual language and one primary action per stage. Use a compact form with a readable summary, not another dashboard. Chinese remains the default; add English UI copy using the existing catalog. At 390 px the fields stack and the action stays reachable.

## Intent and recovery design

Create one validated immutable budget intent when the user submits. It contains the budget value and the expected current case revision needed to construct the message and candidate. Use a deterministic message renderer; recovery must not infer amounts by parsing arbitrary prose.

Persist the minimum required intent in a new closed collaboration journey envelope version. Keep the advisor-family envelope unchanged. Do not weaken the exact-key, phase, role, or mutation-fingerprint checks. The session record is a recovery aid, not business authority.

- Retry the exact submitted message/proposal body and idempotency key after a lost response. Editing a draft must never change the body of an already recorded mutation.
- On reload, reconcile against server messages, candidate identity/value/revision, and confirmed facts before choosing the next action. Replace matching based on the old fixed message or the first `family.budget` item with identity and exact-intent matching. Multiple or inconsistent matches produce a recoverable state rather than selecting one arbitrarily.
- Preserve the submitted intent through role changes until the confirmed same-Case handoff completes. Keep participant projections as limited as the existing API requires.
- Handle the existing fixed-input v2 envelope explicitly. A legacy request may be resumed only when its known legacy fingerprint and server observations support the legacy default intent. Otherwise explain that recovery needs a fresh observation; never silently replay it using a new amount or clear business records.
- Session expiry, response loss, stale revision, and malformed storage must preserve the current recovery protections. Language changes are read-only.

## Read-model outcome design

Use existing `AdvisorLedgerV2` fields to project an actually persisted blocked planning run when a current `needs_evidence` task has a valid matching result. Reuse `_review_projection(..., allow_blocked=True)` only after checking Case, task, revision, and current-result identity. Keep `comparison=null` for an initial planning run; it is not a historical replanning comparison.

Keep the wire phase and endpoint set unchanged. An enriched initial blocked projection may carry its existing `planning_run`, `routes`, and `evidence` fields; it must keep `review_inputs=null`, no current deliverable brief, and no approval action. Actual failed/timed-out/cancelled tasks without a valid planning result retain their existing failure projection. The browser may select explanatory copy based on these observed fields, but must not calculate eligibility, approve a route, or synthesize missing result rows.

If existing model validators or parsers need strengthening to enforce those invariants, update producer and consumer tests together. Do not create a new business state merely to simplify presentation. If this cannot be achieved without a migration or new public contract, return the concrete conflict before expanding the design.

## Implementation sequence

1. Inspect live rules/status and the relevant collaboration, recovery, read-model and browser tests. Account for the already reviewed local walkthrough correction `d50c279d7f96442a7f20321f74a948de319cc62e` without changing or deleting its retained worktree. Carry its relevant correction into this branch if the affected documentation is updated.
2. Add focused failing tests for budget validation, immutable request intent and recovery. Implement the intent builder, versioned collaboration storage and recovery reconciliation.
3. Add the form and advisor readback using existing components/catalog. Keep default, role-switch and same-Case handoff behavior intact.
4. Add producer/consumer tests for observed blocked results, implement the bounded read-model enrichment and readable UI. Confirm ordinary failures remain ordinary failures and blocked results cannot become deliverable.
5. Exercise the actual stack on task-owned synthetic data for default, a distinct valid non-default budget, and the restrictive example. Add/extend the smallest existing browser proof and database integration tests that verify the new behavior.
6. Update the affected walkthrough and README entry with short usable instructions, a current screenshot and the actual scope. Do not rebuild the entire landing page or change release numbers. Record which routes are live local execution versus static presentation.

## Acceptance

- A non-default budget is visible unchanged in the parent message, candidate, advisor confirmation and current confirmed fact. The planner input and persisted result use that fact; verifying only the form text is insufficient.
- Default and non-default viable input reach the existing review/decision path where the actual planner permits it. The restrictive case exposes actual reasons, cannot approve, and produces no receipt/TimelinePlan. If a sample has an unexpected result, inspect policy evidence rather than forcing the expected UI outcome.
- A lost message/candidate/confirmation response followed by retry or reload does not duplicate the corresponding mutation, switch the amount, or skip advisor confirmation. Test the meaningful transitions, not every copy string.
- Existing country revision, parent confirmation, same-Case execution handoff, expired-session recovery, and locale switching remain correct.
- All changed frontend code passes lint, typecheck, relevant tests and build. Changed backend code passes the relevant unit/contract tests, ruff and pyright. Run actual PostgreSQL integration proof for the affected projection and at least the default/restrictive browser flows; mocks alone do not close this phase.
- Reuse the existing locked dependencies and local caches. If an aggregate command reinstalls dependencies or invokes unrelated provider lanes, run its relevant checks directly and record the actual commands. No new dependency, browser, model or base-image download is part of this phase.
- Review the actual 1440 px and 390 px pages, including invalid input, pending confirmation and blocked result; preserve screenshots of the new behavior. No clipped labels or horizontal page overflow.
- End with an independently reviewable local commit, task-owned worktree clean, exact validation results and a compact walkthrough. Stop only task-owned processes and synthetic resources. Do not publish or clean other worktrees/resources.
