# Night Voyager Governed Fact-to-Plan Closure Design

## Status

Implemented and released in `v0.1.3`. PR 1 is merged through PR #57 at
`a85190deb6261ec034979334bd3d953a3cf9d8d4`. PR 2 is merged through PR #58 at
`e7612c7adfd478dda3644706bffb4aed1f2c5b34`. PR 3 is merged through PR #59.

This document defines the next bounded Night Voyager product increment after the
`v0.1.2` Governed Collaboration Core release. Approval of this design authorizes
the design record and subsequent implementation planning. It does not by itself
authorize implementation, push, pull request creation, merge, tag, release,
deployment, live-provider execution, or cleanup of unrelated resources.

PR 1 adds migration `0009`
and the explicit planning-start authority without changing the public HTTP schema.
PR 2 composes that authority into the local same-Case browser walkthrough without a
new backend or BFF route. PR 3 adds the Chinese-first presentation without changing
that authority. All three are released in `v0.1.3`; deployment and live-provider
execution remain separate and unperformed.

## Summary

Night Voyager already proves two complementary local synthetic workflows:

- `/demo/collaboration` proves that a participant message is not Case authority,
  that a typed `MemoryCandidate` remains pending, and that assigned-advisor
  confirmation atomically creates a `ConfirmedFact` plus a new Case revision;
- `/demo` proves explicit planning-task creation, exact Skill runtime pinning,
  durable worker execution, SSE recovery, advisor review, family decision,
  `DecisionReceipt`, and `TimelinePlan` persistence.

The workflows are intentionally separate in `v0.1.2`. The collaboration route
stops at `replan_required`; it does not create an `AgentTask`. Its current link to
the primary demo does not continue the same Case authority. The primary demo starts
or recovers its own seeded Case.

This increment closes that product gap without adding a provider dependency. After
the advisor confirms a fact, the same advisor explicitly hands the same Case to the
existing planning workflow. The destination route re-reads all task inputs from
server authority, creates a deterministic `generate_planning_run_v1` task against
the new Case revision, persists the exact active Skill pin, streams durable events,
and completes the existing advisor-to-family decision path.

The increment also closes a presentation gap in the public portfolio surface. The
current visual system is coherent, but the browser walkthrough reads primarily as
an English technical proof: oversized English headings consume the first viewport,
internal lifecycle terms and Evidence keys compete with the user outcome, and the
next human action appears later than the product value. The final presentation keeps
the existing warm-paper visual identity while making Simplified Chinese the default,
retaining an explicit English switch, front-loading the current decision and next
action, and moving exact technical proof into secondary disclosure.

The increment preserves three distinct human gates:

1. a participant explicitly proposes a typed fact;
2. an assigned advisor explicitly confirms that fact;
3. an assigned advisor explicitly starts planning against the resulting revision.

No message, candidate, confirmation response, browser transition, model, or external
system may combine or bypass those gates.

## Inspected baseline

- The inspected repository baseline is clean
  `main@cf071f792dbf39d9fcea986e7dc1f37073c50c39`, equal to `origin/main`.
- Annotated tag and public GitHub Release `v0.1.2` identify the current local
  synthetic portfolio release, and its public source-archive verification passed.
- The migration graph is exactly `0001 -> ... -> 0008`, with `0008` as head.
- `0007` owns governed collaboration, immutable messages and candidates,
  advisor verification, confirmed-fact provenance, and atomic Case revision
  publication.
- `0008` owns versioned Skill governance, deterministic evaluation, activation,
  rollback, exact task/execution pins, and the hardened task-creation function.
- `app.verify_memory_candidate(...)` accepts only `intake` or supported `planning`
  Cases. A successful confirmation creates revision `N+1`, invalidates any current
  PlanningRun, and deliberately does not create a task or advance Case state.
- The primary collaboration fixture starts in `intake`. After successful
  confirmation it therefore remains in `intake` at the new revision.
- `app.create_agent_task(...)` currently requires the Case to already be in
  `planning`. Calling the existing task endpoint directly after collaboration would
  fail with the stale-input boundary even though the new revision is authoritative.
- `POST /api/v1/cases/{case_id}/agent-tasks` already requires an opaque advisor
  session, exact Origin, CSRF, `Idempotency-Key`, strict request shape, exact Case
  revision, exact source-pack version, `m3a-policy-v1`, and an active compatible
  SkillVersion.
- `generate_planning_run_v1` uses the checked-in deterministic planning adapter and
  persisted source pack. It does not call DRA, MKE, a remote model, or any live
  provider.
- `GET /api/v1/cases/{case_id}/advisor-ledger` already projects the current Case
  revision, canonical task inputs, task state, PlanningRun, routes, Evidence,
  review inputs, and current brief state.
- The existing Next.js BFF exposes explicit task, SSE, advisor-review,
  current-brief, family-decision, collaboration, confirmed-fact, and Skill-inspector
  routes. No catch-all handler is required for this increment.
- The same-tab demo session store already has strict `schema_version=2`
  discriminated envelopes for `collaboration` and `advisor-family` journeys.
- `/demo/collaboration` currently stops after authoritative fact/revision reload and
  tells the user that planning must be started explicitly elsewhere.
- The root `/` route still presents the historical M0 bootstrap message and states
  that product decision workflows are not implemented. That page is stale relative
  to the released v0.1.2 browser product and is a misleading first evaluator entry.
- `DESIGN.md` already defines the coherent `Advisor Ledger × Global Journey`
  warm-paper visual system. The current demo implementation is English-only and
  gives large hero copy and technical state labels more prominence than the product
  outcome and next human decision.

## Problem

### The product story stops before the confirmed fact is consumed

The current collaboration walkthrough proves memory authority but not business use.
The browser can show that a fact was confirmed and that the Case revision changed,
but it cannot prove that planning consumed that revision. Returning to the primary
demo starts an unrelated seeded journey rather than continuing the same Case.

This leaves an avoidable ambiguity in the product story: the repository contains
both a governed fact pipeline and a governed planning pipeline, but the public
browser evidence does not show the handoff between them.

### A browser-only handoff would conceal a real state-authority gap

Changing a link or copying the revision into client storage is insufficient. After
confirmation the collaboration Case remains in `intake`, while task creation accepts
only `planning`. A browser cannot own the transition, and two independent writes
would permit a partial state where the Case advanced but no task exists.

The explicit act of starting the first planning task must be the business authority
that changes `intake -> planning`. Case transition, exact Skill resolution, task
identity, dispatch, first event, and idempotency must succeed or fail together.

### Reimplementing the primary demo would create contract drift

Copying Task/SSE/review/family logic into the collaboration page would create a
second client implementation of recovery, idempotency, role rotation, and decision
authority. A third orchestration route would enlarge maintenance cost without
adding product authority.

The correct design is a controlled same-Case journey handoff into the existing
primary workflow.

### The public entry and first viewport obscure the product value

Opening `/` currently shows historical M0 foundation copy rather than the released
product. Opening either demo then presents an English-first technical walkthrough
whose largest headings describe internal surfaces. A technical evaluator can infer
the authority model, but a family member, recruiter, or non-specialist reviewer must
work too hard to understand the outcome, the evidence, and the next human action.

The presentation must tell the truthful product story in plain language without
removing the exact proof that technical reviewers need. This requires a current
portfolio entry route, a Chinese-default surface, closed human-readable mappings,
and a clearer distinction between the primary product narrative and secondary
technical evidence.

## Goals

1. Continue the confirmed collaboration Case into planning without changing Case,
   actor, confirmed-fact, source-pack, or Skill authority.
2. Preserve explicit human confirmation and explicit advisor planning start as
   separate actions.
3. Make first task creation atomically transition a valid Case from `intake` to
   `planning` while preserving existing task creation from `planning`.
4. Keep the existing task HTTP route, request schema, BFF route, durable worker,
   SSE stream, advisor review, family decision, receipt, and timeline contracts.
5. Re-read canonical task inputs from `advisor-ledger` after confirmation; never
   derive them from collaboration browser state.
6. Convert the same-tab journey from `collaboration` to `advisor-family` without
   minting a new advisor session or treating session storage as authority.
7. Show the current Case revision and server-owned confirmed-fact summary during the
   planning continuation.
8. Prove exact Skill pinning and persisted Case revision consumption through real
   PostgreSQL, worker, HTTP, BFF, SSE, and Chromium paths.
9. Keep the complete flow runnable with no DRA, MKE, remote model, provider
   credential, or network dependency beyond normal build inputs.
10. Preserve the existing standalone `/demo` and `/demo/collaboration` entry points,
    recovery paths, public claim boundary, and synthetic labeling.
11. Make `zh-CN` the default public presentation while preserving an explicit
    `en` presentation for international evaluators.
12. Translate user-visible lifecycle, route, Evidence, reason, recovery, action,
    accessibility, receipt, and timeline copy through a closed project-owned catalog;
    never surface an unknown backend code as fallback text.
13. Make the first viewport answer what happened, why it matters, and what the human
    must do next before presenting implementation detail.
14. Preserve the existing semantic table, responsive country comparison, keyboard
    flow, reduced-motion behavior, and public synthetic boundary while refining
    hierarchy, density, typography, and responsive composition.
15. Replace the stale M0 root page with a truthful, current portfolio entry that
    explains the local synthetic product and routes reviewers into the complete
    collaboration-to-decision journey or the focused advisor-family demo.

## Non-goals

- Automatic planning after advisor confirmation.
- Automatic memory extraction or model-authored Case facts.
- DRA live-provider execution, a new DRA consumer contract, or changes to governed
  mixed Evidence promotion.
- MKE runtime/product integration or changes to the read-only candidate boundary.
- Comparing two PlanningRuns or promising that a changed fact produces a
  predetermined route outcome.
- Generic chat, private channels, notifications, message SSE, external transports,
  email, webhooks, OpenClaw, or attachment storage.
- Multi-case advisor queues, production tenancy, billing, CRM, administration, or a
  new identity role.
- A new queue, worker, orchestration framework, policy engine, or dynamic plugin
  loader.
- A new public deployment, production claim, real-user claim, SLA, admissions
  outcome, or business-impact claim.
- Selecting or publishing a new project version as part of implementation.
- Translating repository documentation, APIs, database values, logs, code symbols,
  or persisted domain records into Chinese.
- Simultaneously rendering every sentence in both languages, adding automatic
  browser-language detection, or supporting locales other than exact `zh-CN` and
  `en`.
- Adding an i18n framework, remote font, icon library, component framework, or other
  presentation dependency.
- Replacing the approved `Advisor Ledger × Global Journey` visual identity with a
  generic SaaS dashboard, KPI strip, chat-first product, or marketing landing page.
- Adding adoption metrics, outcome claims, customer logos, testimonials, pricing,
  signup, or any other unsupported marketing proof to the root portfolio entry.

## Product contract

### User-visible journey

The local synthetic golden path is:

```text
parent message
-> explicit typed proposal
-> advisor session
-> advisor confirmation
-> ConfirmedFact + Case revision N+1
-> Continue to governed planning
-> server re-reads the same Case at revision N+1
-> advisor explicitly creates the planning task
-> exact active Skill pin + durable worker + SSE
-> advisor reviews deterministic PlanningRun
-> parent session
-> family decision
-> DecisionReceipt + TimelinePlan
```

The collaboration page remains responsible only through confirmed fact/revision
proof and controlled navigation. The existing primary demo remains responsible for
task creation through the final family outcome.

### Visible authority language

Public UI copy must make these distinctions understandable without exposing internal
IDs or raw JSON:

- a message records communication;
- a proposal requests review;
- confirmation creates a versioned Case fact;
- planning starts only after an explicit advisor action;
- the planning task is bound to the current Case revision and active Skill version;
- the final family decision is separate from advisor review.

The primary advisor view must show the current Case revision. When current confirmed
facts exist, it shows a bounded server-projected summary. It must not imply that the
browser, message text, or session envelope owns those facts.

Route outcomes, cost, eligibility, review inputs, receipt, and timeline remain the
actual deterministic projections. The UI must not manufacture a before/after delta
or claim that the budget update changed a route when the policy output does not prove
that claim.

### Presentation and locale contract

Night Voyager remains the public product name in both locales. The default public
presentation is exact locale `zh-CN`, with an explicit `English` switch for exact
locale `en`. The Chinese first screen uses the plain-language product promise
`把家庭事实变成可追溯的留学决策与行动计划`; it does not introduce a second Chinese
product name.

Locale is presentation metadata only:

- a small project-owned `PresentationLocaleV1` contract accepts only `zh-CN` or
  `en`;
- the initial server-rendered document and `html[lang]` default to `zh-CN`;
- an explicit `中文` / `English` header control changes the locale and updates
  `html[lang]`;
- a valid preference may be stored under exact `localStorage` key
  `night-voyager:presentation-locale:v1`; missing values resolve to `zh-CN`, while
  malformed or unknown values are removed and resolve to `zh-CN`;
- locale is not added to either same-tab journey envelope, API or BFF requests,
  idempotency fingerprints, PostgreSQL records, task pins, or domain projections;
- switching locale performs no business mutation, session rotation, bootstrap,
  polling, or EventSource creation.

The copy system is a typed, closed, repository-owned catalog. It includes all
visible headings, body copy, action labels, form labels, empty states, recovery
messages, accessibility labels, supported country names, lifecycle stages, route
outcomes, evidence labels, trade-offs, reasons, family receipt labels, timeline
labels, and bounded public problem categories used by the three public routes. Dynamic
values such as currency, dates, revision numbers, versions, and durations are
formatted by locale-aware pure functions while preserving their canonical numeric
or timestamp source.

Known backend codes map to approved human-readable copy. Unknown, additive, or
malformed values fail closed to a bounded localized "status unavailable" message;
the raw value is never interpolated into the DOM, accessible name, toast, console,
or screenshot. Approved exact technical identifiers needed for the Skill and task
proof may remain available inside the secondary technical-evidence disclosure, but
they never replace the main user explanation and never include internal UUIDs, raw
JSON, request hashes, paths, or secrets.

### Outcome-first visual hierarchy

The existing warm canvas, paper surfaces, teal trust color, coral human-decision
accent, restrained rules, semantic comparison, and editorial family narrative remain
the visual foundation. The implementation evolves that system instead of introducing
a competing theme.

Chinese UI text uses a local/system CJK sans stack headed by `PingFang SC`, with
`Microsoft YaHei`, `Noto Sans CJK SC`, and `WenQuanYi Zen Hei` fallbacks. Editorial
Chinese headings may use an available local CJK serif, but must fall back cleanly to
the approved CJK sans stack. English keeps the existing IBM Plex Sans and Source
Serif intent. No route may depend on a downloaded font to render complete text.

The root route and both demo routes use the same presentation shell:

1. a compact header with `Night Voyager`, an explicit locale switch, and a visible
   localized synthetic-demo label;
2. a bounded first-screen outcome block that states the current situation, the
   evidence-backed reason, and the single next human action;
3. the main workflow content in decision order rather than implementation order;
4. a collapsed or visually secondary technical-evidence region for revision, Skill,
   task, provenance, and inspector proof;
5. a final receipt/timeline surface that reads as a family decision record rather
   than a developer response payload.

The root `/` route becomes a concise product entry, not a second demo state machine.
It explains the governed fact-to-plan journey, labels the experience as a local
synthetic demonstration, links the primary action to the complete collaboration
entry, and offers the focused advisor-family route as a secondary path. It contains
no API call, session bootstrap, business mutation, fabricated metric, or claim of
production deployment, real users, admission results, or business impact.

Hero headings must not consume most of the desktop first viewport. Internal terms
such as `review-required`, raw Evidence keys, adapter names, and state-machine labels
do not appear in the primary narrative. Dense technical information remains
inspectable without becoming the dominant visual layer. Desktop, tablet, and 390 px
mobile layouts preserve one clear primary action, comfortable reading width, no
horizontal overflow, minimum 44 px targets, visible keyboard focus, semantic
landmarks, and reduced-motion behavior.

The refinement avoids card grids and nested bordered boxes for every concept. It
uses the existing ledger rules, route-line motif, asymmetric editorial composition,
bounded reading widths, tabular numerals, and restrained semantic accents to create
hierarchy. At most the current outcome and required human action receive dominant
emphasis in one viewport; supporting facts and technical proof remain quieter.

## Authority model

| Operation | Authorized actor | System of record | Result |
|---|---|---|---|
| append message | assigned participant | PostgreSQL | immutable communication event |
| propose typed fact | source participant | PostgreSQL | pending `MemoryCandidate` |
| confirm fact | assigned advisor | PostgreSQL | verification + fact + revision `N+1` |
| continue journey | current advisor browser | none | same-tab navigation metadata only |
| start planning | assigned advisor | PostgreSQL | `intake -> planning` plus pinned task |
| execute planning | worker | PostgreSQL + checked-in runtime | PlanningRun and durable events |
| approve consultation | assigned advisor | PostgreSQL | current DecisionBrief authority |
| decide | assigned parent | PostgreSQL | receipt and timeline |

The browser may request every operation but owns none of the business transitions.
Opaque server session, `ActorContext`, assigned Case membership, forced RLS, narrow
functions, exact input pins, and existing human gates remain authoritative.

## Architecture

```text
Browser
  -> explicit Next.js BFF routes
  -> FastAPI application boundaries
  -> PostgreSQL SECURITY DEFINER functions / forced RLS
  -> durable AgentTask dispatch
  -> existing worker + deterministic planning adapter
  -> PostgreSQL PlanningRun / review / brief / decision
  -> durable SSE and server-owned read models
```

No provider adapter participates in the required path.

### Alternatives considered

1. **Start planning automatically during fact confirmation.** Rejected because it
   collapses the advisor's fact-verification and planning-start decisions into one
   operation. It would also make an accepted memory candidate unexpectedly create
   asynchronous work.
2. **Add a separate Case-state transition endpoint before task creation.** Rejected
   because the transition and task would be independent writes. A failure between
   them could leave a `planning` Case without the task that justified the
   transition, and the extra endpoint would duplicate assignment, revision, and
   idempotency checks.
3. **Copy the Task/SSE/review/family flow into `/demo/collaboration`.** Rejected
   because it would create a second client state machine and a second recovery
   implementation without adding authority.
4. **Reuse the existing task endpoint and make deterministic first-task creation
   the atomic planning-start gate.** Selected because it preserves all three human
   decisions, keeps one public mutation contract, and places the state transition
   beside the task, Skill pin, dispatch, event, and idempotency writes it authorizes.
5. **Render Chinese and English simultaneously throughout the page.** Rejected
   because duplicated copy makes already dense evidence and comparison surfaces
   harder to scan. An explicit locale switch keeps each view coherent.
6. **Adopt a general i18n or design-system dependency.** Rejected because two closed
   demo locales and the existing visual tokens do not justify a new runtime or build
   dependency. A typed local catalog provides a smaller fail-closed surface.
7. **Replace the current visual direction with a generic dashboard or marketing
   redesign.** Rejected because the ledger and editorial journey already express
   the product's evidence and human-authority story. The selected approach improves
   hierarchy and language while preserving that identity.

The implementation is split into three sequential pull requests:

1. **PR 1 — explicit planning-start authority**
   - migration `0009`;
   - atomic Case transition plus task creation;
   - application, HTTP, PostgreSQL, concurrency, rollback, downgrade, and
     compatibility proof;
   - ADR 0010 and backend references.
2. **PR 2 — governed fact-to-plan walkthrough**
   - exact journey-envelope conversion;
   - same-Case controlled navigation;
   - current fact/revision presentation;
   - reuse of existing Task/SSE/review/family UI;
   - functional Chromium golden flow, operations docs, and design matrices.
3. **PR 3 — Chinese-first presentation and visual refinement**
   - closed `zh-CN` / `en` copy and formatting contracts;
   - current Chinese-default root entry, shared presentation shell, and explicit
     English switch;
   - outcome-first information hierarchy and secondary technical disclosure;
   - responsive, accessibility, locale-isolation, and visual-regression proof;
   - refreshed real Chromium screenshots and design documentation.

PR 2 starts from the merged, hosted-green PR 1 contract. Internal implementation
may delegate independent bounded lanes, but migration ownership, shared composition,
full database gates, Compose, and Chromium remain serialized under one integration
owner per PR. PR 3 starts only after the merged, hosted-green PR 2 flow is stable;
it changes presentation, not authority, persistence, transport, or task behavior.

## PR 1 — explicit planning-start authority

### Migration `0009`

Migration `0009_explicit_planning_start_authority.py` changes no table, index, role,
RLS policy, or public HTTP schema. It replaces the `0008` definition of
`app.create_agent_task(...)` with a definition that preserves the exact signature and
task-function grants while adding one state transition. It also removes the legacy
`transition_case(uuid,uuid,text,text)` API grant at head; downgrade to `0008` restores
that historical grant and re-upgrade removes it again.

For a new request, the function performs these steps in one transaction:

1. assert trusted advisor context;
2. take the transaction-scoped organization/actor/operation/key advisory lock;
3. read the idempotency ledger, returning an identical replay or `NV008` mismatch
   before any new-write validation;
4. validate strict task pins and resolve the assigned-advisor relationship;
5. resolve the exact active `study-destination-compare` SkillVersion, activation
   event, complete manifest, and `runtime_binding_sha256`;
6. lock the target Case and require the exact current revision;
7. require the source-pack version and operation-specific evidence boundary;
8. accept `planning` with existing behavior;
9. accept `intake` only for `generate_planning_run_v1` and mark it for transition;
10. reject every other state and continue requiring `planning` for
   `generate_governed_mixed_planning_run_v1`;
11. enforce existing effective-task uniqueness;
12. when applicable, update the Case from `intake` to `planning`;
13. insert the exact pinned task, dispatch row, first immutable event, and
    idempotency row.

Any error after the Case update aborts the transaction, leaving the Case in `intake`
and creating no task, dispatch, event, execution, or idempotency residue.

### Why the transition belongs inside task creation

The transition represents the assigned advisor's explicit decision to start
planning. A separate browser or HTTP transition would create two independent writes
and permit partial completion. Confirmation cannot own the transition because that
would make planning automatic. The existing task creation function already owns
assignment, exact revision, source, Skill, task identity, dispatch, and idempotency;
it is therefore the narrowest coherent authority boundary.

### Compatibility

- Existing `planning` Case task creation remains byte-for-byte compatible at the
  HTTP request/response boundary.
- Existing deterministic and governed mixed operations remain supported.
- Governed mixed task creation from `intake` remains rejected; this design does not
  alter DRA promotion or mixed-planning sequencing.
- Existing task replay returns the original task and does not repeat the transition.
- Activation and rollback still affect future task creation only.
- Worker claim, pin validation, adapter routing, result persistence, SSE, review,
  brief, decision, and timeline functions do not gain authority.
- `0009 -> 0008` restores the exact prior task function definition and legacy API
  transition grant. Re-upgrade removes that grant again. No historical rows are
  deleted or rewritten.

### Error surface

No new public problem code is required. The existing task endpoint continues to
return the bounded conflict surface for stale Case state/revision, effective-task
conflict, invalid inputs, unavailable Skill, invalid Skill pin, and insufficient
Evidence. Authorization remains non-enumerating `resource_unavailable`.

The implementation must not expose SQLSTATE values, raw database errors, internal
paths, stack traces, Skill manifests, source payloads, or credentials through the
public HTTP response.

## PR 2 — governed fact-to-plan walkthrough

### Controlled handoff

At `replan_required`, the collaboration page exposes one primary action:
`Continue to governed planning`.

The action does not create a task. It:

1. keeps the current opaque advisor cookie and CSRF value;
2. reloads the confirmed candidate, current confirmed facts, and
   `advisor-ledger` from existing no-store BFF routes;
3. requires the same `case_id` and the exact authoritative result revision;
4. requires a valid advisor ledger phase and exact task identity if a concurrent
   same-revision task already exists;
5. leaves the collaboration envelope unchanged while validation is pending;
6. on success, replaces the exact `CollaborationJourneyEnvelopeV2` with an exact
   `AdvisorFamilyJourneyEnvelopeV2` for the same Case;
7. sets task identity only from the ledger, resets the SSE cursor to zero, clears
   journey-specific mutation records, and leaves `briefId` null;
8. navigates to `/demo`.

The conversion reuses `schema_version=2`; it does not add optional keys or a third
envelope shape. Browser storage remains recovery metadata, not business authority.

If navigation is interrupted after the envelope replacement, loading either demo
must detect the `advisor-family` journey and offer continuation to `/demo` rather
than revoking the valid advisor session.

### Destination recovery

`/demo` already recovers an existing advisor-family envelope using the stored
`caseId`. It must not substitute the default demo Case when a valid continuation is
present.

On recovery it reloads `advisor-ledger` and derives display state exclusively from
that projection:

- `task-ready` presents explicit task creation;
- `active-task` resumes SSE with durable cursor semantics;
- `review-required` presents existing advisor review;
- a terminal task presents the existing bounded recovery state;
- an already-created current brief continues the existing role switch and family
  flow.

Before creating a task, the destination uses only
`ledger.canonical_task_inputs`. The collaboration page and envelope do not transport
revision, source-pack, policy, or Skill pins as task authority.

### Current fact and revision presentation

The advisor route reuses the existing confirmed-facts BFF/API read. It displays a
bounded summary only when PostgreSQL returns current confirmed facts for the Case.
The summary includes public fact labels, family-safe values, fact version, and Case
revision; it excludes raw messages, candidate request hashes, actor UUIDs, internal
IDs, and advisor-only history unless that history is already part of the approved
advisor projection.

The Advisor Ledger displays the current Case revision in every phase. The existing
read-only Planning Skill inspector remains `not_created` before task creation and
becomes `matched` only after the real pinned task exists.

### Client state

The collaboration reducer gains one transient `handoff_validating` state. It is not
persisted; reload during validation returns safely to `replan_required`.

The successful envelope conversion is a single storage replacement. The destination
continues to use the existing advisor-family reducer, idempotency records, SSE cursor,
and recovery contract. No second EventSource, polling loop, task state machine, or
family-decision implementation is added.

### BFF boundary

The existing allowlisted BFF route modules are sufficient. PR 2 must not add a
catch-all route, dynamic upstream path, arbitrary header forwarding, cookie joining,
or a client-selected actor role. Origin, CSRF, opaque cookies, bounded bodies,
deadlines, no-store behavior, and direct SSE byte forwarding remain unchanged.

## PR 3 — Chinese-first presentation and visual refinement

### Closed copy and formatting surface

PR 3 introduces one presentation module shared by `/`, `/demo`, and
`/demo/collaboration`. It owns the exact locale type, locale labels, the complete
copy catalog, the approved dynamic-code maps, and pure formatting helpers. Components
consume typed keys or validated public-code mappings rather than embedding parallel
Chinese and English literal branches.

The implementation must prove catalog parity: every required key exists exactly once
in both locales, no extra locale is accepted, and every mapped dynamic code has a
bounded unknown-value path. Currency remains integer CNY minor-unit authority and is
formatted without changing amount, range, or currency. Dates and durations preserve
the canonical source value. Revision, Skill, and task proof values remain identical
across locale changes.

The explicit locale preference uses a versioned presentation-only `localStorage` key.
It is not read by server authority and is not combined with the existing
`sessionStorage` journey envelope. Unit tests must prove that toggling or corrupting
locale state cannot create, retry, cancel, approve, decide, bootstrap, revoke, or
reconnect anything.

### Existing design-system evolution

PR 3 updates `DESIGN.md` and the affected design matrices to record the Chinese-first
bilingual presentation contract. It keeps the approved palette, typography intent,
spacing scale, semantic status colors, table behavior, and prohibited-pattern list.
It may refine CSS tokens, responsive composition, typographic scale, whitespace,
surface grouping, and technical-disclosure styling without adding a UI framework,
remote font, or design dependency.

The main hierarchy is outcome first:

- the header establishes product, locale, and synthetic scope without a full-screen
  marketing hero;
- the root route gives a current plain-language product summary and two truthful
  demo entry choices instead of the historical M0 bootstrap message;
- the current outcome, evidence-backed explanation, and next human decision are
  visible in the first desktop viewport;
- country comparison and authority steps use localized public labels;
- the collaboration route explains message, proposal, confirmation, revision, and
  planning handoff in family-readable language;
- the family route prioritizes decision, trade-off, receipt, and timeline;
- exact Skill/task/revision/provenance proof remains available under localized
  technical-evidence disclosure.

No raw backend value is used as a translation key. No visual control is added unless
it performs a real existing action or disclosure. Locale controls remain available
at every responsive width and do not obscure the primary action.

### Screenshot and review contract

Public screenshots are generated from the real deterministic Chromium flow after
PR 2 is merged. The default published evidence is Chinese and covers at least the
portfolio entry, advisor outcome, family receipt/timeline, and governed collaboration
handoff. English is exercised in browser tests across the same authority states even
when duplicate English screenshots would add little reviewer value.

Visual review checks hierarchy, copy fit, alignment, contrast, focus, 44 px targets,
semantic landmarks, reduced motion, 1440 px, tablet, and 390 px layouts. Screenshot
review must reject internal IDs, raw JSON, unmapped codes, browser chrome, private
paths, credentials, clipped copy, misleading production claims, and horizontal
overflow.

## Concurrency and failure handling

### Task start

- Two different first task requests serialize on the Case and effective task
  identity; exactly one succeeds.
- Overlapping same-key transactions serialize before ledger lookup. An identical
  request returns the original task and pin with `replayed=true` after the first commit.
- A different payload under the same overlapping key returns `NV008` after the first
  commit rather than falling through to effective-task conflict.
- Wrong role, unassigned advisor, cross-tenant Case, stale revision, wrong source,
  invalid Skill, missing activation, malformed pin, and unsupported Case state fail
  without changing Case state.
- Injected failure at every write boundary proves rollback of Case state, task,
  dispatch, event, and idempotency records.

### Handoff

- Revision drift or a no-longer-current confirmed fact returns the existing stale
  recovery category and requires authoritative reload.
- An expired session requires re-authentication and server reload; browser metadata
  alone cannot restore authority.
- Wrong-role or unavailable Case remains non-enumerating.
- A concurrent legitimate task is adopted only from `advisor-ledger`; no duplicate
  POST is issued by the handoff.
- Validation failure leaves the collaboration envelope intact.
- Successful conversion followed by interrupted navigation remains recoverable from
  the destination envelope.

### Task and decision recovery

Existing contracts remain authoritative:

- lost task acknowledgement reuses the exact idempotency fingerprint;
- SSE reconnect uses durable event IDs and monotonic cursor storage;
- one Task owns one active EventSource in the browser;
- stale review or family decision reloads authoritative projections rather than
  replaying a changed mutation;
- `skill_pin_invalid`, terminal task failures, and outdated results remain bounded
  terminal states.

## Security and privacy

- The required flow uses the existing opaque local demo session and closed roles.
- Tenant identity and participant assignment come only from trusted server context.
- All business tables remain forced-RLS protected.
- Runtime roles gain no direct table DML.
- Migration `0009` narrows the runtime function grant surface by removing the API's
  legacy standalone Case-transition authority; downgrade restores it only for `0008`.
- Session storage contains only the approved recovery envelope; it contains no raw
  provider output, source content, password, token, cookie value, or private path.
- Local storage contains at most the versioned `zh-CN` or `en` presentation
  preference and never contains a Case, actor, task, CSRF, cookie, decision, or
  provider value.
- Public UI and logs do not expose internal UUIDs, raw JSON, traceback, SQLSTATE,
  source payloads, request hashes, Skill manifest bodies, or credentials.
- Unknown backend presentation values fail closed to bounded localized copy and are
  not interpolated into rendered output or accessibility labels.
- All public fixtures and screenshots remain explicitly synthetic.

## Testing strategy

### PR 1 focused proof

Pure/application and real PostgreSQL tests must cover:

- assigned-advisor deterministic task creation from `intake`;
- atomic `intake -> planning` plus exact task/dispatch/event/idempotency writes;
- existing task creation from `planning`;
- governed mixed creation from `intake` remains rejected;
- wrong role, unassigned actor, cross-tenant Case, stale revision, source mismatch,
  invalid manifest, missing activation, invalid pin, and unsupported Case state;
- committed and overlapping same-key replay, overlapping changed-request `NV008`,
  different-key effective conflict, and concurrent first creation;
- injected failure after each mutation boundary with zero partial residue;
- exact five-field task pin and claim-time execution pin;
- worker materialization consumes revision `N+1` and its confirmed fact rather than
  the checked-in fixture Case;
- `0009 -> 0008 -> 0009` task function parity, legacy transition grant restoration,
  re-revocation, and compatibility.

HTTP tests use the existing endpoint and prove that no new request field or public
response field is required.

### PR 2 focused proof

Frontend and BFF tests must cover:

- exact collaboration-to-advisor-family envelope conversion;
- validation occurs before storage replacement;
- no task POST occurs during handoff;
- stored continuation uses the same `caseId`, CSRF, and authoritative task identity;
- reload before validation, after conversion, during task streaming, during advisor
  review, and after parent rotation;
- `advisor-ledger` rather than the default Case drives destination recovery;
- current confirmed facts and Case revision render without private IDs or raw JSON;
- inspector transitions from `not_created` to `matched` only after task creation;
- one EventSource, monotonic cursor, lost acknowledgement, stale conflicts, and
  terminal recovery;
- existing default `/demo` and standalone `/demo/collaboration` behavior remain
  compatible.

### PR 3 focused proof

Frontend tests must cover:

- exact `zh-CN` and `en` catalog parity and compile-time key coverage;
- Chinese default render, explicit English switch, `html[lang]`, persistence, reload,
  and invalid-preference fallback;
- current localized root entry, primary complete-journey link, secondary focused-demo
  link, synthetic scope, and absence of the stale M0 claim;
- no locale value enters the journey envelope, HTTP/BFF request, idempotency key,
  EventSource URL, or business mutation;
- closed maps for lifecycle, roles, countries, outcomes, Evidence labels,
  trade-offs, reasons, recovery categories, receipt fields, and timeline fields;
- unknown and malformed dynamic values render bounded localized fallback without
  exposing the raw value;
- exact CNY amount/range, date, duration, Case revision, and technical-proof identity
  remain semantically identical in both locales;
- first-screen outcome, reason, next action, locale control, and synthetic label are
  present at desktop, tablet, and 390 px widths;
- technical evidence is secondary but keyboard-accessible and contains only approved
  public proof values;
- existing mutations, role rotation, SSE connection count, recovery, and authority
  calls are unchanged by locale switches;
- all three public routes retain landmarks, semantic comparison where applicable,
  visible focus, reduced-motion
  behavior, minimum target size, and no horizontal overflow.

### Full proof

The final browser lane starts from a fresh database and performs the entire flow:

1. parent session and bounded message;
2. typed budget proposal;
3. real parent-to-advisor session rotation;
4. advisor confirmation and revision `N+1` proof;
5. controlled same-Case handoff;
6. explicit task creation and atomic Case transition;
7. real worker execution and native SSE progress/reconnect;
8. exact Skill inspector match;
9. advisor approval;
10. real advisor-to-parent session rotation;
11. family decision, receipt, timeline, and reload proof.

Database assertions bind the browser-observed Case, revision, fact, task, Skill pin,
execution, PlanningRun, review, brief, decision, receipt, and timeline. The task
operation is exactly `generate_planning_run_v1`; no live-provider credential or DRA
request participates in the lane.

The functional PR 2 lane must cover desktop, tablet, and 390 px mobile layout,
keyboard focus, semantic landmarks, action-target size, and horizontal overflow.
PR 3 reruns the complete real Chromium flow in both locales, refreshes the public
Chinese screenshots, and verifies that presentation changes do not alter the
database-observed authority chain. Public screenshots must be inspected for internal
IDs, raw JSON, browser chrome, unmapped codes, private paths, secrets, clipped copy,
and misleading claims.

Required repository gates include the existing focused collaboration, Skill, task,
database, frontend, release, proof, and Compose commands. Exact commands belong in
the implementation plans and must use the repository's current Make targets rather
than inventing unverified names.

## Documentation impact

PR 1 updates:

- ADR 0010 for explicit planning-start authority;
- AgentTask/event and HTTP references;
- database-role and migration operations;
- the approved design/plan status index.

PR 2 updates:

- English and Chinese README product flow;
- collaboration and connected-demo runbooks;
- demo storyboard, route map, projection matrix, and state/interaction matrix;
- collaboration, confirmed-fact, AgentTask, and Skill references where behavior
  changes;
- the approved plan completion status and functional browser proof.

PR 3 updates:

- `DESIGN.md` bilingual and outcome-first presentation contract;
- English and Chinese README portfolio entry copy where the public demo presentation
  changes;
- connected-demo and collaboration runbooks for the locale control and technical
  disclosure;
- affected storyboard, route, projection, state, interaction, and presentation
  matrices;
- refreshed Chinese-default Chromium screenshots and screenshot assertions;
- the approved plan and documentation indexes when the presentation layer is
  implemented.

Published `v0.1.0`, `v0.1.1`, and `v0.1.2` release notes, verification guides, tags,
GitHub Releases, and source-archive observations remain immutable history.

Each implementation PR performs the repository-required targeted documentation
audit before merge. Documentation must continue to distinguish local synthetic proof
from production deployment, real users, provider execution, and admissions results.

## Acceptance criteria

The increment is complete only when all three sequential PRs are merged, exact
merge-SHA hosted checks succeed, and the following statements are executable facts:

1. the existing collaboration flow creates one authoritative confirmed fact and
   Case revision `N+1` before any planning task exists;
2. confirmation alone neither changes Case state to `planning` nor creates a task;
3. assigned-advisor deterministic task creation from `intake` atomically changes
   Case state and creates the complete pinned task authority;
4. every failure and concurrent loser leaves no partial state transition or task
   residue;
5. existing `planning` Case task creation and governed mixed planning remain
   compatible;
6. the browser continues the same Case and advisor session rather than starting the
   default seeded Case;
7. destination task inputs are re-read from server authority and are not transported
   from collaboration state;
8. the worker consumes the new persisted revision and retains the exact active Skill
   pin through execution;
9. the browser proves Task/SSE/recovery, advisor review, parent decision, receipt,
   and timeline against the same Case;
10. no DRA, MKE, remote model, live provider, provider credential, or external
    message transport is required or called by the golden path;
11. existing standalone demo paths, optional integrations, release verifier, and
    public-hygiene contracts remain green;
12. public documentation and screenshots accurately describe a local synthetic
    portfolio workflow and contain no private process or sensitive material;
13. Compose teardown and task-owned Docker inventory are empty, while retained data
    and unrelated resources remain untouched;
14. `zh-CN` is the stable default demo presentation, `en` is explicitly selectable,
    and locale changes cannot mutate or reconnect the governed journey;
15. all user-visible dynamic codes use closed localized mappings, with unknown values
    failing closed without exposing raw backend content;
16. the first viewport explains the current outcome, evidence-backed reason, and next
    human action before technical detail, while exact approved proof remains
    inspectable in a secondary disclosure;
17. refreshed real Chromium evidence proves Chinese desktop and responsive surfaces,
    English compatibility, accessibility, and the unchanged database authority chain;
18. `/` is a current localized portfolio entry with truthful demo routing and no
    stale M0 statement, unsupported metric, or production claim.

## Deferred work

- DRA live-provider proof and any future program-fit governed consumer proof remain
  separately authorized work with independent credential, cost, deadline, attempt,
  and Evidence-role boundaries.
- MKE product integration remains separate from the read-only candidate proof.
- PlanningRun comparison/history UI is not required by this increment.
- Automatic fact extraction, proactive Agent actions, and external message routing
  require separate designs and authority reviews.
- Multi-case advisor operations and production tenancy remain separate product
  programs.
- Public deployment remains a separate security and operations decision.
- Repository-wide localization, automatic locale negotiation, and additional locales
  remain separate presentation work.

## Release boundary

This design does not change Python or Web package versions and does not authorize a
release. After all three implementation PRs are merged, post-merge hosted checks and
fresh local/browser proof pass, and documentation evidence is complete, maintainers may
evaluate whether the increment merits a bounded patch/minor portfolio release.

No version number, tag, GitHub Release, source-archive gate, or deployment is
preselected by this design.
