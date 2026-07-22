# Night Voyager Governed Fact-to-Plan Closure Design

## Status

Approved design. Implementation has not started.

This document defines the next bounded Night Voyager product increment after the
`v0.1.2` Governed Collaboration Core release. Approval of this design authorizes
the design record and subsequent implementation planning. It does not by itself
authorize implementation, push, pull request creation, merge, tag, release,
deployment, live-provider execution, or cleanup of unrelated resources.

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

The implementation is split into two sequential pull requests:

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
   - Chromium golden flow, screenshots, operations docs, and design matrices.

PR 2 starts from the merged, hosted-green PR 1 contract. Internal implementation
may delegate independent bounded lanes, but migration ownership, shared composition,
full database gates, Compose, and Chromium remain serialized under one integration
owner per PR.

## PR 1 — explicit planning-start authority

### Migration `0009`

Migration `0009_explicit_planning_start_authority.py` changes no table, index, role,
RLS policy, or public HTTP schema. It replaces the `0008` definition of
`app.create_agent_task(...)` with a definition that preserves the exact signature and
grants while adding one state transition.

For a new request, the function performs these steps in one transaction:

1. assert trusted advisor context and validate the strict task pins;
2. resolve and validate the assigned-advisor relationship;
3. resolve the exact active `study-destination-compare` SkillVersion, activation
   event, complete manifest, and `runtime_binding_sha256`;
4. lock the target Case and require the exact current revision;
5. require the source-pack version and operation-specific evidence boundary;
6. accept `planning` with existing behavior;
7. accept `intake` only for `generate_planning_run_v1` and mark it for transition;
8. reject every other state and continue requiring `planning` for
   `generate_governed_mixed_planning_run_v1`;
9. enforce existing effective-task uniqueness and idempotency;
10. when applicable, update the Case from `intake` to `planning`;
11. insert the exact pinned task, dispatch row, first immutable event, and
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
- `0009 -> 0008` restores the exact prior function definition and grants. No
  historical rows are deleted or rewritten.

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

## Concurrency and failure handling

### Task start

- Two different first task requests serialize on the Case and effective task
  identity; exactly one succeeds.
- A same-key replay returns the original task and pin.
- A different payload under the same key remains an idempotency conflict.
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
- Migration `0009` preserves the existing narrow function grant surface.
- Session storage contains only the approved recovery envelope; it contains no raw
  provider output, source content, password, token, cookie value, or private path.
- Public UI and logs do not expose internal UUIDs, raw JSON, traceback, SQLSTATE,
  source payloads, request hashes, Skill manifest bodies, or credentials.
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
- same-key replay, different-key effective conflict, and concurrent first creation;
- injected failure after each mutation boundary with zero partial residue;
- exact five-field task pin and claim-time execution pin;
- worker materialization consumes revision `N+1` and its confirmed fact rather than
  the checked-in fixture Case;
- `0009 -> 0008 -> 0009` function/grant parity and compatibility.

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

The lane must cover desktop, tablet, and 390 px mobile layout, keyboard focus,
semantic landmarks, action-target size, and horizontal overflow. Public screenshots
must be generated from the real Chromium flow and inspected for internal IDs, raw
JSON, browser chrome, private paths, secrets, and misleading claims.

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
- public Chromium evidence and the approved plan completion status.

Published `v0.1.0`, `v0.1.1`, and `v0.1.2` release notes, verification guides, tags,
GitHub Releases, and source-archive observations remain immutable history.

Each implementation PR performs the repository-required targeted documentation
audit before merge. Documentation must continue to distinguish local synthetic proof
from production deployment, real users, provider execution, and admissions results.

## Acceptance criteria

The increment is complete only when both sequential PRs are merged, exact merge-SHA
hosted checks succeed, and the following statements are executable facts:

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
    and unrelated resources remain untouched.

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

## Release boundary

This design does not change Python or Web package versions and does not authorize a
release. After both implementation PRs are merged, post-merge hosted checks and fresh
local/browser proof pass, and documentation evidence is complete, maintainers may
evaluate whether the increment merits a bounded patch/minor portfolio release.

No version number, tag, GitHub Release, source-archive gate, or deployment is
preselected by this design.
