# Governed Plan Execution and Reassessment

**Status:** Approved design; implementation has not started.

## Summary

Night Voyager currently turns a governed family decision into an immutable
`DecisionReceipt` and `TimelinePlan`. This design extends that boundary with a
durable, role-scoped execution ledger. Assigned family participants can report
progress, an assigned advisor can verify completed checkpoints, and a bounded
Agent task can propose the next action without owning business state.

The execution loop stops fail-closed at `reassessment_required`. It does not
silently reuse the pre-decision revision flow, create a new `PlanningRun`, or
replace the final family decision. Reassessment, replacement decisions, and a
successor timeline require a separately approved future design.

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

The existing `TimelinePlan` is immutable and contains only the selected country,
intake, and ordered milestone dates. Existing planning revision authority is
deliberately limited to the period before `FamilyDecision` and `TimelinePlan`.
Finalized Cases must not be routed back through that revision contract.

The existing `AgentTask` ledger already owns durable claim, bounded lease,
heartbeat, retry, cancellation, generation fencing, event replay, and SSE
recovery. Its operation and result contracts remain planning-specific. The new
feature may generalize those operation-specific seams, but must continue to use
the same durable task infrastructure rather than introduce another queue.

## Goals

The implementation must:

1. Turn the immutable `TimelinePlan` into an explicit, durable execution
   workspace without mutating the plan or family decision.
2. Preserve a closed role boundary between family reporting, advisor
   verification, deterministic state transitions, and Agent proposals.
3. Support idempotent mutation, reload recovery, task restart, SSE reconnect,
   and stale-result rejection.
4. Provide a provider-free next-action proposal task whose output remains a
   non-authoritative candidate.
5. Surface overdue and blocked work without changing state during a read.
6. Stop at a durable `reassessment_required` state that requires future human
   and product authorization.
7. Add a bilingual execution workspace and complete a focused professional
   visual-system pass before the `v0.1.5` release.

## Non-Goals

This design does not:

- mutate or replace an existing `FamilyDecision`, `DecisionReceipt`, or
  `TimelinePlan`;
- create a post-decision `StudentCaseRevision`, `PlanningRun`, `AdvisorReview`,
  family decision, receipt, or timeline;
- automatically replan, select a new country, or resume from
  `reassessment_required`;
- connect to school application portals, email, payment, calendar, CRM,
  messaging, or notification systems;
- upload or retain passports, transcripts, financial records, visa documents,
  or other user files;
- add a scheduler, Redis, Celery, Temporal, Kafka, Kubernetes, or a second task
  queue;
- require a paid model, remote Agent, DRA provider, credential, or live
  acceptance attempt;
- change the existing strict DRA consumer status or authorize another provider
  attempt;
- claim production deployment, real student or school coverage, advisor-team
  adoption, admissions results, time savings, business impact, HA, SLA, or an
  audit-zero dependency state.

## Product Flow

```text
plan_ready
  -> explicit family start
  -> execution_active
  -> family progress/completion/blocked report
  -> advisor verification
       -> request_update -> execution_active
       -> verify -> next checkpoint
       -> verify final checkpoint -> execution_completed

execution_active
  -> blocked report or server-derived overdue risk
  -> explicit advisor reassessment
  -> reassessment_required
  -> stop

execution_active
  -> bounded AgentTask
  -> next-action proposal candidate
  -> family may use or ignore the proposal
```

An Agent proposal never advances a checkpoint, verifies a report, opens
reassessment, or completes an execution.

## Authority Model

### Immutable planning anchor

`TimelinePlan` remains the immutable planning artifact. Execution records copy
the exact milestone keys, order, and due dates into a versioned execution
snapshot. The copied values must match the canonical plan exactly at creation
time and cannot be supplied or changed by the browser.

### Execution state

`TimelineExecutionV1.state` is one of:

- `active`
- `reassessment_required`
- `completed`

Only one execution may exist for a `TimelinePlan`. Starting the execution is an
explicit mutation by an assigned family participant. The existing
`StudentCase.state` remains `plan_ready`; the decision lifecycle is not reused
as execution state authority.

Every execution has a positive `row_version`. Mutations must bind the expected
execution version and the immutable decision/timeline identity.

### Checkpoint state

`TimelineCheckpointV1.state` is one of:

- `pending`
- `in_progress`
- `awaiting_advisor`
- `verified`
- `blocked`

The first checkpoint begins as `in_progress`; later checkpoints begin as
`pending`. Only the first unverified checkpoint is mutable. A later checkpoint
cannot start early, and a verified checkpoint cannot be reopened.

The deterministic responsibility policy is:

| Milestone | Accountable role |
| --- | --- |
| `documents` | `student` |
| `application` | `student` |
| `visa` | `student` |
| `arrival` | `parent` |

The assigned advisor verifies completion. The accountable family role reports
progress, completion, or blockage. A participant outside the assigned Case or
an actor with the wrong role receives a non-enumerating unavailable response.

### Risk projection

`risk_state` is derived as:

- `on_track`
- `due_soon`
- `overdue`

It is calculated from the immutable due date and a trusted server clock. A
read does not create an event or mutate execution state. Tests use an injected
clock; production code does not accept a client-supplied authoritative date.

### Reports

`TimelineCheckpointReportV1.report_kind` is one of:

- `progress`
- `completion`
- `blocked`

A `progress` report is append-only and leaves the checkpoint `in_progress`.
A `completion` report moves it to `awaiting_advisor`. A `blocked` report moves
it to `blocked`.

Reports accept closed `evidence_kind` and `reason_code` enums only. The first
release does not accept free-form narrative, URLs, filenames, uploaded bytes,
or external account identifiers.

### Advisor verification

`TimelineCheckpointVerificationV1.action` is one of:

- `verify`
- `request_update`

`verify` is valid only for the latest `completion` report on the current
checkpoint. It marks that checkpoint `verified` and atomically activates the
next checkpoint. Verifying the final checkpoint atomically marks the execution
`completed`.

`request_update` preserves the report and verification history, then returns
the current checkpoint to `in_progress`.

### Reassessment

Only the assigned advisor may create
`TimelineReassessmentRequestV1`. Its trigger is one of:

- `blocked_report`
- `deadline_elapsed`

`blocked_report` must bind the current durable blocked report.
`deadline_elapsed` must bind a server-derived `overdue` projection for the
current checkpoint.

Creation atomically changes the execution to `reassessment_required`. New
reports, verifications, or next-action tasks then fail closed. The request is
append-only and has no resume, replace, or resolve operation in `v0.1.5`.

## Data Model

Migration `0014` introduces:

### `app.timeline_executions`

- organization, execution, Case, family decision, and timeline identities;
- schema version and execution state;
- positive row version;
- created and updated timestamps;
- one execution per timeline plan;
- exact foreign keys through organization and Case authority.

### `app.timeline_checkpoints`

- execution and milestone identity;
- immutable ordinal, milestone key, due date, and accountable role;
- checkpoint state and positive row version;
- report and verification timestamps where applicable;
- unique milestone key and unique ordinal per execution.

### `app.timeline_checkpoint_reports`

- execution and checkpoint identity;
- reporter identity and role;
- report kind, evidence kind, and reason code;
- checkpoint version observed by the request;
- canonical request hash and created timestamp;
- append-only history.

### `app.timeline_checkpoint_verifications`

- execution, checkpoint, and report identity;
- advisor identity;
- action and closed reason code;
- checkpoint version observed by the request;
- canonical request hash and created timestamp;
- append-only history.

### `app.timeline_reassessment_requests`

- execution and checkpoint identity;
- assigned advisor identity;
- exact trigger and trigger reference;
- execution/checkpoint versions observed by the request;
- canonical trigger projection hash;
- created timestamp;
- at most one request per execution.

All new tables use forced RLS and tenant-scoped policies. API and worker roles
may mutate them only through narrow `SECURITY DEFINER` functions that validate
the trusted `ActorContext`, assigned Case membership, role, state, row version,
and idempotency record before mutation.

Migration `0014 -> 0013` must refuse before mutation when any execution history
exists. Empty-schema downgrade must restore the exact prior catalog and grants.

## Agent Task and Proposal Contract

Migration `0015` adds the provider-free proposal operation while retaining the
existing task ledger and worker:

```text
propose_timeline_checkpoint_action_v1
```

The packaged runtime identity is:

- Skill: `plan-execution-guide@1.0.0`
- adapter: `deterministic_timeline_next_action@v1`
- input contract:
  `night-voyager.timeline-checkpoint-action-input.v1`
- output contract:
  `night-voyager.timeline-next-action-proposal.v1`

The task binds:

- organization and Case;
- current Case revision;
- immutable family decision and timeline identity;
- execution identity and version;
- current checkpoint identity and version;
- exact milestone projection hash;
- exact Skill version, activation event, runtime manifest, operation leaf, and
  adapter identity.

`TimelineNextActionProposalV1` contains:

- schema version;
- execution, checkpoint, and observed checkpoint-version identities;
- `action_code`;
- one to eight closed `checklist_codes`;
- zero to eight closed `risk_codes`;
- a bounded non-authoritative explanation;
- canonical input and output SHA-256 values;
- exact Skill and adapter identity.

The explanation is display material only. State transitions use none of its
content.

The existing task, execution, and event records gain nullable
execution/checkpoint subject fields and a proposal result reference. Database
constraints enforce planning-result versus proposal-result exclusivity.
Existing planning tasks retain their exact contract and behavior.

The worker gains an operation-handler boundary:

- the existing planning handler preserves current behavior;
- the new checkpoint handler validates the closed proposal contract;
- claim, start, heartbeat, failure, retry, generation fencing, event emission,
  and recovery stay shared.

Only one effective next-action task may exist for a checkpoint row version. A
proposal bound to an older checkpoint version remains immutable history but is
not current. Stale output fails before proposal persistence.

Migration `0015 -> 0014` refuses before mutation when proposal/task history
using the new operation exists.

## HTTP Contract

New FastAPI endpoints:

```text
POST /api/v1/timeline-plans/{timeline_plan_id}/executions
GET  /api/v1/cases/{case_id}/timeline-execution
POST /api/v1/timeline-executions/{execution_id}/checkpoint-reports
POST /api/v1/timeline-executions/{execution_id}/checkpoint-verifications
POST /api/v1/timeline-executions/{execution_id}/next-action-tasks
POST /api/v1/timeline-executions/{execution_id}/reassessments
```

The existing task read, cancellation, recovery, and SSE endpoints serve the new
proposal task after they are generalized to an operation-aware public
projection.

Every request model:

- uses `extra="forbid"`;
- requires an exact schema version;
- accepts only closed enums and bounded collections;
- omits tenant and actor authority fields;
- requires expected execution/checkpoint versions for mutations.

Every mutation requires the existing session, Origin, CSRF, and an
`Idempotency-Key` of the current bounded format.

The Next.js BFF mirrors the same routes as transport-only handlers. It does not
derive roles, state, due dates, proposal currency, or verification eligibility.

Closed public problem codes include:

- `resource_unavailable`
- `invalid_idempotency_key`
- `idempotency_conflict`
- `stale_execution_version`
- `checkpoint_not_current`
- `checkpoint_report_conflict`
- `advisor_verification_required`
- `proposal_snapshot_stale`
- `reassessment_required`
- `execution_completed`
- `skill_pin_invalid`

Authorization failures remain non-enumerating. Conflicts expose a stable code
but not internal SQL, stack traces, tenant identity, or hidden resource state.

## Idempotency, Concurrency, and Reconciliation

For every mutation, PostgreSQL owns:

```text
organization + actor + operation + key_hash
  -> request_hash + durable response identity
```

The same key and same canonical request return the same durable response. The
same key with a different request returns `idempotency_conflict`.

Execution and current checkpoint rows are locked before validation. A
verification, reassessment, or final task result must match the expected
versions after the lock is acquired. Concurrent requests may produce only one
accepted transition.

Browser recovery uses a bounded local ledger containing:

- Case and execution identity;
- current proposal task identity;
- last durable SSE cursor;
- operation-specific idempotency slots.

Browser storage is never business authority. Reload first reads the durable
execution and task projection. If the expected result already exists, the UI
converges without another mutation. If it does not exist, only an explicit
recovery action may replay the exact prior body with the same key. Recovery
must never mint a new key automatically.

SSE replay uses the existing durable event cursor. A cursor ahead of the
durable stream fails closed. Reconnect never creates a second task.

## Failure Model

The implementation distinguishes:

### Authority failures

- wrong tenant, actor, assigned Case, or role;
- execution not bound to the final timeline;
- checkpoint not current;
- report or verification references stale state;
- reassessment trigger not proven by a current blocked report or overdue risk.

### Idempotency and concurrency failures

- same key with a different canonical request;
- stale row version;
- duplicate execution or effective task;
- concurrent advisor verification;
- lost acknowledgement followed by an incompatible retry.

### Agent and worker failures

- missing or stale Skill pin;
- wrong operation leaf or adapter identity;
- stale execution/checkpoint input snapshot;
- malformed, extra-field, oversized, or cross-subject output;
- lease loss, heartbeat loss, retry exhaustion, or stale finalize replay.

### Projection and browser failures

- BFF/API envelope mismatch;
- response-size or schema failure;
- browser ledger that disagrees with durable state;
- SSE cursor regression or duplicate task observation;
- locale affecting an authority field;
- role transition that exposes an action owned by another role.

All failures preserve previously accepted authority records. No failure path
creates a replacement family decision or timeline.

## Privacy and Retention

The feature stores only synthetic structured workflow records. It accepts no
uploaded file, arbitrary URL, filename, free-form application narrative,
credential, school account, payment information, or external message content.

Reports, verifications, proposals, and reassessment requests are append-only
audit history. There is no public delete endpoint. Task-scoped integration
fixtures and Compose resources are removed through the existing exact teardown
contract; the protected shared PostgreSQL volume and shared images/cache remain
outside task cleanup.

Logs and browser responses expose only stable public codes and bounded
identities. They do not expose SQL, stack traces, secret values, private local
paths, or content-bearing evidence.

## Web Product and Information Architecture

The feature adds `/demo/plan` as a dedicated execution workspace. The existing
`/demo` remains the decision and planning-revision journey.

The workspace contains:

1. **Product header:** Case context, active role, selected route, and execution
   status.
2. **Workspace navigation:** `Overview`, `Plan`, and `Activity`.
3. **Timeline rail:** ordered checkpoints, accountable role, due date, risk,
   and verification state.
4. **Current checkpoint workbench:** current proposal, checklist, reporting
   actions, and advisor verification.
5. **Activity ledger:** reports, verifications, proposal tasks, and
   reassessment history.
6. **Terminal state:** explicit completed or reassessment-required surface.

The UI must not compress the entire lifecycle into an undifferentiated stack of
cards. Decision context, execution work, and audit history have separate visual
hierarchy.

The functional workspace and the later presentation pass are separate review
surfaces:

- the functional journey establishes routes, state, recovery, accessibility
  semantics, and stable component boundaries;
- the presentation pass unifies typography, spacing, color, surfaces,
  navigation, status, and responsive composition across `/`,
  `/demo/collaboration`, `/demo`, and `/demo/plan`;
- the presentation pass may not change API, database, persistence, role, or
  state-machine contracts.

The final release must support exact `zh-CN` and `en`, keyboard operation,
visible focus, sufficient contrast, reduced motion, and no horizontal overflow
at 1440, 768, and 390 CSS pixels.

No unresolved P1 design finding may enter the release. Every P2 finding must be
fixed or have an explicit reviewed disposition.

## Testing Strategy

### Domain and contract tests

- canonical schema round-trip and extra-field rejection;
- exact checkpoint ordering and responsibility policy;
- report, verification, risk, completion, and reassessment transitions;
- Agent proposal output bounds and authority exclusion;
- stable public problem codes.

### PostgreSQL integration and security tests

- forced RLS and runtime-role grants;
- assigned participant and advisor role matrix;
- one execution per timeline;
- exact timeline copy and immutable checkpoint identity;
- ordered checkpoint mutation;
- append-only history;
- idempotent replay and request-hash mismatch;
- row-version concurrency;
- final checkpoint atomic completion;
- read-only overdue projection;
- reassessment trigger proof;
- safe upgrade, empty downgrade, history refusal, and mixed-snapshot lanes.

### Worker tests

- existing planning behavior remains unchanged;
- operation-handler dispatch;
- exact Skill and adapter pin;
- stale snapshot rejection;
- malformed and oversized proposal rejection;
- claim, heartbeat, lease loss, bounded retry, restart, lost finalize
  acknowledgement, and generation fencing;
- one effective task and one durable proposal per checkpoint version;
- proposal persistence never mutates execution authority.

### HTTP and BFF tests

- session, Origin, CSRF, idempotency, and non-enumerating authorization;
- strict request and response schemas;
- problem JSON and response-size boundaries;
- role-safe execution projections;
- reload and mutation reconciliation;
- exact SSE cursor recovery and no second task;
- locale remains presentation-only.

### Browser and database proof

The normal containerized proof must cover both `zh-CN` and `en`:

1. `plan_ready` to explicit execution start;
2. family role transition to the accountable participant;
3. provider-free next-action task and SSE;
4. completion report and advisor verification;
5. atomic activation of the next checkpoint;
6. reload, reconnect, and worker restart with the same task and cursor;
7. blocked report and advisor reassessment;
8. fail-closed mutation after `reassessment_required`;
9. database proof that no new planning run, family decision, receipt, or
   timeline was created;
10. desktop and mobile workspace behavior.

## Verification and Docker Boundary

Every implementation PR runs the checks proportional to its change, including:

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

Heavy gates record host and Docker VM available space independently and enforce
the repository minimum. Each proof uses one task-owned
`COMPOSE_PROJECT_NAME`, records before/after project, container, image, cache,
network, and volume inventory, and explicitly tears down only task-owned
resources.

The protected `night-voyager_postgres-data` volume and shared images/cache are
retained. Broad prune, daemon configuration, proxy configuration, source
replacement, and deletion of unrelated resources are outside scope.

## Delivery Slices

### PR 1: Execution authority

Scope:

- migration `0014`;
- execution/checkpoint/report/verification/reassessment domain, ports,
  application service, PostgreSQL adapter, and FastAPI contracts;
- RLS, grants, migration, authority, idempotency, concurrency, and reference
  documentation.

Exit evidence:

- all authority and migration counterfactuals pass;
- no Agent or web journey claim;
- current planning/revision behavior remains unchanged.

Rollback:

- empty history permits exact downgrade;
- retained history causes downgrade refusal;
- application entry points may be reverted while preserving recorded history.

### PR 2: Provider-free next-action task

Scope:

- migration `0015`;
- task/result generalization and operation handler;
- packaged Skill, deterministic adapter, proposal model, evaluator fixtures,
  worker persistence, public task projection, and SSE;
- provider-free rehearsal and worker recovery documentation.

Exit evidence:

- exact pin, restart, retry, stale snapshot, and lost-ack counterfactuals pass;
- no second queue or worker;
- no execution state mutation from proposal output.

Rollback:

- empty proposal history permits exact downgrade;
- retained history causes downgrade refusal;
- the operation may be disabled without deleting task/proposal history.

### PR 3: Functional execution journey

Scope:

- `/demo/plan`;
- BFF routes, strict web contracts, bounded local recovery ledger, reducer,
  hook, workspace components, bilingual copy, and connected demo handoff;
- complete provider-free browser-to-database proof and operations docs.

Exit evidence:

- both locales pass happy, reload/restart, lost-ack, and reassessment flows;
- desktop and mobile functional behavior passes;
- no presentation-completion claim.

Rollback:

- web and BFF surfaces can be reverted without deleting execution history.

### PR 4: Professional presentation closure

Scope:

- shared visual tokens and application-shell hierarchy;
- navigation, typography, spacing, surfaces, status, timeline, responsive
  composition, focus, contrast, and reduced-motion treatment;
- visual evidence for `/`, `/demo/collaboration`, `/demo`, and `/demo/plan`;
- no domain, database, API, task, or persistence changes.

Exit evidence:

- 1440, 768, and 390 viewport proof;
- functional browser regressions remain green;
- no unresolved P1 design finding;
- every P2 finding has a reviewed disposition.

Rollback:

- presentation-only revert leaves the complete functional journey intact.

## Sequencing and Release

The four PRs are serial:

```text
PR 1 authority
  -> PR 2 Agent task
  -> PR 3 functional journey
  -> PR 4 presentation closure
  -> v0.1.5 release preparation and release gates
```

PR 2 depends on the PR 1 schema and transitions. PR 3 depends on both public
contracts. PR 4 depends on stable PR 3 DOM, copy, and state. Parallel
implementation would create more schema, selector, copy, and visual rework than
it saves.

The approved spec and plans remain leading commits on the first implementation
branch. They do not require a separate documentation-only PR or duplicate
hosted CI. Each implementation PR may merge independently, but no intermediate
release is created. `v0.1.5` is released only after PR 4 and merged-main
verification.

The release candidate must bind:

- exact merged `main`;
- migration head `0015`;
- reviewed feature trees;
- successful hosted `python`, `frontend`, and `compose` checks;
- normal merged-main provider-free proof;
- current release documentation and immutable prior release records.

## Documentation Impact

Implementation updates the affected surfaces as they become true:

- accepted ADR for execution authority;
- HTTP, task/event, Skill, state, and database reference;
- connected demo and worker operations guides;
- product state/interaction matrix;
- bilingual README and docs index;
- visual-system/design documentation;
- spec and implementation-plan status;
- release notes and source-archive verification only during release
  preparation.

Published `v0.1.0` through `v0.1.4` release notes and verification guides remain
immutable.

## Acceptance Boundary

The design is complete only when:

- the immutable planning anchor and separate execution authority are proven;
- every mutation is role-scoped, versioned, idempotent, and recoverable;
- Agent output remains a non-authoritative candidate;
- blocked or overdue work reaches a durable human-gated
  `reassessment_required` stop;
- no post-decision replan or replacement decision occurs;
- the complete bilingual browser-to-database flow is provider-free and
  reproducible;
- professional presentation closure is finished before release;
- public documentation preserves the local synthetic and non-production
  boundaries.
