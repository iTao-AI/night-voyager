# Governed Plan Execution and Reassessment

**Status:** Approved design; PR A/B is implemented locally. PR C, publication,
and release remain pending.

## Summary

Night Voyager currently turns a governed family decision into an immutable
`DecisionReceipt` and `TimelinePlan`. This design extends that boundary with a
durable, role-scoped execution ledger. Assigned family participants can submit
structured progress attestations, an assigned advisor can verify completed
checkpoints, and a deterministic read model can explain the current action
without owning business state.

The execution loop stops fail-closed at `reassessment_required`. It does not
silently reuse the pre-decision revision flow, create a new `PlanningRun`, or
replace the final family decision. The stop records a successor-safe handoff
identity, but reassessment resolution, replacement decisions, a successor
timeline, and a successor execution require a separately approved future
design.

The feature remains a local synthetic, provider-free portfolio workflow. It
does not submit real applications, upload personal documents, call a remote
provider, or claim production adoption or admissions outcomes.

## Current Authority Boundary

The current released flow is:

```text
Message
  -> MemoryCandidate
  -> ConfirmedFact
  -> StudentCaseRevision
  -> AgentTask
  -> PlanningRun
  -> AdvisorReview
  -> FamilyDecision
  -> DecisionReceipt
  -> TimelinePlan
```

The existing `TimelinePlan` is immutable and contains the selected country,
intake, and ordered milestone dates. Existing planning revision authority is
deliberately limited to the period before `FamilyDecision` and `TimelinePlan`.
Finalized Cases must not be routed back through that revision contract.

The existing `AgentTask` ledger owns durable planning work: claim, lease,
heartbeat, retry, cancellation, generation fencing, event replay, and SSE
recovery. This stage does not generalize that ledger. Its current-action
guidance is a synchronous deterministic projection of already-authoritative
execution state. It creates no task, execution, event, Skill binding, worker
operation, proposal row, or new queue.

## Goals

The implementation must:

1. Turn the immutable `TimelinePlan` into an explicit, durable execution
   workspace without mutating the plan or family decision.
2. Preserve a closed role boundary between family attestation, advisor
   verification, deterministic state transitions, and non-authoritative
   current-action guidance.
3. Support idempotent mutation, immutable receipt replay, reload recovery,
   stale-tab rejection, and role/session change recovery.
4. Derive current-action codes synchronously from the authoritative execution
   view without model, provider, worker, Skill, or background task authority.
5. Surface due-soon, overdue, and blocked work without changing state during a
   read.
6. Stop at a durable `reassessment_required` state with a successor-safe
   handoff identity and no successor business mutation.
7. Add a bilingual execution workspace, provider-free browser-to-database
   proof, evaluator-first documentation, and a finding-gated presentation
   closure before the `v0.1.5` release.

## Non-Goals

This design does not:

- mutate or replace an existing `FamilyDecision`, `DecisionReceipt`, or
  `TimelinePlan`;
- create a post-decision `StudentCaseRevision`, `PlanningRun`, `AdvisorReview`,
  family decision, receipt, timeline, or execution successor;
- automatically replan, select a new country, resolve reassessment, or resume
  from `reassessment_required`;
- represent family attestation as source Evidence or accept an Evidence URL,
  file, upload, locator, source snapshot, or arbitrary narrative;
- add a current-action AgentTask, task operation, Skill, adapter, worker
  handler, SSE stream, scheduler, or second queue;
- connect to school application portals, email, payment, calendar, CRM,
  messaging, or notification systems;
- upload or retain passports, transcripts, financial records, visa documents,
  or other user files;
- require a paid model, remote Agent, DRA provider, credential, or live
  acceptance attempt;
- change the existing strict DRA consumer status or authorize another provider
  attempt;
- add a hosted playground, public SDK, new public CLI, product telemetry, or a
  new community service;
- claim production deployment, real student or school coverage, advisor-team
  adoption, admissions results, time savings, business impact, HA, SLA, or an
  audit-zero dependency state.

## Product Flow

```text
plan_ready
  -> explicit family start
  -> execution_active
  -> deterministic current-action projection
  -> family progress/completion/blocked attestation
  -> advisor verification
       -> request_update -> execution_active
       -> verify -> next checkpoint
       -> verify final checkpoint -> execution_completed

execution_active
  -> blocked attestation or PostgreSQL-derived overdue risk
  -> explicit advisor reassessment
  -> reassessment_required
  -> durable future-successor handoff
  -> stop
```

Current-action guidance never advances a checkpoint, verifies an attestation,
opens reassessment, completes an execution, or creates a durable candidate. It
may be ignored by the user.

## Authority Model

### Immutable planning anchor

`TimelinePlan` remains the immutable planning artifact. Execution records copy
the exact milestone keys, order, and due dates into a versioned execution
snapshot. The copied values must match the canonical plan exactly at creation
time and cannot be supplied or changed by the browser.

The first release remains a synthetic study-plan execution contract. It does
not claim to be a generic workflow engine. Milestone, order, date, and
responsibility policy are admitted only from the approved timeline snapshot
and the closed synthetic policy.

### Execution state

`TimelineExecutionV1.state` is one of:

- `active`
- `reassessment_required`
- `completed`

Only one execution may exist for a `TimelinePlan`. Starting the execution is an
explicit mutation by a currently assigned family participant. The existing
`StudentCase.state` remains `plan_ready`; the decision lifecycle is not reused
as execution state authority.

Every execution has a positive `row_version`. Mutations bind the expected
execution version and immutable Case, decision, receipt, and timeline
identities.

### Checkpoint state

`TimelineCheckpointV1.state` is one of:

- `pending`
- `in_progress`
- `awaiting_advisor`
- `verified`
- `blocked`

The first checkpoint begins as `in_progress`; later checkpoints begin as
`pending`. Only the first unverified checkpoint is current. A later checkpoint
cannot start early, and a verified checkpoint cannot be reopened.

The closed synthetic responsibility policy is:

| Milestone | Accountable role |
| --- | --- |
| `documents` | `student` |
| `application` | `student` |
| `visa` | `student` |
| `arrival` | `parent` |

Any currently assigned participant with the exact accountable family role may
submit an attestation. Any currently assigned advisor may verify it. The exact
acting participant is persisted on every accepted record. The design does not
infer a unique actor from a role that may have multiple assignments.

A participant outside the assigned Case or an actor with the wrong role
receives the same non-enumerating unavailable response as an unknown resource.

### Risk projection and authoritative time

`risk_state` is one of:

- `on_track`
- `due_soon`
- `overdue`

The role-safe database read projection derives risk from the immutable due date
and a PostgreSQL-owned observed date without creating events or mutating state.
The application pure projector consumes that observed database date; tests may
inject the observed value. The API and browser cannot supply or override an
authoritative `as_of` value.

An accepted `deadline_elapsed` reassessment derives its authoritative date and
trigger proof inside the PostgreSQL mutation function from the same
database-owned time boundary. The accepted date is not included in the stable
client request hash; the accepted trigger projection is persisted separately.

### Structured attestations

`TimelineCheckpointAttestationV1.attestation_kind` is one of:

- `progress`
- `completion`
- `blocked`

A `progress` attestation is append-only and leaves the checkpoint
`in_progress`. A `completion` attestation moves it to `awaiting_advisor`. A
`blocked` attestation moves it to `blocked`.

Attestations accept closed `status_code`, `attestation_code`, and
`reason_code` enums only. They accept no free-form narrative, URL, filename,
uploaded bytes, external account identifier, or Evidence reference.

An attestation is a participant statement, not verified source Evidence. Public
copy uses “status update” or “attestation”. Only the advisor action is called
“verified”.

### Advisor verification

`TimelineCheckpointVerificationV1.action` is one of:

- `verify`
- `request_update`

`verify` is valid only for the latest `completion` attestation on the current
checkpoint. It marks that checkpoint `verified` and atomically activates the
next checkpoint. Verifying the final checkpoint atomically marks the execution
`completed`.

`request_update` preserves attestation and verification history, then returns
the current checkpoint to `in_progress`.

### Deterministic current-action projection

`TimelineCurrentActionV1` is derived synchronously from the current execution
view. It contains:

- exact schema version;
- execution and checkpoint identities;
- observed execution and checkpoint row versions;
- `action_code`;
- `accountable_role`;
- one to eight closed `checklist_codes`;
- zero to eight closed `risk_codes`;
- `guidance_authority="non_authoritative"`.

The projection is a pure, provider-free function over:

- execution and checkpoint state;
- immutable milestone and responsibility policy;
- latest accepted attestation and verification identities;
- derived risk state.

It returns codes, not localized business text. Web presentation maps the closed
codes to exact `zh-CN` or `en` copy. Locale cannot change an identity, action
code, risk code, transition, or authorization result.

The projection has no durable table and no create, cancel, retry, worker,
event, or SSE lifecycle. It never appears in the `AgentTask` ledger. If an
optional guidance region cannot render, the already-authoritative execution
workspace remains visible. A malformed or contradictory authoritative
execution projection still fails closed rather than guessing state.

### Reassessment and future-successor handoff

Only a currently assigned advisor may create
`TimelineReassessmentRequestV1`. Its trigger is one of:

- `blocked_attestation`
- `deadline_elapsed`

`blocked_attestation` binds the current durable blocked attestation.
`deadline_elapsed` binds a PostgreSQL-derived overdue trigger for the current
checkpoint.

Creation atomically changes the execution to `reassessment_required`.
Subsequent attestations and verifications fail closed. Current-action guidance
becomes a terminal handoff projection and does not offer a resume action.

The request persists:

- `handoff_schema_version`;
- exact predecessor execution, timeline, receipt, decision, Case, revision, and
  checkpoint identities;
- trigger and trigger reference;
- accepted trigger projection hash;
- exact advisor actor and owner role;
- `successor_status="pending_future_authorization"`.

No successor identifier is invented. No successor execution, plan, decision,
receipt, review, or timeline is created in `v0.1.5`. The handoff identity is
designed so a later approved successor contract can bind its predecessor
without rewriting this history.

## Data Model

Migration `0014` introduces the complete stage. Migration `0015` is not part of
this design.

### `app.timeline_executions`

- organization, execution, Case, Case revision, family decision, decision
  receipt, and timeline identities;
- schema version and execution state;
- positive row version;
- created and updated timestamps;
- one execution per timeline plan;
- composite uniqueness and foreign keys through organization and Case
  authority.

### `app.timeline_checkpoints`

- execution and milestone identity;
- immutable ordinal, milestone key, due date, and accountable role;
- checkpoint state and positive row version;
- attestation and verification timestamps where applicable;
- unique milestone key and unique ordinal per execution.

### `app.timeline_checkpoint_attestations`

- execution and checkpoint identity;
- reporter actor identity and role;
- attestation kind, status code, attestation code, and reason code;
- execution and checkpoint versions observed by the request;
- canonical stable client request hash and created timestamp;
- append-only history.

### `app.timeline_checkpoint_verifications`

- execution, checkpoint, and attestation identity;
- advisor actor identity;
- action and closed reason code;
- execution and checkpoint versions observed by the request;
- canonical stable client request hash and created timestamp;
- append-only history.

### `app.timeline_reassessment_requests`

- execution and checkpoint identity;
- assigned advisor actor identity;
- exact trigger and trigger reference;
- execution and checkpoint versions observed by the request;
- canonical stable client request hash;
- separately persisted authoritative trigger projection hash and accepted
  database date;
- handoff schema version and exact predecessor identities;
- successor status;
- created timestamp;
- at most one request per execution.

### `app.timeline_mutation_receipts`

- immutable receipt identity;
- organization, actor, operation, idempotency key hash, and request hash;
- subject execution and optional checkpoint identity;
- immutable accepted result kind and result identity;
- before and after execution/checkpoint versions;
- created timestamp;
- canonical response schema version.

The existing central idempotency authority may own these fields directly or
reference an immutable timeline receipt row. The implementation must choose one
schema shape and prove byte-identical canonical replay; it must not create a
second competing idempotency ledger.

### Activity projection and indexes

The public activity view combines attestations, verifications,
reassessments, and mutation receipts:

- stable order is `created_at DESC, durable_id DESC`;
- each source is locally bounded before `UNION ALL`;
- the global response returns at most 64 records;
- `activity_total` is an exact count and is documented as O(history) for the
  bounded synthetic stage;
- older retained history is not publicly paginated, exported, or deleted in
  this release.

Every activity source has a covering index beginning with:

```text
(organization_id, execution_id, created_at DESC, durable_id DESC)
```

JSON `EXPLAIN` integration tests prove bounded cardinality and index use for
empty, one-row, 64-row, 65-plus, same-timestamp, and mixed-kind histories.

### Database authority

All new tables use forced RLS and tenant-scoped policies. Runtime roles mutate
them only through narrow `SECURITY DEFINER` functions that validate trusted
`ActorContext`, active Case assignment, exact role, immutable anchor, row
version, lock order, idempotency record, and operation before mutation.

Runtime roles receive no direct table write grant. Application reads are
role-safe and non-enumerating. The implementation freezes an operation × role ×
create/read matrix before database code is accepted.

Migration `0014 -> 0013` refuses before mutation when any execution history
exists. Empty-schema downgrade restores the exact prior catalog, functions,
policies, indexes, and grants. Historical migrations and published release
artifacts remain byte-identical.

PR B adds the authority-approved identity-only migration `0015`. It widens the
closed demo-principal allowlist to distinct exact Happy and Blocked
advisor/student/parent triads and restricts rotation to generic-to-generic or
within one scenario. The browser supplies only `happy|blocked`; the server maps
that key to an exact principal and the existing context function resolves the
one assigned Case. There is no arbitrary Case selector. `0014` timeline schema,
functions, grants, and transition semantics remain immutable. `0015 -> 0014`
refuses before catalog mutation when scenario principal or session history
would make downgrade lossy.

## Session, Case, and Recovery Authority

The browser may not select an arbitrary business Case.

The synthetic demo bootstrap accepts only a closed scenario key. The server
maps that key to one exact seeded Case and persists or derives the active Case
context for the authorized session. A role rotation may preserve the context
only when the replacement actor is assigned to the same Case. Otherwise the
session fails closed.

The role-safe plan-context discovery projection returns:

- exact Case and current revision identity;
- final decision, receipt, timeline, and optional execution identity;
- active role and assignment status;
- context schema version.

It returns one context or fails on zero/ambiguous cardinality. It does not
return hidden tenant or participant data.

Browser storage is a recovery hint only. A bounded local envelope may contain:

- context schema version;
- Case and execution identity;
- last immutable mutation receipt identity;
- operation-specific idempotency slots.

Every stored identity is revalidated by the server before use. Reload with an
existing opaque session has a closed CSRF recovery path. The browser never
mints authority, infers a Case from old storage, or silently creates a new
idempotency key.

When another tab rotates or revokes the shared session, the stale tab closes
in-flight work, performs no mutation, and enters a bounded `session_changed`
recovery state.

## HTTP Contract

New FastAPI endpoints:

```text
GET  /api/v1/plan-execution-context
POST /api/v1/timeline-plans/{timeline_plan_id}/executions
GET  /api/v1/cases/{case_id}/timeline-execution
POST /api/v1/timeline-executions/{execution_id}/checkpoint-attestations
POST /api/v1/timeline-executions/{execution_id}/checkpoint-verifications
POST /api/v1/timeline-executions/{execution_id}/reassessments
```

The execution GET returns:

- immutable planning anchor;
- execution and checkpoint state;
- deterministic current-action projection;
- latest accepted attestation and verification identities;
- bounded activity view;
- terminal reassessment handoff when applicable.

Every request model:

- uses `extra="forbid"`;
- requires an exact schema version;
- accepts only closed enums and bounded collections;
- omits tenant and actor authority fields;
- requires expected execution and checkpoint versions for mutations.

Every mutation requires the existing session, Origin, CSRF, and bounded
`Idempotency-Key`. The Next.js BFF mirrors the same routes as transport-only
handlers. It does not derive roles, state, due dates, current action,
verification eligibility, or reassessment authority.

Successful mutations return an immutable `TimelineMutationReceiptV1`, not a
mutable execution view. The client then performs a fresh execution GET.

Closed public problem codes include:

- `resource_unavailable`
- `plan_execution_context_unavailable`
- `invalid_idempotency_key`
- `idempotency_conflict`
- `stale_execution_version`
- `stale_checkpoint_version`
- `checkpoint_not_current`
- `checkpoint_attestation_conflict`
- `advisor_verification_required`
- `reassessment_required`
- `execution_completed`
- `session_changed`
- `execution_projection_unavailable`

The API path classifier includes all new timeline endpoints so framework-level
validation also returns the closed Problem JSON shape.

Authorization failures remain non-enumerating. Each public code has a stable
documentation anchor describing:

- the problem;
- safe probable cause;
- whether retry is permitted;
- the next user or operator action.

Responses never expose internal SQL, stack traces, tenant identity, hidden
resource state, secret values, session tokens, CSRF values, or raw sensitive
payload.

## Idempotency, Concurrency, and Reconciliation

For every mutation, PostgreSQL owns:

```text
organization + actor + operation + key_hash
  -> stable_client_request_hash + immutable_mutation_receipt
```

The stable request hash contains only the public request body and immutable
subject identities. It excludes server time and any later read-model state.

The same key and same stable request return the exact original immutable
receipt, even after later transitions. The same key with a different request
returns `idempotency_conflict`.

Execution and current checkpoint rows are locked in one documented order before
validation. Attestation, verification, reassessment, and start operations must
match expected versions after the lock is acquired. Concurrent requests
produce at most one accepted transition.

Browser reconciliation is:

```text
mutation
  -> immutable receipt
  -> fresh execution GET
```

If the mutation response is lost, an explicit recovery action replays the exact
prior body with the same key. Recovery never mints a new key automatically.
Later state changes do not alter the replayed receipt. A fresh GET supplies the
current state.

## Failure Model

### Authority failures

- wrong tenant, actor, active Case, assignment, or role;
- zero or ambiguous server-owned Case context;
- execution not bound to the final decision, receipt, and timeline;
- checkpoint not current;
- attestation or verification references stale state;
- reassessment trigger not proven by a current blocked attestation or
  PostgreSQL-derived overdue trigger.

### Idempotency and concurrency failures

- same key with a different stable request;
- stale execution or checkpoint version;
- duplicate execution;
- concurrent attestation, verification, or reassessment;
- lost acknowledgement followed by an incompatible retry;
- fixed lock-order or uniqueness violation.

### Projection failures

- contradictory execution/checkpoint authority rows;
- missing deterministic current-action mapping;
- activity cardinality or schema violation;
- database projection unavailable;
- BFF/API envelope mismatch;
- locale affecting an authority field.

### Browser and session failures

- stored context disagrees with durable state;
- shared-cookie role rotation invalidates another tab;
- CSRF recovery is missing or stale;
- mutation navigation occurs before immutable receipt capture;
- optional guidance presentation fails while the durable workspace remains
  available.

All failures preserve previously accepted authority records. No failure path
creates a replacement family decision, timeline, execution, task, or
successor.

## Privacy and Retention

The feature stores only synthetic structured workflow records. It accepts no
uploaded file, arbitrary URL, filename, free-form application narrative,
credential, school account, payment information, external message content, or
real source Evidence.

Attestations, verifications, receipts, and reassessment requests are append-only
audit history. There is no public delete, pagination, export, or retention
operation in this release. Documentation states that the latest-64 view is not
the complete retained history.

Task-scoped integration fixtures and Compose resources are removed through the
existing exact teardown contract. The protected shared PostgreSQL volume and
shared images/cache remain outside task cleanup.

Logs, issue templates, and browser responses expose only stable public codes,
bounded identities, phase names, and sanitised counts. They prohibit secret
values, session or CSRF values, private local paths, raw database payload, and
content-bearing Evidence.

## Web Product and Information Architecture

The feature adds `/demo/plan` as a dedicated execution workspace. The existing
`/demo` remains the decision and planning-revision journey.

The route is one semantic page, not a generic admin dashboard or competing
route-level tabs. Desktop and mobile DOM order is:

1. current checkpoint, state, accountable role, and due date;
2. one primary current action;
3. next human handoff and risk summary;
4. immutable approved plan context;
5. activity and optional technical run details.

`Overview`, `Plan`, and `Activity` are landmarks, anchors, or secondary
disclosures. The current action remains first on narrow screens and at 200%
zoom. Raw hashes, row versions, task internals, database rows, and lease
concepts are not default UI content.

The complete state matrix includes:

| State | Preserved content | Primary action | Owner |
| --- | --- | --- | --- |
| not started | approved plan and milestones | start execution | assigned family role |
| checkpoint active | current checkpoint and verified history | submit attestation | accountable family role |
| awaiting advisor | submitted attestation and receipt | advisor: verify or request update; family: explain waiting | assigned advisor |
| update requested | history and advisor reason | revise attestation | accountable family role |
| completed | verified history and final receipt | review activity | none |
| reassessment required | trigger, stop impact, predecessor handoff | view handoff context | advisor/future workflow |
| wrong role | safe status content | switch role if allowed | participant |
| session changed | last confirmed safe content | reconnect | participant |
| projection unavailable | last confirmed safe content when valid | retry/reconnect | operator/read model |
| activity truncated | latest 64 and exact total | disclose limitation | none |

Every main state explains:

1. what is happening now;
2. what the user should do;
3. who acts next.

Attestation success, lost-ack reconciliation, stale-tab refresh,
`request_update`, completion, and reassessment each have an explicit focus
destination and one deduplicated live-region announcement.

The feature preserves two intentional presentation identities:

- the root `Virtual Night Voyage` portfolio surface;
- the warm-paper governed demo workspace.

The functional slices freeze semantic DOM, headings, accessible names, focus,
state ordering, and responsive behavior. The final presentation slice may
change existing routes only when a rendered baseline records a P1/P2 hierarchy,
accessibility, or cross-route consistency finding. No finding means no rewrite.

Acceptance covers:

- exact `zh-CN` and `en`;
- 1440, 768, 390, and 320 CSS pixels;
- 200% zoom without horizontal page scrolling;
- keyboard-complete mutation and disclosure flows;
- visible focus and deterministic post-mutation focus;
- WCAG 2.2 AA text contrast;
- at least 24×24 CSS-pixel targets, with 44×44 preferred for primary mobile
  actions;
- `aria-describedby` error association;
- reduced-motion behavior;
- long Chinese and English copy without hiding owner or action.

Stable semantic assertions cover the state matrix. A small representative
screenshot set covers happy, waiting, reassessment, narrow, and recovery
states. Pixel snapshots are evidence, not authority contracts.

## Testing Strategy

### Domain and contract tests

- strict schema round-trip and extra-field rejection;
- immutable timeline-to-execution copy;
- exact checkpoint order and responsibility policy;
- attestation, verification, completion, and reassessment transitions;
- deterministic current-action codes and authority exclusion;
- trusted-clock read projection and PostgreSQL mutation clock boundary;
- immutable mutation receipt canonical bytes;
- successor-safe terminal handoff;
- stable public problem codes.

### PostgreSQL integration and security tests

- forced RLS, policies, owners, grants, and runtime role separation;
- operation × role × create/read matrix;
- any-currently-assigned-role cardinality and exact acting actor;
- one execution per timeline;
- exact composite Case/decision/receipt/timeline anchor;
- append-only attestations, verifications, receipts, and reassessment;
- same-key replay after later transitions;
- different-body conflict;
- row-version and two-tab concurrency;
- fixed lock order;
- final checkpoint atomic completion;
- PostgreSQL-owned deadline trigger;
- no successor business rows;
- activity indexes, local/global bounds, exact count, tie order, and JSON
  `EXPLAIN`;
- safe upgrade, empty downgrade, history refusal, re-upgrade, mixed snapshots,
  and current-head runner ownership.

### HTTP and BFF tests

- session, Origin, CSRF, idempotency, and non-enumerating authorization;
- closed scenario-to-Case discovery and zero/ambiguous cardinality;
- role rotation on the same Case and cross-Case rejection;
- strict request, response, receipt, and Problem JSON schemas;
- malformed UUID, extra field, wrong version, body limit, enum, and content type;
- immutable receipt replay followed by fresh GET;
- response-size and upstream transport boundaries;
- locale remains presentation-only;
- no execution endpoint creates an AgentTask or SSE stream.

### Web tests

- full page/region/action state matrix;
- current action and owner remain first in DOM;
- attestation and advisor verification role boundaries;
- partial optional guidance failure preserves the execution workspace;
- lost acknowledgement, stale tab, session change, reload, and CSRF recovery;
- keyboard, focus, live-region, contrast, reduced motion, zoom, and reflow;
- one active bounded recovery envelope after server revalidation.

### Browser and database proof

The normal containerized proof covers exact `zh-CN` and `en` Happy and Blocked
scenarios:

1. server-owned session and Case context;
2. `plan_ready` to explicit execution start;
3. current checkpoint, owner, due date, and deterministic current action;
4. family attestation and immutable receipt;
5. advisor `request_update` or `verify`;
6. atomic activation of the next checkpoint;
7. reload, lost-ack reconciliation, stale tab, and role rotation;
8. blocked attestation and advisor reassessment;
9. terminal handoff and fail-closed later mutation;
10. database proof of exact execution history and zero successor
    `PlanningRun`, `AdvisorReview`, `FamilyDecision`, `DecisionReceipt`,
    `TimelinePlan`, execution, and `AgentTask` rows;
11. responsive and accessibility matrix.

## Verification, CI, and Docker Boundary

Every implementation PR runs proportional targeted gates followed by one
authoritative full gate. Applicable commands include:

```text
uv lock --check
Ruff
Pyright
frontend lint
frontend typecheck
frontend unit tests
frontend production build
focused authority tests
make check
make proof
make compose-proof when the changed boundary is containerized
```

Public evaluator commands remain:

```text
make doctor
make proof
make demo
make compose-proof
make down
```

No third public proof command is introduced. Internal focused verifier scripts
may be called by existing Make targets or CI.

README and operations documentation distinguish:

- quick provider-free contract proof;
- manual walkthrough;
- full browser-to-database Compose proof.

Each path states prerequisites, expected stable success markers, proof
boundary, cleanup, and measured cold/warm observations after implementation.
Full Compose is not promised to complete in under five minutes.

Long-running proof output identifies build, health, migration, API, browser,
database, and teardown phases. Failures state problem, safe cause category,
next action, and the last successful phase without exposing sensitive content.

Heavy gates record host and Docker VM available space independently and enforce
the repository minimum. Each proof uses one task-owned
`COMPOSE_PROJECT_NAME`, records before/after project, container, image, cache,
network, and volume inventory, and explicitly tears down only task-owned
resources.

The protected `night-voyager_postgres-data` volume and shared images/cache are
retained. Broad prune, daemon configuration, proxy configuration, source
replacement, and deletion of unrelated resources are outside scope.

Hosted `python`, `frontend`, and `compose` checks remain required. CI duration,
proof phase duration, and cold/warm local observations are measured after the
new lanes exist; workflow timeout or sharding changes require observed evidence.
No product analytics or remote telemetry is added.

## Delivery Slices

### PR A: Execution authority and minimal functional vertical

Scope:

- migration `0014`;
- execution/checkpoint/attestation/verification/reassessment/receipt domain and
  database authority;
- deterministic current-action projection;
- role-safe Case/session/CSRF discovery;
- FastAPI and transport-only BFF contracts;
- minimal functional `/demo/plan` showing current checkpoint, owner, due date,
  current action, attestation, verification, and completion;
- migration, HTTP, error, and evaluator documentation.

Exit evidence:

- a user can identify the current checkpoint, owner, due date, required action,
  and next human handoff;
- start, progress, completion, advisor verification, and final completion are
  durable and recoverable;
- immutable receipt replay remains exact after later transitions;
- no AgentTask, worker, SSE, provider, or successor business row is created;
- all authority, migration, query-plan, and minimal browser counterfactuals
  pass.

Rollback:

- web and BFF surfaces can be reverted without deleting history;
- empty execution history permits exact downgrade;
- retained history causes downgrade refusal;
- application entry points may be disabled while preserving audit records.

### PR B: Blocked reassessment and recovery closure

Scope:

- blocked and PostgreSQL-owned overdue triggers;
- successor-safe terminal handoff;
- stale tab, shared-cookie role rotation, CSRF recovery, and lost
  acknowledgement reconciliation;
- complete Happy/Blocked exact `zh-CN` and `en` browser-to-database proof;
- terminal non-claims and operations documentation.

Exit evidence:

- blocked users understand why execution stopped and who owns the next action;
- reassessment creates one terminal request and exact handoff;
- subsequent attestation and verification fail closed;
- no successor planning, decision, timeline, execution, or task mutation
  occurs;
- both locales and all required role/session recovery paths pass.

Rollback:

- web and recovery presentation can be reverted without deleting history;
- terminal records remain readable and immutable;
- no future successor contract is implied.

### PR C: Finding-gated presentation, DX, and release closure

Scope:

- rendered baseline and recorded P1/P2 findings;
- only the token, layout, surface, copy, accessibility, and responsive changes
  required to close those findings;
- preserve root portfolio and governed demo identities;
- evaluator-first README/docs index, HTTP examples, error catalog, migration
  runbook, contributor matrix, and bounded proof-failure issue template;
- representative visual evidence and release-surface preparation.

Exit evidence:

- no unresolved P1 presentation or DX finding;
- every P2 finding is fixed or has a reviewed disposition;
- 1440/768/390/320, 200% zoom, keyboard, focus, live-region, contrast, and
  bilingual proof pass;
- quick and full proof paths show expected output, measured observations,
  failure recovery, and teardown;
- routes without a recorded finding are not rewritten;
- no domain, database, authority, or transition change is hidden in the
  presentation slice.

Rollback:

- presentation-only changes can be reverted while the complete functional
  execution journey remains intact.

## Sequencing and Release

The three PRs are serial:

```text
PR A execution authority + minimal vertical
  -> PR B reassessment + recovery closure
  -> PR C presentation + DX + release closure
  -> v0.1.5 release preparation and release gates
```

Implementation is serial because the slices share migration head, HTTP DTOs,
session recovery, execution state, browser semantics, and presentation DOM.
After contracts freeze, only test fixtures, semantic test skeletons, and a
read-only rendered baseline may be prepared independently.

The approved spec and plans remain leading commits on the first implementation
branch. They do not require a separate documentation-only PR or duplicate
hosted CI. Each implementation PR may merge independently, but no intermediate
release is created. `v0.1.5` is released only after PR C and merged-main
verification.

The release candidate binds:

- exact merged `main`;
- migration head `0014`;
- reviewed feature trees;
- successful hosted `python`, `frontend`, and `compose` checks;
- normal merged-main provider-free proof;
- current release documentation and immutable prior release records.

## Documentation Impact

Implementation updates the affected surfaces only as they become true:

- accepted execution authority ADR;
- timeline execution HTTP and database reference;
- execution operations and current-development migration runbooks;
- evaluator-first walkthrough and public error recovery catalog;
- product state/interaction matrix;
- bilingual README and docs index;
- contributor change-to-test matrix and safe proof-failure issue template;
- design documentation and representative visual evidence;
- spec and implementation-plan status;
- release notes and source-archive verification only during release
  preparation.

Existing AgentTask, worker, SSE, and Skill documentation remains
planning-specific. This stage does not claim that execution guidance uses that
infrastructure.

Published `v0.1.0` through `v0.1.4` release notes and verification guides remain
immutable.

## Acceptance Boundary

The design is complete only when:

- the immutable planning anchor and separate execution authority are proven;
- every mutation is role-scoped, versioned, idempotent, and recoverable;
- family input is represented as structured attestation, not source Evidence;
- advisor verification is the only trust-upgrade action;
- deterministic current-action guidance is synchronous and non-authoritative;
- blocked or overdue work reaches a durable human-gated
  `reassessment_required` stop with a successor-safe handoff;
- no post-decision replan, replacement decision, successor timeline,
  successor execution, AgentTask, or worker operation occurs;
- the complete bilingual browser-to-database flow is provider-free and
  reproducible;
- user-facing proof explains current action, next human owner, stop reason,
  expected output, recovery, and teardown;
- presentation changes are finding-gated and preserve the two intentional
  visual identities;
- public documentation preserves the local synthetic and non-production
  boundaries.
