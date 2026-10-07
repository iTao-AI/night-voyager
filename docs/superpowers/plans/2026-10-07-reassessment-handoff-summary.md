# Reassessment handoff summary implementation plan

Status: approved; implementation in progress.

**Goal:** turn a saved reassessment into a specific bilingual, user-copyable
handoff while preserving its authority boundary.

**Architecture:** a pure frontend projection selects saved facts from existing
typed reads; a small React component presents and copies that projection. The
workspace exposes it only for the current settled reassessment context.

**Tech stack:** TypeScript, React, existing presentation catalog, Vitest,
Testing Library and Playwright.

**Spec:** [approved handoff summary](../specs/2026-10-07-reassessment-handoff-summary.md).

**Global constraints:** no backend/lockfile changes; no local-clock trigger
inference; no actor or credential export; no authority writes; retain the Stop
and future-authorization status. Retain ignored execution evidence. Remote
delivery and heavy native recovery are separate gates.

**Review focus:** saved checkpoint differs from current; wrong trigger reference;
wrong execution/checkpoint attestation; saved date differs from observed date;
clipboard failure or delayed completion across loading/session/context changes.

## Task 1: Derive the saved facts

- [x] Add synthetic full DTO fixtures in `web/tests/fixtures/reassessment-handoff.ts`.
- [x] Write failing `web/tests/unit/reassessment-handoff.test.tsx` tests for
  checkpoint selection, matching blocker reason, dates, identity consistency and
  export privacy. Use literal expected facts independently of the builder.
- [x] Implement `web/lib/plan-execution/reassessment-handoff.ts` with
  `buildReassessmentHandoff(context, view, locale)`, returning localized fact
  rows, identity rows and their plain text, or `null` for unsettled/mismatched
  authority. Reuse `web/lib/presentation/catalog.ts` for bilingual labels.
- [x] Verify RED then GREEN with `cd web && npm test -- tests/unit/reassessment-handoff.test.tsx`.
- [x] Review and commit the coherent projection and tests.

## Task 2: Present and copy the current handoff

- [ ] Extend regression tests for real `ReassessmentHandoff` and
  `PlanExecutionWorkspace`: copy, rejected/unavailable clipboard, new context,
  busy/mutation/loading/session state and pending asynchronous results.
- [ ] Update `web/components/plan-execution/ReassessmentHandoff.tsx` to display
  facts, collapsed identities, copy feedback and a read-only selectable fallback.
  Reuse the existing Stop/trigger copy and add scoped styles to
  `web/app/workspace.css`.
- [ ] Update `PlanExecutionWorkspace.tsx` to gate the component on settled state,
  matching requested authority, context and projection; remount copy state on
  changed summary/role/authority/locale rather than carrying stale fallback.
- [ ] Run focused RED/GREEN tests, then `cd web && npm test`, inspect the diff
  and commit the current-summary copy behavior.

## Task 3: Browser acceptance and documentation

- [ ] Add `web/e2e/reassessment-handoff.spec.ts`: explicitly fixture-only routed
  HTTP reads, blocked/deadline in both languages at 1440/390, actual clipboard
  copy, failed-copy selection and session/context refresh. No native mutations.
- [ ] Run the new browser file in a task-owned server/browser profile and retain
  screenshots/results under ignored `tmp/`. Existing installed browser may be
  reused read-only; no unapproved external tools are downloaded.
- [ ] Inspect existing HTTP/DB projection tests and
  `docs/reference/timeline-execution-contract.md`; update the reference,
  applicable walkthrough and docs indexes for the new handoff behavior.
- [ ] Run `cd web && npm run lint`, `npm run typecheck`, `npm run build`, and
  link/diff checks. Do not restart frozen native recovery acceptance.
- [ ] Run targeted `gstack-workflows:document-release` audit and one fresh
  whole-branch review; fix Important/Critical findings with regression checks.
- [ ] Mark this plan/spec complete only after evidence is available. Commit
  docs/browser proof assets, then report exact HEAD, commands, evidence classes,
  limits and the remote-delivery approval candidate.
