
# Night Voyager Advisor-Centered Product Experience Redesign

## Status

Implemented and locally verified on the local synthetic candidate. The stable
release remains `v0.1.5`; this closeout records no release, deployment, provider,
adoption, real-user, or production-use claim.

The implementation candidate verified for this redesign is
`010802c65f356f0914fe0c6eec62c443f59cb343`. The fresh local verification record
includes the full Vitest suite (`38` files, `422` tests), frontend lint, typecheck,
production build, architecture/documentation governance tests, the successful
`scripts/verify_compose.sh` presentation lane (`71/71`), the complete normal and
blocked deterministic Compose proof, and one GStack `design-review` over all four
routes in normal and blocked states. The nine current screenshot assets are real
coded Chromium captures and remain review evidence rather than product authority.

This document defines one bounded presentation and interaction redesign for the
existing Night Voyager local synthetic portfolio product. It supersedes the current
split between a cinematic student-facing root and warm-paper family-heavy demo
routes. It does not change product authority, domain contracts, backend behavior,
synthetic fixture results, or public maturity claims.

## Product correction

Night Voyager is an AI collaboration workspace for study-abroad advisors. The
advisor is the primary operator. Students and parents are client participants who
provide information, review a proposal, and confirm consequential personal
trade-offs. The Agent assists with information organization, evidence research,
route comparison, drafting, state tracking, and recovery; it does not approve its
own work or decide for a client.

The existing implementation correctly preserves `AdvisorReview`,
`FamilyDecision`, `DecisionReceipt`, and `TimelinePlan` as separate authority
boundaries. The current presentation incorrectly elevates the family-facing gate
into the product's top-level identity. This redesign keeps the domain boundary and
changes the information architecture:

```text
Buyer / deployer: study-abroad organization or advisor team
Primary operator: advisor
Client participants: student and parent
AI role: organize, research, compare, draft, track, and explain
Authority: advisor confirms professional judgment; client confirms personal choice
```

Top-level product language must therefore describe an advisor workspace, not a
family self-service dashboard.

## Problem

### The product identity changes after the first click

The root route currently presents a deep-navy cinematic voyage poster, while the
three demo routes present a sparse warm-paper ledger. Both surfaces can be read in
isolation, but they do not feel like the same product. The root creates an
atmospheric expectation that the application does not continue.

### The current hierarchy follows contracts instead of advisor work

Headings such as “家庭表达”, “家庭决定”, “当前决策阶段”, and technical labels
such as `authority`, `Case revision`, and `Skill pin` receive excessive visual
weight. They are valid domain or engineering concepts, but they do not answer the
advisor's first questions:

1. Which client Case am I handling?
2. What changed?
3. What needs my judgment now?
4. What evidence supports the proposed route?
5. What should happen next?

### Tables and controls do not express the real decision

The existing route table is semantically correct but visually flat. Outcome,
evidence sufficiency, trade-off, and review eligibility compete as equal columns.
Actions use system language rather than the business result of the action. The
current layouts therefore resemble an internal proof ledger rather than a deliberate
advisor product.

### Engineering evidence competes with the product story

The implementation has strong evidence, state, role, recovery, and durable-task
boundaries. Showing all of them at the same visual level makes the interface harder
to understand and weakens their credibility. Technical evidence should be
progressively disclosed after the advisor can understand the current client work.

## Goals

1. Make “AI collaboration workspace for study-abroad advisors” unmistakable in the
   first viewport of `/` and every demo route.
2. Unify `/`, `/demo/collaboration`, `/demo`, and `/demo/plan` under one continuous
   product identity while preserving the truthful scenario boundary between the
   same-Case fact-to-plan proof and the separately seeded execution proof.
3. Organize the visible workflow around advisor work:
   `consultation intake -> client fact review -> route analysis -> client
   confirmation -> execution follow-up`.
4. Keep the existing student, parent, advisor, Agent, API, PostgreSQL, task, and
   human-gate authority unchanged.
5. Give each state one current outcome, one responsible role, and at most one
   primary action.
6. Make normal, waiting, blocked, recoverable, and completed states visually and
   semantically distinct without turning the product into an infrastructure console.
7. Show route trade-offs and evidence sufficiency before implementation identifiers
   or internal status codes.
8. Use only actual coded interfaces and the repository's deterministic synthetic
   fixture for screenshots and previews. Do not generate fictitious product screens,
   people, institutions, users, outcomes, or metrics.
9. Preserve the exact root side-effect boundary and every existing demo request,
   mutation, idempotency, SSE, session, and persistence behavior.
10. Produce a credible flagship surface for reproducible documentation screenshots
    and a concise public demo walkthrough.

## Non-goals

- No new backend capability, API route, DTO, domain state, migration, table, RLS
  policy, worker operation, task transition, SSE event, or provider integration.
- No new multi-Case list, CRM, team inbox, notification center, billing, public
  registration, organization settings, or production tenancy operation.
- No complete chat assistant, long-term autonomous companion, voice interface,
  attachment upload, or third-party message gateway.
- No change to the canonical Australia/Japan/Malaysia fixture, budget values,
  evidence, route results, server-owned message bodies, advisor reasons, or
  limitations.
- No automatic evidence promotion, advisor approval, client choice, or timeline
  execution.
- No new framework, package, icon set, animation library, font download, image
  generator, or lockfile change.
- No real student, institution coverage, admission result, accuracy, productivity,
  ROI, production, enterprise-adoption, SLA, or deployment claim.
- No tag, GitHub Release, package publication, provider call, or deployment.

## Product language

### Role hierarchy

The first-layer vocabulary is:

| Product concept | First-layer Chinese | First-layer English |
|---|---|---|
| product category | 留学顾问 AI 协作工作台 | AI collaboration workspace for study-abroad advisors |
| Case | 客户档案 | client case |
| conversation input | 咨询记录 | consultation record |
| candidate fact | 待确认信息 | proposed client fact |
| confirmed fact | 已确认客户信息 | confirmed client fact |
| planning run | 方案研判 | route analysis |
| advisor review | 顾问审核 | advisor review |
| family-facing brief | 客户方案 | client proposal |
| family decision | 客户确认 | client confirmation |
| timeline plan | 申请与准备计划 | application and preparation plan |
| checkpoint | 执行节点 | execution checkpoint |
| recoverable error | 可以继续处理 | recoverable state |
| blocked | 当前受阻 | blocked |

Exact domain and technical terms remain visible in the technical evidence layer.
`FamilyDecision`, `DecisionReceipt`, `Case revision`, `Fact version`, `Skill pin`,
`AgentTask`, and `checkpoint` must not be renamed in code, API contracts, or exact
technical disclosure.

### Workflow stages

The presentation-only workflow stage keys become:

```ts
export const WORKFLOW_STAGES = [
  "consultation_intake",
  "client_fact_review",
  "route_analysis",
  "client_confirmation",
  "execution_followup",
] as const;
```

Their visible Chinese labels are exactly:

```text
咨询接入 -> 信息核验 -> 方案研判 -> 客户确认 -> 执行跟进
```

These stages are a closed display projection of existing UI state. Unknown values
render no invented stage. They own no fetch, mutation, storage, session, role, task,
or authority behavior.

### Primary public copy

Chinese metadata:

```text
Title: Night Voyager｜留学顾问的 AI 协作工作台
Description: 把分散在聊天、资料和研究中的信息，整理成可核对、可沟通、可推进的留学方案。
```

Chinese root hero:

```text
Eyebrow: AI 协作工作台 · 为留学顾问设计
Title: 把零散咨询，整理成可以推进的留学方案
Summary: Night Voyager 帮助顾问整理客户信息、核对证据、比较留学路线并推进后续计划。AI 负责研究与草拟，关键判断仍由顾问确认。
Primary action: 查看一次完整咨询流程
Secondary action: 了解方案如何被核对
```

English metadata and hero:

```text
Title: Night Voyager | AI Collaboration Workspace for Study-Abroad Advisors
Description: Turn fragmented conversations, evidence, and route research into a reviewable client plan.
Eyebrow: AI collaboration workspace for study-abroad advisors
Title: Turn scattered consultations into a client plan you can move forward
Summary: Night Voyager helps advisors organize client facts, review evidence, compare study routes, and carry the decision into execution. AI researches and drafts; the advisor keeps professional judgment.
Primary action: Walk through one client case
Secondary action: See how the proposal is verified
```

## Information architecture

### Root `/`

The root is no longer a separate cinematic microsite. It uses the same dark product
frame and warm decision surface as the workspace.

The desktop page has five ordered sections:

1. **Advisor-first hero** — product category, human-readable value, two actions, and
   one coded read-only workspace preview using the canonical synthetic fixture.
2. **One advisor workflow, two deterministic proof segments** — consultation intake,
   information review, route analysis, client confirmation, and execution follow-up
   shown as one connected product model rather than feature cards. The first segment
   carries one Case from `/demo/collaboration` through `/demo` to the receipt and
   `TimelinePlan`; `/demo/plan` is a separately seeded execution scenario and must be
   labelled as such rather than presented as the same Case.
3. **Current route analysis** — Australia, Japan, and Malaysia shown as ordered
   alternatives with outcome, trade-off, evidence sufficiency, and unresolved gap.
4. **How AI and the advisor divide responsibility** — organize/research/draft/track
   on the Agent side; confirm/communicate/approve consequential actions on the
   advisor/client side.
5. **Engineering evidence** — one concise technical disclosure linking the product
   story to Evidence, deterministic gates, human review, durable task state, receipt,
   and recovery. It remains below the business story.

The root remains static and side-effect-free. Its preview is a real React component
using presentation-owned copies of the existing deterministic fixture. It performs
no API request, cookie operation, session bootstrap, storage write, task operation,
SSE subscription, or mutation.

The preview uses one typed presentation projection for route outcome, evidence
sufficiency, unresolved gap, and next action. Tests bind that projection to the
current deterministic public contract so the preview cannot drift into a plausible
but fictitious Case.

### Demo workspace shell

All three demo routes use one shared advisor workspace shell:

```text
dark product frame
  -> compact product header
  -> Case context bar
  -> workflow rail
  -> current work canvas
  -> decision/evidence rail
  -> technical evidence disclosure
```

The Case context bar contains only existing or presentation-owned facts:

- visible synthetic-demo boundary;
- current workflow stage;
- active role;
- current state or outcome;
- next responsible participant when already present in the projection.
- a visible separate-scenario label on `/demo/plan`; it must not imply that the
  connected-demo Case or session was carried into execution.

It must not invent a student name, advisor name, institution, team, timestamp,
completion percentage, or service-level status.

Desktop uses a narrow workflow rail, a dominant work canvas, and a restrained
decision/evidence rail. Intermediate widths use one main column plus a compact stage
strip. Mobile uses the same semantic order in one column. The layout must not become
a generic three-column analytics dashboard.

### `/demo/collaboration`

This route is presented as consultation intake and client-information review:

1. consultation record;
2. proposed client fact;
3. advisor confirmation requirement;
4. confirmed client fact and Case revision;
5. handoff into route analysis.

The parent remains the exact actor for the existing message and proposal actions,
but first-layer headings use “客户” or “咨询” where the exact parent role is not the
point. Exact role and source remain visible beside the relevant message or action.

### `/demo`

This route is presented as the advisor's route-analysis and proposal-review surface:

- the current question and recommended next action come first;
- Australia, Japan, and Malaysia are displayed as ordered route rows, not three
  marketing cards and not a dense equal-weight table;
- each route exposes outcome, business reason, review eligibility, accepted
  evidence, and unresolved gap;
- revision comparison shows what changed and why a new advisor review is required;
- client confirmation is visually a downstream handoff, not the product identity;
- receipt and timeline become the durable result of a confirmed client choice.

The semantic comparison table remains available to assistive technology. The visual
surface may use ordered route rows or a focused route detail panel.

### `/demo/plan`

This route is presented as execution follow-up using the existing independently
seeded Happy or Blocked synthetic scenario. It shares the five-stage workflow model
and visual shell with the other routes, but it is not a same-Case continuation from
`/demo` and must not claim that it is.

The route shows:

- current checkpoint, accountable participant, due date, risk, and next handoff;
- exactly one primary action for the active role;
- immutable approved plan as contextual reference;
- blocked and overdue states preserve the last confirmed progress and expose one
  bounded reassessment path;
- technical activity remains a secondary disclosure.

The role switcher is explicitly labelled as demo perspective control. It must not
look like an end-user permission-management feature.

## Action language

The visible Chinese actions use business outcomes rather than implementation verbs:

| Existing intent | Required first-layer action |
|---|---|
| add the canonical parent message | 记录这条客户信息 |
| create the typed proposal | 提交顾问核验 |
| switch to advisor | 进入顾问核验 |
| confirm the candidate fact | 确认并写入客户档案 |
| continue to planning | 基于最新信息研判方案 |
| create a planning task | 开始方案研判 |
| approve a planning result | 确认这版方案可与客户沟通 |
| request revision | 退回并说明需要补充的内容 |
| confirm preferred countries | 确认客户最新意向 |
| confirm the family route | 确认选择澳大利亚方案 |
| start timeline execution | 开始执行计划 |
| record progress | 保存当前进度 |
| submit completion | 提交顾问复核 |
| record blocked | 标记阻塞并保留进度 |
| advisor verifies checkpoint | 确认节点完成 |
| advisor requests update | 退回补充材料 |
| request reassessment | 重新评估后续计划 |

Each state exposes at most one filled primary action. Secondary, corrective, and
exit actions use outline or text treatment. Destructive or stop actions use the
warning/danger semantic layer and cannot visually compete with the normal primary
path.

## Visual system

### Aesthetic

The approved direction is **Midnight Editorial Advisor Workspace**:

- product frame: deep ink, quiet, precise, and adult;
- working surface: warm ivory and white, similar to a carefully prepared advisory
  document rather than a paper ledger;
- brand motif: one restrained route line, coordinate, or star mark;
- primary visual content: the real coded product interface;
- no generated cosmic hero, stock campus photography, portrait, glassmorphism,
  gradient CTA, KPI strip, bubbly card grid, or generic AI orb.

The Night Voyager name remains emotional without borrowing copyrighted imagery,
lyrics, cover art, animation frames, or franchise language.

### Tokens

```css
:root {
  --nv-frame: #081113;
  --nv-frame-soft: #101b1d;
  --nv-canvas: #f2ede3;
  --nv-surface: #fffdf8;
  --nv-ink: #14201e;
  --nv-muted: #5b6762;
  --nv-trust: #0d655c;
  --nv-trust-soft: #dcece7;
  --nv-attention: #b8503f;
  --nv-warning: #93630a;
  --nv-danger: #9f372f;
  --nv-border: #d8d1c4;
  --nv-frame-border: #263537;
  --nv-highlight: #c7aa69;
  --nv-focus: #18a99a;
}
```

Gold is a rare navigation highlight, not a text color or luxury gradient. Trust,
warning, and danger always retain semantic meaning.

### Typography and shape

- Chinese interface: existing local CJK sans stack.
- English interface: existing local sans stack.
- Editorial emphasis may use the existing local serif fallback only for short
  product statements, not for form labels, tables, buttons, or dense Chinese body.
- Base body is at least `16px` with `1.55` line height.
- Main workspace headings use a controlled `clamp(2rem, 4vw, 4.5rem)` only where
  content density supports it; routine state headings remain `1.5–2rem`.
- Borders define document hierarchy. Shadows are subtle and never encode state.
- Radii use `0`, `4`, `8`, and at most `12px`; no uniform rounded-card system.
- Visible interactive targets remain at least `44px` in both dimensions.

### Motion

- Motion communicates stage continuity, changed content, or disclosure.
- Normal transitions remain between `120ms` and `280ms`.
- No parallax, looping stars, animated gradient, cursor-following light, or page-load
  spectacle.
- `prefers-reduced-motion: reduce` removes non-essential transition and animation.

## Agent engineering translated into product experience

The interface must reflect the following engineering principles without turning
them into marketing jargon:

1. **Context sufficiency** — the current Case, confirmed constraints, workflow stage,
   and unresolved gaps remain visible near the action that depends on them.
2. **Tool and authority separation** — research and drafting results are visibly
   proposals until deterministic gates and required human review succeed.
3. **Human intervention** — advisor review and client confirmation are first-class
   states, not generic confirmation modals.
4. **Explicit runtime state** — running, waiting, blocked, recoverable, reassessment,
   and completed states have stable, human-readable presentations.
5. **Role transition with continuity** — the same Case continues across student,
   parent, and advisor views in `/demo/collaboration` and `/demo` while each role sees
   only its available action. `/demo/plan` retains its separate deterministic
   scenario identity.
6. **Verification and correction** — evidence gaps, requested revisions, blocked
   checkpoints, and recovery are preserved instead of being hidden behind a success
   narrative.

## Accessibility and responsive contract

- Keep semantic `header`, `nav`, `main`, `aside`, `section`, `footer`, table, list,
  form, button, `details`, and live-region behavior.
- Keep exactly one visible `h1` per route and a valid heading hierarchy.
- Preserve keyboard order, focus return after accepted transitions, visible focus,
  native disclosure operation, and at least `44px` controls.
- Preserve exact `zh-CN` default/fail-closed behavior and explicit `en` selection.
- Verify `/`, `/demo/collaboration`, `/demo`, and `/demo/plan` at `1440`, `1024`,
  `768`, `390`, and `320` CSS pixels in both locales, including reduced motion and
  200% zoom.
- No horizontal overflow, clipped long copy, hidden primary action, or color-only
  state communication.
- Root and demos must remain legible without motion, images, or a specific font.

## Code and asset boundaries

Expected presentation changes include:

```text
DESIGN.md
docs/design/demo-storyboard.md
docs/design/route-map.md
docs/design/state-and-interaction-matrix.md
docs/superpowers/specs/2026-08-09-advisor-centered-product-experience.md
docs/superpowers/plans/2026-08-09-advisor-centered-product-experience.md
web/app/layout.tsx
web/app/styles.css
web/app/portfolio.css                         # new
web/app/workspace.css                         # new
web/components/presentation/PortfolioEntry.tsx
web/components/presentation/PortfolioShell.tsx
web/components/presentation/AdvisorWorkspacePreview.tsx   # new
web/components/presentation/AdvisorWorkspaceShell.tsx     # new
web/components/presentation/WorkflowRail.tsx               # new
web/components/collaboration-demo/*.tsx       # presentation only
web/components/connected-demo/*.tsx           # presentation only
web/components/plan-execution/*.tsx           # presentation only
web/lib/presentation/catalog.ts
web/lib/presentation/journey.ts
web/tests/unit/*presentation*.test.tsx
web/tests/unit/*demo*.test.tsx
web/tests/unit/*execution*.test.tsx
web/e2e/portfolio-design-review.spec.ts
web/e2e/presentation.spec.ts
docs/assets/*.png                             # refreshed real captures only
```

The obsolete generated root backdrop and its dedicated presentation components may
be removed only after the new root is implemented, its references are zero, and the
deletion is included in the approved implementation mandate:

```text
web/components/presentation/PortfolioBackdrop.tsx
web/components/presentation/PortfolioJourney.tsx
web/components/presentation/PortfolioRouteAtlas.tsx
web/components/presentation/DecisionJourney.tsx
web/components/presentation/PresentationShell.tsx
web/tests/unit/portfolio-journey.test.tsx
web/tests/unit/portfolio-route-atlas.test.tsx
web/public/portfolio/night-voyager-voyage-960.avif
web/public/portfolio/night-voyager-voyage-960.webp
web/public/portfolio/night-voyager-voyage-1680.avif
web/public/portfolio/night-voyager-voyage-1680.webp
```

Do not remove historical release records or tracked historical screenshots. New
screenshots replace only the current presentation entry points explicitly named by
the implementation plan.

## Acceptance criteria

### Product comprehension

- In the first viewport, `zh-CN` explicitly identifies the product as a workspace
  for study-abroad advisors.
- The first visible product preview contains current Case context, advisor work,
  route analysis, and one next action without a fictitious person or institution.
- “家庭表达”, “家庭决定”, and “顾问到家庭决策流程” are absent from top-level
  navigation, route context, workflow-stage labels, and root copy.
- Exact parent/family terms remain where they identify the real actor or domain
  authority.
- A first-time reviewer can follow consultation intake through execution follow-up
  without opening technical disclosure.
- The same-Case boundary ends at the connected receipt and `TimelinePlan` proof;
  `/demo/plan` is visibly identified as a separate deterministic execution scenario.

### Behavior preservation

- Root performs zero product-side requests, mutations, storage writes, session
  operations, or SSE connections.
- Existing collaboration, planning, review, revision, client confirmation, receipt,
  timeline, execution, blocked, reassessment, recovery, and role-switch behavior is
  byte-for-byte equivalent at API/BFF boundaries.
- Server-owned messages, reasons, evidence limitations, route results, budgets, and
  ids are not rewritten into new business facts.
- No navigation, workflow rail, README, screenshot, or context bar claims that the
  connected-demo Case or session continues into `/demo/plan`.
- Unknown presentation state still fails closed.
- Locale switching does not remount the task-owning children or duplicate requests,
  idempotency keys, EventSource connections, or mutations.

### Visual quality

- Root and all demo routes visibly share one product shell, palette, type hierarchy,
  action system, workflow rail, and evidence disclosure pattern.
- No generated hero image is required for the composition to work.
- The dominant content on demo routes is the advisor's current work, not a giant
  heading, empty canvas, technical ledger, or generic dashboard.
- One filled primary action appears at most once per state.
- Normal and blocked workflows both remain understandable in screenshots without
  relying on animation.

### Verification

- Focused unit and E2E RED tests are recorded before implementation.
- Frontend lint, typecheck, full Vitest suite, production build, presentation
  accessibility matrix, and relevant architecture tests pass on the implementation
  candidate.
- A task-owned Compose run passes the same-Case collaboration-to-receipt lane, the
  separate plan-execution Happy/Blocked lanes, and the exact 58-cell presentation
  audit or an intentionally updated equivalent that retains the same
  route/locale/width/motion/zoom coverage.
- Real Chromium checks normal and blocked routes, keyboard navigation, 200% zoom,
  console errors, favicon, responsive overflow, and current screenshots.
- GStack `design-review` runs once on the completed implementation and all accepted
  same-scope findings are closed before authority review.
- No dependency, lockfile, backend, API, migration, fixture, provider, release, or
  deployment change enters the diff.

## Delivery shape

Use one coherent pull request. The root, shared shell, workflow vocabulary, and demo
routes share the same visual tokens, copy catalog, responsive rules, and browser
proof. Splitting them would publish an incoherent intermediate product and duplicate
the presentation audit.

The implementation branch carries this design and its implementation plan as
preparatory commits. A separate docs-only pull request is not required.
