# Reassessment handoff summary implementation plan

Status: completed locally, including the progressive-disclosure repair after
the first hosted proof failure. Renewed hosted delivery remains separately authorized.

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
Also cover a retained live controller switching Happy/Blocked in either
direction before a new validated read.

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

- [x] Extend regression tests for real `ReassessmentHandoff` and
  `PlanExecutionWorkspace`: copy, rejected/unavailable clipboard, new context,
  busy/mutation/loading/session state and pending asynchronous results.
- [x] Update `web/components/plan-execution/ReassessmentHandoff.tsx` to display
  facts, collapsed identities, copy feedback and a read-only selectable fallback.
  Render technical contents only while explicitly expanded and remove on close.
  Reuse the existing Stop/trigger copy and add scoped styles to
  `web/app/workspace.css`.
- [x] Update `PlanExecutionWorkspace.tsx` to gate the component on settled state,
  matching requested authority, context and projection; remount copy state on
  changed summary/role/authority/locale rather than carrying stale fallback.
- [x] Run focused RED/GREEN tests, then `cd web && npm test`, inspect the diff
  and commit the current-summary copy behavior.

## Task 3: Browser acceptance and documentation

- [x] Add `web/e2e/reassessment-handoff.spec.ts`: explicitly fixture-only routed
  HTTP reads, blocked/deadline in both languages at 1440/390, actual clipboard
  copy, failed-copy selection and session/context refresh. No native mutations.
- [x] Run the new browser file in a task-owned server/browser profile and retain
  screenshots/results under ignored `tmp/`. Existing installed browser may be
  reused read-only; no unapproved external tools are downloaded.
- [x] Inspect existing HTTP/DB projection tests and
  `docs/reference/timeline-execution-contract.md`; update the reference,
  applicable walkthrough and docs indexes for the new handoff behavior.
- [x] Run `cd web && npm run lint`, `npm run typecheck`, `npm run build`, and
  link/diff checks. Do not restart frozen native recovery acceptance.
- [x] Run targeted `gstack-workflows:document-release` audit and one fresh
  whole-branch review; fix Important/Critical findings with regression checks.
- [x] Mark this plan/spec complete only after evidence is available. Commit
  docs/browser proof assets, then report exact HEAD, commands, evidence classes,
  limits and the remote-delivery approval candidate.

The final review's seeded scenario finding was fixed with four live-hook
RED/GREEN regressions and targeted owner review. The repaired tree passed 54
frontend files / 667 tests, lint, typecheck, build and 17 browser tests. The
subsequent hosted guard repair is recorded below. See the
[acceptance record](../../evidence/reassessment-handoff-summary.md) for source
mapping and evidence limits. Ignored execution evidence and the local worktree
are retained; no hosted delivery is implied.

## Hosted guard repair

The first hosted `compose / proof` attempt on `e51764a` failed because the
whole-main text guard consumed IDs from visually closed details. Retain that
failure count of 1, its log and existing local captures; the runner's failure
screenshot/trace was not uploaded and is unavailable as a retained artifact.
The accepted repair changes only
this component's disclosure DOM lifecycle; native guard/regex/timeout/gate,
shared frame, copy whitelist and business authority are unchanged.

- [x] Reproduce the exact raw-data pattern in the actual DOM consumer (RED).
- [x] Render identities/projection explanation on native open and remove on close (GREEN).
- [x] Verify default/closed DOM, exact disclosed IDs, copy/fallback and new-context isolation.
- [x] Run the full frontend suite (54 files / 668 tests), static/build checks and
  17 bilingual 1440/390 fixture/browser cases, including Enter/Space and no new requests.
- [x] Update current reference/walkthrough and acceptance classification; commit locally.

No new push, hosted rerun, local native/Compose proof, merge or cleanup is part
of this repair. The revised candidate returns for acceptance and a concrete
next hosted authorization.
