# Chinese-First Portfolio Presentation Implementation Plan

**Implementation status:** Approved plan. Implementation has not started.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` as the primary controller. If the implementation
> owner chooses isolated bounded lanes, use `superpowers:subagent-driven-development`
> instead, not in addition. Use GStack `design-review` after implementation for live
> visual QA. Every contract, component, and browser slice follows RED -> GREEN.

**Goal:** Turn the released functional walkthrough into a Chinese-default,
English-switchable, outcome-first portfolio presentation that non-technical
recruiters and family reviewers can understand in the first viewport while keeping
exact technical proof available to engineering evaluators.

**Architecture:** A dependency-free, project-owned `PresentationLocaleV1` and closed
typed copy catalog serve `/`, `/demo`, and `/demo/collaboration`. Server rendering
always starts in `zh-CN`; a client provider reads one versioned presentation-only
`localStorage` preference after hydration, updates `html[lang]`, and never touches
the business journey. Components consume typed copy keys and closed code maps.
Existing backend/BFF/domain values remain canonical and unmodified. The visual layer
evolves the approved warm-paper `Advisor Ledger × Global Journey` system through
clearer hierarchy, restrained composition, responsive behavior, and secondary
technical disclosure.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, CSS, Vitest, Testing
Library, Playwright/Chromium, current BFF/authority contracts, and local/system CJK
font fallbacks. No i18n, font, icon, component, animation, or design dependency.

## Global Constraints

- Start only after PR 2 is merged to clean `main` and its exact merge-SHA hosted
  `python`, `frontend`, and `compose` checks are green. Record the actual base SHA.
- PR 3 owns presentation locale, closed copy/formatting, the current root portfolio
  entry, shared public shell, component hierarchy/styling, bilingual browser proof,
  screenshots, design docs, and final three-PR status. It does not modify migration,
  backend authority, API/BFF routes, request/response contracts, dependencies,
  lockfiles, worker, task/SSE behavior, DRA/MKE, provider transport, package version,
  release history, or deployment.
- Supported locales are exactly `zh-CN` and `en`. Server-rendered and missing/invalid
  preference behavior is always `zh-CN`. No browser-language auto-detection.
- Use exact preference key `night-voyager:presentation-locale:v1`. Invalid values are
  removed. This key is presentation-only and never enters `sessionStorage`, cookies,
  CSRF, idempotency, HTTP/BFF, EventSource, database, task pins, or domain models.
- Locale changes perform zero bootstrap, mint, revoke, mutation, retry, fetch, task,
  polling, navigation, or EventSource operations.
- Copy is a closed typed catalog. Both locales have exact key parity. Dynamic domain
  values use closed maps or pure validated formatters. Unknown/malformed values
  render a bounded localized “status unavailable” fallback without interpolating the
  raw value in visible text, accessible names, console output, or screenshots.
- Preserve canonical amounts, timestamps, dates, revision numbers, versions, and
  public proof values. Presentation formatting cannot round, convert, localize, or
  translate underlying authority.
- Keep the product name `Night Voyager` in both locales. Chinese plain-language
  promise is exact: `把家庭事实变成可追溯的留学决策与行动计划`.
- Keep the approved palette, spacing scale, restrained borders, semantic accents,
  table behavior, route-line motif, and editorial family narrative. Do not introduce
  a generic SaaS card grid, KPI strip, chat shell, control tower, gradient blob,
  decorative icon circles, uniform bubbly cards, or unsupported marketing claims.
- Use named local font stacks. Chinese UI starts with `PingFang SC`, then
  `Microsoft YaHei`, `Noto Sans CJK SC`, `WenQuanYi Zen Hei`, and a safe sans fallback.
  English preserves IBM Plex Sans / Source Serif intent. No downloaded font is a
  runtime requirement.
- Root `/` is a truthful portfolio entry, not a second state machine. It performs no
  API call, session action, mutation, or fabricated metric.
- The first viewport on each public route prioritizes exactly: current outcome or
  purpose, evidence-backed reason, next human action. Technical detail is secondary
  and inspectable through semantic disclosure.
- Preserve 16 px minimum body text, 4.5:1 body contrast, 44 px targets, visible
  focus, semantic landmarks, reduced motion, keyboard order, and no horizontal
  overflow at 1440, 768, and 390 px.
- Use explicit path staging and `git diff --cached --check` before every commit.
- Before Docker/Chromium proof, run `make doctor MODE=dev`; record host and Docker VM
  capacity, task-owned Compose resources, teardown, and final inventory. Do not use
  broad prune or delete unrelated/retained data.
- Preserve all tagged v0.1.0/v0.1.1/v0.1.2 release documents and screenshots as
  historical artifacts unless current non-versioned documentation explicitly points
  to refreshed post-v0.1.2 evidence. Do not rewrite old release records.
- Keep public text and images synthetic, truthful, and neutral. No real user,
  admission, business-impact, SLA, deployment, credential, private path, or private
  process claim.

## What Already Exists

- `DESIGN.md` defines the warm canvas, paper surface, ink/trust/coral semantic
  palette, 4 px spacing scale, named local font intent, semantic table/mobile route
  comparison, 44 px targets, reduced motion, and prohibited patterns.
- `web/app/styles.css` already provides header, ledger, family editorial frame,
  route comparison, collaboration panel, inspector, and responsive primitives.
- `AdvisorLedger`, `FamilyDecisionBrief`, `DecisionReceiptTimeline`,
  `CollaborationDemo`, `ConfirmedFactSummary`, and `PlanningSkillInspector` already
  consume strict server projections.
- `web/lib/connected-demo/presentation.ts` already validates exact CNY minor units
  and closes three English code maps. PR 3 replaces/absorbs it rather than leaving a
  parallel formatter.
- Current Chromium tests already exercise desktop/tablet/mobile, keyboard focus,
  SSE recovery, role switching, receipts, and three screenshots.

## Information Architecture

### Shared shell

```text
header
  Night Voyager
  current route/context
  中文 | English
  本地合成演示 / Local synthetic demo
main
  outcome block: what happened / why / next action
  primary workflow content in decision order
  technical evidence disclosure
  persisted receipt/timeline when available
footer
  truthful synthetic/non-production boundary
```

### Root `/`

```text
Night Voyager + locale + synthetic label
把家庭事实变成可追溯的留学决策与行动计划
one sentence: message -> reviewed fact -> planning -> family receipt
[体验完整决策流程]  primary -> /demo/collaboration
[直接查看顾问到家庭流程] secondary -> /demo
three compact authority beats, rendered as a route line, not cards
technical scope disclosure: local synthetic, no live provider/real student/deploy
```

### `/demo/collaboration`

```text
current outcome / current role / next human action
shared communication record
typed proposal
advisor confirmation
confirmed fact + Case revision
same-Case planning handoff
technical evidence disclosure: provenance + Skill inspector
```

### `/demo`

```text
current decision stage + current Case revision
one primary human action
route comparison / reason / eligibility
current confirmed family fact
task progress or review/family outcome
technical evidence disclosure: task + Skill + provenance
receipt and timeline
```

Constraint worship: if a first viewport can show only three facts, they are (1) the
current decision/outcome, (2) why the system can say it, and (3) what the human must
do next. Adapter, digest, lifecycle code, and raw Evidence key never displace them.

## Interaction State Coverage

| Surface | Loading | Empty | Error | Success | Partial/recovery |
| --- | --- | --- | --- | --- | --- |
| locale | Chinese SSR; control hydrates without layout jump | missing preference = Chinese | invalid preference removed, Chinese shown | visible selected locale and correct `html[lang]` | switch changes copy only; business state stays mounted |
| root | static Chinese content | not applicable | not applicable | two truthful routes visible | JavaScript disabled still shows Chinese entry/links |
| collaboration bootstrap | one bounded start action | no thread yet explains message is not authority | localized safe pause + reload | role and first action visible | residual-cookie/journey conflict preserves server boundary |
| thread | localized loading status | warm empty state explains first message action | bounded recovery | messages in chronological record | existing messages remain visible during mutation |
| proposal/confirmation | disabled reason and live status | no candidate means explicit proposal action | closed category, no raw code | status + advisor action | stale/expired/current states remain distinct |
| handoff | confirmed fact stays visible; button disabled | not applicable | collaboration envelope preserved | same-Case transition to `/demo` | interrupted navigation recovers from destination envelope |
| planning task | localized progress, one live region | task-ready explains no task exists yet | bounded recovery/terminal state | next advisor action visible | one EventSource, current cursor, inspector cleared while pending |
| route comparison | semantic table/switcher skeleton not invented; server data decides | no routes shows bounded status unavailable | unknown code uses closed fallback | outcome/reason/eligibility readable | technical claims/gaps stay secondary |
| family brief | persisted server values | not applicable | explicit confirmation disabled reason | family action and trade-off clear | stale decision reloads current brief |
| receipt/timeline | not applicable | impossible by strict phase contract | invalid projection fails closed | durable record reads as a family document | technical identifiers remain absent |
| technical proof | collapsed by default where native `<details>` is appropriate | “尚未创建/Not created” is explicit | bounded unavailable state | approved proof labels/values | keyboard accessible, no hidden required action |

## User Journey and Emotional Arc

| Step | User does | Intended feeling | Plan support |
| --- | --- | --- | --- |
| 1 | opens `/` | oriented in 5 seconds | Chinese promise, synthetic label, one primary route |
| 2 | records family message | safe to speak without silently changing facts | copy states message is communication, not authority |
| 3 | proposes typed budget | sees structure without false automation | pending status and explicit advisor gate |
| 4 | confirms as advisor | understands responsibility | current revision/proposal agreement and explicit action |
| 5 | hands off to planning | feels continuity, not a reset | same Case/fact summary remains visible |
| 6 | starts task | sees controlled automation | explicit action, progress, Skill proof secondary |
| 7 | reviews routes | sees reasons before implementation | outcome/reason/eligibility hierarchy |
| 8 | decides as family | feels agency | server-derived range, trade-off, explicit checkbox |
| 9 | reads receipt/timeline | leaves with a durable plan | editorial record and chronological next steps |

Five-second goal: know what Night Voyager does and where to start. Five-minute goal:
complete the synthetic journey without learning internal state names. Reflective
goal: trust that messages, facts, automation, review, and decision are deliberately
separate authorities.

## Visual Direction

- Classifier: hybrid. Root is a restrained portfolio entry; demo routes are task-
  focused application UI. Root uses a poster-like editorial composition without a
  marketing card grid. Demo routes use calm ledger structure, not decorative cards.
- Visual anchor: one thin route line linking `家庭事实 -> 顾问确认 -> 规划任务 -> 家庭决定`.
  It may reuse CSS rules/pseudo-elements; no icon package or illustration asset.
- Root first viewport: asymmetric 7/5 desktop grid, text/action on the wider column,
  authority route on the narrow column. At 768 px it becomes one reading column; at
  390 px the route line becomes vertical and locale controls remain in the header.
- Demo first viewport: compact outcome block, max heading scale below current 6.8rem,
  current status/reason/action in a two-column desktop composition with one narrow
  context rail. Root display text is bounded by
  `clamp(2.75rem, 6vw, 4.75rem)`; demo display text is bounded by
  `clamp(2.5rem, 5vw, 4.25rem)` and falls to at most `2.75rem` at 390 px.
  Tablet/mobile follow semantic reading order.
- Surfaces earn boundaries: ledger comparison, actionable proposal, family record,
  and technical disclosure may have a surface. Explanatory prose does not receive a
  decorative card.
- Motion is limited to focus/hover transitions and a short CSS reveal where it
  clarifies hierarchy. All transforms/transitions are disabled under
  `prefers-reduced-motion` and no state depends on animation.

## Closed Presentation Surface

The implementation creates:

```typescript
export type PresentationLocaleV1 = "zh-CN" | "en";
export const DEFAULT_PRESENTATION_LOCALE: PresentationLocaleV1 = "zh-CN";
export const PRESENTATION_LOCALE_STORAGE_KEY =
  "night-voyager:presentation-locale:v1" as const;

export type PresentationCopyKey = keyof typeof zhCN;
export const catalog: Record<PresentationLocaleV1, Record<PresentationCopyKey, string>>;

export function resolveStoredLocale(storage: Pick<Storage, "getItem" | "removeItem">): PresentationLocaleV1;
export function presentCode(locale: PresentationLocaleV1, kind: PresentationCodeKind, value: unknown): string;
export function formatCnyMinor(locale: PresentationLocaleV1, minor: unknown, currency: unknown): string;
export function formatCnyRange(locale: PresentationLocaleV1, minimum: unknown, maximum: unknown, currency: unknown): string;
export function formatIsoDate(locale: PresentationLocaleV1, value: unknown): string;
```

Closed code kinds include roles, countries, demo phases, task statuses, route
outcomes, route reasons, dimension labels/outcomes, evidence claims/roles/authority,
known gaps, required claims, trade-offs, decision sources, milestones, collaboration
candidate states, fact keys, recovery categories, and inspector pin/operation labels.
The plan does not assume every backend string is safe presentation input.

Static interface labels and closed enum-like values are localized. Trusted bounded
server-authored content remains data: shared-message bodies, institution/publisher
names, evidence limitations, dates, amounts, versions, and receipt facts are never
machine-translated or rewritten. They wrap in full, preserve source meaning, and sit
beside localized labels. Unknown code-like values use the closed fallback instead of
being mistaken for translatable prose.

Technical-evidence allowlist includes human-readable active Skill key/version,
activation sequence, bounded digest prefixes already exposed by the server,
operation label, adapter label, task attempt, Case revision, fact version, and source
snapshot date. It excludes UUIDs, full hashes, request digests, actor IDs, cookies,
CSRF, raw messages outside the shared thread, raw JSON, SQL, paths, and secrets.

## Responsive and Accessibility Contract

| Width | Root | Demo routes | Navigation and actions |
| --- | --- | --- | --- |
| `>=1280` | 7/5 editorial split, one visual route anchor | ledger/workspace plus narrow context rail | locale inline; one dominant action |
| `768-1279` | single column, horizontal route line may wrap by beat | semantic table retained, context follows outcome | header wraps without hiding locale |
| `<=767` | compact heading, vertical route line | visual table replaced by country switcher; semantic table remains assistive | actions full width where useful, 44 px minimum |
| `390` proof | no clipped CJK or English copy | no horizontal scroll; disclosure and timeline wrap | locale and primary action both visible without overlap |

- `header`, `nav`, `main`, `section`/`article`, `aside`, and `footer` landmarks have
  localized accessible names where needed.
- Skip links are localized and first in tab order.
- Locale control is a two-option labelled group or semantically equivalent control;
  selected state is exposed without color alone.
- Native `<details>/<summary>` is preferred for technical evidence. Required actions
  never live inside a collapsed disclosure.
- Focus moves only after existing consequential state transitions; locale switching
  does not steal focus.
- Status uses restrained text plus semantic color; body and muted contrast satisfy
  WCAG AA. No information depends only on color.
- Chinese and English strings are tested for clipping, long labels, and reflow.
  User-authored and trusted server-authored prose wraps without ellipsis or line
  clamping; internal identifiers remain excluded rather than visually truncated.
- Textual navigation and documentation links expose a non-color-only underline and a
  distinct visited state. Button-like workflow actions keep stable action styling so
  browser history never looks like a business-state transition.

## Dependency and Ownership Map

```text
Task 1 locale/catalog/formatter contract
  -> Task 2 provider/shared shell/root
  -> Task 3 connected demo localization
  -> Task 4 collaboration/inspector localization
  -> Task 5 CSS hierarchy/responsive/a11y
  -> Task 6 bilingual Chromium/screenshots/docs
  -> Task 7 full verification and review handoff
```

Integration-owner files:

- `web/app/layout.tsx`, `web/app/page.tsx`, `web/app/styles.css`
- presentation provider/context and shared shell
- copy catalog and formatters
- Playwright configuration, screenshot assets, design docs, full gates

Optional component lanes may edit only the connected-demo or collaboration-demo
component set after Task 1 freezes interfaces. They may not edit shared catalog,
provider, CSS, tests owned by another lane, or docs.

---

### Task 1: Freeze locale, catalog, code-map, and formatter contracts

**Files:**

- Create: `web/lib/presentation/locales.ts`
- Create: `web/lib/presentation/catalog.ts`
- Create: `web/lib/presentation/codes.ts`
- Create: `web/lib/presentation/format.ts`
- Create: `web/tests/unit/presentation-locales.test.ts`
- Create: `web/tests/unit/presentation-catalog.test.ts`
- Create: `web/tests/unit/presentation-codes.test.ts`
- Create: `web/tests/unit/presentation-format.test.ts`
- Modify: `web/tests/unit/connected-demo-presentation.test.ts`
- Delete after migration is complete: `web/lib/connected-demo/presentation.ts`

- [ ] **Step 1: Write locale RED tests**

  Cover exact accepted values, missing preference, invalid/additive/case-changed
  values, removal, storage exceptions, and default Chinese. Storage errors fail
  closed to Chinese without throwing into the UI.

- [ ] **Step 2: Write catalog parity RED tests**

  Derive `PresentationCopyKey` from one canonical object and use `satisfies` so
  missing/extra English keys fail TypeScript. Runtime tests compare sorted keys,
  require non-empty bounded strings, forbid raw code-as-copy, and check the exact
  Chinese promise.

  ```typescript
  export const en = { /* exact same keys */ } satisfies Record<keyof typeof zhCN, string>;
  ```

- [ ] **Step 3: Write code-map and formatter RED tests**

  Exhaust all values from strict frontend contracts and fixture projections.
  Unknown values return localized fallback and never contain the input. Exact money
  tests use integer minor units, 0-decimal and fractional cases, invalid currency,
  unsafe integers, reversed ranges, and semantic equality across locales.

- [ ] **Step 4: Run RED**

  ```bash
  npm --prefix web run test -- presentation-locales presentation-catalog \
    presentation-codes presentation-format connected-demo-presentation
  npm --prefix web run typecheck
  ```

- [ ] **Step 5: Implement GREEN and remove the old formatter**

  Components are not migrated in this Task; export compatibility wrappers only if
  needed for an intermediate green commit, then delete them before the Task commit.

- [ ] **Step 6: Verify and commit**

  ```bash
  npm --prefix web run test -- presentation-locales presentation-catalog \
    presentation-codes presentation-format connected-demo-presentation
  npm --prefix web run lint
  npm --prefix web run typecheck
  git add web/lib/presentation/locales.ts web/lib/presentation/catalog.ts \
    web/lib/presentation/codes.ts web/lib/presentation/format.ts \
    web/tests/unit/presentation-locales.test.ts \
    web/tests/unit/presentation-catalog.test.ts \
    web/tests/unit/presentation-codes.test.ts \
    web/tests/unit/presentation-format.test.ts \
    web/tests/unit/connected-demo-presentation.test.ts \
    web/lib/connected-demo/presentation.ts
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add closed bilingual presentation contracts"
  ```

---

### Task 2: Add the shared presentation provider, shell, and current root entry

**Files:**

- Create: `web/lib/presentation/context.tsx`
- Create: `web/components/presentation/PresentationShell.tsx`
- Create: `web/components/presentation/LocaleSwitch.tsx`
- Create: `web/components/presentation/PortfolioEntry.tsx`
- Modify: `web/app/layout.tsx`
- Modify: `web/app/page.tsx`
- Create: `web/tests/unit/presentation-provider.test.tsx`
- Create: `web/tests/unit/presentation-shell.test.tsx`
- Create: `web/tests/unit/portfolio-entry.test.tsx`
- Modify: `web/e2e/bootstrap.spec.ts`

**Provider contract:**

- Initial state is `zh-CN` on server and client render.
- After mount, one bounded effect reads local storage; valid `en` updates catalog,
  `document.documentElement.lang`, and localized document title/description without
  remounting children.
- `setLocale()` writes only the locale key. It does not invoke any demo API or
  navigation. Storage failure leaves current presentation usable.

- [ ] **Step 1: Write provider/shell RED tests**

  Assert Chinese SSR, `html[lang]`, explicit switch labels/selected state, valid
  persistence/reload, invalid cleanup, no hydration error, stable child identity,
  and zero network/business callbacks.

- [ ] **Step 2: Write root RED tests**

  Assert current Chinese promise, synthetic boundary, primary complete-flow link to
  `/demo/collaboration`, secondary focused link to `/demo`, English parity, no stale
  M0 statement, no fake metric, no API/session call, and meaningful landmarks.

- [ ] **Step 3: Implement shared shell and root**

  `RootLayout` renders `<html lang="zh-CN">` and Chinese-default metadata, wraps
  `body` in `PresentationProvider`, and does not use browser-language negotiation.
  The shared shell owns header/footer/skip link slots; route components provide the
  localized context and main ID.

- [ ] **Step 4: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- presentation-provider presentation-shell \
    portfolio-entry bootstrap
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  git add web/lib/presentation/context.tsx \
    web/components/presentation/PresentationShell.tsx \
    web/components/presentation/LocaleSwitch.tsx \
    web/components/presentation/PortfolioEntry.tsx \
    web/app/layout.tsx web/app/page.tsx \
    web/tests/unit/presentation-provider.test.tsx \
    web/tests/unit/presentation-shell.test.tsx \
    web/tests/unit/portfolio-entry.test.tsx web/e2e/bootstrap.spec.ts
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add the Chinese-first portfolio shell"
  ```

---

### Task 3: Localize and reorder the advisor-family workflow

**Files:**

- Modify: `web/components/connected-demo/ConnectedDemo.tsx`
- Modify: `web/components/connected-demo/AdvisorLedger.tsx`
- Modify: `web/components/connected-demo/TaskProgress.tsx`
- Modify: `web/components/connected-demo/RecoveryNotice.tsx`
- Modify: `web/components/connected-demo/FamilyDecisionBrief.tsx`
- Modify: `web/components/connected-demo/DecisionReceiptTimeline.tsx`
- Modify: `web/components/connected-demo/EvidenceDisclosure.tsx`
- Modify: `web/components/connected-demo/CurrentConfirmedFacts.tsx`
- Modify: `web/components/demo-session/JourneyConflictNotice.tsx`
- Modify: `web/tests/unit/connected-demo-ui.test.tsx`
- Modify: `web/tests/unit/connected-demo-recovery.test.tsx`
- Modify: `web/tests/unit/connected-demo-inspector.test.tsx`

**Hierarchy:**

- First: current stage/outcome, current Case revision, and one next action.
- Second: route outcome/reason/eligibility and current confirmed family fact.
- Third: task trail, Evidence claims, Skill/adapter/digests in technical disclosure.
- Family phase: decision range/trade-off/action before provenance; final phase:
  receipt summary then chronological timeline.

- [ ] **Step 1: Write component RED in both locales**

  Cover every demo phase, loading/busy/terminal/recovery state, route table and mobile
  switcher, no-route fallback, long copy, family confirmation, receipt, timeline,
  journey conflict, and technical disclosure. Assert raw phase/status/public/error/
  claim codes do not appear in primary text.

- [ ] **Step 2: Prove locale isolation**

  Mount a live hook fixture, switch locale, and assert task/review/decision call
  counts, idempotency records, EventSource URL/count, stored journey envelope, and
  reducer state remain unchanged.

- [ ] **Step 3: Implement localized components**

  Consume presentation context and closed maps. Do not use dynamic object indexing
  on unvalidated server strings. Keep semantic table and family form labels.

- [ ] **Step 4: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- connected-demo-ui connected-demo-recovery \
    connected-demo-inspector connected-demo-presentation
  npm --prefix web run lint
  npm --prefix web run typecheck
  git add web/components/connected-demo/ConnectedDemo.tsx \
    web/components/connected-demo/AdvisorLedger.tsx \
    web/components/connected-demo/TaskProgress.tsx \
    web/components/connected-demo/RecoveryNotice.tsx \
    web/components/connected-demo/FamilyDecisionBrief.tsx \
    web/components/connected-demo/DecisionReceiptTimeline.tsx \
    web/components/connected-demo/EvidenceDisclosure.tsx \
    web/components/connected-demo/CurrentConfirmedFacts.tsx \
    web/components/demo-session/JourneyConflictNotice.tsx \
    web/tests/unit/connected-demo-ui.test.tsx \
    web/tests/unit/connected-demo-recovery.test.tsx \
    web/tests/unit/connected-demo-inspector.test.tsx
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: localize the advisor-family journey"
  ```

---

### Task 4: Localize collaboration, confirmed facts, and Skill proof

**Files:**

- Modify: `web/components/collaboration-demo/CollaborationDemo.tsx`
- Modify: `web/components/collaboration-demo/SharedThread.tsx`
- Modify: `web/components/collaboration-demo/MemoryCandidateCard.tsx`
- Modify: `web/components/collaboration-demo/ConfirmedFactSummary.tsx`
- Modify: `web/components/collaboration-demo/CollaborationRecoveryNotice.tsx`
- Modify: `web/components/skill-inspector/PlanningSkillInspector.tsx`
- Modify: `web/tests/unit/collaboration-demo.test.tsx`
- Modify: `web/tests/unit/collaboration-recovery.test.tsx`
- Modify: `web/tests/unit/planning-skill-inspector.test.tsx`
- Modify: `web/tests/unit/use-collaboration-demo.test.tsx`

**Hierarchy:**

- State message/proposal/confirmation/revision/planning-start as distinct human
  gates in plain language.
- Keep actual shared-message body visible as user content, but localize role/meta
  labels and never translate or alter server-authored content.
- Budget proposal and confirmed fact show formatted range, public state, fact version,
  and Case revision. Internal candidate/fact/actor IDs remain absent.
- Skill inspector becomes one localized technical disclosure and remains secondary.

- [ ] **Step 1: Write RED in both locales and unknown-code cases**

  Cover empty thread, busy mutations, all candidate states, all seven recovery
  categories, handoff validation, confirmed fact, inspector statuses/operations,
  unknown/additive values, and absence of raw codes.

- [ ] **Step 2: Prove locale switch causes no recovery or mutation**

  Assert no extra bootstrap/mint/revoke, append/propose/confirm, handoff reads,
  storage replacement, retry action, or navigation.

- [ ] **Step 3: Implement and run GREEN**

  ```bash
  npm --prefix web run test -- collaboration-demo collaboration-recovery \
    planning-skill-inspector use-collaboration-demo presentation-codes
  npm --prefix web run lint
  npm --prefix web run typecheck
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add web/components/collaboration-demo/CollaborationDemo.tsx \
    web/components/collaboration-demo/SharedThread.tsx \
    web/components/collaboration-demo/MemoryCandidateCard.tsx \
    web/components/collaboration-demo/ConfirmedFactSummary.tsx \
    web/components/collaboration-demo/CollaborationRecoveryNotice.tsx \
    web/components/skill-inspector/PlanningSkillInspector.tsx \
    web/tests/unit/collaboration-demo.test.tsx \
    web/tests/unit/collaboration-recovery.test.tsx \
    web/tests/unit/planning-skill-inspector.test.tsx \
    web/tests/unit/use-collaboration-demo.test.tsx
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: localize governed collaboration proof"
  ```

---

### Task 5: Refine hierarchy, responsive composition, and accessibility

**Files:**

- Modify: `web/app/styles.css`
- Create: `web/tests/unit/presentation-accessibility.test.tsx`
- Modify: `web/tests/unit/presentation-shell.test.tsx`
- Modify: `web/tests/unit/connected-demo-ui.test.tsx`
- Modify: `web/tests/unit/collaboration-demo.test.tsx`
- Modify: `web/e2e/fact-to-plan.spec.ts`

**CSS token evolution:**

- Keep existing color token values unless contrast proof requires a documented minor
  adjustment. Add named typography/measure/layout tokens rather than scattered magic
  values.
- Reduce demo H1 to a bounded scale that does not consume most of a 900 px desktop
  viewport. Use max reading widths for Chinese and English.
- Add route-line, outcome block, context rail, technical disclosure, and portfolio
  entry classes. Reuse them across routes instead of route-specific visual forks.
- Remove decorative borders where proximity/whitespace already groups content.
- Preserve native controls and obvious click affordances; do not hide actions behind
  hover or disclosure.

- [ ] **Step 1: Add RED structure/a11y tests**

  Assert landmarks, skip links, locale group labelling, selected state, focus-visible
  class/token contract, native disclosure, one H1, heading order, no placeholder-only
  labels, visible/visited textual-link treatment, full wrapping without line clamp,
  and primary action outside technical details.

- [ ] **Step 2: Add responsive browser RED**

  At 1440/768/390, inspect bounding boxes for header locale/action overlap, first-
  viewport outcome/reason/action visibility, minimum action target, technical
  disclosure access, and `scrollWidth === clientWidth`. Test both locales and long
  English labels.

- [ ] **Step 3: Implement CSS and run GREEN**

  ```bash
  npm --prefix web run test -- presentation-accessibility presentation-shell \
    connected-demo-ui collaboration-demo
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  ```

- [ ] **Step 4: Run GStack live `design-review` against the real pages**

  Review `/`, `/demo/collaboration`, advisor review, family review, and final receipt
  at desktop/tablet/mobile. Fix actionable hierarchy, typography, spacing, clipping,
  focus, contrast, and AI-slop findings in this Task. Do not use the review to expand
  product scope.

- [ ] **Step 5: Commit**

  ```bash
  git add web/app/styles.css web/tests/unit/presentation-accessibility.test.tsx \
    web/tests/unit/presentation-shell.test.tsx \
    web/tests/unit/connected-demo-ui.test.tsx \
    web/tests/unit/collaboration-demo.test.tsx web/e2e/fact-to-plan.spec.ts
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "style: refine the portfolio decision journey"
  ```

---

### Task 6: Capture bilingual Chromium evidence and govern documentation

**Files:**

- Create: `docs/assets/night-voyager-portfolio-entry.png`
- Modify: `docs/assets/m5-advisor-ledger.png`
- Modify: `docs/assets/m5-family-receipt-timeline.png`
- Modify: `docs/assets/collaboration-confirmed-fact.png`
- Modify: `web/e2e/fact-to-plan.spec.ts`
- Modify: `web/e2e/connected-demo.spec.ts`
- Modify: `web/e2e/collaboration-demo.spec.ts`
- Modify: `web/playwright.compose.config.ts`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DESIGN.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/operations/connected-demo.md`
- Modify: `docs/operations/collaboration-walkthrough.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/route-map.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `docs/superpowers/specs/2026-07-22-governed-fact-to-plan-closure-design.md`
- Modify: `docs/superpowers/plans/2026-07-22-chinese-first-portfolio-presentation.md`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `tests/unit/test_release_surface.py`

**Browser evidence:**

- Default Chinese screenshots from the real deterministic flow:
  1. current root portfolio entry;
  2. advisor outcome/review state;
  3. family receipt/timeline;
  4. collaboration confirmed fact/handoff.
- English runs the same states and selectors but need not duplicate public image files.
- Screenshot assertions reject browser chrome, raw codes/JSON/UUIDs, private paths,
  secrets, clipped text, overflow, stale M0 copy, and unsupported claims.

- [ ] **Step 1: Add screenshot/documentation RED**

  Bind exact required assets, dimensions, Chinese headings, root routing, locale
  contract, design tokens, plan status, and immutable historical release hashes.

- [ ] **Step 2: Run real Chromium in both locales**

  Use the existing Compose-mounted `/workspace/docs/assets` path. Reset only the
  task-owned synthetic project between full locale flows when required. Never
  manufacture screenshot state with query parameters or frontend-only fixtures.

- [ ] **Step 3: Inspect every image at original resolution**

  Manually verify hierarchy, copy fit, visual rhythm, alignment, contrast, focus
  evidence where applicable, no IDs/codes/chrome, and truthful synthetic boundaries.
  Record exact dimensions and SHA-256 in the handoff, not as permanent identity.

- [ ] **Step 4: Run GStack `document-release`**

  Audit README entry, design explanation, operations guidance, screenshot
  discoverability, route/state/projection matrices, and current plan status. Use
  `document-generate` only for a concrete missing document.

- [ ] **Step 5: Update docs and run GREEN**

  ```bash
  uv run pytest -q tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  uv run python scripts/verify_release.py --tree-mode development
  git diff --check
  ```

- [ ] **Step 6: Commit**

  Stage every listed file explicitly, inspect the staged file set, then:

  ```bash
  git diff --cached --check
  git commit -m "docs: publish the bilingual portfolio evidence"
  ```

---

### Task 7: Run full verification and prepare authority review

**Files:** None expected.

- [ ] **Step 1: Preflight and frontend gates**

  ```bash
  git status --short
  make doctor MODE=dev
  uv lock --check
  npm --prefix web ci
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  ```

- [ ] **Step 2: Full repository proof**

  ```bash
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  ```

  Run one clean Chinese-default full flow and one English full-flow assertion against
  the same authority contracts. Confirm final task-owned Compose resources are gone
  and retained/unrelated resources are untouched.

- [ ] **Step 3: Final visual and diff review**

  ```bash
  BASE=$(git merge-base HEAD origin/main)
  git diff --check "$BASE"..HEAD
  git diff --stat "$BASE"..HEAD
  uv run python scripts/verify_release.py --tree-mode development
  git status --short
  ```

  Review all changed code and screenshots. Confirm no backend, migration, API/BFF,
  dependency, lockfile, version, release, DRA/MKE, provider, or deployment diff.

- [ ] **Step 4: Handoff**

  Keep a clean local branch/worktree for independent authority review. Report exact
  base/HEAD, commits, RED -> GREEN, locale-isolation call counts, responsive/a11y
  proof, screenshot dimensions/hashes and manual review, `design-review` findings,
  documentation audit, Docker inventory, and remaining release/deployment boundary.
  Do not push or create a PR without separate authorization.

## Acceptance Checklist

- [ ] Chinese is the deterministic SSR/default presentation; English is explicit and
  persistent.
- [ ] Locale storage is isolated from every business/session/transport authority.
- [ ] Catalog keys and dynamic code maps are closed and parity-tested.
- [ ] Unknown values never render raw input.
- [ ] Root `/` is current, truthful, and routes to both real demo paths.
- [ ] First viewport communicates outcome/purpose, reason, and next action before
  technical proof.
- [ ] All business actions, request bodies, idempotency, SSE, recovery, and database
  effects are unchanged by locale.
- [ ] Desktop/tablet/390 px, keyboard, landmarks, contrast, reduced motion, touch
  targets, and overflow are proven in both locales.
- [ ] Four current Chinese Chromium screenshots are generated and manually inspected.
- [ ] Design and documentation governance are updated without rewriting release
  history.

## Not in Scope

- Additional locales, browser-language detection, simultaneous bilingual sentences,
  repository-doc translation, or persisted localized domain values.
- New design/i18n/font/icon/component dependency, generic dashboard redesign, or
  unsupported marketing content.
- Backend/API/BFF/migration/task/worker/provider changes.
- Public deployment, live-provider proof, real-user claims, version bump, tag, or
  release.

## Implementation Tasks

The build-actionable tasks are the seven Tasks above. No additional design debt is
deferred from this plan; visual QA after implementation is part of Task 5, not a
future TODO.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | NOT RUN | Product scope was approved before this implementation-plan review. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | NOT RUN | No separate outside-model review was requested. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | NOT RUN | Normal engineering authority review remains part of the pre-implementation gate. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | Score: 8/10 -> 9/10; five decisions added after auditing three current Chromium baselines. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT RUN | No new developer-facing workflow is introduced by PR 3. |

**VERDICT:** DESIGN CLEARED — the plan is design-complete; normal engineering authority review remains required before implementation.

NO UNRESOLVED DECISIONS
