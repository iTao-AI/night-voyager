# Night Voyager Reference-Driven Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task by task. Use
> `superpowers:test-driven-development` for every behavior or presentation
> contract change, `superpowers:receiving-code-review` for authority findings,
> and `superpowers:verification-before-completion` before every readiness claim.

Status: `LOCAL CANDIDATE / IN REVIEW`
Implementation: `IMPLEMENTED LOCALLY`
Publication: `NOT PUSHED / NOT MERGED / NOT RELEASED / NOT DEPLOYED`
Target base: `main@e28efdb53d72c8b42c9636f3440dd41ebcb426e0`

**Goal:** Implement the approved reference-driven Night Voyager public site and
advisor-workspace composition without changing business authority or adding any
runtime capability.

**Architecture:** Keep every existing route controller and reducer as the sole
business-state authority. Add one pure shared `AdvisorProductFrame`, one
presentation-only public-story controller, and route-local composition changes.
Catalog and typed deterministic projections supply display copy and static root
facts; existing live controllers continue to supply demo facts and actions.

**Tech stack:** Next.js 16.3.0, React 19.2.8, TypeScript 5.9.3, CSS, Vitest 4.1.10,
Testing Library, Playwright 1.58.2, Python architecture tests, Docker Compose.
No dependency or lockfile change.

---

## Global constraints

1. Do not implement until the user approves the complete implementation and
   unattended-ship mandate.
2. Work in a new isolated `codex/reference-driven-presentation` worktree task.
   Do not edit the primary checkout.
3. Preserve the exact base unless authority explicitly rebases the plan after a
   fresh drift review.
4. No backend, BFF, API, domain, schema, database, migration, RLS, reducer, session,
   SSE, idempotency, fixture, provider, package, lockfile, deployment, tag, or
   release change.
5. Do not copy prototype source into the repository. Recreate the approved
   composition from existing components, deterministic values, and the public
   contract. Prototype QA chrome and view-query labels are excluded.
6. Do not add third-party assets, fonts, logos, icons, layout code, or visual
   effects. Use original CSS, plain text, and existing components.
7. Keep Chinese as the deterministic default. English must preserve the same state,
   action, and authority.
8. Run TDD RED before implementation GREEN. Do not weaken existing behavioral
   assertions to accommodate presentation changes.
9. Exact-stage task files only. Do not use `git add .` or `git add -A`.
10. Each commit must be reviewable, semantically atomic, and clean. No WIP or
    micro-commits.
11. Docker/Compose work uses one unique task-owned project name, explicit pre/post
    inventory, and same-project cleanup. No broad prune or global Docker change.
12. Public files must contain no private path, coordination identity, private motive,
    unsupported claim, credential, or personal data.

## What already exists

The implementation reuses these proven foundations:

| Existing capability | Reuse decision |
| --- | --- |
| four route entry points | unchanged |
| `PresentationProvider` and exact `zh-CN`/`en` storage behavior | unchanged; only catalog values change |
| `WORKFLOW_STAGES` and fail-closed state maps | unchanged keys and behavior; visible labels change |
| `PortfolioShell`, `PortfolioEntry`, `AdvisorWorkspacePreview` | recomposed, not replaced with raster media |
| `AdvisorWorkspaceShell` and `WorkflowRail` | recomposed into the shared product frame |
| collaboration controller/reducer and recovery | unchanged |
| connected-demo controller/reducer, role rotation, revision, receipt, timeline | unchanged |
| plan-execution controller/reducer, `happy`/`blocked`, replay/recovery | unchanged |
| presentation Vitest and architecture contracts | extended; never weakened |
| provider-free Compose and real-Chromium lane | reused with stronger presentation assertions |
| nine public screenshot paths | refreshed from coded deterministic flows only |

The plan does not build a parallel design system, state machine, data authority,
fixture, screenshot-only route, or visual testing framework.

## NOT in scope

- Backend/domain/API/database work: the task only changes presentation composition.
- A new root data fetch: it would violate the static public-root boundary.
- A new fixture or demo selector: approved states already exist.
- New dependencies or framework features: React, CSS, `IntersectionObserver`, and
  existing tests are sufficient.
- New public screenshot filenames: the existing nine remain the committed public
  evidence set; additional viewport images stay task-owned review evidence.
- Automatic visual-diff gating against prototype pixels: semantic/browser gates and
  human screenshot review remain authority.
- Deploy, tag, Release, provider call, real data, account/repository settings, or
  broad cleanup.

## Architecture and data flow

```text
PUBLIC ROOT (read-only)
catalog.ts + portfolio.ts deterministic projection
                  |
                  v
        PortfolioStory (visual scene only)
                  |
                  v
       AdvisorWorkspacePreview
                  |
                  v
        AdvisorProductFrame

LIVE DEMOS (business state unchanged)
existing hook/controller -> existing reducer/API authority
                  |
                  v
route component maps authorized state to display slots
                  |
                  v
AdvisorWorkspaceShell -> AdvisorProductFrame
                  |
                  v
existing button callback / existing recovery callback

Forbidden reverse edge:
presentation frame -X-> reducer/API/storage/session/domain inference
```

Shared product frame slots:

```text
AdvisorProductFrame
├── topBand: record | stage | state | flow boundary
├── workflowRail: five closed presentation stages
├── primary: current business object
├── evidence: current supporting facts or persisted record
├── authority: responsible human + zero/one filled primary action
└── technical: native details, closed by default
```

## Exact file responsibility map

### Add

| File | Responsibility |
| --- | --- |
| `docs/superpowers/specs/2026-08-14-reference-driven-presentation.md` | public-neutral approved contract |
| `docs/superpowers/plans/2026-08-14-reference-driven-presentation.md` | this self-contained implementation plan |
| `web/components/presentation/AdvisorProductFrame.tsx` | pure shared frame; no fetch, storage, mutation, or authority logic |
| `web/components/presentation/PortfolioStory.tsx` | public sticky/sequential scene selection only |
| `web/tests/unit/reference-driven-presentation.test.tsx` | exact copy, hierarchy, projection, frame, and no-side-effect contract |

### Modify: public presentation foundation

| File | Responsibility |
| --- | --- |
| `web/app/layout.tsx` | new static metadata matching the approved positioning |
| `web/app/styles.css` | global tokens, system font stack, focus, reduced-motion, and solid fallbacks |
| `web/app/portfolio.css` | public narrative, sticky/sequential story, Hero, depth budget, responsive reflow |
| `web/app/workspace.css` | shared 2/7/3 frame, tablet/mobile order, action plane, state surfaces |
| `web/components/presentation/PortfolioShell.tsx` | plain wordmark, product navigation, GitHub link, footer without duplicate claim |
| `web/components/presentation/PortfolioEntry.tsx` | fixed public chapter order and exact CTA wiring |
| `web/components/presentation/AdvisorWorkspacePreview.tsx` | typed root scenes using the shared frame |
| `web/components/presentation/AdvisorWorkspaceShell.tsx` | live-route landmarks and slots around the shared frame |
| `web/components/presentation/WorkflowRail.tsx` | preserve five stage keys and accessible current/complete/upcoming semantics |
| `web/lib/presentation/catalog.ts` | exact approved Chinese and faithful English copy; first-level terminology |
| `web/lib/presentation/portfolio.ts` | closed `¥300,000–400,000` connected-story projection and persisted-outcome display facts |

`web/lib/presentation/context.tsx`, `locales.ts`, `facts.ts`, `format.ts`, and
`journey.ts` remain unchanged unless a test proves a mechanical type-only update is
required. Any behavioral change to them is a stop condition.

### Modify: route-local presentation only

| File | Responsibility |
| --- | --- |
| `web/components/collaboration-demo/CollaborationDemo.tsx` | map existing branches into primary/evidence/authority slots |
| `web/components/collaboration-demo/SharedThread.tsx` | compact source record; preserve raw message, loading, empty |
| `web/components/collaboration-demo/MemoryCandidateCard.tsx` | proposed-information summary |
| `web/components/collaboration-demo/ConfirmedFactSummary.tsx` | dominant confirmed budget and natural version labels |
| `web/components/collaboration-demo/CollaborationRecoveryNotice.tsx` | last-safe state and one revalidation action |
| `web/components/connected-demo/ConnectedDemo.tsx` | route-state composition and persisted-result handoff |
| `web/components/connected-demo/AdvisorLedger.tsx` | dominant Australia route, reduced alternatives, existing actions split into authority plane |
| `web/components/connected-demo/CurrentConfirmedFacts.tsx` | natural first-level confirmed-information ledger |
| `web/components/connected-demo/FamilyDecisionBrief.tsx` | client-confirmation plane using the server brief only |
| `web/components/connected-demo/DecisionReceiptTimeline.tsx` | persisted receipt and action timeline |
| `web/components/connected-demo/PlanningRevisionComparison.tsx` | readable old/new comparison without changing revision behavior |
| `web/components/connected-demo/EvidenceDisclosure.tsx` | retain evidence content in the lower information layer |
| `web/components/connected-demo/RecoveryNotice.tsx` | retained safe display and reconnect action |
| `web/components/plan-execution/PlanExecutionWorkspace.tsx` | current checkpoint first; action plane second; plan/activity later on mobile |
| `web/components/plan-execution/CurrentCheckpoint.tsx` | paired milestone and next-actor summary |
| `web/components/plan-execution/AdvisorVerificationPanel.tsx` | one mineral primary and one outline secondary action |
| `web/components/plan-execution/ExecutionRecoveryNotice.tsx` | last-safe revalidation action |
| `web/components/plan-execution/ReassessmentHandoff.tsx` | restrained stop/handoff surface; no successor action |
| `web/components/plan-execution/ExecutionActivity.tsx` | closed secondary activity proof |

`CheckpointAttestationForm.tsx` changes only if CSS class/DOM grouping is required;
its values and callbacks remain unchanged.

### Modify: tests and browser proof

| File | Responsibility |
| --- | --- |
| `web/tests/unit/portfolio-entry.test.tsx` | exact new root copy, CTAs, and no product side effects |
| `web/tests/unit/portfolio-route-contract.test.ts` | supersede root 340k with confirmed 300k and preserve accepted 305.5k |
| `web/tests/unit/advisor-workspace-design.test.tsx` | shared frame, stage vocabulary, projection, and no-authority contract |
| `web/tests/unit/design-contract.test.tsx` | exact live-route shell and initial action |
| `web/tests/unit/presentation-accessibility.test.tsx` | headings, landmarks, disclosure, focus, and target semantics |
| `web/tests/unit/collaboration-demo.test.tsx` | all collaboration visual states and unchanged actions |
| `web/tests/unit/connected-demo-ui.test.tsx` | route comparison, client confirmation, persisted result, failures |
| `web/tests/unit/plan-execution-ui.test.tsx` | normal/blocked/recovery/completed composition and action ownership |
| `web/tests/unit/plan-execution-presentation.test.ts` | exact first-level execution/reassessment copy |
| `web/e2e/portfolio-design-review.spec.ts` | Hero/product hierarchy at six widths and both locales |
| `web/e2e/presentation.spec.ts` | full semantic matrix, scene captures, blur/motion/fallback metrics |
| `web/e2e/bootstrap.spec.ts` | initial copy/route contract |
| `web/e2e/collaboration-demo.spec.ts` | connected confirmed-information capture and unchanged journey |
| `web/e2e/connected-demo.spec.ts` | advisor review and persisted result captures |
| `web/e2e/planning-revision.spec.ts` | changed copy/selectors only; revision authority unchanged |
| `web/e2e/plan-execution-minimal.spec.ts` | completed normal execution copy/selectors |
| `web/e2e/plan-execution.spec.ts` | blocked, recovery, stale/session, and full execution copy/selectors |
| `tests/architecture/test_portfolio_presentation_contract.py` | dependency lock, pure components, projection identity, screenshot/public-scan contract |
| `tests/architecture/test_documentation_governance.py` | current-doc links, claims, and supersession wording |

No change is planned for `scripts/verify_compose.sh`,
`web/playwright.compose.config.ts`, or
`tests/architecture/test_compose_contract.py`: their existing presentation lane
already executes the required specs and safely wires task/public evidence roots.
Changing any of these requires a demonstrated RED contract gap and authority notice.

### Modify: current docs and real captures

| File | Responsibility |
| --- | --- |
| `DESIGN.md` | current visual system and unchanged authority boundaries |
| `docs/design/demo-storyboard.md` | new site/workspace composition and real state order |
| `docs/design/route-map.md` | existing routes with updated public presentation |
| `docs/design/projection-matrix.md` | root confirmed/persisted display projections and authority |
| `docs/design/state-and-interaction-matrix.md` | slot/reflow/focus presentation layer; lifecycle unchanged |
| `docs/superpowers/README.md` | discover the new spec/plan |
| `README.md`, `README_CN.md`, `docs/README.md` | product entry copy and current screenshots |
| `docs/operations/collaboration-walkthrough.md` | updated UI labels/selectors only |
| `docs/operations/connected-demo.md` | updated route-analysis/client-confirmation surface |
| `docs/operations/plan-execution-walkthrough.md` | updated normal/blocked/reassessment surface |
| existing nine `docs/assets/*.png` presentation files | refreshed coded Chromium evidence only |

The 2026-08-09 spec and plan remain immutable historical records. Current docs point
to the 2026-08-14 contract as their presentation successor.

---

## Task 1: Preflight, baseline, and mechanical plan landing

**Files:** add only the two 2026-08-14 public-neutral docs and update
`docs/superpowers/README.md` in this task.

- [ ] Fresh-read base/head/tree/status/branch/worktrees/remotes and confirm the
      isolated worktree is clean at the exact approved base.
- [ ] Recompute both approved visual-manifest hashes and verify every manifest entry.
- [ ] Read `AGENTS.md`, `DESIGN.md`, current design docs, package/lock, CI, and the
      exact existing route/test files named above.
- [ ] Record host and Docker VM inventory before any Compose action: Docker daemon,
      disk use, running containers, networks, volumes, images, and active Compose
      projects. Do not mutate inventory.
- [ ] Set a unique project name such as
      `nv-reference-presentation-YYYYMMDDHHMMSS`; record ownership and teardown rule.
- [ ] Record baseline frontend resource evidence from the unmodified base: production
      static JS/CSS byte totals and browser request/transfer/resource counts for all
      four routes under identical settings. This is comparison evidence, not a
      performance claim.
- [ ] Run the focused baseline commands:

```bash
npm --prefix web run test -- --run \
  tests/unit/portfolio-entry.test.tsx \
  tests/unit/portfolio-route-contract.test.ts \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/design-contract.test.tsx \
  tests/unit/presentation-accessibility.test.tsx \
  tests/unit/collaboration-demo.test.tsx \
  tests/unit/connected-demo-ui.test.tsx \
  tests/unit/plan-execution-ui.test.tsx
uv run pytest -q \
  tests/architecture/test_portfolio_presentation_contract.py \
  tests/architecture/test_documentation_governance.py
```

Expected at the approved base: `8` Vitest files / `96` tests pass and `45` Python
tests pass. If the fresh base differs, stop for drift review rather than editing
expected counts.

- [ ] Mechanically land the exact public-neutral spec and plan, verify content
      identity, then add the index link.
- [ ] Scan the landed documents for private paths, coordination identifiers, private
      motives, and unsupported claims.
- [ ] Exact-stage and commit:

```bash
git add -- \
  docs/superpowers/specs/2026-08-14-reference-driven-presentation.md \
  docs/superpowers/plans/2026-08-14-reference-driven-presentation.md \
  docs/superpowers/README.md
git diff --cached --check
git commit -m "docs: define reference-driven presentation"
```

## Task 2: Freeze the presentation contract with RED tests

**Files:** the unit, E2E, and architecture test files listed in the test map.

- [ ] Add `reference-driven-presentation.test.tsx` and update existing tests before
      implementation.
- [ ] Freeze exact Chinese public copy and faithful English translation.
- [ ] Freeze public-site section order, CTA targets, one H1, one non-claim boundary,
      no raster product subject, and zero root product requests/storage/session effects.
- [ ] Freeze the connected-story root facts: 300k confirmed budget, `计算机方向`,
      fact 1, record 2, and route outcomes. Explicitly forbid 340k on the root and
      keep 305.5k only in persisted outcome.
- [ ] Freeze the pure `AdvisorProductFrame` import boundary: no `fetch`,
      `XMLHttpRequest`, `EventSource`, cookies, storage, controller, mutation, or
      API imports.
- [ ] Freeze 2/7/3 desktop semantics and mobile DOM order using stable data
      attributes, not pixel/class implementation details.
- [ ] Freeze first-level forbidden terminology while permitting exact technical
      terms only within closed technical disclosures.
- [ ] Freeze six audit widths (`1440`, `1280`, `1024`, `768`, `390`, `320`), two
      locales, reduced motion, 200% equivalent reflow, focus, target size, contrast,
      overflow, long copy, blur count, and forced no-blur fallback.
- [ ] Freeze route-state captures for confirmed handoff, advisor review, receipt,
      execution normal/blocked/recovery/completed, loading, empty, and recoverable.
- [ ] Run RED:

```bash
npm --prefix web run test -- --run \
  tests/unit/reference-driven-presentation.test.tsx \
  tests/unit/portfolio-entry.test.tsx \
  tests/unit/portfolio-route-contract.test.ts \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/design-contract.test.tsx \
  tests/unit/presentation-accessibility.test.tsx \
  tests/unit/collaboration-demo.test.tsx \
  tests/unit/connected-demo-ui.test.tsx \
  tests/unit/plan-execution-ui.test.tsx \
  tests/unit/plan-execution-presentation.test.ts
uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
```

Expected: non-zero with failures tied only to the new copy/projection/frame/layout
contract. Preserve the exact failure output as RED evidence. If behavioral tests
fail for unrelated reasons, stop and diagnose.

- [ ] Exact-stage and commit:

```bash
git add -- \
  web/tests/unit/reference-driven-presentation.test.tsx \
  web/tests/unit/portfolio-entry.test.tsx \
  web/tests/unit/portfolio-route-contract.test.ts \
  web/tests/unit/advisor-workspace-design.test.tsx \
  web/tests/unit/design-contract.test.tsx \
  web/tests/unit/presentation-accessibility.test.tsx \
  web/tests/unit/collaboration-demo.test.tsx \
  web/tests/unit/connected-demo-ui.test.tsx \
  web/tests/unit/plan-execution-ui.test.tsx \
  web/tests/unit/plan-execution-presentation.test.ts \
  web/e2e/portfolio-design-review.spec.ts \
  web/e2e/presentation.spec.ts \
  tests/architecture/test_portfolio_presentation_contract.py
git diff --cached --check
git commit -m "test: freeze reference-driven presentation contract"
```

## Task 3: Build the shared product frame and material foundation

**Files:** `AdvisorProductFrame.tsx`, `AdvisorWorkspaceShell.tsx`,
`WorkflowRail.tsx`, `styles.css`, `workspace.css`, shared design tests.

- [ ] Implement `AdvisorProductFrame` as a pure slot component. Keep all state and
      callbacks in its caller.
- [ ] Recompose `AdvisorWorkspaceShell` around the frame while preserving skip link,
      one H1, focus target, role/status data, synthetic boundary, footer, and native
      technical disclosure.
- [ ] Preserve the five closed stage keys and `complete/current/upcoming` semantics.
      Update visible stage labels to the approved first-level vocabulary without
      changing `journey.ts` mappings.
- [ ] Add the exact semantic tokens, system-font fallbacks, solid surface ladder,
      product rim/shadow budget, and light/dark focus rings.
- [ ] Implement desktop 2/7/3 layout, tablet top-band/stage reflow, and mobile source
      order. The action plane must appear before alternatives/history on mobile.
- [ ] Define solid backgrounds before progressive `@supports` blur. Enforce maximum
      blur surfaces by breakpoint and zero blur/microtexture at `≤560px`.
- [ ] Keep dense data, evidence, receipts, timelines, and main work surfaces solid.
- [ ] Run GREEN for the shared tests, lint, and typecheck:

```bash
npm --prefix web run test -- --run \
  tests/unit/reference-driven-presentation.test.tsx \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/presentation-accessibility.test.tsx
npm --prefix web run lint
npm --prefix web run typecheck
```

- [ ] Exact-stage and commit:

```bash
git add -- \
  web/components/presentation/AdvisorProductFrame.tsx \
  web/components/presentation/AdvisorWorkspaceShell.tsx \
  web/components/presentation/WorkflowRail.tsx \
  web/app/styles.css web/app/workspace.css
git diff --cached --check
git commit -m "feat: build shared advisor product frame"
```

## Task 4: Implement the public site and deterministic product story

**Files:** `layout.tsx`, `PortfolioShell.tsx`, `PortfolioEntry.tsx`,
`AdvisorWorkspacePreview.tsx`, new `PortfolioStory.tsx`, `catalog.ts`,
`portfolio.ts`, `portfolio.css`, root tests.

- [ ] Replace metadata and root copy with the locked contract. Keep exact Chinese
      line spans in the Hero and direct English translations.
- [ ] Use the plain `Night Voyager` wordmark, approved navigation, and existing
      GitHub repository link. Do not create an icon/logo asset.
- [ ] Replace the root projection budget with the existing connected-story
      `¥300,000–400,000`; retain `computing` internally and present `计算机方向`.
- [ ] Add typed root scenes for confirmed information, route comparison, persisted
      outcome, reassessment trust, and explicit loading/empty/recoverable/completed
      coverage. Do not import demo controllers into root presentation code.
- [ ] Implement fixed public order: Hero, product reveal, first three workflow
      chapters, persisted outcome, fourth reassessment chapter, trust, technical
      disclosure, closing CTA, exact boundary/footer.
- [ ] Implement presentation-only `IntersectionObserver` scene selection for desktop.
      Disconnect observers on unmount; observe no hidden/mobile branch; never write
      storage or call product APIs.
- [ ] Under `≤860px` and reduced motion, render the chapters in static semantic order
      with no sticky interpolation. Ensure SSR/hydration produces no warning or text
      mismatch.
- [ ] Motion may change only opacity/transform. Reduced motion renders complete end
      state with `transition: none`, `transform: none`, and no smooth scroll.
- [ ] Render the exact non-claim boundary once and keep technical terms inside the
      closed disclosure.
- [ ] Run GREEN:

```bash
npm --prefix web run test -- --run \
  tests/unit/reference-driven-presentation.test.tsx \
  tests/unit/portfolio-entry.test.tsx \
  tests/unit/portfolio-route-contract.test.ts \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/design-contract.test.tsx \
  tests/unit/presentation-accessibility.test.tsx \
  tests/unit/presentation-catalog.test.ts \
  tests/unit/presentation-provider.test.tsx
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
```

- [ ] Exact-stage and commit:

```bash
git add -- \
  web/app/layout.tsx web/app/portfolio.css \
  web/components/presentation/PortfolioShell.tsx \
  web/components/presentation/PortfolioEntry.tsx \
  web/components/presentation/AdvisorWorkspacePreview.tsx \
  web/components/presentation/PortfolioStory.tsx \
  web/lib/presentation/catalog.ts web/lib/presentation/portfolio.ts
git diff --cached --check
git commit -m "feat: rebuild reference-driven product story"
```

## Task 5: Recompose consultation intake and confirmed-information handoff

**Files:** the five `collaboration-demo` components and collaboration presentation
tests.

- [ ] Preserve every `CollaborationDemo` state branch and callback.
- [ ] Place the current source/candidate/confirmed object in the primary plane and
      the existing authorized action in the human-action plane.
- [ ] Make confirmed budget dominant only after advisor confirmation.
- [ ] Keep the raw English message visible as source evidence, unchanged.
- [ ] Present `事实版本 1` and `档案版本 2` in the first layer; keep English domain
      identifiers only in the closed technical disclosure.
- [ ] Preserve disabled stale-candidate behavior, conflict focus, exact retry,
      handoff validation, and same-Case continuation.
- [ ] Assert one visible filled primary action at each actionable state.
- [ ] Run focused GREEN and unchanged recovery suites:

```bash
npm --prefix web run test -- --run \
  tests/unit/collaboration-demo.test.tsx \
  tests/unit/collaboration-recovery.test.tsx \
  tests/unit/collaboration-session.test.ts \
  tests/unit/use-collaboration-demo.test.tsx \
  tests/unit/presentation-journey.test.tsx
```

- [ ] Exact-stage and commit the five component files plus exact changed tests:

```bash
git add -- \
  web/components/collaboration-demo/CollaborationDemo.tsx \
  web/components/collaboration-demo/SharedThread.tsx \
  web/components/collaboration-demo/MemoryCandidateCard.tsx \
  web/components/collaboration-demo/ConfirmedFactSummary.tsx \
  web/components/collaboration-demo/CollaborationRecoveryNotice.tsx \
  web/tests/unit/collaboration-demo.test.tsx
git diff --cached --check
git commit -m "feat: recompose confirmed-information handoff"
```

Stage any additional changed collaboration test only after showing its diff and
proving it is required by the presentation selector/copy change.

## Task 6: Recompose plan comparison, advisor review, and persisted result

**Files:** the eight named `connected-demo` presentation components and connected
presentation tests.

- [ ] Keep `ConnectedDemo` state mapping, `runUserAction`, focus handling, role
      rotation, revision, and recovery unchanged.
- [ ] Split `AdvisorLedger` display and action presentation within the same file:
      Australia is dominant; Japan/Malaysia remain readable alternatives; all
      evidence claims, gaps, eligibility, and existing actions remain available.
- [ ] Preserve a semantic comparison table for assistive technology; use a record
      layout rather than compressed table columns on mobile.
- [ ] Keep current confirmed facts and record version visible without duplicate
      summaries.
- [ ] Keep the client confirmation bound to the server brief and existing checkbox.
- [ ] Render the decision receipt and action timeline as the primary completed
      result, with exact accepted values and no same-Case claim into `/demo/plan`.
- [ ] Preserve revision comparison, blocked no-action, terminal failure, and
      recoverable reconnect paths.
- [ ] Run focused GREEN and unchanged reducer/recovery suites:

```bash
npm --prefix web run test -- --run \
  tests/unit/connected-demo-ui.test.tsx \
  tests/unit/connected-demo-presentation.test.ts \
  tests/unit/connected-demo-reducer.test.ts \
  tests/unit/connected-demo-recovery.test.tsx \
  tests/unit/connected-demo-inspector.test.tsx
```

- [ ] Exact-stage and commit only changed component/test paths:

```bash
git add -- \
  web/components/connected-demo/ConnectedDemo.tsx \
  web/components/connected-demo/AdvisorLedger.tsx \
  web/components/connected-demo/CurrentConfirmedFacts.tsx \
  web/components/connected-demo/FamilyDecisionBrief.tsx \
  web/components/connected-demo/DecisionReceiptTimeline.tsx \
  web/components/connected-demo/PlanningRevisionComparison.tsx \
  web/components/connected-demo/EvidenceDisclosure.tsx \
  web/components/connected-demo/RecoveryNotice.tsx \
  web/tests/unit/connected-demo-ui.test.tsx
git diff --cached --check
git commit -m "feat: focus advisor review and persisted result"
```

## Task 7: Recompose execution follow-up, recovery, and reassessment

**Files:** the six named plan-execution presentation components, optional mechanical
grouping change in `CheckpointAttestationForm.tsx`, and execution presentation tests.

- [ ] Preserve scenario parsing, principal mapping, controller, reducer, API calls,
      receipt/GET reconciliation, replay keys, role locks, and recovery behavior.
- [ ] Show `独立演示场景，不沿用当前客户档案。` in the first layer.
- [ ] Put current checkpoint and next actor first; put the responsible role and
      authorized action second; put approved plan and activity later on mobile.
- [ ] Keep one primary action per active role. Advisor cannot start; family cannot
      verify; blocked family controls disappear before advisor reassessment.
- [ ] Preserve last confirmed progress in blocked and recoverable states.
- [ ] Render reassessment as a stopped execution with a separately authorized future
      handoff. Add no resume, successor-plan, decision, timeline, or execution action.
- [ ] Preserve focus return and exactly one polite live region after accepted user
      transitions.
- [ ] Run focused GREEN and unchanged recovery suites:

```bash
npm --prefix web run test -- --run \
  tests/unit/plan-execution-ui.test.tsx \
  tests/unit/plan-execution-presentation.test.ts \
  tests/unit/plan-execution-reducer.test.ts \
  tests/unit/plan-execution-recovery.test.tsx \
  tests/unit/plan-execution-scenario.test.ts
```

- [ ] Exact-stage and commit only changed component/test paths:

```bash
git add -- \
  web/components/plan-execution/PlanExecutionWorkspace.tsx \
  web/components/plan-execution/CurrentCheckpoint.tsx \
  web/components/plan-execution/AdvisorVerificationPanel.tsx \
  web/components/plan-execution/ExecutionRecoveryNotice.tsx \
  web/components/plan-execution/ReassessmentHandoff.tsx \
  web/components/plan-execution/ExecutionActivity.tsx \
  web/tests/unit/plan-execution-ui.test.tsx \
  web/tests/unit/plan-execution-presentation.test.ts
git diff --cached --check
git commit -m "feat: clarify execution follow-up and reassessment"
```

## Task 8: Complete browser, responsive, material, and state proof

**Files:** the named E2E specs, CSS only for verified same-scope corrections, and
architecture presentation test.

- [ ] Extend the real-Chromium audit from five to six widths by adding `1280` while
      retaining `1024` and all existing cells.
- [ ] For every route/locale/width cell assert: one H1, heading order, landmarks,
      no page overflow, no clipped long copy/focus, `44px` targets, contrast,
      current stage, route boundary, and one or fewer filled primary actions.
- [ ] Add material metrics: maximum two visible blur surfaces desktop, one tablet,
      zero at `≤560px`; no dense-data blur; no transition of filter/blur/shadow.
- [ ] Force `backdrop-filter: none` through Playwright-injected audit CSS and rerun
      hierarchy/contrast/geometry assertions. Do not add prototype query parameters
      to product code.
- [ ] Assert reduced motion renders exact end state with no transform, sticky
      interpolation, or smooth scroll.
- [ ] Capture task-owned native viewport evidence for Hero desktop/mobile, product
      reveal, sticky start/current/end, collaboration confirmed handoff, advisor
      review, persisted outcome, execution normal/blocked/recovery/completed, tablet
      advisor, and 320/390 mobile states.
- [ ] Compare composition and content against the approved keyframes. Pixel identity
      is not required; every intentional delta must be explained by live DOM,
      accessibility, copy, or runtime truth.
- [ ] Run one final coded `design-review` over `/`, `/demo/collaboration`, `/demo`,
      and `/demo/plan`, including normal and blocked states. Fix only verified
      same-scope findings and rerun targeted browser cells.
- [ ] Run local browser specs against the production build where possible, then the
      canonical task-owned Compose lane:

```bash
TASK_COMPOSE_PROJECT="nv-reference-presentation-$(date +%Y%m%d%H%M%S)"
export TASK_COMPOSE_PROJECT
TASK_AUDIT_ROOT="$(mktemp -d)"
export TASK_AUDIT_ROOT

PRESENTATION_AUDIT=1 \
PRESENTATION_AUDIT_OUTPUT_DIR="$TASK_AUDIT_ROOT" \
UPDATE_PORTFOLIO_SCREENSHOTS=1 \
UPDATE_COLLABORATION_SCREENSHOT=1 \
UPDATE_PLANNING_REVISION_SCREENSHOT=1 \
PRESENTATION_PUBLIC_EVIDENCE_ROOT=/workspace/docs/assets \
COMPOSE_PROJECT_NAME="$TASK_COMPOSE_PROJECT" \
  scripts/verify_compose.sh
```

The task must preserve the exact command exit, Playwright results, screenshot
dimensions/hashes, console output, and pre/post Compose inventory. Whether success
or failure, remove only the exact task-owned project/process/temp evidence after
the required evidence has been retained. Do not prune unrelated images, volumes,
networks, caches, projects, or browser state.

- [ ] Refresh only the existing nine approved public screenshot files from coded
      deterministic states. Reject any unlisted public asset write.
- [ ] Exact-stage and commit the E2E/architecture test changes plus inspected nine
      images. Do not stage task-owned private evidence.

## Task 9: Update current product documentation

**Files:** current design docs, READMEs, operations docs, and documentation tests.

- [ ] Update current docs after the coded candidate exists. Do not write
      implemented/verified language from the plan alone.
- [ ] Preserve all route, same-Case, separate-scenario, authority, deterministic,
      local-synthetic, stable-release, and non-production boundaries.
- [ ] Replace old visual direction language and current screenshot descriptions.
- [ ] Link the new spec/plan as current presentation authority; retain 2026-08-09
      documents as historical implementation records.
- [ ] Run link/claim/documentation tests and inspect every changed public image.

```bash
uv run pytest -q \
  tests/architecture/test_portfolio_presentation_contract.py \
  tests/architecture/test_documentation_governance.py \
  tests/architecture/test_compose_contract.py
git diff --check
```

- [ ] Exact-stage current docs and screenshot assets; commit:

```bash
git add -- \
  DESIGN.md README.md README_CN.md docs/README.md \
  docs/design/demo-storyboard.md \
  docs/design/projection-matrix.md \
  docs/design/route-map.md \
  docs/design/state-and-interaction-matrix.md \
  docs/operations/collaboration-walkthrough.md \
  docs/operations/connected-demo.md \
  docs/operations/plan-execution-walkthrough.md \
  tests/architecture/test_documentation_governance.py
git diff --cached --check
git commit -m "docs: refresh reference-driven product proof"
```

Add the nine exact screenshot paths to the stage command only after image inspection.

## Task 10: Fresh full verification and execution readiness

- [ ] Fresh-read HEAD, status, staged/unstaged/untracked diff, worktrees, branch,
      processes, Compose projects, images, networks, volumes, and temporary evidence.
- [ ] Run frontend gates:

```bash
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
```

- [ ] Run provider-free backend/architecture regression and repository checks:

```bash
make check
```

`make check` must actually finish. Do not substitute targeted frontend checks for
the backend, contract, DB, Docker, and proof portions it invokes.

- [ ] Re-run the task-owned presentation Compose/browser proof from Task 8 if any
      code, copy, CSS, docs wiring, or screenshot selector changed afterward.
- [ ] Record candidate static JS/CSS and browser resource measures under the same
      settings as baseline. Explain unexpected growth; make no improvement claim.
- [ ] Scan the complete diff and changed assets:

```bash
git diff --check "e28efdb53d72c8b42c9636f3440dd41ebcb426e0"..HEAD
git diff --name-status "e28efdb53d72c8b42c9636f3440dd41ebcb426e0"..HEAD
git status --short --branch
git log --oneline --decorate "e28efdb53d72c8b42c9636f3440dd41ebcb426e0"..HEAD
```

Review text and binary metadata for absolute user paths, private tool-state paths,
task/thread identifiers,
tokens, credentials, real personal data, UUID leakage in screenshots, raw internal
errors, unsupported outcomes, deployment/adoption/ROI claims, copied assets, and
prototype QA chrome.

- [ ] Verify no backend/BFF/API/domain/schema/database/migration/reducer/fixture,
      dependency/lockfile, CI topology, provider, release, or unrelated path changed.
- [ ] Run `superpowers:verification-before-completion` with fresh output.
- [ ] Return `READY` to the independent review authority with exact base/head/tree, commits,
      diff inventory, RED/GREEN evidence, all command results, browser/design evidence,
      screenshot hashes, resource inventory, remaining risk, and mini-retro. The
      execution worktree and branch must be clean; do not push or create a PR unless
      the approved unattended package includes publication.

## Task 11: Independent authority review and same-scope repair

This task is owned by the independent review authority, not the execution window.

- [ ] Fresh-read the returned branch/head/worktree and verify clean ownership.
- [ ] Compare the complete branch diff against the approved spec, plan, source
      keyframes, real commands, tests, screenshots, and public boundaries.
- [ ] Run one full pre-PR branch-diff review over the exact candidate. It is
      findings-only; authority does not directly implement public-project fixes.
- [ ] If findings exist, send exact verified findings to the same execution task.
      Execution uses `superpowers:receiving-code-review`, adds RED regression tests
      where applicable, repairs only same-scope findings, reruns targeted and full
      verification, commits, and returns the new exact head.
- [ ] Authority performs targeted re-review of the delta. A new full review is
      required only if the diff materially widens or changes product/authority
      boundaries.
- [ ] Stop before publication if review is not clean or the reviewed head is not the
      exact candidate to publish.

## Task 12: Authorized publication, exact-head CI, conditional merge, and cleanup

Run only if the user approves the complete unattended-ship package.

- [ ] Fresh-read remote, auth, exact reviewed HEAD, branch tree, worktree status, and
      actual Git smart-transport ability.
- [ ] Push the exact reviewed head to its task branch and read back the remote SHA.
- [ ] Create a ready PR with a concise English Conventional Commit title and a
      Simplified Chinese public-neutral body using `Summary`, `Completion`,
      `Verification`, `Scope`, `Risk / Impact`, and `Documentation impact`.
- [ ] Read back persisted PR title/body/base/head/draft state. The body lists genuine
      pending hosted gates as unchecked and makes no release/deploy/production claim.
- [ ] Discover required checks from actual hosted runs. Wait at low frequency for
      exact PR-head checks and platform review; do not infer check names from YAML.
- [ ] For same-scope CI/review findings, return to the execution task, repair with
      RED tests, rerun verification, commit, and obtain targeted authority re-review.
      Any new diff invalidates the prior reviewed HEAD.
- [ ] Merge conditionally only when all are true:

```text
reviewed HEAD == current PR head == successful check SHA
reviewed tree == current PR tree
required approvals/checks are satisfied
no unresolved actionable review thread or platform blocker
PR is mergeable against the intended base
persisted PR body accurately reflects current gates
```

- [ ] Use squash merge. Verify the reviewed head tree equals the merge commit tree.
- [ ] If merge triggers a default-branch workflow, require the run head SHA to equal
      the exact merge SHA and wait for success. PR-head green is not a substitute.
- [ ] Reconcile the PR body to terminal truth, mark satisfied gates `[x]`, preserve
      true non-claims, and read back the persisted final body.
- [ ] Inventory all task-owned remote/local branches, worktree, open PR/checks,
      Compose resources, browser processes, temp/evidence paths, and execution task.
- [ ] Remove only clean, inactive, task-owned residue after proving merged history
      retains every intended unique change. The approved package includes the exact
      task-owned remote branch, local branch, worktree, processes, temporary evidence,
      Compose project, and execution-task archive. Preserve anything unclear.
- [ ] Fast-forward a clean primary checkout to the exact merge commit only if the
      authorized cleanup package, ownership, and no-unique-change checks permit it.
- [ ] Return `DONE` only when inventory is clear and exact-merge main CI is green.
      Otherwise return `DONE_WITH_RESIDUE` with exact owner, resource, reason, and
      recovery condition.

---

## TDD coverage diagram

```text
CODE PATHS                                        USER FLOWS
[+] catalog + typed root projection               [+] Public product understanding
  ├── [RED->GREEN UNIT] zh-CN exact copy             ├── [E2E] Hero -> product anchor
  ├── [RED->GREEN UNIT] en semantic parity           ├── [E2E] product -> /demo
  ├── [RED->GREEN UNIT] 300k vs 305.5k boundary      ├── [E2E] final -> collaboration
  └── [RED->GREEN ARCH] no 340k root drift           └── [E2E] GitHub external link

[+] PortfolioStory scene selection                [+] Responsive reading
  ├── [UNIT] observer selects fact/route/outcome     ├── [E2E] desktop sticky states
  ├── [UNIT] observer disconnects                    ├── [E2E] tablet authored reflow
  ├── [UNIT] reduced-motion static order             ├── [E2E] 390/320 action order
  └── [E2E] no hydration/console error               └── [E2E] 200% no 2-D scrolling

[+] AdvisorProductFrame                           [+] Keyboard/accessibility
  ├── [UNIT] slots + one H1 + landmarks             ├── [E2E] skip -> brand -> locale
  ├── [UNIT] fail-closed stage                       ├── [E2E] authorized action order
  ├── [ARCH] no authority imports                    ├── [E2E] focus after transition
  └── [E2E] blur/motion/solid fallback               └── [E2E] native details Enter/Space

[+] collaboration presentation                    [+] Connected fact handoff
  ├── [EXISTING+UNIT] all reducer states             ├── [E2E] message -> candidate
  ├── [EXISTING+UNIT] stale/conflict/recovery        ├── [E2E] advisor confirmation
  └── [UNIT] primary/evidence/action slots           └── [E2E] same-Case /demo handoff

[+] connected-demo presentation                   [+] Plan and client decision
  ├── [EXISTING+UNIT] task/review/revision states    ├── [E2E] create -> review
  ├── [UNIT] dominant + alternative routes          ├── [E2E] approve/request revision
  ├── [UNIT] client brief gate                       ├── [E2E] client confirmation
  └── [UNIT] receipt/timeline values                 └── [E2E] persisted result readback

[+] plan-execution presentation                   [+] Execution and recovery
  ├── [EXISTING+UNIT] role/action authority          ├── [E2E] happy completion
  ├── [EXISTING+UNIT] replay/session recovery        ├── [E2E] lost acknowledgement
  ├── [UNIT] blocked/reassessment composition        ├── [E2E] blocked -> advisor -> stop
  └── [UNIT] completed no-action state               └── [E2E] stale/session-change closure

COVERAGE TARGET: every changed conditional and every visible state has a unit,
architecture, or real-browser assertion; all unchanged controller/reducer recovery
suites remain green.
```

## Failure-mode matrix

| New/changed path | Realistic failure | Test | Existing handling / user result |
| --- | --- | --- | --- |
| root scene observer | unsupported/disabled observer or unmount | unit + reduced-motion E2E | static semantic chapters remain complete |
| viewport mode change | stale observer updates hidden branch | unit + resize E2E | observer disconnect/rebind; one accessible branch |
| English long copy | clipped action or two-dimensional scroll | six-width + 200% E2E | authored reflow; no hidden action |
| font fallback | Chinese clause breaks or wordmark shifts | screenshot/browser metrics | system stack; content remains readable |
| blur unsupported | authority plane loses hierarchy/contrast | forced no-blur E2E | solid fallback, rims, shadows remain |
| reduced motion | hidden start state never reaches content | reduced-motion bitmap/DOM E2E | immediate complete end state |
| unknown workflow state | raw internal value appears | unit | fail closed; no invented stage |
| missing root projected value | plausible replacement is rendered | unit/architecture | explicit empty state; no new fact |
| live route transport/session error | layout discards last safe state | existing recovery + new presentation unit | existing controller state retained; revalidate |
| action split into authority plane | callback or disabled guard lost | unit + Compose E2E | exact existing callback and disabled rule |
| mobile route comparison | six-column table becomes unusable | 390/320 E2E | readable record view; semantic table retained |
| screenshot refresh | private path/UUID/unsupported claim leaks | architecture + manual image inspection | reject asset and rerun deterministic capture |

No changed path is allowed to fail silently without a test and a visible safe result.

## Performance review contract

- No database or network performance path changes.
- Root product request count remains zero.
- No runtime image is introduced for the product subject.
- Added JavaScript is limited to one bounded presentation observer and scene state.
- One observer instance watches only the three public story sentinels and is
  disconnected on unmount or mode change.
- CSS blur is bounded by surface count and viewport area; dense content is solid;
  blur/filter/shadow never animates.
- Record equivalent base/candidate JS/CSS bytes, route request count, transferred
  bytes, resource bytes, and visible blur area. Investigate unexplained growth; do
  not invent a performance threshold or claim an improvement.

## Sequential implementation strategy

One isolated execution task owns the coherent worktree. The tasks touch the same
presentation components, catalog, CSS, tests, and screenshots, so parallel
worktrees would create merge conflicts and split visual authority.

```text
Task 1 docs/baseline
  -> Task 2 RED contract
  -> Task 3 shared frame
  -> Task 4 public story
  -> Task 5 collaboration
  -> Task 6 connected plan/receipt
  -> Task 7 execution/reassessment
  -> Task 8 browser/design proof
  -> Task 9 docs/screenshots
  -> Task 10 fresh full verification
  -> authority full review
  -> same-scope repair + targeted re-review
  -> authorized publication/merge/cleanup
```

No parallel implementation lane is approved.

## Completion definition

Implementation is complete only after:

1. every locked copy, projection, hierarchy, state, responsive, accessibility,
   material, motion, and non-claim criterion in the spec is implemented;
2. every unchanged business/recovery suite remains green;
3. frontend lint/typecheck/tests/build, `make check`, task-owned Compose/browser
   proof, coded design review, screenshots, and public scans pass on the exact head;
4. the independent authority's full review and any targeted re-review are clean;
5. if publication is authorized, exact reviewed-head PR, persisted body, exact-head
   hosted checks, conditional merge, exact-merge main checks, and cleanup all finish;
6. no task-owned residue remains, or `DONE_WITH_RESIDUE` identifies the exact owner
   and recovery condition.

The local candidate is implemented in the approved worktree and remains subject
to authoritative review. It is not pushed, merged, released, or deployed.

## Implementation Tasks

Synthesized from the targeted engineering review. The main implementation remains
the ordered Task 1-12 sequence above.

- [ ] **T1 (P1, human: ~20min / CC: ~5min)** — documentation — land a
  public-neutral contract with no private coordination residue.
  - Surfaced by: Code Quality Review — the private candidate initially contained
    internal authority, model, and local tool-path language.
  - Files: `docs/superpowers/specs/2026-08-14-reference-driven-presentation.md`,
    `docs/superpowers/plans/2026-08-14-reference-driven-presentation.md`.
  - Verify: run the repository public-scan architecture tests and manually inspect
    both landed documents before their exact-stage commit.

_No new tasks from Architecture Review, Test Review, or Performance Review._

## Targeted Engineering Review Summary

- Step 0 — Scope Challenge: scope accepted as-is; locked product, copy, visual,
  dependency, and authority boundaries were not reopened.
- Architecture Review: 0 unresolved issues. Existing controllers/reducers remain
  authoritative; the shared frame and root story stay presentation-only.
- Code Quality Review: 1 issue found and folded. Internal authority/model/tool-path
  wording was removed from the public-neutral source artifacts, with a landing scan
  retained as P1 Task T1.
- Test Review: combined code-path/user-flow diagram produced; 0 uncovered gaps after
  the planned RED-to-GREEN unit, architecture, and real-browser requirements.
- Performance Review: 0 issues. One bounded observer, zero root product requests,
  no runtime product image, and measured rather than claimed resource impact.
- NOT in scope: written.
- What already exists: written and reused.
- `TODOS.md` updates: 0 items; no valuable work is being deferred from this bounded
  phase.
- Failure modes: 0 critical gaps; every changed path has a planned test and visible
  safe result.
- Outside voice: attempted with Codex read-only; timed out at five minutes without
  findings, so no recommendation or cross-model tension was incorporated.
- Parallelization: 1 sequential lane, 0 parallel lanes; shared presentation modules
  and visual authority make worktree splitting counterproductive.
- Lake Score: 1/1 complete; the one mechanical public-neutrality correction was
  required by the already-approved boundary and introduced no new product decision.
- Retrospective: recent presentation commits `54b78eb` and `e28efdb` touched the same
  route shells and control surfaces, so this plan gives callback ownership, keyboard
  focus, recovery branches, and unchanged reducer suites explicit regression gates.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | ---: | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | Not rerun; product direction was already approved. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | UNAVAILABLE | Read-only outside voice timed out without output. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 1 issue folded, 0 critical gaps. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | Not rerun; approved keyframes and prior visual QA remain the source contract. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | Not applicable to this presentation-only phase. |

**VERDICT:** ENG CLEARED — decision-complete plan is ready for implementation approval.

NO UNRESOLVED DECISIONS
