# Collaboration Walkthrough and Skill Inspector Implementation Plan

**Implementation status:** Implemented locally on 2026-07-20 from exact base
`8283b8df0b955712baf7b24a7d0b19996007fd1b`; all Tasks C1-C7 and local acceptance
gates are complete. The capability remains post-v0.1.1 and unreleased.

> **Execution record:** implementation used `superpowers:using-git-worktrees` and
> `superpowers:executing-plans` as the only primary controllers. C2 followed C1, and
> every BFF, session, reducer, UI, recovery, browser, and documentation slice followed
> test-first RED -> GREEN.

**Goal:** Add a secondary `/demo/collaboration` walkthrough that proves a
parent-authored message can become a typed candidate and then an advisor-confirmed
Case revision, while a shared technical inspector exposes the active/pinned planning
Skill contract without turning the product into generic chat or an Agent console.

**Architecture:** PR C adds no migration and no backend authority. Eight explicit
transport-only Next.js BFF methods proxy the frozen PR A/B FastAPI contracts. A new
strict collaboration reducer and versioned same-tab recovery envelope own browser
state. PostgreSQL remains authoritative for thread, candidate, fact, revision, task,
execution, activation, and pin status. A shared no-store Skill inspector is rendered
on both `/demo` and `/demo/collaboration` from the server-owned composite read model.

**Tech Stack:** Next.js 16.2.10 App Router, React 19.2.7, TypeScript, Vitest,
Testing Library, Playwright/Chromium, existing transport-only BFF utilities,
FastAPI/PostgreSQL/Compose contracts from PR A and PR B, and existing CSS with no new
frontend dependency.

## Global Constraints

- Begin only from clean `main` after PR A and PR B are merged and their OpenAPI,
  read-model, problem-code, seed, and migration contracts are frozen. Record the
  actual base SHA. Do not implement from either retained backend feature branch.
- PR C adds no migration, table, grant, backend mutation authority, dependency,
  lockfile change, queue, worker, task operation, EventSource, provider transport,
  live proof, release, or deployment.
- Keep `/demo` as the primary advisor-to-family flow. Add exactly one secondary route
  `/demo/collaboration`; do not redirect or replace the existing route.
- The collaboration route proves exactly one local synthetic storyline: parent
  session -> shared thread -> parent message -> one `family.budget` proposal -> real
  parent-session revoke -> advisor bootstrap/mint -> advisor confirmation ->
  authoritative fact/revision reload -> `replan_required`.
- The route does not create an AgentTask, poll planning state, or open EventSource.
  `replan_required` means a new task is needed; it does not silently create one.
- The shared Skill inspector is an ordinary `no-store` GET and browser projection.
  It never joins registry/task/execution records client-side and exposes no raw SQL,
  prompt, internal dataset location, role name, secret, or unbounded digest.
- On `/demo`, inspector progression is `pin_status=not_created` before task creation
  and `pin_status=matched` after a pinned task/execution is authoritative. On
  `/demo/collaboration`, it remains `not_created` because that route creates no task.
- Add exactly eight BFF methods through seven explicit route files. There is no
  catch-all proxy, dynamic upstream URL, header forwarding, cookie joining, or
  generic request relay.
- BFF mutation handlers require exact browser Origin, existing opaque-session cookie,
  session-bound CSRF header, bounded body, and `Idempotency-Key`. They use the
  server-configured FastAPI origin and preserve independent `Set-Cookie` headers.
- The existing `sessionStorage` key remains `night-voyager:m5`, but its value becomes an
  exact `schema_version=2` discriminated union with
  `journey=advisor-family|collaboration`. Legacy/unversioned, malformed, or
  Case/role-invalid data fails closed and is cleared; it is never partially upgraded
  by guessing. A valid envelope for the other journey is preserved and rendered by
  `JourneyConflictNotice`, not cleared as malformed.
- Collaboration metadata is cursor-free and contains only server-projected
  Case/thread/message/candidate IDs, phase, role, CSRF, and exact mutation records.
  A residual cookie or envelope from the other journey is never silently reused.
  The UI offers only “Return to current walkthrough” or “End current walkthrough and
  start collaboration”; the latter performs a real CSRF-protected revoke. Only a
  confirmed revoke, or an explicit bounded-401 retry that clears the cookie, permits
  the next bootstrap. Lost acknowledgement preserves the current journey metadata.
- Before each append/propose/confirm mutation, persist the exact canonical request
  fingerprint and idempotency key. Unknown outcome retries only the identical body
  and key. A 401 clears retry metadata and forbids automatic mutation replay. A 409
  first reloads authority and decides from the server result.
- The collaboration reducer states are exactly `bootstrapping_parent`,
  `thread_ready`, `message_submitting`, `proposal_pending`,
  `switching_to_advisor`, `advisor_reviewing`, `confirmation_submitting`,
  `replan_required`, and `recoverable_error`. Do not enlarge the existing connected
  demo reducer.
- `replan_required` is reached only after a read proves both the confirmed fact and
  incremented Case revision. A successful mutation response or lost-ack retry alone
  is insufficient.
- Before advisor confirmation, the advisor candidate projection supplies the
  candidate's pinned `case_revision`, and the existing advisor-ledger GET supplies
  the current Case revision. The UI enables confirmation only when they are equal.
  `expected_case_revision` is copied from that server projection into the exact
  verification body and its canonical fingerprint; it is never a user-editable field
  or a value inferred from local increment logic.
- The revision proof reuses the existing explicit
  `GET /api/demo/cases/{caseId}/advisor-ledger` BFF after advisor mint; its
  `case_revision` must equal the verification result's revision. The new
  confirmed-facts GET must contain the exact resulting current fact/value/version.
  Both reads must agree before `replan_required`. Lost acknowledgement first reloads
  candidate terminal state, then performs the same two-read proof.
- Public backend problem codes map to exactly seven UI categories:
  `stale`, `expired_or_terminal`, `active_task_blocked`,
  `unsafe_or_unsupported`, `wrong_role_or_not_found`,
  `session_recovery_required`, and `transport_unavailable_or_timeout`.
  Unknown codes fail closed as transport unavailable; not every 409 is stale.
- The active-task, stale-candidate, and expired-candidate browser cases come from the
  deterministic PR A seed and real backend responses. Frontend query parameters,
  mocks, request overrides, or test-only local state cannot manufacture them.
- The collaboration walkthrough has no role selector. Its parent-to-advisor switch is
  the fixed real revoke/bootstrap sequence, while the visible role is status only.
- 1440, 768, and 390 px layouts preserve provenance order, readable selected-country
  comparison, keyboard focus, landmarks, and >=44 px primary touch targets. No raw
  JSON, UUID-first presentation, random ID, internal code, or horizontal overflow.
- Keep existing `/demo` one-EventSource and monotonic cursor behavior unchanged.
  Existing terminal/reconnect browser proof must remain green.
- Keep v0.1.1 release docs and identity unchanged. This is post-v0.1.1 unreleased
  functionality; no version bump or release claim.
- All code, test output, screenshots, commits, PR body, and docs remain public-neutral
  and synthetic. Never expose cookies, CSRF, credentials, private paths, raw SQL,
  tracebacks, private workflow, or real-person data.

## Closed BFF Surface

Create exactly these route files and methods:

| File | Method | Upstream |
| --- | --- | --- |
| `web/app/api/demo/cases/[caseId]/collaboration-thread/route.ts` | GET | `/api/v1/cases/{case_id}/collaboration-thread` |
| `web/app/api/demo/collaboration-threads/[threadId]/messages/route.ts` | GET | `/api/v1/collaboration-threads/{thread_id}/messages` |
| same file | POST | same upstream collection |
| `web/app/api/demo/messages/[messageId]/memory-candidates/route.ts` | POST | `/api/v1/messages/{message_id}/memory-candidates` |
| `web/app/api/demo/cases/[caseId]/memory-candidates/route.ts` | GET | `/api/v1/cases/{case_id}/memory-candidates` |
| `web/app/api/demo/memory-candidates/[candidateId]/verification-decisions/route.ts` | POST | `/api/v1/memory-candidates/{candidate_id}/verification-decisions` |
| `web/app/api/demo/cases/[caseId]/confirmed-facts/route.ts` | GET | `/api/v1/cases/{case_id}/confirmed-facts` |
| `web/app/api/demo/cases/[caseId]/planning-skill-inspector/route.ts` | GET | `/api/v1/cases/{case_id}/planning-skill-inspector` |

These are eight HTTP methods, not eight files. Existing bootstrap/mint/revoke handlers
are reused for role switching and must not be duplicated.

## File Ownership and Lane Boundaries

The integration owner exclusively owns:

- `web/lib/connected-demo/session-storage.ts`
- any modification to existing `/demo` components/hooks
- `web/app/styles.css`
- `web/lib/demo-bff/transport.ts`
- `web/tests/unit/demo-bff.test.ts`
- `scripts/verify_compose.sh`, Playwright Compose orchestration
- shared docs/index, screenshots, full frontend/Docker/Chromium gates

Bounded lane C1 owns transport/contracts only:

- seven new BFF route files
- `web/lib/collaboration-demo/{contracts,api}.ts`
- `web/lib/skill-inspector/contracts.ts`
- focused BFF/contract tests

Bounded lane C2 starts after C1 freezes contracts and owns new client/UI files only:

- `web/lib/collaboration-demo/{reducer,use-collaboration-demo}.ts`
- `web/components/collaboration-demo/*`
- `web/app/demo/collaboration/page.tsx`
- focused reducer/hook/component tests

The integration owner builds the shared session envelope, shared inspector component,
existing `/demo` integration, styles, Playwright, Compose, screenshots, and docs.
Both lanes stop before editing shared files.

---

### Task C1: Freeze strict collaboration and Skill-inspector browser contracts

**Files:**
- Create: `web/lib/collaboration-demo/contracts.ts`
- Create: `web/lib/skill-inspector/contracts.ts`
- Create: `web/tests/unit/collaboration-contracts.test.ts`
- Create: `web/tests/unit/skill-inspector-contracts.test.ts`

**Interfaces:**
- Produces exact TypeScript validators for thread, message page, candidate projections,
  confirmed facts, verification result, Case revision evidence, and planning Skill
  inspector. Validators reject extra fields, malformed UUID/timestamp/digest,
  unbounded strings, wrong candidate projection by role, and unknown pin status.

- [x] **Step 1: Write validator RED tests**

  Cover every valid role projection plus missing/additive/wrong-type fields, candidate
  metadata hidden from student/parent, inspector
  `not_created|matched|legacy_unpinned`, bounded digest prefixes, and no raw contract
  or evaluator payload.

  ```typescript
  it("rejects an inspector projection with an unknown pin status", () => {
    expect(() => parsePlanningSkillInspector({
      ...validInspector,
      pin_status: "active",
    })).toThrow();
  });
  ```

- [x] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- collaboration-contracts skill-inspector-contracts
  ```

  Expected: modules do not exist.

- [x] **Step 3: Implement closed validators**

  Use exact own-property checks and discriminated role projections. Do not accept a
  generic `Record<string, unknown>` after validation. Return immutable typed objects
  used by the API and components.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- collaboration-contracts skill-inspector-contracts
  npm --prefix web run lint
  npm --prefix web run typecheck
  ```

  ```bash
  git add web/lib/collaboration-demo/contracts.ts \
    web/lib/skill-inspector/contracts.ts \
    web/tests/unit/collaboration-contracts.test.ts \
    web/tests/unit/skill-inspector-contracts.test.ts
  git commit -m "feat: add collaboration browser contracts"
  ```

### Task C2: Add eight explicit transport-only BFF methods

**Files:**
- Create: `web/app/api/demo/cases/[caseId]/collaboration-thread/route.ts`
- Create: `web/app/api/demo/collaboration-threads/[threadId]/messages/route.ts`
- Create: `web/app/api/demo/messages/[messageId]/memory-candidates/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/memory-candidates/route.ts`
- Create: `web/app/api/demo/memory-candidates/[candidateId]/verification-decisions/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/confirmed-facts/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/planning-skill-inspector/route.ts`
- Create: `web/lib/collaboration-demo/api.ts`
- Modify: `web/lib/demo-bff/transport.ts` (integration owner only)
- Modify: `web/tests/unit/demo-bff.test.ts` (integration owner only)
- Modify: `web/tests/unit/demo-bff-handlers.test.ts`
- Create: `web/tests/unit/collaboration-api.test.ts`

**Interfaces:**
- Reuses existing BFF config, bounded transport, problem parsing, cookie append, exact
  Origin, CSRF, and idempotency helpers. Produces typed client calls for all eight
  methods and existing identity role-switch calls.

- [x] **Step 1: Write BFF/client RED tests**

  Test exact upstream paths/methods, query cursor forwarding, no arbitrary headers,
  server-configured Origin, mutation CSRF/idempotency forwarding, independent
  `Set-Cookie`, no-store, body/deadline bounds, upstream problem preservation,
  malformed success fail-closed, and no catch-all route. Prove JSON GET forwards only
  the server-configured Origin and session cookie; JSON mutation forwards only the
  server-configured Origin, session cookie, `Content-Type`, `X-CSRF-Token`, and
  `Idempotency-Key`; and only SSE forwards `Last-Event-ID`. Other browser headers are
  dropped. Freeze verification JSON as exactly `schema_version`, server-projected
  `expected_case_revision`, `decision`, and `reason`; extra/missing/retyped fields are
  rejected by the BFF validator.

  The messages GET accepts only `after_sequence` and `limit`. Canonicalize
  `after_sequence` as an integer `>= 0` and `limit` as an integer in `1..100`; reject
  repeated, unknown, non-integer, or out-of-range parameters and never forward the
  browser's raw query string.

- [x] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- demo-bff demo-bff-handlers collaboration-api
  ```

  Expected: seven route modules and collaboration API are absent.

- [x] **Step 3: Implement explicit handlers and client**

  Each route hard-codes one approved upstream path template and method. Split the
  existing JSON and SSE header allowlists: JSON GET forwards only the server Origin
  and session cookie; JSON mutation additionally forwards only `Content-Type`,
  `X-CSRF-Token`, and `Idempotency-Key`; only SSE may forward `Last-Event-ID`. GET
  handlers forward only approved pagination parameters. Reuse the existing unified
  deadline and bounded problem response. The integration owner applies the shared
  transport and direct transport-test edits after the bounded route lane is
  integrated; bounded lanes do not edit those shared files.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- demo-bff demo-bff-handlers collaboration-api
  npm --prefix web run lint
  npm --prefix web run typecheck
  ```

  ```bash
  git add web/app/api/demo web/lib/collaboration-demo/api.ts \
    web/lib/demo-bff/transport.ts web/tests/unit/demo-bff.test.ts \
    web/tests/unit/demo-bff-handlers.test.ts \
    web/tests/unit/collaboration-api.test.ts
  git commit -m "feat: add collaboration BFF transport"
  ```

### Task C3: Version same-tab session and mutation recovery

**Files:**
- Modify: `web/lib/connected-demo/session-storage.ts`
- Modify (integration owner): `web/lib/connected-demo/use-connected-demo.ts`
- Modify (integration owner): `web/components/connected-demo/ConnectedDemo.tsx`
- Create: `web/lib/collaboration-demo/reducer.ts`
- Create: `web/lib/collaboration-demo/use-collaboration-demo.ts`
- Create: `web/components/demo-session/JourneyConflictNotice.tsx`
- Modify (integration owner): `web/tests/unit/connected-demo-recovery.test.tsx`
- Create: `web/tests/unit/collaboration-session.test.ts`
- Create: `web/tests/unit/collaboration-reducer.test.ts`
- Create: `web/tests/unit/use-collaboration-demo.test.tsx`

**Interfaces:**
- Produces exact `schema_version=2` journey envelope, three mutation retry records,
  nine-state collaboration reducer, recovery classifier, role switch, authoritative
  reload, and lost-ack replay behavior.

- [x] **Step 1: Write session/reducer/hook RED tests**

  Freeze:

  ```typescript
  type DemoJourneyEnvelopeV2 =
    | AdvisorFamilyJourneyEnvelopeV2
    | CollaborationJourneyEnvelopeV2;

  type CollaborationMutationKind =
    | "append-message"
    | "propose-memory-candidate"
    | "verify-memory-candidate";

  type CollaborationPersistedPhase = Exclude<
    CollaborationPhase,
    "recoverable_error"
  >;
  ```

  Exact envelope keys are:

  ```typescript
  interface AdvisorFamilyJourneyEnvelopeV2 {
    schema_version: 2;
    journey: "advisor-family";
    role: "advisor" | "parent";
    csrf: string;
    caseId: string;
    taskId: string | null;
    briefId: string | null;
    cursor: number;
    mutations: Partial<Record<AdvisorFamilyMutationKind, IdempotencyRecord>>;
  }

  interface CollaborationJourneyEnvelopeV2 {
    schema_version: 2;
    journey: "collaboration";
    role: "parent" | "advisor";
    csrf: string;
    caseId: string;
    threadId: string | null;
    messageId: string | null;
    candidateId: string | null;
    phase: CollaborationPersistedPhase;
    mutations: Partial<Record<CollaborationMutationKind, IdempotencyRecord>>;
  }
  ```

  Cover old schema, malformed JSON, valid other-journey preservation, Case mismatch, role mismatch,
  request fingerprint mismatch, 401 clearing, same-body/key retry, 409 reload,
  confirmation lost acknowledgement, fact/revision proof requirement, reload at each
  state, and unknown problem code fail-closed. Freeze cross-field invariants:

  - `bootstrapping_parent` permits `threadId=null`; every later phase requires the
    server-projected thread ID;
  - every parent phase through `switching_to_advisor` requires `candidateId=null`;
  - advisor candidate GET success stores the candidate ID before entering
    `advisor_reviewing`;
  - `advisor_reviewing|confirmation_submitting|replan_required` require
    `role=advisor` and a non-null server-projected candidate ID;
  - a parent envelope carrying a candidate ID, or an advisor phase requiring one but
    lacking it, is malformed and is cleared fail closed.

  `recoverable_error` is reducer-only and is never persisted. Its in-memory state
  carries a bounded error category plus `resumePhase: CollaborationPersistedPhase`;
  the envelope keeps the last valid authority phase and no error text. Reload starts
  from that persisted phase, re-reads authority, and may classify a new bounded
  error. Tests prove bootstrap errors can retain `threadId=null`, parent errors never
  retain a candidate ID, advisor candidate-read errors may resume from
  `switching_to_advisor` with `candidateId=null`, and no serialized envelope contains
  `recoverable_error` or raw failure data.

  The advisor hook must read candidate and advisor-ledger projections before
  verification, require equal revisions, and persist the complete verification body
  fingerprint and idempotency key before sending. Lost acknowledgement reuses that
  byte-equivalent body/key. A changed candidate revision, ledger revision, decision,
  or reason invalidates the retry and forces an authority reload.

- [x] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- collaboration-session collaboration-reducer \
    use-collaboration-demo
  ```

  Expected: schema v2 and collaboration state machine are absent.

- [x] **Step 3: Implement exact envelope and reducer**

  The integration owner first replaces schema v1 with the discriminated schema v2,
  updates existing advisor-family restore, and implements `JourneyConflictNotice`
  in both `/demo` and `/demo/collaboration`. A valid other-journey envelope offers
  only return or a real revoke; it is cleared only after successful revoke or bounded
  401 recovery. Ambiguous revoke preserves metadata and blocks bootstrap. The
  existing connected-demo recovery regression must prove this symmetric behavior
  before lane C2 starts.

  After that commit is integrated, lane C2 implements only the collaboration reducer
  and hook. The hook transitions through the closed states and uses candidate,
  confirmed-fact, and existing advisor-ledger reads to prove recovery. It never
  infers authority from local state or mutation success. The participant projection
  does not reveal a candidate ID, so parent proposal completion stores only own-
  proposal status. After the real role switch, the advisor candidate read discovers
  and stores the server-projected candidate ID before verification.

- [x] **Step 4: Freeze exact problem mapping**

  Map:

  ```text
  case_revision_stale | memory_candidate_stale
    -> stale
  memory_candidate_expired | memory_candidate_terminal
    -> expired_or_terminal
  active_task_blocks_revision
    -> active_task_blocked
  invalid_collaboration_message | unsupported_fact_key | unsafe_fact_value |
  idempotency_conflict
    -> unsafe_or_unsupported
  resource_unavailable
    -> wrong_role_or_not_found
  bff_session_recovery_required
    -> session_recovery_required
  persistence_unavailable | bff_upstream_unavailable | bff_upstream_timeout |
  unknown
    -> transport_unavailable_or_timeout
  ```

- [x] **Step 5: Run GREEN and commit the two ownership slices**

  ```bash
  npm --prefix web run test -- collaboration-session collaboration-reducer \
    use-collaboration-demo
  npm --prefix web run lint
  npm --prefix web run typecheck
  ```

  ```bash
  git add web/lib/connected-demo/session-storage.ts \
    web/lib/connected-demo/use-connected-demo.ts \
    web/components/connected-demo/ConnectedDemo.tsx \
    web/components/demo-session/JourneyConflictNotice.tsx \
    web/tests/unit/collaboration-session.test.ts \
    web/tests/unit/connected-demo-recovery.test.tsx
  git commit -m "feat: version demo journey recovery"

  git add web/lib/collaboration-demo \
    web/tests/unit/collaboration-reducer.test.ts \
    web/tests/unit/use-collaboration-demo.test.tsx
  git commit -m "feat: add collaboration recovery state"
  ```

### Task C4: Build the collaboration walkthrough UI

**Files:**
- Create: `web/app/demo/collaboration/page.tsx`
- Create: `web/components/collaboration-demo/CollaborationDemo.tsx`
- Create: `web/components/collaboration-demo/SharedThread.tsx`
- Create: `web/components/collaboration-demo/MemoryCandidateCard.tsx`
- Create: `web/components/collaboration-demo/ConfirmedFactSummary.tsx`
- Create: `web/components/collaboration-demo/CollaborationRecoveryNotice.tsx`
- Create: `web/tests/unit/collaboration-demo.test.tsx`
- Modify: `web/app/styles.css`

**Interfaces:**
- Renders one shared thread, source-parent proposal, advisor verification, confirmed
  fact/revision provenance, closed recovery states, and visible `role=status` without
  generic chat, task controls, fake route actions, or raw JSON.

- [x] **Step 1: Write component RED tests**

  Assert six storyline beats, role switch, shared message history, one typed budget
  proposal, pending/confirmed status, advisor reason, confirmed fact version,
  incremented Case revision, `replan_required`, error categories, focus movement,
  empty/loading states, and absence of UUID-first/raw JSON/internal codes.

- [x] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- collaboration-demo
  ```

  Expected: route and components are absent.

- [x] **Step 3: Implement semantic UI**

  Use headings, landmarks, labelled controls, status text, and bounded human-readable
  copy. Display the source message sequence and fact provenance appropriate to the
  active role, not hidden advisor-only fields. Disable only the active mutation and
  keep recovery action explicit.

- [x] **Step 4: Implement responsive/focus behavior**

  At 390 px, render thread, proposal, advisor decision, confirmed fact, revision, and
  collapsed Skill inspector in one readable column without horizontal scrolling. On role
  switch or recovery, send focus to the new state heading. Touch targets are at least
  44 px.

- [x] **Step 5: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- collaboration-demo
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  ```

  ```bash
  git add web/app/demo/collaboration web/components/collaboration-demo \
    web/components/demo-session/JourneyConflictNotice.tsx \
    web/tests/unit/collaboration-demo.test.tsx web/app/styles.css
  git commit -m "feat: add governed collaboration walkthrough"
  ```

### Task C5: Add the shared planning Skill inspector

**Files:**
- Create: `web/components/skill-inspector/PlanningSkillInspector.tsx`
- Create: `web/tests/unit/planning-skill-inspector.test.tsx`
- Modify: `web/components/connected-demo/ConnectedDemo.tsx`
- Modify: `web/lib/connected-demo/use-connected-demo.ts`
- Modify: `web/components/collaboration-demo/CollaborationDemo.tsx`

**Interfaces:**
- Renders server-owned operation, active Skill key/version, evaluation/activation
  identity, task pin, actual leaf adapter, bounded digest prefixes, and exact
  `pin_status`, with role-safe labels and no client-side relational join.

- [x] **Step 1: Write inspector RED tests**

  Prove `/demo` initial `not_created`, post-task `matched`, collaboration
  `not_created`, legacy projection, wrong-role absence, no raw digest/UUID-first
  output, and no mutation affordance.

- [x] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- planning-skill-inspector connected-demo \
    collaboration-demo
  ```

  Expected: shared inspector is absent and existing `/demo` does not fetch it.

- [x] **Step 3: Implement shared no-store read model**

  Task C4/lane C2 must be fully integrated and no longer editing
  `CollaborationDemo.tsx` before the integration owner begins this task.

  Fetch the inspector only at authoritative advisor milestones: advisor Case load
  and after task creation/terminal recovery on `/demo`; after advisor bootstrap and
  after final confirmed-fact reload on `/demo/collaboration`. Clear/hide the cached
  inspector before `/demo` switches to parent. No parent phase may call or retain an
  advisor-only inspector projection. Do not poll and do not open another stream.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- planning-skill-inspector connected-demo \
    collaboration-demo
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  ```

  ```bash
  git add web/components/skill-inspector \
    web/tests/unit/planning-skill-inspector.test.tsx \
    web/components/connected-demo web/lib/connected-demo \
    web/components/collaboration-demo/CollaborationDemo.tsx
  git commit -m "feat: expose planning Skill execution pins"
  ```

### Task C6: Prove the real browser-to-database collaboration flow

**Files:**
- Create: `web/e2e/collaboration-demo.spec.ts`
- Modify: `web/playwright.compose.config.ts`
- Modify: `scripts/verify_compose.sh`
- Modify: Compose/browser proof architecture regressions

- [x] **Step 1: Write Playwright/Compose RED proof**

  Use real seeded PostgreSQL, FastAPI, Next BFF, cookies, Origin/CSRF,
  idempotency, and browser state. Cover:

  1. parent bootstrap and shared thread read;
  2. parent message and exact budget proposal;
  3. reload during pending proposal;
  4. parent revoke and advisor mint;
  5. advisor read and confirmation;
  6. fact/revision reload before `replan_required`;
  7. same-key lost-ack replay;
  8. 1440/768/390, keyboard/focus/landmarks;
  9. wrong-role hiding;
  10. deterministic stale, expired, and active-task-blocked seeded Cases;
  11. collaboration inspector remains `not_created`;
  12. existing `/demo` inspector reaches `matched` while one-EventSource cursor proof
      remains unchanged.

- [x] **Step 2: Run RED**

  ```bash
  make compose-proof
  ```

  Expected: the new collaboration browser lane and inspector assertions fail before
  C1-C5 are integrated; all earlier backend lanes stay green up to that point.

- [x] **Step 3: Integrate deterministic proof without test injection**

  Route negative cases to PR A's stable seeded identities. Do not mutate database
  state from Playwright except through approved HTTP operations. Capture evidence only
  after authoritative UI state is visible.

- [x] **Step 4: Run focused and full GREEN**

  ```bash
  npm --prefix web run test
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  make compose-proof
  make down
  docker compose ps --all
  ```

  Expected: frontend gates and every existing/new browser lane pass; Compose is empty.

- [x] **Step 5: Commit browser proof**

  ```bash
  git add web/e2e/collaboration-demo.spec.ts web/playwright.compose.config.ts \
    scripts/verify_compose.sh tests
  git commit -m "test: prove collaboration browser authority"
  ```

### Task C7: Refresh public evidence, docs, and local closeout

**Files:**
- Create: `docs/operations/collaboration-walkthrough.md`
- Create: `docs/assets/collaboration-confirmed-fact.png`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DESIGN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/design/route-map.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/operations/connected-demo.md`
- Modify: `docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md`
- Modify: `docs/superpowers/plans/2026-07-16-collaboration-walkthrough-and-inspector.md`
- Modify: release/docs architecture regressions

- [x] **Step 1: Write documentation/evidence RED tests**

  Assert both demo routes, primary-vs-secondary narrative, accepted PR A/B authority,
  collaboration role switch, read-only inspector, no task creation on collaboration,
  screenshot dimensions/existence, post-v0.1.1 unreleased status, and unchanged
  local-synthetic/non-production claims.

- [x] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/test_release_surface.py \
    tests/architecture/test_collaboration_contract.py \
    tests/architecture/test_skills_contract.py -q
  ```

  Expected: route/docs/screenshot/status assertions fail.

- [x] **Step 3: Capture and inspect the real screenshot**

  Generate `docs/assets/collaboration-confirmed-fact.png` from the real Chromium flow
  at 1440 px after fact/revision reload. Inspect the image for readable message,
  proposal, advisor decision, confirmed fact, revision and Skill inspector; reject
  raw JSON, UUID-first text, browser chrome, secrets, paths, clipping, or overflow.

- [x] **Step 4: Update public docs**

  Explain `/demo` as the primary advisor-family flow and `/demo/collaboration` as the
  governed memory walkthrough. ADR 0006 already records M5 as implemented; preserve that
  status while updating route/state/storyboard docs, runbooks, HTTP surface, spec/plan
  status, and reviewer index. Do not claim deployment, real users, external routing, or
  v0.1.2 release.

- [x] **Step 5: Run fresh final verification**

  ```bash
  make doctor MODE=dev
  uv lock --check
  uv run pytest -q -m "not database and not mke"
  uv run ruff check .
  uv run pyright
  uv build --build-constraints build-constraints.txt --require-hashes
  npm --prefix web ci
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  make db-check
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  git diff --check "$(git merge-base HEAD origin/main)"..HEAD
  ```

  Expected: every command exits 0, screenshot/public-hygiene checks pass, no migration
  or dependency/lockfile delta exists, and Compose is empty.

- [x] **Step 6: Review and commit**

  Review the complete diff for exact eight BFF methods, schema-v2 envelope, closed
  reducer/error mappings, authority reads, one-EventSource preservation, responsive
  proof, screenshot hygiene, docs accuracy, and absence of backend/migration changes.

  ```bash
  git add README.md README_CN.md CONTRIBUTING.md DESIGN.md docs web scripts tests
  git commit -m "docs: complete collaboration walkthrough evidence"
  ```

- [x] **Step 7: Stop at local authority-review handoff**

  Report base/branch/worktree/HEAD/ordered commits, exact diff, RED -> GREEN evidence,
  BFF route matrix, session/recovery tests, viewport/focus evidence, screenshot hash,
  full commands, documentation impact, inventory, and remaining risks. Keep the
  worktree clean. Do not push, create PR, merge, tag, release, deploy, run live proof,
  or start a version bump.

## PR C Acceptance Checklist

- [x] `/demo` remains the primary unchanged advisor-family journey; the secondary
  `/demo/collaboration` proves parent proposal -> advisor confirmation -> authoritative
  fact/revision reload without creating a task.
- [x] Exactly eight explicit BFF methods proxy only frozen PR A/B endpoints through
  existing bounded transport, cookie, Origin, CSRF, idempotency, and no-store rules.
- [x] The schema-v2 journey envelope, exact mutation fingerprints, 401/409 recovery,
  closed reducer, and seven error categories are fail-closed and fully tested.
- [x] Real PostgreSQL seed drives stale, expired, active-task, wrong-role, replay, and
  confirmation paths; frontend injection does not manufacture authority.
- [x] Shared inspector is server-owned and no-store; collaboration shows
  `not_created`, default demo progresses to `matched`, and no client-side join or
  mutation authority exists.
- [x] 1440/768/390, keyboard/focus, landmarks, touch targets, no overflow, and one
  public screenshot are verified through real Chromium.
- [x] Existing backend authority, task/SSE/reconnect, M1-M5, DRA, MKE, v0.1.1, and
  release/public-neutral boundaries remain green with no migration/dependency change.
