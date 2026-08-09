# Governed Demo Presentation Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` as the primary
> execution controller. Follow RED → GREEN for behavioral changes and run fresh
> verification before any completion claim.

**Goal:** Align `/demo/collaboration`, `/demo`, and `/demo/plan` around a
shared five-stage presentation journey while preserving every existing business
authority and deterministic synthetic flow.

**Architecture:** Add a pure `DecisionJourney` display component and route-local
closed mappings from existing reducer/UI state to `JourneyStage`. Route shells
continue to own their current hooks and mutation callbacks. Catalog additions,
labels, CSS, and favicon are presentation-only. No backend, BFF, session,
database, task, SSE, or dependency surface changes are allowed.

**Plan status:** Implementation and local authority verification complete.
Publication status is tracked by repository history and GitHub rather than this
execution plan.

## Constraints

- Work only from the current repository HEAD and the existing task worktree.
- Do not create or use a child agent, remote transport, approval escalation,
  GitHub operation, push, PR, merge, tag, release, deploy, or cleanup.
- Do not modify the home page's core visual or CTA, synthetic fixtures, package
  versions, lockfiles, Compose topology, or business authority.
- The shared component accepts only the closed `JourneyStage` union and has no
  fetch, mutation, storage, cookie, session, database, task, or role-switch
  behavior.
- Unknown route state maps to no journey stage; do not expose raw state.
- Server-owned message bodies, advisor reasons, and evidence limitations are
  rendered byte-for-byte with additive presentation labels only.
- Use exact tracked paths and keep commits semantic: one docs/spec commit,
  followed by one or a small number of implementation commits after verification.

## Work items

### 1. Land the public-neutral contract

- [x] Add this plan and the matching presentation design spec.
- [x] Keep the design index discoverable without task identity or execution
      metadata.
- [x] Review the exact docs diff and commit it separately before code changes.

### 2. Freeze the RED contract

- [x] Add tests for the five closed journey stages and the horizontal/vertical
      semantic order.
- [x] Add tests for each route's existing UI-state mapping, including unknown
      fail-closed behavior.
- [x] Add Chinese/English catalog key parity and natural business vocabulary
      assertions, with exact technical terms confined to disclosure assertions.
- [x] Add byte-for-byte tests for a server message body, advisor reason, and
      evidence limitation.
- [x] Add static boundary assertions that `DecisionJourney` has no fetch,
      mutation, storage, cookie, API, session, database, task, or role-switch
      surface.
- [x] Run the focused tests and record an expected RED failure caused by the
      missing implementation.

### 3. Implement the shared journey and route mapping

- [x] Add `web/components/presentation/DecisionJourney.tsx` with the closed
      `JourneyStage` type and pure display props.
- [x] Add a presentation mapping module for collaboration, connected, and plan
      execution states; unknown values return `null`.
- [x] Render the journey in all three routes without changing existing action
      callbacks, disabled conditions, focus behavior, or live regions.
- [x] Reorder the route shells so stage/role, outcome, boundary, primary action,
      journey, business content, and technical disclosure read in that order.

### 4. Refine bilingual presentation and visual system

- [x] Add natural bilingual journey/authority-label catalog keys with exact key
      parity.
- [x] Add additive labels for `消息原文`, `顾问确认原文`, and technical
      disclosure; preserve server-owned strings exactly.
- [x] Add the dependency-free `web/app/icon.svg`.
- [x] Add restrained desktop horizontal and mobile vertical journey CSS, shared
      internal spacing/rhythm, focus/contrast/target/reduced-motion rules, and
      no-overflow behavior without touching the home-page visual layer.
- [x] Update the storyboard, state/interaction matrix, and internal-demo rules
      in `DESIGN.md` to describe the presentation-only contract.

### 5. Verify the real deterministic flow

- [x] Run `npm --prefix web run lint`.
- [x] Run `npm --prefix web run typecheck`.
- [x] Run `npm --prefix web run test`.
- [x] Run `npm --prefix web run build`.
- [x] Run `make check` and the repository public-hygiene, diff, dependency,
      and route-contract checks available in the current checkout.
- [x] In one task-owned Compose project, replay normal collaboration, same-Case
      planning, advisor review, family receipt/timeline, plan happy, and plan
      blocked/reassessment safe-stop paths.
- [x] Use real Chromium at 1440/768/390/320, including focus, reduced motion,
      44px targets, contrast, and overflow checks.
- [x] Generate and inspect the tracked advisor route-comparison and family
      receipt/timeline screenshots.
- [x] Run the GStack `design-review` visual QA and fix only in-scope findings.

### 6. Close locally and hand off

- [x] Run `superpowers:verification-before-completion` with fresh evidence,
      review the exact final diff, and confirm no backend or local-only paths changed.
- [x] Commit the implementation after the docs commit; if commit or branch
      metadata is blocked, preserve the exact diff and report the one mechanical
      authority bridge.
- [x] Preserve this worktree and branch for authority review. No push, PR,
      merge, tag, release, deploy, or cleanup is performed.

## Completion record

The final handoff must report the exact base/head/tree/worktree, commits and
changed-file summary, RED and GREEN evidence, actual verification commands and
results, screenshot paths and browser QA outcome, remaining risk or blocked
external gate, a mini-retro seed, the next gate of authority full branch-diff
review, and the absence of push/PR/merge/cleanup.

## Authority verification record

- Fresh `make check` completed successfully, including backend, frontend,
  architecture, database, dependency, release, and public-hygiene gates.
- A fresh task-owned Compose proof completed successfully and removed its
  containers, network, volume, and local images. It included the existing
  normal, blocked, recovery, restart, bilingual, browser, and database paths.
- The provider-free presentation matrix ran exactly 58 real Chromium tests
  across four routes, two locales, four widths, reduced motion, 200% zoom, and
  the normal and blocked journeys.
- GStack Browser rechecked the three live routes at desktop, tablet, and mobile
  sizes. No console error, horizontal overflow, undersized visible target, or
  new high/medium design finding remained.
- The final authority diff review found no backend, API, schema, migration,
  package, lockfile, synthetic-fixture, or business-authority change.
