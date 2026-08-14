# Night Voyager Design System

## Product context

Night Voyager is an evidence-grounded study-abroad decision workflow. The current `/` route is a static, Chinese-first, local synthetic, provider-free portfolio entry. Its primary action begins the complete governed walkthrough at `/demo/collaboration`; that route proves governed parent proposal, advisor confirmation, confirmed fact, and Case revision authority before a read-only same-Case handoff continues into `/demo`. The advisor-centered route-analysis and downstream client-confirmation surface at `/demo` remains independently usable: it creates the durable planning task, follows authorized SSE, records advisor review, rotates to a parent session, and produces a persisted `DecisionReceipt` and `TimelinePlan`. Both demo routes render a server-owned planning Skill projection. The M1 Japan fixture remains historical design context only. The previous cosmic root and family-heavy route presentation are historical presentation context; the current reference-driven advisor workspace is presentation-only and locally verified on the local synthetic candidate. Stable release `v0.1.5` remains unchanged, with no release, deployment, provider, or production-use claim.

The current visual authority is the [reference-driven presentation spec](docs/superpowers/specs/2026-08-14-reference-driven-presentation.md) and [implementation plan](docs/superpowers/plans/2026-08-14-reference-driven-presentation.md). The public root projects `¥300,000–400,000`; the persisted connected outcome remains `¥305,500–400,000`; `/demo/plan` is an independently seeded scenario.

- **Portfolio entry:** `/` (complete-flow primary action to `/demo/collaboration`, route-evidence secondary action to `#route-atlas`)
- **Complete governed walkthrough:** `/demo/collaboration` -> read-only same-Case handoff -> explicit task action on `/demo`
- **Advisor route-analysis and client-confirmation surface:** `/demo`
- **Governed plan-execution route:** `/demo/plan` (`happy` by default; exact
  `blocked` query scenario)
- **Implemented presentation direction:** reference-driven Midnight Editorial Advisor Workspace for study-abroad advisors; locally verified
- **Audience:** study-abroad organizations and advisor teams first; students and parents are client participants
- **Page boundary:** root presentation has zero product-side network/session/task effects; demo routes use local synthetic data and real backend mutations/SSE only; no remote provider or real student data
- **Memorable idea:** evidence gaps and human decisions become a traceable family brief and timeline

## Aesthetic direction

The previous visual layers are historical presentation context:

1. **Historical root `/` — Virtual Night Voyage:** deep navy, ivory, and champagne framed a cinematic voyage backdrop, route atlas, and student-first decision trajectory. Its generated AVIF/WebP runtime assets are not the approved direction.
2. **Historical demo routes — warm-paper ledger:** `/demo`,
   `/demo/collaboration`, and `/demo/plan` retain the existing warm reading
   surfaces, advisor ledger, family decision documents, restrained rules, and
   semantic status accents.

The current direction is the **Midnight Editorial Advisor Workspace**: one dark
product frame, warm decision surface, advisor-first hierarchy, a closed
five-stage display projection, and progressive technical disclosure. It is
implemented across `/`, `/demo/collaboration`, `/demo`, and `/demo/plan` without
changing their server-owned authority.

The product must feel calm, accountable, and readable; it should not resemble a generic chat product, KPI dashboard, or infrastructure control tower.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `canvas` | `#F7F3EA` | Page background |
| `surface` | `#FFFDF8` | Primary reading surface |
| `ink` | `#17211F` | Body and heading text |
| `muted` | `#5F6B66` | Secondary copy |
| `trust` | `#0F5C55` | Approved state and primary action |
| `attention` | `#C96855` | Human-decision emphasis |
| `warning` | `#9A6500` | Evidence gaps and conditional state |
| `danger` | `#A33A32` | Blocked state |
| `border` | `#D9D4C8` | Rules and boundaries |

Body text uses `ink` on `canvas` or `surface`. Muted text is reserved for secondary content and must retain at least 4.5:1 contrast on its rendered background.

## Typography

- **Chinese UI and labels:** local CJK stack headed by `"PingFang SC"`, then `"Hiragino Sans GB"`, `"Microsoft YaHei"`, and system sans fallbacks.
- **English UI and labels:** IBM Plex Sans intent, rendered with safe local fallbacks: `"IBM Plex Sans", "Aptos", "Segoe UI", sans-serif`.
- **Family/editorial headings:** local CJK serif intent for Chinese and Source Serif 4 intent for English, both with dependency-free system fallbacks.
- **Body:** at least `16px`, with a comfortable `1.6` line height.
- **Data:** UI stack with tabular numerals enabled.

No remote font or font package is required.

## Spacing and shape

- Base unit: `4px`; common steps: `8`, `12`, `16`, `24`, `32`, `48`, `64`.
- Reading surfaces use restrained `2px`, `6px`, and `12px` radii; avoid uniform bubbly cards.
- Borders carry ledger structure. Shadows are subtle and never encode status.
- Touch targets are at least `44px` in both dimensions.

## Responsive layout

- **Approved audit widths:** `1440`, `1280`, `1024`, `768`, `390`, and `320` CSS pixels in both `zh-CN` and `en`, with reduced motion, 200% zoom, material fallback, and no dense-data blur.
- **Historical root desktop/mobile:** the former voyage composition and crop are retained only as historical evidence; no current claim depends on them.
- **Desktop (`>=1280px`):** advisor ledger uses a main comparison surface with a narrow decision rail. Family frames remain linear and editorial.
- **Intermediate (`1024–1279px`):** compact horizontal workflow strip with a two-column workspace and semantic comparison preserved.
- **Tablet (`768–1023px`):** one-column reading order with a readable five-stage horizontal workflow strip and semantic comparison preserved.
- **Mobile (`<=767px`):** the desktop table is visually replaced by a country switcher and dimension-by-dimension comparison. The semantic table remains available to assistive technology.

## Lifecycle and interaction contract

The first screen contains exactly one current lifecycle stage, one required human decision, and one primary action. The connected lifecycle projects `task_ready`, `active_task`, `review_required`, `revision_requested`, `revision_fact_pending`, `replan_required`, `revision_task_active`, `revision_review_required`, `revision_blocked`, `family_review`, `plan_ready`, or `terminal_task_failure` from the backend. Consequential actions expose disabled reasons and confirmation summaries; `plan_ready` retains a visible receipt and timeline. Same-tab recovery uses opaque-cookie bootstrap plus a closed V3 advisor-family `sessionStorage` envelope and fails closed when that metadata is missing or inconsistent.

The current walkthrough uses the canonical synthetic Australia Case and backend-owned route, budget, trade-off, role, task, review, and currentness facts. M1 Japan material is not current runtime authority. Technical lease and adapter detail remains secondary disclosure even though the UI follows the durable task through authorized SSE.

The DRA strict-consumer prerequisite is provider-free backend authority only. It
adds migration `0011` and a closed v1/v2 import boundary for the existing
candidate endpoint, but no browser route, visual state, task operation, or
automatic promotion. Strict live acceptance remains incomplete.

Presentation locale is a separate, dependency-free layer shared by `/`, `/demo`, and `/demo/collaboration`. SSR, missing, invalid, and storage-failure states resolve to exact `zh-CN`; exact `en` is selected explicitly and persisted only at `night-voyager:presentation-locale:v1`. Locale changes update copy and `html[lang]` while preserving mounted children, the journey envelope, requests, idempotency, EventSource URL/count, task state, and navigation.

PR A and PR B are released in `v0.1.2`: PR A adds the governed-collaboration backend
contract, while PR B adds the versioned Skill catalog, deterministic evaluation,
owner-controlled activation/rollback, persisted planning-revision materialization, and
five-field task/execution pins. PR C implements the task-free `/demo/collaboration` route,
closed browser reducer, and shared read-only inspector from the frozen role-safe HTTP
projections. It adds no backend authority, migration, task operation, polling, or
EventSource. The existing task-owning `/demo` lifecycle remains the advisor route-analysis
and client-confirmation flow
and preserves one SSE connection. Catalog-only Skills are never presented as executing
capabilities merely because they have versions or passing evaluations.

Fact-to-plan PRs #57–#59, the high-end root PR #60, and route presentation polish PR #61 are released in `v0.1.3`. This presentation surface owns only the route-specific shell, closed copy/data additions, responsive imagery, route atlas, continuous journey, accessibility proof, and refreshed root screenshot. It adds no backend, BFF, task, worker, provider, or deployment authority.

The v0.1.4 planning revision journey keeps the same editorial hierarchy while
adding a controlled student preferred-country editor, retained predecessor context,
deterministic old/new comparison, renewed advisor review, and current-revision family
decision. `revision_blocked` keeps the comparison visible but exposes no approval or
family-decision action. This remains controlled provider-free evidence rather than
strict live acceptance.

The v0.1.5 local synthetic portfolio release adds a governed plan-execution
surface using the same dark product frame and warm decision surface with a stricter action hierarchy: current milestone, state,
due date, accountable role, risk, and next handoff precede the one available
action. The immutable four-step plan remains visible, technical activity is a
secondary disclosure, accepted transitions move focus to the current-action
heading, and one polite live region announces terminal or waiting changes.
Presentation locale and responsive layout never alter PostgreSQL, HTTP, BFF,
receipt-then-GET, recovery, role, or reassessment authority.

The historical internal-demo presentation layer used a shared, display-only
decision journey. The implemented replacement uses one closed, display-only workflow
projection on `/demo/collaboration`, `/demo`, and `/demo/plan`:
`咨询接入 -> 信息核验 -> 方案研判 -> 客户确认 -> 执行跟进`. Unknown values render
no stage. The replacement owns no fetch, mutation, storage, session, or authority
responsibility. Each route keeps its existing primary action, business content,
raw server-owned message/reason/limitation, and technical evidence disclosure.
The collaboration authority path remains six exact technical facts, but is now
an accessible native disclosure after the message, candidate, and confirmed-fact
business content rather than a competing first-layer process strip. Known
recoverable or role-switching states retain only the existing resume/prior stage
as a read-only projection; unknown state still renders no journey. Desktop uses a
horizontal journey and mobile uses a vertical journey; the root portfolio uses the
same product-frame tokens and a coded static preview while remaining side-effect-free.

## Accessibility

- Provide a skip link and semantic `header`, `nav`, `main`, `section`, and `footer` landmarks.
- Use a semantic comparison table and labelled country switcher.
- Maintain keyboard-visible focus and minimum `44px` targets.
- Respect `prefers-reduced-motion`.
- Do not create a drawer or sheet; focus-return behavior is therefore not applicable.

## Prohibited patterns

No KPI strip, match percentage, three colored country cards, generic control-tower panel, chat-first navigation, automatic approval, or family dashboard.

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-12 | Freeze Advisor Ledger × Global Journey for M1 | Keeps evidence and human authority primary while making the family handoff editorial and legible. |
| 2026-07-12 | Use local/system font fallbacks | Preserves the typography intent without adding dependencies or remote runtime requirements. |
| 2026-07-14 | Connect the M5 Australia walkthrough | Preserves backend authority while proving the advisor-to-parent flow in real Chromium. |
| 2026-07-17 | Keep PR A collaboration backend-only | Freezes conversation, candidate, and confirmed-fact authority without prebuilding the deferred PR C interface. |
| 2026-07-18 | Keep PR B Skill governance backend-only | Pins checked-in runtime compatibility to durable tasks while leaving the deferred PR C inspector as a server-projected consumer. |
| 2026-07-20 | Add PR C as a secondary governed walkthrough | Proves collaboration authority and a read-only Skill projection while preserving `/demo`, backend ownership, and the no-task boundary. |
| 2026-07-22 | Make the portfolio presentation Chinese-first | Adds an exact `zh-CN`/`en` presentation-only layer and outcome-first root while preserving the same server authority and warm-paper direction. |
| 2026-07-23 | Split the root from the governed demo visual layer | Gives `/` the Virtual Night Voyage entry while preserving the warm-paper ledger and every existing authority boundary on both demo routes. |
| 2026-07-28 | Extend the connected ledger with a revision journey | Preserves backend phase/role authority while presenting the retained predecessor, deterministic comparison, fresh advisor authorization, and a fail-closed blocked counterfactual. |
| 2026-08-09 | Add a shared internal-demo decision journey | Helps a first-time visitor understand role, result, boundary, action, route trade-offs, and next steps before opening existing technical evidence; it changes no business authority or route contract. |
| 2026-08-09 | Approve the advisor-centered workspace redesign | Replaces the historical cosmic root/family-heavy presentation with one advisor-first shell and five-stage display projection; this row records the approved direction before the subsequent implementation and verification record. |
| 2026-08-10 | Verify the advisor-centered workspace redesign | Local deterministic Compose and real-Chromium evidence verify the implemented four-route, bilingual presentation matrix and the nine declared review captures; domain authority, stable release `v0.1.5`, and non-production boundaries remain unchanged. |
| 2026-08-14 | Implement and verify the reference-driven presentation | The shared frame, root story, three demo routes, six-width browser matrix, material fallback, bilingual Compose proof, and nine approved captures are locally verified; the change remains presentation-only and release-neutral. |
