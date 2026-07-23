# Night Voyager Design System

## Product context

Night Voyager is an evidence-grounded study-abroad decision workflow. The current `/` route is a static, Chinese-first, local synthetic, provider-free portfolio entry. Its primary action begins the complete governed walkthrough at `/demo/collaboration`; that route proves governed parent proposal, advisor confirmation, confirmed fact, and Case revision authority before a read-only same-Case handoff continues into `/demo`. The focused advisor-family/evidence route at `/demo` remains independently usable: it creates the durable planning task, follows authorized SSE, records advisor review, rotates to a parent session, and produces a persisted `DecisionReceipt` and `TimelinePlan`. Both demo routes render a server-owned planning Skill projection. The M1 Japan fixture remains historical design context only.

- **Portfolio entry:** `/` (complete-flow primary action to `/demo/collaboration`, route-evidence secondary action to `#route-atlas`)
- **Complete governed walkthrough:** `/demo/collaboration` -> read-only same-Case handoff -> explicit task action on `/demo`
- **Focused advisor-family/evidence route:** `/demo`
- **Audience:** advisors first, then students and families
- **Page boundary:** root presentation has zero product-side network/session/task effects; demo routes use local synthetic data and real backend mutations/SSE only; no remote provider or real student data
- **Memorable idea:** evidence gaps and human decisions become a traceable family brief and timeline

## Aesthetic direction

Night Voyager intentionally has two visual layers:

1. **Root `/` — Virtual Night Voyage:** deep navy, ivory, and champagne frame a cinematic but legible voyage backdrop, an evidence-bearing route atlas, and one continuous student-first decision trajectory. Responsive AVIF/WebP files are runtime assets; the source PNG is provenance only.
2. **Governed demo routes — warm-paper ledger:** `/demo` and `/demo/collaboration` retain the existing advisor ledger, family decision documents, restrained rules, and semantic status accents.

The root may feel atmospheric; the governed application must feel calm, accountable, and readable. Neither layer should resemble a generic chat product, KPI dashboard, or infrastructure control tower.

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

- **Root desktop (`1440 × 1000`):** thesis and origin remain primary while the full route atlas exposes recommendation, reserve, and current exclusion.
- **Root tablet (`768 × 1024`):** the route atlas becomes a compact ordered summary without changing meaning.
- **Root mobile (`390 × 844` and `320 × 720`):** actions stack, route evidence stays in document order, and no content depends on the cinematic crop or motion.
- **Desktop (`>=1280px`):** advisor ledger uses a main comparison surface with a narrow decision rail. Family frames remain linear and editorial.
- **Intermediate (`768–1279px`):** one-column reading order with the semantic table preserved.
- **Mobile (`<=767px`):** the desktop table is visually replaced by a country switcher and dimension-by-dimension comparison. The semantic table remains available to assistive technology.

## Lifecycle and interaction contract

The first screen contains exactly one current lifecycle stage, one required human decision, and one primary action. The connected lifecycle projects `task-ready`, `active-task`, `review-required`, `family-review`, `plan-ready`, or `terminal-task-failure` from the backend. Consequential actions expose disabled reasons and confirmation summaries; `plan-ready` retains a visible receipt and timeline. Same-tab recovery uses opaque-cookie bootstrap plus session-bound `sessionStorage` metadata and fails closed when that metadata is missing or inconsistent.

The current walkthrough uses the canonical synthetic Australia Case and backend-owned route, budget, trade-off, role, task, review, and currentness facts. M1 Japan material is not current runtime authority. Technical lease and adapter detail remains secondary disclosure even though the UI follows the durable task through authorized SSE.

Presentation locale is a separate, dependency-free layer shared by `/`, `/demo`, and `/demo/collaboration`. SSR, missing, invalid, and storage-failure states resolve to exact `zh-CN`; exact `en` is selected explicitly and persisted only at `night-voyager:presentation-locale:v1`. Locale changes update copy and `html[lang]` while preserving mounted children, the journey envelope, requests, idempotency, EventSource URL/count, task state, and navigation.

PR A and PR B are released in `v0.1.2`: PR A adds the governed-collaboration backend
contract, while PR B adds the versioned Skill catalog, deterministic evaluation,
owner-controlled activation/rollback, persisted planning-revision materialization, and
five-field task/execution pins. PR C implements the task-free `/demo/collaboration` route,
closed browser reducer, and shared read-only inspector from the frozen role-safe HTTP
projections. It adds no backend authority, migration, task operation, polling, or
EventSource. The existing task-owning `/demo` lifecycle remains the advisor-family flow
and preserves one SSE connection. Catalog-only Skills are never presented as executing
capabilities merely because they have versions or passing evaluations.

Fact-to-plan PRs #57–#59, the high-end root PR #60, and route presentation polish PR #61 are released in `v0.1.3`. This presentation surface owns only the route-specific shell, closed copy/data additions, responsive imagery, route atlas, continuous journey, accessibility proof, and refreshed root screenshot. It adds no backend, BFF, task, worker, provider, or deployment authority.

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
