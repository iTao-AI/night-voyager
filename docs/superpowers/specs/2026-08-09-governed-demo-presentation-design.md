# Governed Demo Presentation Surface

**Status:** Approved for implementation

## Summary

Night Voyager already exposes three locally runnable governed demonstrations:
family collaboration and fact confirmation at `/demo/collaboration`, the
advisor-to-family decision flow at `/demo`, and plan execution at `/demo/plan`.
This design aligns their presentation layer around one visible decision journey
without changing the business workflow, server authority, or synthetic data.

The presentation layer is responsible for helping a first-time visitor answer,
in order: what stage is active, who is accountable, what outcome is visible,
what boundary supports it, what one action is available, and where the stage
sits in the journey. Detailed route, fact, evidence, task, receipt, timeline,
and execution material follows that orientation. Engineering evidence remains
available as a secondary disclosure.

## Scope

### Goals

- Share one five-stage visual journey across the three demo routes:
  `family_input`, `advisor_confirmation`, `route_review`, `family_decision`,
  and `plan_execution`.
- Map only existing UI state to the closed journey stages; unknown or additive
  values fail closed and never become visible raw state.
- Keep the first-screen hierarchy consistent: current stage and role, user-
  understandable result, basis or boundary, one primary action, journey,
  business content, and technical evidence disclosure.
- Preserve the warm-paper ledger identity, trust/warning/danger semantics,
  focus movement, live regions, disabled reasons, reduced-motion behavior, and
  minimum 44px interaction targets.
- Keep Chinese business vocabulary primary while retaining exact technical
  terms in secondary disclosure where they are useful for verification.
- Preserve server-owned message bodies, advisor reasons, and evidence
  limitations byte-for-byte; presentation may add a label or visual hierarchy
  only.
- Add a dependency-free local `icon.svg` and two reproducible public-safe
  screenshots for advisor route comparison and family receipt/timeline states.

### Non-goals

This presentation change does not modify the API, BFF, domain policy, database,
migrations, RLS, sessions, CSRF, idempotency, durable tasks, SSE, workers,
Evidence authority, provider adapters, Skill runtime, fixtures, package
versions, Compose topology, release records, or the portfolio home page's core
visuals and CTA. It does not add a dependency, font, icon library, i18n layer,
role selector, automatic approval, production claim, or live-provider path.

## Presentation contract

### Closed journey

The shared component accepts only this union:

```ts
type JourneyStage =
  | "family_input"
  | "advisor_confirmation"
  | "route_review"
  | "family_decision"
  | "plan_execution";
```

The component is presentational only. It does not fetch, mutate, access
storage/cookies/session/database/task state, switch roles, or infer authority.
Its current stage is supplied by a route-local mapping from existing UI state.
An unknown state returns no stage and renders no fabricated journey position.

### Shared journey copy

The five visible business labels are, in Chinese, `家庭表达`、`顾问确认`、
`路线比较`、`家庭决定`、`行动计划`; English keeps natural equivalents. The
catalogs must have exact key parity and every visible value must remain bounded
and non-empty.

The journey is a display projection, not a second lifecycle. Existing route
states remain the sole source of truth for current stage, role, action enabled
state, disabled explanation, focus target, live-region announcement, and
navigation.

### Evidence hierarchy

The route-specific content follows the shared orientation. Business copy uses
natural Chinese terms such as `结构化事实提案`、`档案版本`、`事实版本`、
`规划能力版本` and `行动节点`. Exact contract names such as `typed proposal`,
`Case revision`, `Fact version`, `Skill pin`, and `checkpoint` remain in the
technical disclosure when needed. Server-owned raw content is labelled as
`消息原文` or `顾问确认原文` without rewriting it.

## Responsive and accessibility contract

- Desktop uses a horizontal five-stage journey; mobile uses a vertical ordered
  journey without changing meaning.
- The three routes remain usable at 1440, 768, 390, and 320 CSS pixels with no
  horizontal overflow.
- Focus-visible styling, one polite live region where the existing route has
  one, disabled conditions, semantic headings/landmarks, and 44px targets are
  preserved.
- `prefers-reduced-motion: reduce` disables the journey transition and keeps
  the existing no-motion behavior.
- Engineering evidence is a native disclosure and does not compete with the
  primary action.

## Acceptance evidence

The change is accepted only when unit tests prove the closed journey and
catalog/authority boundaries, existing route tests remain green, the required
lint/typecheck/test/build and repository checks pass, and real Chromium covers
the normal and blocked/reassessment flows at desktop and mobile sizes. At
least two tracked public-safe screenshots must be generated from the
deterministic flow and inspected for hierarchy, contrast, focus, target size,
reduced motion, and overflow. Screenshots supplement rather than replace
semantic assertions.
