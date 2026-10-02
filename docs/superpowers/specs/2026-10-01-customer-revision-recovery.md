# Editable client decisions and explicit task recovery

Date: 2026-10-01. Status: approved design for local implementation by the design owner under the delegated improvement scope. This remains a controlled synthetic pilot.

## Goal and baseline

Turn the existing connected journey into a demonstrable client workflow: a household proposes a real supported change, an advisor confirms it, the system replans against the new CaseRevision, the family explicitly chooses its accepted budget and trade-offs, and an advisor can start a fresh task after an eligible terminal failure.

The backend already supports confirmed-fact candidates, budget and preferred-country revisions, immutable planning history, comparisons, renewed advisor approval, family receipts, PostgreSQL-backed tasks, bounded worker retries, and SSE. Initial budget intake is already editable. The revision UI currently submits a fixed preferred-country script; family decision inputs are mostly auto-filled; terminal-task retry_allowed has no matching UI operation and is too broad. Extend these actual seams instead of rebuilding intake, orchestration, or generic retry infrastructure.

## A. Real supported revision inputs

Replace the fixed baseline/target lists with a small form initialized from the current authoritative facts and CaseRevision. The household selects one supported fact per revision:

- student.preferred_countries: an explicit non-empty, duplicate-free selection from the existing Australia/Japan/Malaysia domain values.
- family.budget: an explicit valid budget using the existing domain shape, currency and minor-unit conversion; preserve current backend bounds.

Show current and proposed values, require a material change, and reject invalid input before submission while keeping server validation authoritative. Submit through the existing participant proposal -> candidate -> advisor confirmation -> new revision flow. A household draft cannot directly mutate confirmed facts or authorize replanning. Display the actual pending candidate and let the advisor confirm it with a meaningful reason; do not identify a candidate by matching a hard-coded target list.

Persist idempotency for one submitted body; edited values create a new intention. A stale CaseRevision must force authoritative reload rather than silently apply against the newer case. After confirmation, old planning and approval remain historical; the current revision requires a new task, comparison, and advisor review. Preserve the existing one-fact-per-revision rule and explicitly unsupported combinations.

## B. Explicit family acceptance

Use the current DecisionBrief's requirements to collect accepted budget minimum and maximum and separate acknowledgments for required trade-offs. Initialize clearly explained suggested values, but submission sends the actual current form values and selected acknowledgments, not hidden automatic acceptance of every requirement.

The accepted interval must contain the pinned cost, stay within the hard ceiling, and use the current currency/minor-unit contract. All required trade-offs must be acknowledged. The existing eligible route remains the route submitted; the UI must not invent additional eligible routes or a decorative selection among unsupported countries.

The real parent-role action, current brief version, Origin/CSRF guard, and server policy remain mandatory. Brief/version changes reset stale confirmation. Store the explicit choices in the existing immutable FamilyDecision/receipt so the rendered receipt matches what was accepted. A checkbox in the advisor view does not impersonate family authority.

## C. Explicit recovery after a terminal task

Worker-level transient retries already exist and remain bounded. This feature is a separate, advisor-authorized fresh-task operation; it does not resume a crashed model call or mutate the old task into success.

Add POST /api/v1/tasks/{task_id}/retry and the matching BFF client path using the existing authentication, actor, Origin/CSRF, idempotency, task DTO, and creation service. The request supplies the expected source-task row version and expected current CaseRevision. The server owns the new task's current canonical Source/policy/skill pins.

Eligibility is deterministic: the source belongs to the current case/organization, is the latest terminal task for the current revision, has no accepted result or concurrent successor, and has a recognized recoverable failure. The allowlist is transient_unavailable, transport_interrupted, lease_expired, and deadline_exceeded, but only codes with a real current terminal producer may be enabled. Unknown codes, cancellation, outdated results, invalid_schema, pin_mismatch, fallback_authority, and policy_rejected have no unchanged-input retry affordance. Correcting facts/configuration and deliberately creating a new ordinary task is a separate existing authorized workflow, not this recovery action.

Re-read and guard eligibility in the same application/database operation that creates the new task. Reuse durable creation, role/RLS constraints, uniqueness, and transaction primitives; do not add an in-memory queue. One consent creates one fresh idempotency key bound to source-task identity and the requested revision. Ambiguous network replay reuses that key; a later distinct failed task does not. Concurrent clicks or stale actors cannot create duplicate active tasks or replay a previous successful create response as the retry result.

Keep the failed task and its diagnostics immutable. Return the new Task resource and refresh the authoritative ledger. Use the existing active-task -> review flow; no prior advisor approval applies to the new result.

Keep v1 field shapes and legacy reads compatible. The existing v2 ledger can expose canonical_task_inputs for an eligible terminal failure without a new schema version; strengthen its phase checks and make retry_allowed truthful. Populate this affordance from server policy, never from browser failure-code guessing. The endpoint revalidates independently even if the ledger is stale. Record the authority/API decision in an ADR.

## Architecture, references, and boundaries

Browser -> BFF -> application services and deterministic policy -> PostgreSQL remains the authority path. LLMs may draft; they cannot confirm facts, decide recovery eligibility, grant approval, or commit family choices. Preserve tenant isolation, parent/advisor roles, source provenance, active revision, and synthetic labeling.

Use the existing contracts and installed dependencies. Verify native PostgreSQL task/actor behavior with runtime-equivalent roles; fixture objects alone cannot prove the transaction or RLS boundary. No new orchestrator or paid model is needed. The accepted bilingual terminal-failure explanations are carried into this branch and should remain useful in the new recovery view.

Deferred: reassessment successor-case automation, source refresh and promotion, new eligible routes, multiple simultaneous fact edits, production accounts/billing, external applications, and automatic approvals. Reassessment remains an explicit terminal handoff to future authorization.

## Delivery slices and acceptance

1. Replace the fixed revision proposal and advisor matcher with actual supported form values; prove preferred-country and budget revision paths, comparison, and renewed approval, including stale/invalid input cases.
2. Implement explicit family budget/trade-off choices and prove the receipt matches the submitted choices, with invalid bounds and old brief-version negative controls.
3. Implement guarded terminal recovery, backend concurrency/idempotency/RLS tests, truthful ledger semantics, and the UI action. Prove one recoverable failure -> explicit retry -> new task -> advisor review, plus hard/unknown failure rejection and concurrent replay.
4. Inspect the real connected UI at desktop and narrow/mobile widths in Chinese and English, run relevant frontend/backend checks and required PostgreSQL/Compose gates on the final candidate, and perform the important-feature documentation audit. Keep role and revision evidence readable in a concise runnable walkthrough.

Use deterministic/synthetic adapters for the complete demonstration. Do not claim real household adoption or admissions outcomes. Return exact HEAD, checks and role/concurrency proof, actual screenshots/observations, documentation impact, and unfinished gates. No success claim substitutes for a missing required database check.

## Execution and authorization

Delivery owner: the dedicated project task, Sol Max. Use Superpowers writing-plans to close implementation detail, then select direct execution or subagent-driven development. Sol High handles behavioral implementation and substantive review; Luna Max is limited to clear mechanical work. Ordinary in-scope decisions remain with the owner; changes to goals, authority, domain scope, or authorization return to the design owner.

Public main was verified at 4abeac36142f719cda1c2696c89531d64ef7312c. Prepared local baseline: 5226ec2c5e3dfbbb676d68f09676dc7ed6c8a6fc, carrying current local workflow rules and accepted terminal-failure wording. This is an explicit local stack; older task branches remain preserved. Only the prepared worktree is mutable by this task.

Authorized now: local implementation, existing-environment tests, documentation, review, and semantic local commits. No push/PR/merge/release/deploy, new installation, paid provider, or permanent system-setting change is included. Docker daemon was unavailable at preparation. Continue provider-free implementation first; before database/Compose gates, confirm daemon and actual VM capacity, use task-owned project names/ports, and request any concrete missing action without pretending the gate passed. Coordinate heavy gates to avoid competing builds. GUI work uses a temporary task-owned caffeinate assertion when needed and releases it on stop.
