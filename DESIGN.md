# Night Voyager Design System

## Product context

Night Voyager is an evidence-grounded study-abroad decision workflow. The M5 `/demo` route is now a connected local synthetic application: it creates a durable planning task, follows authorized SSE, records advisor review, rotates to a parent session, and produces a persisted `DecisionReceipt` and `TimelinePlan`. The M1 Japan fixture remains historical design context only.

- **Primary route:** `/demo`
- **Audience:** advisors first, then students and families
- **Page boundary:** local synthetic data and real backend mutations/SSE only; no remote provider or real student data
- **Memorable idea:** evidence gaps and human decisions become a traceable family brief and timeline

## Aesthetic direction

- **Direction:** Advisor Ledger × Global Journey
- **Decoration:** intentional, restrained rules and route-line motifs
- **Layout:** a ledger-like advisor frame followed by a linear editorial family story
- **Color:** balanced neutrals with scarce semantic accents
- **Motion:** minimal-functional; the page must remain complete with motion disabled

The system should feel calm, accountable, and readable. It must not resemble a generic chat product, a KPI dashboard, or an infrastructure control tower.

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

- **UI and labels:** IBM Plex Sans intent, rendered with safe local fallbacks: `"IBM Plex Sans", "Aptos", "Segoe UI", sans-serif`.
- **Family/editorial headings:** Source Serif 4 intent, rendered with safe local fallbacks: `"Source Serif 4", "Iowan Old Style", "Palatino Linotype", serif`.
- **Body:** at least `16px`, with a comfortable `1.6` line height.
- **Data:** UI stack with tabular numerals enabled.

No remote font or font package is required.

## Spacing and shape

- Base unit: `4px`; common steps: `8`, `12`, `16`, `24`, `32`, `48`, `64`.
- Reading surfaces use restrained `2px`, `6px`, and `12px` radii; avoid uniform bubbly cards.
- Borders carry ledger structure. Shadows are subtle and never encode status.
- Touch targets are at least `44px` in both dimensions.

## Responsive layout

- **Desktop (`>=1280px`):** advisor ledger uses a main comparison surface with a narrow decision rail. Family frames remain linear and editorial.
- **Intermediate (`768–1279px`):** one-column reading order with the semantic table preserved.
- **Mobile (`<=767px`):** the desktop table is visually replaced by a country switcher and dimension-by-dimension comparison. The semantic table remains available to assistive technology.

## Lifecycle and interaction contract

The first screen contains exactly one current lifecycle stage, one required human decision, and one primary action. The connected lifecycle projects `task-ready`, `active-task`, `review-required`, `family-review`, `plan-ready`, or `terminal-task-failure` from the backend. Consequential actions expose disabled reasons and confirmation summaries; `plan-ready` retains a visible receipt and timeline. Same-tab recovery uses opaque-cookie bootstrap plus session-bound `sessionStorage` metadata and fails closed when that metadata is missing or inconsistent.

The current walkthrough uses the canonical synthetic Australia Case and backend-owned route, budget, trade-off, role, task, review, and currentness facts. M1 Japan material is not current runtime authority. Technical lease and adapter detail remains secondary disclosure even though the UI follows the durable task through authorized SSE.

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
