
# Night Voyager Advisor-Centered Product Experience Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan in one coherent execution
> window. Do not use `superpowers:subagent-driven-development`: the root, shared
> shell, copy catalog, styles, browser matrix, and screenshots share state and must
> stay under one write owner.

**Goal:** Rebuild Night Voyager's public root and three deterministic demo routes
as one credible, advisor-centered study-abroad AI collaboration workspace, while
preserving every existing domain authority, API/BFF contract, reducer transition,
synthetic fixture, persistence effect, and maturity boundary.

**Architecture:** Keep all product behavior in the existing route hooks and
controllers. Replace only the presentation projection: a static root preview, one
shared advisor workspace shell, a closed five-stage workflow rail, route-local
state-to-stage mappings, bilingual business copy, and a split CSS layer. Domain
types such as `FamilyDecision`, `DecisionReceipt`, `AdvisorReview`, and
`TimelinePlan` remain unchanged and appear only where their exact authority matters.

**Tech Stack:** Next.js 16, React 19, TypeScript, existing CSS, Vitest, Testing
Library, Playwright, Python standard-library architecture tests, Docker Compose,
and the existing GStack browser/design-review tooling. Add no package or framework.

**Plan status:** Design approved; implementation has not started. The audited
baseline is `main@54b78ebda9fea263de68b5e3f623aef31c5ffe48`. Execution must fresh-read
`origin/main` and stop for authority review if intervening changes overlap this
presentation scope.

## Global constraints

- Use a dedicated `codex/` branch and task-owned worktree. Record base commit, tree,
  branch, worktree, complete status, open PR inventory, and Docker inventory before
  the first write.
- Mechanically land the approved public-neutral design and this implementation plan
  in the project before source changes. Do not re-open product positioning in the
  execution window.
- The visible hierarchy is advisor-centered:
  `咨询接入 -> 信息核验 -> 方案研判 -> 客户确认 -> 执行跟进`.
- This is one product workflow with two truthful deterministic proof segments. The
  same Case continues from `/demo/collaboration` through `/demo` to its receipt and
  `TimelinePlan`; `/demo/plan` uses the existing separately seeded Happy/Blocked
  execution Cases. Never imply a Case or session handoff between those segments.
- The buyer/deployer is a study-abroad organization or advisor team; the advisor is
  the primary operator; the student and parent are client participants. Do not turn
  the product into a family self-service app or a student-facing recommendation
  portal.
- Keep exact role and authority language where it matters. A parent message remains
  a parent message; `FamilyDecision` remains the domain object; a client choice is
  never silently converted into advisor or Agent authority.
- Do not modify backend code, BFF behavior, public request/response shapes, reducer
  state values, database schema, migration, RLS, worker, task lifecycle, SSE,
  idempotency, session, fixture, DRA/MKE producer, Compose topology, dependency,
  package version, lockfile, provider, or deployment configuration.
- Do not add a client list, CRM, team inbox, messaging gateway, upload, notification,
  organization setting, billing, registration, production tenancy, autonomous
  companion, or any capability not implemented by the current product.
- Use only the repository's current deterministic synthetic data. Do not invent a
  person, advisor, school, employer, institution result, timestamp, conversion,
  admission, customer, ROI, productivity metric, or production claim.
- The root remains static: no API request, cookie write, session bootstrap, local or
  session storage write, task operation, EventSource, mutation, or product-side
  effect. Locale preference behavior may remain exactly as it is today.
- Server-owned message bodies, advisor reasons, evidence limitations, route results,
  budgets, ids, and timestamps remain byte-identical at their existing boundaries.
- One state has at most one filled primary action. Corrective, secondary, role
  switch, exit, and destructive actions must not compete visually with it.
- Keep `zh-CN` as the fail-closed default and explicit `en` parity. Unknown state or
  copy code renders no invented workflow stage or friendly claim.
- Keep release `v0.1.5` immutable. This phase creates no tag, GitHub Release,
  package publication, provider call, or deployment.
- Preserve unrelated changes and ownership-unknown resources. Never broad-prune
  Docker, branches, worktrees, caches, volumes, screenshots, or generated evidence.

## Target structure

The presentation layer after implementation is:

```text
web/app/styles.css                   tokens, reset, accessibility, shared controls
web/app/portfolio.css                public root only
web/app/workspace.css                three demo routes only
web/lib/presentation/catalog.ts      exact bilingual business and evidence copy
web/lib/presentation/journey.ts      closed presentation-only workflow projection
web/lib/presentation/portfolio.ts    one typed deterministic root-preview projection
web/components/presentation/
  PortfolioShell.tsx                 root frame and public navigation
  PortfolioEntry.tsx                 five-section root narrative
  AdvisorWorkspacePreview.tsx        static coded preview using existing facts
  AdvisorWorkspaceShell.tsx          shared demo product frame
  WorkflowRail.tsx                   pure five-stage progress projection
  LocaleSwitch.tsx                   existing locale ownership
```

The demo controllers continue to own runtime state:

```text
CollaborationDemo -> useCollaborationDemo
ConnectedDemo -> useConnectedDemo
PlanExecutionWorkspace -> usePlanExecution
```

No new context provider, global store, query layer, design framework, or icon
dependency is introduced.

The closed presentation contract is:

```ts
export const WORKFLOW_STAGES = [
  "consultation_intake",
  "client_fact_review",
  "route_analysis",
  "client_confirmation",
  "execution_followup",
] as const;

export type WorkflowStage = (typeof WORKFLOW_STAGES)[number];

export type WorkflowProofSegment =
  | "connected_same_case"
  | "independent_execution_scenario";

export type WorkflowStateReference = {
  value: string;
  prior?: WorkflowStateReference;
};
```

`collaborationWorkflowStage`, `connectedWorkflowStage`, and
`planExecutionWorkflowStage` map the existing state values into this union. They
must return `null` for unknown values and recursively recover only the same known
prior-state behavior already covered by the current journey tests.

The mapping is frozen as follows:

| Route projection | Existing state values | Workflow stage |
|---|---|---|
| collaboration | `bootstrapping_parent`, `thread_ready`, `message_submitting` | `consultation_intake` |
| collaboration | `proposal_pending`, `switching_to_advisor`, `advisor_reviewing`, `confirmation_submitting` | `client_fact_review` |
| collaboration | `replan_required`, `handoff_validating` | `route_analysis` |
| connected | `revision_requested`, `revision_fact_pending` | `client_fact_review` |
| connected display state | `bootstrapping`, `advisor_ready`, `task_creating`, `task_streaming`, `advisor_review`, `review_submitting`, `replan_required`, `revision_blocked`, `terminal_task_failure` | `route_analysis` |
| connected | `family_review`, `decision_submitting` | `client_confirmation` |
| connected | `plan_ready` | `execution_followup` |
| plan execution | `loading`, `ready_to_start`, `checkpoint_active`, `mutation_in_flight`, `awaiting_advisor`, `execution_completed`, `reassessment_required`, `session_changed`, `recoverable_error` | `execution_followup` |

`role_switching` and connected `recoverable_error` recurse through the retained prior
state. Collaboration `recoverable_error` maps only through its known `resumePhase`.
Missing prior/resume state and every unknown value return `null`.

The connected mapping consumes reducer display states, not raw backend phases. Tests
must first prove `active_task` and `revision_task_active` reduce to `task_streaming`,
and `review_required` and `revision_review_required` reduce to `advisor_review`, then
prove those display states map to `route_analysis`. Raw phases are never added as
unreachable keys in `connectedWorkflowStage`.

The shared shell contract is presentation-only:

```ts
type AdvisorWorkspaceShellProps = {
  activeRole: "student" | "parent" | "advisor" | null;
  children: ReactNode;
  contextKey: PresentationCopyKey;
  currentStage: WorkflowStage | null;
  mainId: string;
  proofSegment: WorkflowProofSegment;
  status: ReactNode;
  supportingEvidence?: ReactNode;
  technicalEvidence?: ReactNode;
  titleKey: PresentationCopyKey;
};
```

It renders the product header, synthetic boundary, Case context bar, workflow rail,
one route-level `h1`, work canvas, supporting decision/evidence rail, default-closed
technical disclosure, and footer. State panels, recovery, role switching, and
reassessment use `h2` or lower; they never add a second `h1`. The shell renders the
closed proof-segment label and boundary: collaboration/connected use
`connected_same_case`; plan execution uses `independent_execution_scenario`. It owns
no hook, request, mutation, storage, task, role switch, or reducer behavior.

## What already exists and must be reused

- `PresentationProvider`, `LocaleSwitch`, `catalog.ts`, and the exact `zh-CN` / `en`
  parity and fail-closed locale behavior.
- `useCollaborationDemo`, `useConnectedDemo`, `usePlanExecution`, their reducers,
  API/BFF clients, session ownership, idempotency, SSE, retry, and focus behavior.
- Existing route/fact/evidence presentation functions in `codes.ts`, `facts.ts`, and
  `format.ts`; business copy may change but raw codes must still pass through the
  closed projection.
- Existing semantic HTML, live-region, keyboard, 44px-target, contrast, reduced
  motion, 200%-zoom, and long-copy assertions.
- The canonical four-route Playwright matrix and normal/blocked deterministic
  Compose journey.
- The current local CJK/sans/serif fallbacks. Do not fetch or package a new font.
- The existing product icon may be refined only if the current SVG fails the new
  product-frame composition; no decorative icon system is added.

## Page and viewport hierarchy

The first three things a reader sees are fixed.

```text
ROOT /
1. What this is: AI collaboration workspace for study-abroad advisors
2. What is happening now: one synthetic Case and current route-analysis work
3. What to do next: walk through the client Case or inspect proposal verification

DEMO ROUTES
1. Orientation: product, synthetic boundary, Case, role, current stage
2. Current work: outcome, missing information, responsible participant, one action
3. Supporting proof: conversation/facts/routes/receipt/activity, then technical evidence
```

The root is a hybrid portfolio/product surface: the hero follows landing-page
hierarchy, while its coded preview and all demo routes follow calm app-workspace
hierarchy. Neither side may borrow the other's worst pattern: the hero is not a
dashboard mosaic, and the workspace is not an atmospheric poster.

The root preview's only runtime source is the typed constant in `portfolio.ts`. Its
parity authority is the checked-in `fixtures/m3a/manifest.json`: country order comes
from `case.student.preferred_countries`; the intended field comes from
`case.student.intended_field`; route outcomes come from `expected`; evidence
sufficiency and gaps come from `source_pack.entries[].coverage` / `known_gaps`; budget
comes from `case.family.budget` (`preferred_minor=34,000,000`,
`hard_ceiling_minor=40,000,000`, CNY minor units). The preview therefore says
`computing` and CNY 340,000–400,000, not the old unbound “data science / CNY
300,000–400,000” editorial copy. The next action is presentation-owned navigation,
not a fixture fact, and must be labelled as such. Architecture tests read the manifest
and compare these exact closed fields to `portfolio.ts`; runtime code does not import,
fetch, or expose fixture IDs, synthetic institution names, publisher names, paths, or
timestamps.

## Interaction-state presentation contract

| Surface | Loading / bootstrap | No usable projection | Active / partial | Error / blocked | Completed |
|---|---|---|---|---|---|
| root | none; static first paint | not applicable; no invented empty Case | static coded preview is explicitly illustrative | not applicable; root has no product request | CTA leads into the deterministic flow |
| consultation | show current connection/start action without fake progress | preserve the synthetic boundary and one way to start; no empty dashboard | show the message/fact being handled, role, current stage, and one action | retain last confirmed context, name the recoverable condition, expose one retry | show confirmed fact, Case revision, and route-analysis handoff |
| route analysis | show current task/review status without marketing spinner copy | fail closed when no known ledger or stage exists | show ordered routes, evidence sufficiency, unresolved gap, role, and one review action | retain prior ledger/revision, explain what can continue, expose one recovery action | show client confirmation result, durable receipt, and plan handoff |
| execution | identify the independently seeded Happy/Blocked scenario while showing connection/current checkpoint retrieval without fake percentage | preserve approved plan context and the one valid start/recovery path | show checkpoint, owner, date, risk, handoff, and one action | retain last confirmed progress; blocked/overdue/reassessment/recovery stay distinct | show verified completion and no invented next task |

Loading, empty, error, partial, and success are presentation projections of existing
state only. This plan does not create a new empty-state domain, background operation,
optimistic result, progress percentage, or retry authority.

The executable interaction matrix is:

| Existing state or exact group | Retained visible context | Primary/disabled action | Focus and announcement |
|---|---|---|---|
| collaboration `bootstrapping_parent`, `thread_ready` | synthetic boundary, consultation context, current messages | existing start/message/proposal action; disabled reason stays beside the control | route `h1` on entry; accepted action returns focus to current-work `h2`; one polite live region |
| collaboration `message_submitting`, `switching_to_advisor`, `confirmation_submitting`, `handoff_validating` | exact prior message/candidate/fact and Case revision already present | the in-flight action is visible but disabled; no second action or fake progress | current-work `h2`; polite in-flight announcement only |
| collaboration `proposal_pending`, `advisor_reviewing`, `replan_required` | proposal/source actor, confirmed fact when present, active role, stage | exactly the existing role switch, advisor confirmation, or handoff action | accepted transition focuses the new current-work `h2` |
| collaboration `recoverable_error` or journey conflict | exact `resumePhase`/last confirmed context; unknown resume fails closed | one retry, return, or protected end action using existing authority | error/conflict `h2` receives focus; one alert, no duplicate `h1` |
| connected `bootstrapping`, `advisor_ready`, `task_creating`, `task_streaming`, `advisor_review`, `review_submitting` | last known ledger/task/routes/evidence and advisor role | existing create/review action or disabled in-flight action | route `h1` remains unique; current-work `h2` receives accepted-transition focus; one polite task/status region |
| connected revision group (`revision_requested`, `revision_fact_pending`, `replan_required`, `revision_blocked`) | predecessor comparison, current facts/revision, unresolved gap | exact proposal/fact/replan action; blocked exposes no approval/client action | changed-decision or blocked `h2` receives focus; blocked state is announced once |
| connected `role_switching`, `family_review`, `decision_submitting`, `plan_ready` | recursively retained prior state, exact actor authority, receipt/timeline when complete | existing role/client confirmation action; `plan_ready` only has a secondary link to the independent execution demo | handoff `h2` receives focus; no second route title or cross-scenario announcement |
| connected `recoverable_error`, `terminal_task_failure`, or journey conflict | retained prior ledger where valid; unknown prior fails closed | one existing retry/remediation/return action | recovery `h2` receives focus; one alert; no duplicate `h1` |
| execution `loading`, `ready_to_start`, `checkpoint_active`, `mutation_in_flight`, `awaiting_advisor` | independent-scenario label, approved plan, last server-owned checkpoint/progress | exactly the existing start/attest/verify action; in-flight action disabled with reason | current-action `h2` receives transition focus; one polite status region |
| execution `execution_completed`, `reassessment_required`, `session_changed`, `recoverable_error` | immutable completed progress or last confirmed checkpoint and approved plan | no mutation after completion/reassessment; one existing authority revalidation for session/recovery | terminal/recovery `h2` receives focus; one status or alert, never both |

`PlanningSkillInspector` and collaboration authority steps render in a named,
default-closed technical `details`. `ExecutionActivity` is also default-closed.
`EvidenceDisclosure` renders a visible business summary with its raw/provenance detail
closed. `TaskProgress` remains visible only while it explains current work; lease,
adapter, pin, and event internals remain in technical disclosure. DOM order is always
current work -> supporting business proof -> technical disclosure, even when desktop
CSS places supporting proof in a side rail.

## Trust and emotional arc

| Time horizon | Advisor/reviewer question | Required experience |
|---|---|---|
| first 5 seconds | “这是什么，给谁用？” | advisor category, current Case, product boundary, and next action are obvious without reading technical copy |
| first 5 minutes | “AI 做了什么，我为什么能信？” | route trade-offs, evidence gaps, advisor review, client choice, blocked path, and durable result are visible in one continuous story |
| repeated use | “中断后还能不能继续，责任会不会混乱？” | same-Case continuity through the connected receipt, explicit separate execution-scenario identity, role ownership, last confirmed state, recovery, reassessment, and technical evidence stay findable without dominating normal work |

The desired feeling is controlled clarity, not excitement. The interface earns trust
by showing what is known, what is missing, who decides, and what happens next. It
must never use confident visual treatment to hide a missing evidence gate or blocked
state.

## Responsive behavior

| Width | Navigation and workflow | Work canvas | Evidence and actions |
|---|---|---|---|
| 1280+ | compact product header; `176–208px` vertical workflow rail | `minmax(560px, 1fr)` work canvas plus `280–320px` supporting-evidence rail | primary action stays in source order; no sticky action or sticky evidence in this phase |
| 1024–1279 | compact header; workflow is a full-width horizontal ordered strip | two columns, `minmax(0, 2fr) minmax(280px, 1fr)`; evidence remains after work in DOM | action stays with its reason; technical disclosure spans the content width below both columns |
| 768–1023 | compact header; workflow remains a horizontal ordered strip | one main column; supporting evidence and technical disclosure follow current work | no hidden navigation dependency; controls retain 44px targets |
| 390–767 | product/context header wraps intentionally; workflow becomes a concise ordered strip | one semantic column in desktop reading order | primary action appears after its reason, never detached at the page bottom |
| 320–389 | no decorative side content; stage labels may wrap, not truncate | single column with reduced spacing but 16px body text | no horizontal scroll, clipped evidence, icon-only action, or hover dependency |

At 200% zoom, use the same single-column semantic order rather than shrinking type
or hiding evidence. Reduced motion removes non-essential transitions without hiding
state changes. The automated browser matrix includes `1024` in addition to
`1440`, `768`, `390`, and `320`; CSS placement never changes DOM or keyboard order.

## Task 1: Preflight and mechanically land the approved contract

**Files:**

- Create: `docs/superpowers/specs/2026-08-09-advisor-centered-product-experience.md`
- Create: `docs/superpowers/plans/2026-08-09-advisor-centered-product-experience.md`
- Modify: `DESIGN.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/route-map.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/superpowers/README.md`
- Modify: `tests/architecture/test_documentation_governance.py`

- [ ] Record `BASE_SHA`, `BASE_TREE`, `origin/main`, clean status, open PRs, linked
      worktrees, branches, running project processes, and Docker resources.
- [ ] Before the first write, classify write ownership, Git metadata permission,
      Git/GitHub smart transport, and the publication `remote_owner`; record these in
      the private execution receipt rather than public project documents. Also verify
      host and Docker-VM free space, task-owned Compose-name/resource availability,
      and local Chromium/browser availability. Do not change Docker, host, credential,
      or account configuration during preflight.
- [ ] Create one task worktree and `codex/nv-advisor-workspace-redesign` branch from
      the exact accepted base. Do not write in the primary checkout.
- [ ] Copy the approved public-neutral design body and the implementation body through
      `Completion definition` into the two target project documents. Remove source
      frontmatter, the temporary restore comment, and the terminal private review-status
      appendix. Retain the public-neutral execution/TDD instructions, including the
      existing `superpowers:` references that the repository permits; do not add private
      machine paths, authority task IDs, model/provider routing, or private planning motives.
      All accepted implementation requirements must already be present in the copied
      body and remain semantically identical.
- [ ] Add a documentation-governance assertion that both documents exist, describe
      an advisor-centered presentation-only change, retain domain authority, and
      prohibit backend/dependency/fixture/release/deploy expansion. Assert that the
      connected same-Case proof and separately seeded execution proof are not merged
      into a fictitious Case journey.
- [ ] Update `DESIGN.md`, the storyboard, route map, and state/interaction matrix to
      mark the previous cosmic root/family-heavy layout as historical presentation
      and the new advisor-centered surface as approved but not yet verified.
- [ ] Add the new spec and plan to `docs/superpowers/README.md`; the existing
      `test_superpowers_index_links_every_approved_spec_and_plan` must stay GREEN.
- [ ] Run the documentation test before updating the docs and record its expected
      RED; then complete the documents and run it GREEN.

Run:

```bash
uv run pytest -q tests/architecture/test_documentation_governance.py
git diff --check
```

Expected: the initial new assertion fails only on absent/stale design text; the
completed docs pass with no private path, task id, private planning motive, or
execution metadata.

Commit after GREEN:

```bash
git add -- DESIGN.md docs/design/demo-storyboard.md docs/design/route-map.md \
  docs/design/state-and-interaction-matrix.md docs/superpowers/README.md \
  docs/superpowers/specs/2026-08-09-advisor-centered-product-experience.md \
  docs/superpowers/plans/2026-08-09-advisor-centered-product-experience.md \
  tests/architecture/test_documentation_governance.py
git commit -m "docs: define advisor-centered product experience"
```

## Task 2: Freeze the advisor-first and behavior-preservation RED contract

**Files:**

- Create: `web/tests/unit/advisor-workspace-design.test.tsx`
- Modify: `web/tests/unit/portfolio-entry.test.tsx`
- Modify: `web/tests/unit/presentation-journey.test.tsx`
- Modify: `web/tests/unit/presentation-catalog.test.ts`
- Modify: `web/tests/unit/presentation-locales.test.ts`
- Modify: `web/tests/unit/design-contract.test.tsx`
- Modify: `web/tests/unit/portfolio-route-contract.test.ts`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`
- Modify: `web/tests/unit/presentation-provider.test.tsx`
- Modify: `tests/architecture/test_portfolio_presentation_contract.py`

- [ ] Add exact Chinese and English hero assertions from the design spec.
- [ ] Assert the first viewport identifies an AI collaboration workspace for
      study-abroad advisors and links to `/demo/collaboration` and `/demo`.
- [ ] Assert top-level navigation, route context, workflow labels, hero text, and
      section headings are advisor-first in both locales. In Chinese they do not use
      `家庭表达`, `家庭决定`, or `顾问到家庭决策流程`; in English they do not use
      `Family input`, `Family decision`, `Advisor-to-family decision flow`, or
      equivalent family-first headings. Keep these checks structure-scoped rather
      than globally banning exact actor/domain terms.
- [ ] Assert exact actor and authority terms still appear in the detailed parent
      message, advisor review, client confirmation, receipt, and technical evidence
      surfaces.
- [ ] Assert the five `WorkflowStage` values and all existing reducer-state mappings,
      including `recoverable_error`, `role_switching`, recursive prior state, and
      unknown fail-closed behavior.
- [ ] Assert the closed `WorkflowProofSegment` values. Collaboration/connected render
      `connected_same_case`; `/demo/plan` renders
      `independent_execution_scenario`, and the proof boundary is visible in the Case
      context rather than relying only on footer copy.
- [ ] Assert connected raw backend phases reduce to existing display states before
      stage mapping: `active_task`/`revision_task_active` -> `task_streaming` and
      `review_required`/`revision_review_required` -> `advisor_review`. Assert raw
      phases are not direct `connectedWorkflowStage` keys.
- [ ] Assert `AdvisorWorkspaceShell`, `WorkflowRail`, and the root preview contain no
      forbidden side-effect primitives: `fetch`, `XMLHttpRequest`, `EventSource`,
      `localStorage.setItem`, `sessionStorage.setItem`, cookie write, session bootstrap,
      mutation callback, task creation, or role-switch callback.
- [ ] Assert root render calls no `fetch` and does not read the product session key.
      Keep the existing locale read behavior out of this product-session assertion.
- [ ] Assert each rendered state has no more than one filled primary action.
- [ ] Freeze shared/root contracts here: the shell owns exactly one visible route
      `h1`; state panels use `h2` or lower; presentation-provider locale changes do
      not remount task-owning children; root route metadata and navigation remain
      side-effect free. Tasks 4–6 add route-state RED assertions for accepted
      transition focus, recovery/conflict focus, heading order, and live-region/alert
      cardinality immediately before each corresponding route migration.
- [ ] Assert static preview facts are drawn only from the closed
      `fixtures/m3a/manifest.json` projection: synthetic boundary, `computing` intent,
      CNY 340,000–400,000 budget, Australia/Japan/Malaysia order, exact current route
      outcomes, coverage/gaps, and no named person or real/synthetic institution.
- [ ] Assert one typed preview projection in `portfolio.ts` owns outcome, evidence
      sufficiency, unresolved gap, and next action, and is parity-checked against the
      current deterministic public fixture contract. Components must not duplicate
      those facts as free-form literals.
- [ ] Assert `/demo/plan`, README navigation, workflow context, and screenshot copy
      identify Happy/Blocked as a separate deterministic execution scenario; no test
      may imply that the connected Case or session continued into it.
- [ ] Update the architecture contract to expect split CSS, the coded root preview,
      no runtime voyage image dependency, exact unchanged package/lock identities,
      four routes, two locales, five widths, reduced motion, 200% zoom, and the
      normal/blocked semantic paths.
- [ ] Extend the existing route, provider, and accessibility inventories rather than
      replacing them: freeze `layout.tsx` base/portfolio/workspace CSS imports,
      unique route headings, locale-child identity, legacy-to-new component
      replacement, and the exact four-route navigation contract.
- [ ] Run the focused suite and retain the expected RED output. Do not weaken tests to
      match the current UI.

Run:

```bash
npm --prefix web run test -- \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/portfolio-entry.test.tsx \
  tests/unit/presentation-journey.test.tsx \
  tests/unit/presentation-catalog.test.ts \
  tests/unit/presentation-locales.test.ts \
  tests/unit/design-contract.test.tsx \
  tests/unit/portfolio-route-contract.test.ts \
  tests/unit/presentation-accessibility.test.tsx \
  tests/unit/presentation-provider.test.tsx
uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
```

Expected RED: missing advisor shell/preview/workflow vocabulary, stale family-heavy
copy, old asset contract, and absent CSS split. Existing API/controller tests must
not fail.

Retain the exact expected RED output as task evidence, but do not commit a failing
HEAD. Continue directly to Task 3. Stage and commit these foundation/root tests with
their implementation only after the complete Task 3 group is GREEN. Tasks 4–6 use
the same RED-then-GREEN rule for route-specific tests; no intermediate failing commit
is permitted.

## Task 3: Build the shared visual foundation and coded root

**Files:**

- Create: `web/app/portfolio.css`
- Create: `web/app/workspace.css`
- Create: `web/components/presentation/AdvisorWorkspacePreview.tsx`
- Create: `web/components/presentation/AdvisorWorkspaceShell.tsx`
- Create: `web/components/presentation/WorkflowRail.tsx`
- Modify: `web/app/layout.tsx`
- Modify: `web/app/styles.css`
- Modify: `web/components/presentation/PortfolioShell.tsx`
- Modify: `web/components/presentation/PortfolioEntry.tsx`
- Modify: `web/lib/presentation/catalog.ts`
- Modify: `web/lib/presentation/journey.ts`
- Modify: `web/lib/presentation/portfolio.ts`
- Modify: `web/tests/unit/advisor-workspace-design.test.tsx`
- Modify: `web/tests/unit/portfolio-entry.test.tsx`
- Modify: `web/tests/unit/presentation-journey.test.tsx`
- Modify: `web/tests/unit/presentation-catalog.test.ts`
- Modify: `web/tests/unit/presentation-locales.test.ts`
- Modify: `web/tests/unit/design-contract.test.tsx`
- Modify: `web/tests/unit/portfolio-route-contract.test.ts`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`
- Modify: `web/tests/unit/presentation-provider.test.tsx`
- Modify: `tests/architecture/test_portfolio_presentation_contract.py`
- Delete after zero-reference proof:
  `web/components/presentation/PortfolioBackdrop.tsx`
- Delete after zero-reference proof:
  `web/components/presentation/PortfolioJourney.tsx`
- Delete after zero-reference proof:
  `web/components/presentation/PortfolioRouteAtlas.tsx`
- Delete after replacement-test proof:
  `web/tests/unit/portfolio-journey.test.tsx`
- Delete after replacement-test proof:
  `web/tests/unit/portfolio-route-atlas.test.tsx`
- Delete after zero runtime reference:
  `web/public/portfolio/night-voyager-voyage-960.avif`
- Delete after zero runtime reference:
  `web/public/portfolio/night-voyager-voyage-960.webp`
- Delete after zero runtime reference:
  `web/public/portfolio/night-voyager-voyage-1680.avif`
- Delete after zero runtime reference:
  `web/public/portfolio/night-voyager-voyage-1680.webp`

- [ ] Add the approved `--nv-*` tokens and separate base, portfolio, and workspace
      CSS. `layout.tsx` imports all three explicitly.
- [ ] Prune obsolete selectors from `styles.css`; do not merely append another visual
      system to the existing 2,700-line sheet. Keep only selectors with current
      references or documented browser/a11y purpose.
- [ ] Implement `WorkflowRail` as a pure ordered list with `complete`, `current`, and
      `upcoming` states and one `aria-current="step"`. It accepts only the closed
      stage union and copy function.
- [ ] Implement `AdvisorWorkspaceShell` with a dark product frame, compact header,
      Case context, workflow rail, dominant work canvas, supporting decision/evidence
      rail, default-closed technical disclosure, and footer. It must remain a
      presentation wrapper.
- [ ] Rebuild `/` as five ordered sections: advisor-first hero and coded preview; one
      continuous client workflow; current route analysis; AI/advisor responsibility
      split; concise engineering evidence.
- [ ] The preview must be a React composition, not a generated screenshot. It shows
      one current client Case, route-analysis state, Australia/Japan/Malaysia order,
      evidence sufficiency, unresolved gap, and one next advisor action using only
      the typed projection in `portfolio.ts`. Do not duplicate or creatively rewrite
      those facts inside the component.
- [ ] Use the approved Midnight Editorial Advisor Workspace system: deep-ink frame,
      warm-ivory canvas, restrained green trust color, rare gold navigation accent,
      no cosmic background, glass cards, KPI strip, generic AI orb, stock portrait,
      gradient CTA, or decorative fake product data.
- [ ] Delete the root-only backdrop/components/assets only after `rg` confirms zero import,
      URL, CSS, test, and runtime references. Retain
      `docs/assets/design/night-voyager-voyage-source.png` as historical provenance;
      do not use it at runtime. Keep `DecisionJourney`, `PresentationShell`, and
      `presentation-shell.test.tsx` until Tasks 4–6 migrate all three demos; deleting
      them in this root-only task would break the current build.
- [ ] Bring all Task 2 root/workflow/catalog tests GREEN without changing runtime
      controllers.

Run:

```bash
npm --prefix web run test -- \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/portfolio-entry.test.tsx \
  tests/unit/presentation-journey.test.tsx \
  tests/unit/presentation-catalog.test.ts \
  tests/unit/presentation-locales.test.ts \
  tests/unit/design-contract.test.tsx \
  tests/unit/portfolio-route-contract.test.ts \
  tests/unit/presentation-accessibility.test.tsx \
  tests/unit/presentation-provider.test.tsx
uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
npm --prefix web run typecheck
npm --prefix web run build
rg -n "PortfolioBackdrop|PortfolioJourney|PortfolioRouteAtlas|night-voyager-voyage-(960|1680)" web tests docs README.md README_CN.md DESIGN.md
```

Expected: tests GREEN; the final `rg` returns only explicitly historical design/plan
references, never an import, stylesheet URL, public runtime reference, or current
README instruction.

Commit after GREEN and zero-reference review:

```bash
git add -- web/app/layout.tsx web/app/styles.css web/app/portfolio.css \
  web/app/workspace.css \
  web/components/presentation/AdvisorWorkspacePreview.tsx \
  web/components/presentation/AdvisorWorkspaceShell.tsx \
  web/components/presentation/WorkflowRail.tsx \
  web/components/presentation/PortfolioShell.tsx \
  web/components/presentation/PortfolioEntry.tsx \
  web/components/presentation/PortfolioBackdrop.tsx \
  web/components/presentation/PortfolioJourney.tsx \
  web/components/presentation/PortfolioRouteAtlas.tsx \
  web/lib/presentation/catalog.ts web/lib/presentation/journey.ts \
  web/lib/presentation/portfolio.ts \
  web/tests/unit/advisor-workspace-design.test.tsx \
  web/tests/unit/portfolio-entry.test.tsx \
  web/tests/unit/portfolio-journey.test.tsx \
  web/tests/unit/portfolio-route-atlas.test.tsx \
  web/tests/unit/presentation-journey.test.tsx \
  web/tests/unit/presentation-catalog.test.ts \
  web/tests/unit/presentation-locales.test.ts \
  web/tests/unit/design-contract.test.tsx \
  web/tests/unit/portfolio-route-contract.test.ts \
  web/tests/unit/presentation-accessibility.test.tsx \
  web/tests/unit/presentation-provider.test.tsx \
  tests/architecture/test_portfolio_presentation_contract.py \
  web/public/portfolio/night-voyager-voyage-960.avif \
  web/public/portfolio/night-voyager-voyage-960.webp \
  web/public/portfolio/night-voyager-voyage-1680.avif \
  web/public/portfolio/night-voyager-voyage-1680.webp
git commit -m "feat: rebuild Night Voyager advisor workspace surface"
```

Before committing, inspect the exact staged paths and confirm that every deleted
path has a zero-reference proof and a tested replacement.

## Task 4: Recompose consultation intake and client fact review

**Files:**

- Modify: `web/components/collaboration-demo/CollaborationDemo.tsx`
- Modify: `web/components/collaboration-demo/SharedThread.tsx`
- Modify: `web/components/collaboration-demo/MemoryCandidateCard.tsx`
- Modify: `web/components/collaboration-demo/ConfirmedFactSummary.tsx`
- Modify: `web/components/collaboration-demo/CollaborationRecoveryNotice.tsx`
- Modify: `web/components/demo-session/JourneyConflictNotice.tsx`
- Modify: `web/components/skill-inspector/PlanningSkillInspector.tsx`
- Modify: `web/tests/unit/collaboration-demo.test.tsx`
- Modify: `web/tests/unit/collaboration-recovery.test.tsx`
- Modify: `web/tests/unit/advisor-workspace-design.test.tsx`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`

- [ ] First add focused RED assertions for the route shell, unique heading hierarchy,
      accepted-transition/recovery/conflict focus, live-region cardinality, retained
      callbacks, and current-state action count. Record the expected failures; do not
      commit a failing HEAD. Then migrate the route and bring the same assertions GREEN.
- [ ] Keep `useCollaborationDemo` untouched. Derive `activeRole`, current workflow
      stage, human-readable outcome, and next responsibility from existing state.
- [ ] Present the route as consultation intake and client-information review:
      consultation record, proposed client fact, advisor confirmation, confirmed
      client fact/Case revision, then handoff into route analysis.
- [ ] Use “客户” and “咨询” at first layer where the exact actor is irrelevant. Keep
      parent, advisor, source message, fact version, and Case revision visible where
      they establish authority or provenance.
- [ ] Put the current work and one primary action above the message/fact evidence.
      Keep Skill detail and authority steps in secondary technical disclosure.
- [ ] Preserve focus movement, disabled reasons, live regions, retry behavior,
      message body, proposal body, verification reason, and all callbacks exactly.
- [ ] Convert the shared `JourneyConflictNotice` state heading from a competing `h1`
      to the route shell's `h2` hierarchy, expose a focusable heading ref with
      `tabIndex={-1}`, and focus it only on conflict-state entry. Cover both
      collaboration and connected conflict routes without duplicating announcements.
- [ ] Add focused normal, disabled, recoverable, and replan handoff assertions.

Run:

```bash
npm --prefix web run test -- \
  tests/unit/collaboration-demo.test.tsx \
  tests/unit/collaboration-recovery.test.tsx \
  tests/unit/use-collaboration-demo.test.tsx \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/presentation-accessibility.test.tsx
```

Expected: all focused tests GREEN; no request count, body, idempotency, recovery, or
focus assertion changes.

## Task 5: Recompose advisor route analysis and downstream client confirmation

**Files:**

- Modify: `web/components/connected-demo/ConnectedDemo.tsx`
- Modify: `web/components/connected-demo/AdvisorLedger.tsx`
- Modify: `web/components/connected-demo/CurrentConfirmedFacts.tsx`
- Modify: `web/components/connected-demo/EvidenceDisclosure.tsx`
- Modify: `web/components/connected-demo/PlanningRevisionComparison.tsx`
- Modify: `web/components/connected-demo/FamilyDecisionBrief.tsx`
- Modify: `web/components/connected-demo/DecisionReceiptTimeline.tsx`
- Modify: `web/components/connected-demo/RevisionFactEditor.tsx`
- Modify: `web/components/connected-demo/RecoveryNotice.tsx`
- Modify: `web/components/connected-demo/TaskProgress.tsx`
- Modify: `web/tests/unit/connected-demo-ui.test.tsx`
- Modify: `web/tests/unit/connected-demo-inspector.test.tsx`
- Modify: `web/tests/unit/connected-demo-recovery.test.tsx`
- Modify: `web/tests/unit/connected-demo-presentation.test.ts`
- Modify: `web/tests/unit/design-contract.test.tsx`
- Modify: `web/tests/unit/advisor-workspace-design.test.tsx`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`

- [ ] First add focused RED assertions for the route shell, unique heading hierarchy,
      accepted-transition/recovery/conflict focus on the shared
      `JourneyConflictNotice`, live-region cardinality, retained callbacks, and
      current-state action count. Record the expected failures; do not commit a
      failing HEAD. Then migrate the route and bring the same assertions GREEN.
- [ ] Keep `useConnectedDemo`, reducers, contracts, API modules, and callback bodies
      untouched.
- [ ] Lead with the current advisor question, route-analysis outcome, evidence gap,
      and one next professional action.
- [ ] Render Australia, Japan, and Malaysia as ordered route rows. Each row exposes
      current outcome, human-readable reason, review eligibility, accepted evidence,
      and unresolved gap. Retain a semantic comparison table for assistive
      technology if the visual surface is not a table.
- [ ] Keep revision comparison adjacent to the decision it invalidates and explain
      why renewed advisor review is required. Do not expose raw state codes as
      headings.
- [ ] Present client confirmation as a downstream handoff. The exact parent/family
      actor and `FamilyDecision` semantics remain visible inside the confirmation,
      receipt, and technical evidence layers.
- [ ] In `plan_ready`, offer only a secondary, explicitly labelled navigation to the
      independent execution-follow-up demo. It must not claim to carry the current
      Case, session, receipt, or timeline into `/demo/plan`.
- [ ] Preserve all planning, task, review, revision, role-switch, decision, receipt,
      timeline, SSE, recovery, and focus behavior.
- [ ] Add focused assertions for initial advisor state, review-required, revision,
      client confirmation, plan-ready receipt, and recoverable failure.

Run:

```bash
npm --prefix web run test -- \
  tests/unit/connected-demo-ui.test.tsx \
  tests/unit/connected-demo-inspector.test.tsx \
  tests/unit/connected-demo-recovery.test.tsx \
  tests/unit/connected-demo-presentation.test.ts \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/design-contract.test.tsx \
  tests/unit/presentation-accessibility.test.tsx
```

Expected: all focused tests GREEN; byte-identity and request-count assertions remain
unchanged.

## Task 6: Recompose execution follow-up, blocked state, and recovery

**Files:**

- Modify: `web/components/plan-execution/PlanExecutionWorkspace.tsx`
- Modify: `web/components/plan-execution/CurrentCheckpoint.tsx`
- Modify: `web/components/plan-execution/CheckpointAttestationForm.tsx`
- Modify: `web/components/plan-execution/AdvisorVerificationPanel.tsx`
- Modify: `web/components/plan-execution/ExecutionActivity.tsx`
- Modify: `web/components/plan-execution/ExecutionRecoveryNotice.tsx`
- Modify: `web/components/plan-execution/ReassessmentHandoff.tsx`
- Modify: `web/app/workspace.css`
- Modify if legacy presentation selectors remain: `web/app/styles.css`
- Modify: `web/tests/unit/plan-execution-ui.test.tsx`
- Modify: `web/tests/unit/plan-execution-presentation.test.ts`
- Modify: `web/tests/unit/plan-execution-recovery.test.tsx`
- Modify: `web/tests/unit/advisor-workspace-design.test.tsx`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`
- Delete after all three demos use the replacement shell/rail and zero-reference proof:
  `web/components/presentation/DecisionJourney.tsx`
- Delete after all three demos use the replacement shell/rail and zero-reference proof:
  `web/components/presentation/PresentationShell.tsx`
- Delete after replacement-test proof:
  `web/tests/unit/presentation-shell.test.tsx`

- [ ] First add focused RED assertions for the execution shell, unique heading
      hierarchy, accepted-transition/recovery focus, live-region cardinality,
      retained callbacks, and current-state action count. Record the expected
      failures; do not commit a failing HEAD. Then migrate the route and bring the
      same assertions GREEN.
- [ ] Keep `usePlanExecution`, reducer, BFF, contracts, scenario parser, and request
      callbacks untouched.
- [ ] Lead with current checkpoint, accountable participant, due date, risk, next
      handoff, and exactly one primary action for the active role.
- [ ] Keep the approved immutable plan as contextual reference and technical activity
      as secondary disclosure.
- [ ] Make blocked, overdue, waiting-advisor, completed, reassessment, session-changed,
      and recoverable states visually distinct without hiding the last confirmed
      progress.
- [ ] Label the role switcher as a synthetic demo perspective control; do not imply a
      production permissions feature.
- [ ] Preserve action availability, disabled reasons, focus transfer, live messages,
      immutable plan visibility, reassessment safe stop, and recovery exactly.
- [ ] Add focused normal, waiting, blocked, reassessment, completed, and recovery
      assertions.
- [ ] After Tasks 4–6 are GREEN, run a zero-reference check for `DecisionJourney` and
      `PresentationShell`; then delete both old components and
      `presentation-shell.test.tsx`. The replacement shell/rail tests must cover all
      landmarks, locale, synthetic boundary, proof segment, unique `h1`, and state
      focus behavior before deletion.
- [ ] Remove obsolete `.decision-journey*` and legacy `.presentation-*` selectors
      from `workspace.css` and `styles.css` only after PascalCase component/import,
      kebab-case selector, test, and stylesheet references are all zero.

Run:

```bash
npm --prefix web run test -- \
  tests/unit/plan-execution-ui.test.tsx \
  tests/unit/plan-execution-presentation.test.ts \
  tests/unit/plan-execution-recovery.test.tsx \
  tests/unit/plan-execution-idempotency.test.ts \
  tests/unit/advisor-workspace-design.test.tsx \
  tests/unit/presentation-accessibility.test.tsx
npm --prefix web run test
npm --prefix web run typecheck
npm --prefix web run build
```

Expected: all focused tests GREEN; controller request identities and state
transitions remain unchanged.

Commit Tasks 4–6 together only after the complete shared behavior suite is GREEN:

```bash
git add -- web/components/collaboration-demo/CollaborationDemo.tsx \
  web/components/collaboration-demo/SharedThread.tsx \
  web/components/collaboration-demo/MemoryCandidateCard.tsx \
  web/components/collaboration-demo/ConfirmedFactSummary.tsx \
  web/components/collaboration-demo/CollaborationRecoveryNotice.tsx \
  web/components/demo-session/JourneyConflictNotice.tsx \
  web/components/connected-demo/ConnectedDemo.tsx \
  web/components/connected-demo/AdvisorLedger.tsx \
  web/components/connected-demo/CurrentConfirmedFacts.tsx \
  web/components/connected-demo/EvidenceDisclosure.tsx \
  web/components/connected-demo/PlanningRevisionComparison.tsx \
  web/components/connected-demo/FamilyDecisionBrief.tsx \
  web/components/connected-demo/DecisionReceiptTimeline.tsx \
  web/components/connected-demo/RevisionFactEditor.tsx \
  web/components/connected-demo/RecoveryNotice.tsx \
  web/components/connected-demo/TaskProgress.tsx \
  web/components/plan-execution/PlanExecutionWorkspace.tsx \
  web/components/plan-execution/CurrentCheckpoint.tsx \
  web/components/plan-execution/CheckpointAttestationForm.tsx \
  web/components/plan-execution/AdvisorVerificationPanel.tsx \
  web/components/plan-execution/ExecutionActivity.tsx \
  web/components/plan-execution/ExecutionRecoveryNotice.tsx \
  web/components/plan-execution/ReassessmentHandoff.tsx \
  web/app/workspace.css web/app/styles.css \
  web/components/presentation/DecisionJourney.tsx \
  web/components/presentation/PresentationShell.tsx \
  web/components/skill-inspector/PlanningSkillInspector.tsx \
  web/tests/unit/collaboration-demo.test.tsx \
  web/tests/unit/collaboration-recovery.test.tsx \
  web/tests/unit/connected-demo-ui.test.tsx \
  web/tests/unit/connected-demo-inspector.test.tsx \
  web/tests/unit/connected-demo-recovery.test.tsx \
  web/tests/unit/connected-demo-presentation.test.ts \
  web/tests/unit/design-contract.test.tsx \
  web/tests/unit/plan-execution-ui.test.tsx \
  web/tests/unit/plan-execution-presentation.test.ts \
  web/tests/unit/plan-execution-recovery.test.tsx \
  web/tests/unit/presentation-shell.test.tsx \
  web/tests/unit/presentation-accessibility.test.tsx \
  web/tests/unit/advisor-workspace-design.test.tsx
git commit -m "feat: align advisor workflow presentation"
```

Before staging, run:

```bash
rg -n "DecisionJourney|PresentationShell|decision-journey|presentation-(shell|header|footer|controls)" web tests
```

Expected: only explicitly historical documentation references remain; there are no
imports, JSX uses, CSS selectors, or live tests. Inspect the staged diff and confirm
that every path belongs to Tasks 4–6.

## Task 7: Prove visual quality, refresh real screenshots, and update public navigation

**Files:**

- Modify: `web/e2e/portfolio-design-review.spec.ts`
- Modify: `web/e2e/presentation.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/bootstrap.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/fact-to-plan.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/collaboration-demo.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/connected-demo.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/planning-revision.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/plan-execution-minimal.spec.ts`
- Modify as copy/structure assertions require: `web/e2e/plan-execution.spec.ts`
- Modify: `web/playwright.compose.config.ts`
- Modify if matrix wiring changes: `scripts/verify_compose.sh`
- Modify if exact lane contract changes: `tests/architecture/test_compose_contract.py`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/operations/collaboration-walkthrough.md`
- Modify: `docs/operations/connected-demo.md`
- Modify: `docs/operations/plan-execution-walkthrough.md`
- Refresh from real deterministic Chromium only:
  `docs/assets/night-voyager-portfolio-entry.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/collaboration-confirmed-fact.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/m5-advisor-ledger.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/m5-family-receipt-timeline.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/night-voyager-planning-revision.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/plan-execution-current-action.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/plan-execution-advisor-review.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/plan-execution-reassessment-mobile.png`
- Refresh from real deterministic Chromium only:
  `docs/assets/plan-execution-recovery-mobile.png`

The nine public assets have this fixed provenance; this is evidence classification,
not a third product workflow:

| Asset | Evidence class | Required visible boundary |
|---|---|---|
| `night-voyager-portfolio-entry.png` | product-orientation evidence | advisor workspace, static illustrative preview, local synthetic boundary |
| `collaboration-confirmed-fact.png` | Segment A: connected same-Case proof | consultation/fact review and confirmed Case revision |
| `m5-advisor-ledger.png` | Segment A: connected same-Case proof | route analysis, advisor responsibility, evidence gap |
| `m5-family-receipt-timeline.png` | Segment A: connected same-Case proof | downstream client confirmation, receipt, `TimelinePlan` |
| `night-voyager-planning-revision.png` | Segment A supporting revision variant | connected-route predecessor/current comparison; not a third workflow and not plan execution |
| `plan-execution-current-action.png` | Segment B: independent execution scenario | independently seeded Happy scenario and current action |
| `plan-execution-advisor-review.png` | Segment B: independent execution scenario | independently seeded advisor-review handoff |
| `plan-execution-reassessment-mobile.png` | Segment B: independent execution scenario | Blocked -> reassessment safe stop |
| `plan-execution-recovery-mobile.png` | Segment B: independent execution scenario | retained progress and existing authority revalidation |

- [ ] Keep the presentation matrix at exactly four routes, two locales, five widths,
      reduced motion, 200% zoom, keyboard/focus, contrast, overflow, long copy,
      normal journey, and blocked journey. If the test count changes, prove the
      coverage set is equivalent or stronger; do not merely update a number.
- [ ] Add semantic assertions for first-viewport advisor positioning, shared shell,
      current stage, current responsibility, one primary action, no family-heavy
      top-level vocabulary, and detailed actor/authority retention.
- [ ] Verify 1440, 1024, 768, 390, and 320 layouts in the canonical real-Chromium
      automated matrix. Do not leave 1024 as a manual-only checkpoint.
- [ ] Verify `44px` targets, visible focus, one `h1`, heading order, semantic table or
      list fallback, color contrast, reduced motion, 200% zoom, no horizontal
      overflow, no clipped long copy, no console error, and favicon success.
- [ ] Replay two truthful task-owned Compose proof segments: (1) consultation normal
      -> confirmed fact -> same-Case route analysis -> advisor approval -> client
      confirmation -> receipt/timeline; (2) independently seeded plan Happy, then
      independently seeded plan Blocked -> reassessment safe stop -> recovery.
- [ ] Capture all nine current public screenshots from that real deterministic flow.
      Do not add a presentation-only fixture or selector. The existing closed
      `?scenario=blocked` selector remains the authoritative deterministic execution
      scenario selector and is allowed.
      Inspect every image for synthetic labelling, private path, raw UUID, internal
      task identity, credential, traceback, clipping, empty canvas, and visual
      consistency.
- [ ] Rewrite README and operations entry copy around the advisor workspace. Keep the
      actual local synthetic and release boundaries. Screenshots remain review
      evidence, not functional authority.
- [ ] Make the Compose real-Chromium presentation lane execute
      `bootstrap.spec.ts`, `portfolio-design-review.spec.ts`, and
      `presentation.spec.ts`; do not leave root comprehension/design assertions in
      files that no canonical command runs. Freeze the exact file invocation and
      evidence-root wiring in `test_compose_contract.py`. Keep the existing behavior
      lanes for fact-to-plan, collaboration, connected decision, revision, minimal
      execution, and full execution in the complete Compose proof.
- [ ] Make evidence-root handling safe under `set -u`: initialize from
      `${PRESENTATION_PUBLIC_EVIDENCE_ROOT:-}`, pass it only to the presentation-audit
      browser lane, and prove that an unset/empty value writes no public asset. With
      the exact approved root set, refresh only the declared nine assets, including
      the four execution screenshots, and reject every unlisted output.
- [ ] Record a production-build and Chromium resource baseline before presentation
      implementation, then record the candidate's static JS/CSS bytes, browser
      request count, and transferred/resource bytes on the same routes and settings.
      Use the comparison to identify unexplained growth; do not invent a performance
      threshold or improvement claim. The root must still issue zero product requests
      and the removed voyage images must have zero runtime requests.
- [ ] Run GStack `design-review` once on the complete candidate, covering `/`,
      `/demo/collaboration`, `/demo`, and `/demo/plan` in normal and blocked states.
      Resolve only verified same-scope findings; do not add a new visual direction.

Run the task-owned environment with a unique Compose name and task-owned evidence
root. Always run same-project teardown and inventory after success or failure.

Run at minimum:

```bash
TASK_COMPOSE_PROJECT="nv-advisor-workspace-$(date +%Y%m%d%H%M%S)"
export TASK_COMPOSE_PROJECT
PRESENTATION_PUBLIC_EVIDENCE_ROOT="${PRESENTATION_PUBLIC_EVIDENCE_ROOT:-}"
export PRESENTATION_PUBLIC_EVIDENCE_ROOT
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py \
  tests/architecture/test_compose_contract.py \
  tests/architecture/test_documentation_governance.py
PRESENTATION_AUDIT=1 \
UPDATE_PORTFOLIO_SCREENSHOTS=1 \
UPDATE_COLLABORATION_SCREENSHOT=1 \
UPDATE_PLANNING_REVISION_SCREENSHOT=1 \
PRESENTATION_PUBLIC_EVIDENCE_ROOT=/workspace/docs/assets \
COMPOSE_PROJECT_NAME="$TASK_COMPOSE_PROJECT" \
  scripts/verify_compose.sh
```

Expected: all gates GREEN; real Chromium evidence exists for the normal and blocked
flows; same-project containers, network, temporary volume, browser process, and
temporary evidence are removed or precisely reported.

`scripts/verify_compose.sh` must read
`${PRESENTATION_PUBLIC_EVIDENCE_ROOT:-}` safely and thread a non-empty value only into
the presentation-audit browser container. The corresponding architecture test
freezes the three-spec real-Chromium invocation, proves the unset/empty mode cannot
write public assets, and proves the set mode names the exact four execution captures
alongside the five root/connected assets. After the run, verify the exact nine
approved asset paths changed, are non-empty images with recorded dimensions/hashes,
and contain no unreviewed tenth capture.

Commit only after screenshot inspection and documentation verification:

```bash
git add -- README.md README_CN.md docs/README.md \
  docs/operations/collaboration-walkthrough.md \
  docs/operations/connected-demo.md \
  docs/operations/plan-execution-walkthrough.md \
  docs/assets/night-voyager-portfolio-entry.png \
  docs/assets/collaboration-confirmed-fact.png \
  docs/assets/m5-advisor-ledger.png \
  docs/assets/m5-family-receipt-timeline.png \
  docs/assets/night-voyager-planning-revision.png \
  docs/assets/plan-execution-current-action.png \
  docs/assets/plan-execution-advisor-review.png \
  docs/assets/plan-execution-reassessment-mobile.png \
  docs/assets/plan-execution-recovery-mobile.png \
  web/e2e/portfolio-design-review.spec.ts web/e2e/presentation.spec.ts \
  web/e2e/bootstrap.spec.ts web/e2e/fact-to-plan.spec.ts \
  web/e2e/collaboration-demo.spec.ts web/e2e/connected-demo.spec.ts \
  web/e2e/planning-revision.spec.ts web/e2e/plan-execution-minimal.spec.ts \
  web/e2e/plan-execution.spec.ts \
  web/playwright.compose.config.ts scripts/verify_compose.sh \
  tests/architecture/test_compose_contract.py
git commit -m "docs: refresh advisor workspace proof surface"
```

Stage only paths that actually changed and belong to this task.

## Task 8: Full verification and authority handoff

- [ ] After Tasks 1–7 and screenshot/design review are complete, update
      `docs/superpowers/specs/2026-08-09-advisor-centered-product-experience.md`,
      `docs/superpowers/plans/2026-08-09-advisor-centered-product-experience.md`,
      `DESIGN.md`, `docs/design/demo-storyboard.md`, `docs/design/route-map.md`, and
      `docs/design/state-and-interaction-matrix.md` from approved/candidate wording to
      implemented and locally verified wording. Record actual command/evidence
      identities, not claims of release, deployment, adoption, or production use;
      `v0.1.5` remains the stable release.
- [ ] Run the documentation-governance tests and `git diff --check` on that complete
      working tree, inspect the exact staged docs, and create one closeout commit:

```bash
uv run pytest -q tests/architecture/test_documentation_governance.py
git diff --check
git add -- DESIGN.md docs/design/demo-storyboard.md docs/design/route-map.md \
  docs/design/state-and-interaction-matrix.md \
  docs/superpowers/specs/2026-08-09-advisor-centered-product-experience.md \
  docs/superpowers/plans/2026-08-09-advisor-centered-product-experience.md
git diff --cached --name-status
git commit -m "docs: record advisor workspace verification"
```

- [ ] Run `superpowers:verification-before-completion` with fresh commands, not cached
      output or a prior branch receipt.
- [ ] Run the complete repository gate:

```bash
make check
git diff --check "$BASE_SHA"..HEAD
git status --short --branch
git log --oneline --decorate "$BASE_SHA"..HEAD
```

- [ ] Verify the complete diff contains no backend, BFF, API contract, reducer,
      database, migration, RLS, worker, task lifecycle, SSE, session, fixture,
      package, lockfile, Compose-topology, provider, release, deployment,
      or unrelated change.
- [ ] Verify the root, route navigation, README, workflow rail, and screenshots state
      the same-Case connected proof and separate execution-scenario proof truthfully;
      no surface claims a cross-scenario Case/session handoff.
- [ ] Verify no current public file references the deleted runtime voyage assets or
      obsolete presentation components. Historical plans/specs may retain their
      historical names but must not claim they are current runtime guidance.
- [ ] Scan all changed text and image evidence for private paths, task ids, private
      motives, credentials, tokens, real personal data, raw internal errors, UUIDs,
      and unsupported outcome/production claims.
- [ ] Report exact base/head/tree, commit list, changed paths, RED/GREEN evidence,
      unit/type/lint/build/Compose/browser/design-review results, screenshot
      dimensions/hashes, resource inventory, remaining risks, and mini-retro.
- [ ] Stop at `READY` for review-authority branch-diff review. Do not push or create a
      PR unless the approved implementation mandate explicitly includes the
      unattended publication package below.

## Review-authority and unattended publication package

The authority reviews the exact branch diff once before publication. Findings are
returned to the same execution window. The execution window verifies each finding,
performs RED-first same-scope repair, reruns focused and complete verification, and
returns the new exact head. Authority performs targeted re-review; a new full review
is required only for a materially widened diff or a changed product/authority
boundary.

If the user approves the complete unattended package, the same bounded phase also
covers:

```text
exact reviewed HEAD push
-> ready PR with persisted public-neutral body
-> exact PR-head hosted CI and platform review
-> same-scope CI/review repair and targeted re-review
-> conditional squash merge only when reviewed tree == merge tree and required checks pass
-> final main, PR body, checks, screenshot/navigation and remote-ref readback
-> task-owned branch/worktree/Compose/temp cleanup
-> execution task archive
```

The package does not cover a tag, GitHub Release, deployment, package publication,
provider call, dependency change, account/Pages/repository setting, broad cleanup,
or a change to another repository. Any such need is a new decision gate.

## Stop conditions

Stop and return `USER_ACTION_REQUIRED` only when:

- live code drift creates a real product, authority, dependency, or acceptance
  decision not resolved by this plan;
- the implementation would require a backend/API/schema/reducer/fixture/dependency
  change;
- a real browser, Docker, Git metadata, network, or GitHub permission boundary has
  no safe in-scope recovery path;
- a screenshot can only be produced by inventing state or data;
- publication would require a tag, release, deploy, account change, or other
  unapproved external action.

Ordinary test repair, exact copy refinement, responsive correction, same-scope
design-review findings, hosted CI repair, persisted PR-body correction, and
task-owned cleanup are not new user decisions when included in the approved
unattended package.

## Completion definition

This phase is complete only when:

1. the first viewport and every demo route identify an advisor-centered product;
2. family/parent language appears only where actor or authority requires it;
3. the root and demos share one deliberate visual system and current-work hierarchy;
4. the root preview and all public screenshots come from typed or real coded
   deterministic product surfaces, never generated mockups, and the separate
   execution scenario is labelled truthfully;
5. normal, waiting, blocked, reassessment, recovery, and completed states remain
   understandable and behaviorally unchanged;
6. all unit, architecture, lint, type, build, Compose, browser, accessibility, and
   design-review gates pass on the exact candidate;
7. the public README and current screenshots match the implemented product;
8. the final diff contains no out-of-scope capability or unsupported claim;
9. the approved publication gate, if any, is complete with persisted readback; and
10. all task-owned residue is removed or returned as `DONE_WITH_RESIDUE` with exact
    owner, path/resource, reason, and recovery condition.

After completion, stop product UI development. Future presentation work requires
fresh repository or user evidence and a separately approved plan.
