# Night Voyager DRA Strict Consumer and Versioned Planning Revision Design

## Status

**Design status:** Approved; PR 1 implemented provider-free; PR 2 and PR 3 approved but not implemented.

### Current runtime correction after PR 1

Night Voyager now implements the provider-free strict-consumer prerequisite:
migration head `0011`, the exact post-release commit pin,
`generic-strict-citation@1`, `dra.strict-citation-profile.v1`, closed v1/v2
candidate import on the existing endpoint, durable strict identity, V3
readiness, and strict outcome evaluation. No provider, candidate freeze, third
live attempt, release, or deployment was performed. The two prior 25/83
`uncited` attempts remain failed pre-import history and strict live acceptance
remains incomplete. Planning revision PR 2 and journey PR 3 remain approved but
not implemented.

This design defines two ordered capabilities after the `v0.1.3` release:

1. a provider-free Night Voyager consumer prerequisite pinned to the immutable
   Decision Research Agent strict-citation contract; and
2. a pre-final-decision planning revision loop with durable lineage,
   deterministic old/new comparison, and renewed human authorization.

The two capabilities are delivered through three serial pull requests. Each pull
request must remain independently reviewable, testable, mergeable, and
rollback-aware. They are not three separate releases. The default publication
boundary is one Night Voyager release after the third pull request is merged and
the merged-main release gates pass.

This design does not authorize another live-provider attempt. Two separately
authorized live attempts already stopped safely before candidate import because
the selected DRA `generic` profile returned no cited Evidence. Those attempts
remain incomplete evidence, not successful acceptance.

## Summary

Night Voyager already owns the business authority required to turn confirmed
student and family facts into a deterministic planning result, require an
assigned-advisor review, accept a family decision, and issue a
`DecisionReceipt` plus `TimelinePlan`.

It also owns a governed DRA consumer boundary:

- immutable producer identity;
- strict artifact and Evidence projection;
- `UNTRUSTED_CANDIDATE` import;
- assigned-advisor source attestation;
- atomic promotion;
- governed mixed planning;
- durable task, worker, event, and SSE execution;
- closed evaluation and candidate-freeze receipts.

The current DRA live request still selects `profile_id="generic"`. Two bounded
attempts returned respectively 25 and 83 same-run Evidence rows, all `uncited`,
and therefore stopped before candidate import. Decision Research Agent now
provides an opt-in, post-release strict profile at an immutable commit:

```text
repository       = https://github.com/iTao-AI/decision-research-agent
ref_kind         = commit
ref              = 01ba21f2996769e68cbc88f4bb0596740df27f6b
profile_id       = generic-strict-citation
profile_version  = 1
proof_schema     = dra.strict-citation-profile.v1
```

Night Voyager will adopt that exact tuple provider-free. It will not describe
the strict profile as part of the DRA `v0.1.6` release, because the latest DRA
release still peels to
`7d43324b469cb5e445c2e8be83af3be4d841cf1c`. An immutable commit pin is the
selected producer identity.

After that prerequisite, Night Voyager will add one bounded revision journey:

```text
advisor requests revision
-> student changes confirmed preferred countries
-> new Case revision records the exact predecessor PlanningRun
-> advisor explicitly starts a new planning task
-> new PlanningRun supersedes the retained predecessor
-> server produces a deterministic old/new comparison
-> advisor grants a new review for the new revision
-> only the current revision may reach family decision and timeline
```

The public happy path changes:

```text
student.preferred_countries
from [australia, japan, malaysia]
to   [australia, japan]
```

A lowered-budget scenario is retained as a negative proof. It must produce a
blocked revised run, preserve the comparison, and deny advisor and family
decision authority.

## Inspected baseline

### Night Voyager

- The inspected repository is clean
  `main@f42f9d25598c02e875dc895a71e244c177f0ffdc`, equal to
  `origin/main`.
- The latest annotated tag and GitHub Release remain `v0.1.3`, peeled to
  `a487ee2805e6e744abce8120bfba6cb90f8df87b`.
- Post-release main includes the DRA live consumer, capture, Stage 2-4 closure,
  candidate freeze, evaluation, and effective-query v2 contracts.
- The migration head is `0010`.
- Migration `0010` admits the DRA `v0.1.6` producer commit but still requires
  `profile_id="generic"`.
- Current runtime models and the live controller also require
  `profile_id="generic"`.
- The candidate ledger persists `producer_release`, `producer_commit`,
  `contract_schema`, `fixture_sha256`, and `profile_id`, but not
  `profile_version` or `proof_schema`.
- Historical DRA producer identities, fixture bytes, migrations, and published
  release documents must remain immutable.
- The existing `request_revision` advisor action returns a Case from
  `advisor_review` to `planning`.
- Confirmed facts already support immutable versions, supersession,
  role-scoped policy, complete current-fact references, and atomic Case
  revisions.
- `student.preferred_countries` is a student-owned fact.
- `PlanningRun` already has `supersedes_run_id` and `is_current`.
- Task creation, worker leases, idempotency, restart recovery, events, and SSE
  already exist.
- The connected demo exposes initial collaboration and advisor-to-family
  journeys, but not a complete post-review revision journey.

### Decision Research Agent

- The inspected repository is clean
  `main@01ba21f2996769e68cbc88f4bb0596740df27f6b`, equal to
  `origin/main`.
- The strict-profile reviewed tree and squash-merge tree are both
  `06e5282414d3801b11040bba735dd107105e8a30`.
- The latest release remains `v0.1.6`, peeled to
  `7d43324b469cb5e445c2e8be83af3be4d841cf1c`.
- The post-release strict profile is opt-in and preserves generic behaviour.
- A consumer opts in through the existing `profile_id` request field.
- The producer resolves and persists `profile_version="1"`.
- A strict ready result is valid only when its canonical current-run report
  contains at least one exact admitted public source URL.
- The model may select opaque source identifiers, but application code owns URL
  bytes, exact rendering, recomputation, persistence, and final delivery state.
- The strict profile adds no endpoint, database field, status, or error type to
  the public producer API.
- The generic downstream-consumer fixture remains byte-identical across DRA
  `v0.1.6`, current DRA main, and Night Voyager:
  `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157`.
- The strict profile does not prove source truth, citation correctness,
  citation completeness, source quality, entailment, provider quality, or
  production reliability.

## Problem

### The producer identity is overloaded

Night Voyager currently treats a producer release and producer commit as one
closed pair. That is valid for the released `v0.1.3` and `v0.1.6` producer
contracts, but not for a post-release capability pinned directly to a commit.

Writing `producer_release="v0.1.6"` for the strict profile would falsely imply
that the release contains the feature. A strict consumer therefore needs an
explicit tag-or-commit reference model.

### The current request cannot prove the selected strict policy

The outbound `profile_id` alone does not bind:

- the producer repository;
- immutable source ref;
- resolved profile version;
- proof schema;
- persisted candidate identity.

Those values do not all come from the same producer response. Night Voyager
must distinguish:

- consumer-owned pin identity: repository, ref kind, ref, commit, downstream
  contract, fixture hash, and proof schema;
- producer request identity: requested `profile_id` and canonical request hash;
- producer-observed identity: status `profile_id`, the existing single-profile
  manifest's `profile_id` and `version`, plus run, artifact, and Evidence
  identity.

The proof schema is verified from the exact-commit source contract and a
checked-in consumer constant. It is not claimed as a DRA request, status,
manifest, or result field. The three provenance sources must be reconciled
before candidate import and their closed identity must survive through
readiness, durable candidate storage, outcome projection, and evaluation.

### Planning lineage is inferred too late

The current worker loads `supersedes_run_id` by querying the PlanningRun that is
current at worker execution time. Confirming a changed fact already makes the old
run non-current. A later worker can therefore observe no predecessor and create
an unlinked run.

Lineage must be frozen before asynchronous execution begins.

### The connected projection is not revision-aware

The connected ledger currently reasons from the latest task rather than the
latest task for the current Case revision. After a fact change, an old task can
produce a revision mismatch instead of a stable `replan_required` state.

### A new plan without a comparison is not explainable

Retaining the old PlanningRun is necessary but insufficient. The product must
show:

- what confirmed fact changed;
- which countries were added, removed, changed, or unchanged;
- how each deterministic outcome and reason changed;
- whether the new run is eligible for advisor review;
- which human authorization applies to which revision.

The comparison must be server-owned and deterministic. A model-generated summary
cannot own these facts.

## Goals

1. Adopt the DRA strict profile through one immutable, provider-free consumer
   identity.
2. Preserve all legacy generic producer history without semantic rewriting.
3. Keep required CI deterministic, offline, and provider-free.
4. Freeze the exact predecessor PlanningRun before a revised task can execute.
5. Retain every prior run and review for audit while removing their current
   business authority.
6. Provide one deterministic old/new comparison keyed by country.
7. Require a fresh assigned-advisor authorization for the revised run.
8. Permit family decision, receipt, and timeline only for the current revision,
   current run, and current decision brief.
9. Demonstrate the complete journey in both `zh-CN` and `en`.
10. Preserve bounded idempotency, concurrency, recovery, SSE, privacy, and Docker
    lifecycle evidence.

## Non-goals

- A third DRA provider attempt.
- Reclassifying either prior live attempt as successful.
- Automatic candidate import or automatic Evidence promotion.
- Modifying DRA runtime, API, database, release, or repository.
- Waiting for or creating a new DRA release.
- A new DRA endpoint or public handoff artifact.
- Source truth, provider quality, school coverage, admissions outcome, or
  production reliability claims.
- Revisions after a final family decision or issued timeline.
- A generic multi-version history dashboard.
- Arbitrary fact editing or free-form JSON fact submission.
- Multiple predecessor comparisons in one product view.
- Model-owned fact confirmation, lineage, route eligibility, approval, or
  current-version selection.
- A new Agent framework, graph runtime, queue, business workflow, or authority
  database.
- Production deployment, distributed HA, SLA, or exactly-once claims.

## Decision and rejected alternatives

### Selected producer path: exact DRA commit pin

Night Voyager will pin DRA
`01ba21f2996769e68cbc88f4bb0596740df27f6b` and the exact strict tuple.

This is preferred because:

- the DRA consumer contract explicitly permits a tag or commit;
- the commit and tree are immutable;
- the strict profile has provider-free tests and hosted checks;
- it avoids an unknown release schedule;
- it does not bundle unrelated future producer changes;
- it preserves a truthful release boundary.

### Rejected: keep `generic`

The existing path has twice returned zero cited Evidence under the bounded live
scenario. Keeping it would preserve a known incompatibility between producer
delivery and Night Voyager source-selection authority.

### Rejected: wait for a new DRA release

A future tag could provide a friendlier label but no stronger semantic identity
than the already immutable commit. Waiting would block independent Night Voyager
work and could introduce unrelated producer drift.

### Rejected: new DRA endpoint or handoff artifact

The strict policy fits the existing request, status, result, artifact, and
Evidence surfaces. A second producer endpoint or export file would duplicate
authority and increase compatibility and retention risk.

### Selected product path: one pre-final-decision revision

The first product slice changes a student-owned preferred-country fact before
any family decision. It reuses existing collaboration, fact confirmation,
planning, advisor review, and family decision authority.

### Rejected: post-decision revision

Changing an already issued decision or timeline requires withdrawal, audit,
notification, and replacement semantics beyond the current bounded product
claim.

### Rejected: budget decrease as the public happy path

A lower budget is valuable as a blocked counterfactual, but it is less legible
than a destination-preference change and does not guarantee a new reviewable
route set.

### Rejected: model-generated comparison

A model can phrase a non-authoritative explanation, but it cannot determine the
fact delta, route delta, lineage, eligibility, or approval state. The first
version therefore uses only closed deterministic projections and localized
copy.

## Architecture

### Ordered capability flow

```text
PR 1: DRA strict consumer prerequisite
  immutable commit pin
  -> closed strict request identity
  -> provider-free projection and import contracts
  -> no live attempt

PR 2: durable revision authority
  request_revision review
  -> confirmed fact supersession
  -> Case revision lineage
  -> task-frozen predecessor
  -> successor PlanningRun
  -> deterministic comparison projection

PR 3: connected revision journey
  advisor request
  -> student change
  -> advisor confirmation
  -> explicit replan
  -> comparison
  -> renewed advisor approval
  -> current family decision and timeline
```

### Authority map

| Concern | Authority | Explicitly not authority |
| --- | --- | --- |
| Producer code identity | Exact DRA repository and commit pin | DRA release label alone |
| Strict delivery policy | Exact profile id, version, and proof schema | Request text or model acknowledgement |
| Artifact and Evidence transport | DRA status/result contract | Night Voyager business acceptance |
| Candidate admission | Night Voyager strict import contract | DRA cited or verified flags alone |
| Confirmed fact | Role-scoped advisor confirmation | Student proposal or model output |
| Case revision | PostgreSQL transaction | Browser session state |
| Planning predecessor | Frozen task/revision lineage | Worker-time current-run query |
| Route outcome | Deterministic planning policy | Model preference |
| Comparison | Server-owned closed projection | Client diff or generated prose |
| Advisor approval | Current assigned-advisor review | Prior review or DRA output |
| Family decision | Current brief plus assigned participant | Old run, old brief, or UI selection |
| Recovery | Durable database rows and idempotency ledger | Local browser memory |

## Capability A: strict DRA consumer prerequisite

### `DraProducerPinV2`

New strict operations use a closed v2 identity:

```json
{
  "schema": "night-voyager.dra-producer-pin.v2",
  "repository": "https://github.com/iTao-AI/decision-research-agent",
  "ref_kind": "commit",
  "ref": "01ba21f2996769e68cbc88f4bb0596740df27f6b",
  "commit": "01ba21f2996769e68cbc88f4bb0596740df27f6b",
  "consumer_contract_schema": "dra.downstream-consumer.v1",
  "consumer_fixture_sha256": "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157",
  "profile_id": "generic-strict-citation",
  "profile_version": "1",
  "proof_schema": "dra.strict-citation-profile.v1"
}
```

All fields are required and exact. Extra fields fail closed.

`ref_kind="release"` remains valid only for the existing legacy producer tuples.
`ref_kind="commit"` is required for the strict profile. The implementation must
not synthesize a release value for the strict row.

### Migration `0011`

Migration `0011` evolves the existing candidate ledger. It does not replace the
table or rewrite migrations `0005` or `0010`.

The candidate ledger adds:

- `producer_repository`;
- `producer_ref_kind`;
- `producer_ref`;
- `profile_version`;
- `proof_schema`.

Legacy rows are backfilled as release-referenced rows:

- repository is the exact DRA repository;
- `producer_ref_kind="release"`;
- `producer_ref=producer_release`;
- existing release, commit, contract, fixture, and generic profile are
  preserved;
- `profile_version` and `proof_schema` remain absent under the explicit legacy
  branch.

The backfill is a migration-owned exception to the immutable-row contract, not
a runtime capability. In one Alembic transaction, migration `0011` takes an
exclusive table lock, temporarily removes FORCE RLS for the table owner, and
disables only the existing candidate immutable trigger. It adds nullable
columns, updates only the five new fields on legacy rows, installs the closed
constraints, re-enables the trigger, and restores FORCE RLS before commit.
Success and injected-failure tests require the trigger and FORCE RLS flags,
legacy row bytes, function ACL/search paths, and Alembic version to be fully
restored.

New strict rows require:

- `producer_ref_kind="commit"`;
- `producer_ref=producer_commit=01ba21f...`;
- no fabricated producer release;
- exact strict profile id, version, and proof schema;
- the unchanged downstream-consumer contract and fixture hash;
- all current artifact, Evidence, request, selected-source, and actor gates.

A closed table constraint distinguishes the legacy branch from the strict
branch. Mixed tuples fail. The current
`app.import_dra_research_candidate(...)` signature remains the explicit legacy
wire; strict input uses a separate expanded overload. Both overloads have
closed signatures, fixed search paths, explicit grants, and replay tests.

Downgrade is allowed only when no strict commit-referenced candidate or
downstream row exists. Otherwise downgrade fails without partial mutation.
Refusal tests exact-compare catalog, function, ACL, RLS/trigger, row, and
Alembic-version snapshots. A separate empty-history test proves safe
downgrade/re-upgrade and restores the exact `0010` legacy function.

Migration `0011` also redefines `app.project_dra_live_outcome` so the durable
candidate identity cannot disappear before evaluation. Its strict projection
returns the candidate id plus repository, ref kind, ref, release-or-null,
commit, downstream contract, fixture hash, profile id, profile version, proof
schema, and request-identity hash. Safe downgrade restores the exact `0010`
function shape.

### Runtime and DTO evolution

New strict paths use versioned v2 models for:

- producer pin;
- outbound run request identity;
- observed single-profile manifest projection;
- terminal status/result projection;
- capture intent and receipts;
- candidate import;
- durable outcome projection and candidate evaluation;
- candidate readiness.

Historical v1 generic models remain readable for immutable history and
historical fixtures. They are not accepted for new strict readiness or import.

The live controller composes:

```json
{
  "profile_id": "generic-strict-citation",
  "query": "<exact effective-query v2 bytes>"
}
```

The controller reads only the existing allowlisted
`GET /api/profiles/generic-strict-citation` endpoint and projects
`profile.profile_id` plus `profile.version`. It does not add a DRA endpoint,
enumerate profiles, or perform a provider call. The terminal status must return
the requested profile id; the profile manifest must resolve version `"1"`;
`proof_schema="dra.strict-citation-profile.v1"` remains local exact-commit pin
authority.

The canonical request hash and the reconciled strict consumer identity are
bound across:

- provider-free scenario and outbound create request;
- accepted run receipt and terminal status/result projection;
- observed profile-manifest projection;
- selected Evidence and candidate import;
- durable candidate row and `DraLiveOutcomeProjectionV2`;
- evaluation report and readiness receipt.

Evaluation V2 derives candidate authority only from the database outcome. It
binds candidate id, durable candidate-identity digest, readiness digest,
request-identity digest, and outcome-projection digest. Scenario or readiness
data may be compared with that projection but cannot refill missing database
authority. Any profile-version, proof-schema, request-hash, or producer-pin
mismatch between candidate, readiness, outcome, and evaluation fails closed.

### Provider-free proof

Required CI provides deterministic fake scenarios for:

1. strict terminal success with exactly admitted cited public HTTPS Evidence;
2. zero-cited strict projection rejected before candidate import;
3. wrong profile id;
4. wrong profile version;
5. wrong proof schema;
6. wrong producer repository, ref, or commit;
7. generic and strict request identity collision;
8. cited URL mismatch between Evidence and canonical report;
9. legacy v1 readiness supplied to the strict path;
10. extra-field and malformed canonical JSON.

No required test performs network, credential, provider, or GitHub access.

An optional source-proof may inspect a caller-supplied DRA checkout at the exact
commit. It must remain provider-free and must not become required CI.

### Candidate freeze and live boundary

The prerequisite pull request may test candidate-freeze code paths with
controlled provider-free evidence. It does not operationally issue a new
candidate readiness for live acceptance and does not consume another live
authorization.

The two prior live attempts remain:

- attempt one: 25 same-run Evidence, cited count zero;
- attempt two: 83 same-run Evidence, cited count zero;
- both stopped before selection and import;
- neither is rewritten as a strict-profile attempt;
- neither becomes successful acceptance.

Any future live attempt requires a new design and explicit authority. This
design grants none.

## Capability B: versioned planning revision

### Product scenario

The bounded happy path begins after an initial PlanningRun reaches
`advisor_review` and before any family decision.

1. The assigned advisor submits `request_revision` for the current run and
   exact Case revision.
2. The Case returns to `planning`; the immutable review records the request.
3. The connected session explicitly rotates to the assigned student.
4. The student proposes
   `student.preferred_countries=[australia,japan]`.
5. The assigned advisor confirms the proposal through the existing
   collaboration authority.
6. Confirmation creates the next Case revision and records the exact
   request-review and predecessor PlanningRun.
7. The assigned advisor explicitly creates a new planning task.
8. The task freezes the predecessor identity.
9. The worker creates one successor PlanningRun with
   `supersedes_run_id=predecessor`.
10. The server projects a deterministic old/new comparison.
11. The assigned advisor approves the new run.
12. A currently assigned student or parent makes the family decision.
13. The current brief produces a new `DecisionReceipt` and `TimelinePlan`.

No step is automatic merely because a fact was proposed or confirmed.

### Migration `0012`

Migration `0012` adds lineage to existing records rather than creating a second
workflow.

`student_case_revisions` gains:

- `revision_requested_by_review_id`;
- `superseded_planning_run_id`.

For an initial revision both are null. For a post-review fact revision both are
required and must bind:

- the same organization and Case;
- the immediately previous Case revision;
- the current predecessor PlanningRun for that previous revision;
- an immutable assigned-advisor review with
  `action="request_revision"`;
- no family decision or timeline for that predecessor.

`agent_tasks` gains:

- `predecessor_planning_run_id`.

For initial planning it is null. For revision planning it must equal the
revision's `superseded_planning_run_id`.

Migration `0012` owns every affected SQL authority function as one atomic
catalog change: advisor review, fact confirmation, task creation, task
finalization, and PlanningRun persistence. It freezes each signature, fixed
search path, and API/worker/PUBLIC grant. The finalizer locks the task row,
requires any compatibility caller predecessor to equal the task-owned value
with null-safe equality, and supplies only the task-owned predecessor to
persistence.

Database uniqueness closes:

- one `request_revision` review per PlanningRun;
- one revision lineage row per predecessor;
- one current task per Case revision;
- one successor PlanningRun per predecessor.

No existing PlanningRun, AdvisorReview, DecisionBrief, family decision, receipt,
or timeline is deleted.

Downgrade refuses when revision-lineage rows or revision tasks exist. Refusal
must leave catalog, functions, grants, RLS/trigger flags, rows, and
`alembic_version` byte-for-byte equivalent to the before snapshot. A separate
empty-history round trip proves safe downgrade to exact `0011` and re-upgrade.

### `request_revision` authority

The existing review function remains the only mutation entry.

It must reject:

- wrong tenant;
- unassigned advisor;
- stale Case revision;
- non-current PlanningRun;
- run not in `advisor_review`;
- already decided or plan-ready Case;
- replay with a different payload;
- a second revision request for the same run;
- `reject` presented as `request_revision`;
- any eligible-route payload that does not match the closed action contract.

The successful transaction:

- inserts one immutable `AdvisorReview`;
- moves the Case to `planning`;
- keeps the predecessor run current until a changed fact is confirmed;
- creates no task and no successor run.

Same-key/same-payload requests replay that review; same-key/different-payload
requests return the public idempotency conflict. Different-key overlap is
serialized by fixed Case-then-run locking plus a partial unique index on the
request action. Exactly one review, audit record, and authority result survives;
the loser receives a stable closed conflict rather than a raw database error.

### Confirmed fact revision authority

The existing collaboration candidate and verification APIs are reused.

The student may propose only the closed
`student.preferred_countries` value. The value must be:

- a non-empty array;
- exact lowercase country identifiers;
- unique;
- canonically sorted;
- within the existing allowed country set.

The assigned advisor confirms the exact candidate.

For a Case returning from `request_revision`, fact confirmation must atomically:

1. lock the Case and predecessor PlanningRun;
2. validate the request-revision review;
3. supersede the old confirmed fact;
4. construct a complete current-fact reference set;
5. create revision `N+1`;
6. store the request-review and predecessor-run links;
7. mark the predecessor PlanningRun non-current;
8. move no task and perform no planning;
9. emit one bounded audit event;
10. commit one idempotency response.

Any failure rolls back all ten effects.

An active task still blocks fact confirmation.

### Explicit task creation

The assigned advisor explicitly starts revised planning after confirmation.

Task creation must:

- lock the current Case revision;
- require state `planning`;
- require no current task for the revision;
- read the predecessor only from the revision lineage;
- copy that predecessor into the new task;
- bind the current complete fact refs, source pack, policy, and Skill runtime;
- retain the existing idempotency-key and request-hash contract;
- reject a caller-supplied predecessor;
- reject missing, stale, cross-Case, or cross-tenant lineage.

Concurrent same-key/same-payload calls return the same task. Same key with a
different payload returns the existing public idempotency conflict. Different
keys may produce at most one accepted current task.

### Worker and PlanningRun persistence

The worker loads `predecessor_planning_run_id` from the claimed task. It must not
query for an arbitrary current run.

Planning result persistence validates:

- the task lease and generation;
- exact Case revision;
- exact predecessor from the task;
- predecessor belongs to revision `N`;
- predecessor is already non-current;
- no successor already exists;
- new run belongs to revision `N+1`;
- `new.supersedes_run_id=predecessor.id`;
- the result uses the exact pinned facts, sources, policy, and Skill runtime.

Persistence inserts one successor and makes it current. It does not attempt to
invalidate the predecessor a second time.

Lost acknowledgements reconcile the same task and same successor. They do not
create a second PlanningRun.

Lease expiry and worker restart reclaim the same durable task, preserve its
frozen predecessor, elect one execution winner, and still persist only one
successor. A caller-supplied predecessor that differs from the task row fails
before persistence.

### Planning state outcomes

If deterministic planning produces one or more eligible recommended or
conditional routes, the run reaches `advisor_review`.

If the changed facts make every route ineligible, the run reaches the existing
blocked terminal state. The blocked run:

- remains the current run for the current revision;
- retains predecessor lineage;
- receives a deterministic comparison;
- exposes a closed reason;
- cannot receive an approval review;
- cannot create a DecisionBrief;
- cannot reach family decision or timeline.

### `PlanningRevisionComparisonV1`

The server constructs one closed comparison:

```json
{
  "schema": "night-voyager.planning-revision-comparison.v1",
  "case_id": "<uuid>",
  "previous_revision": 1,
  "current_revision": 2,
  "previous_planning_run_id": "<uuid>",
  "current_planning_run_id": "<uuid>",
  "previous_output_sha256": "<sha256>",
  "current_output_sha256": "<sha256>",
  "changed_fact": {
    "fact_key": "student.preferred_countries",
    "previous_value": ["australia", "japan", "malaysia"],
    "current_value": ["australia", "japan"]
  },
  "countries": [],
  "current_run_state": "review_required",
  "approval_eligible": true
}
```

Each country row contains:

- canonical country;
- delta: `added`, `removed`, `changed`, or `unchanged`;
- previous outcome and reason code, nullable only when added;
- current outcome and reason code, nullable only when removed.

Rows are sorted by canonical country. Comparison never uses route UUID as its
semantic key.

The projection rejects:

- duplicate or unsorted countries;
- unknown outcomes or reason codes;
- missing expected countries;
- an extra country absent from both runs;
- mismatched predecessor/successor lineage;
- role-unsafe fact values;
- caller-supplied `approval_eligible`;
- a current run that is not the unique successor.
- any reconstructed run state, top-level reason, route, comparison dimension,
  or evidence-use row whose complete canonical `PlanningResult` bytes do not
  match the corresponding retained `PlanningRun.output_sha256`.

`approval_eligible` is true only when the current run is reviewable under the
existing deterministic policy. It is false for blocked runs.

The hash authority is the complete persisted `PlanningResult`, not the public
comparison and not a route-only tuple. An internal closed projection rebuilds
exactly the predecessor and current results in original policy order, validates
them through the existing model, and applies the existing canonical hash
algorithm before public comparison is allowed.

### Read models and HTTP

The existing connected ledger and BFF are evolved; no second mutation API is
created. To keep PR 2 compatible with the existing frontend and Compose proof,
the advisor-ledger and current-decision-brief routes continue to return V1 by
default. One exact `contract_version=2` query selects their V2 responses; empty,
repeated, or unknown negotiation values fail closed. PR 3 opts in explicitly.

The current projection must select:

- the exact current Case revision;
- the task for that revision;
- the current PlanningRun for that revision;
- the predecessor from durable lineage;
- the current AdvisorReview and DecisionBrief only when they match that run;
- the comparison when a predecessor exists.

Old tasks and runs are audit/history inputs only. They cannot become current
because they are more recently timestamped than another row.

The comparison repository reads exactly the predecessor and current
PlanningRun plus their persisted route projections. HTTP callers and browsers
cannot submit route rows or output hashes. The query is bounded to those two
runs and must not scan complete Case history. Migration/catalog tests provide
indexes for current revision lineage, predecessor-to-successor lookup,
Case-plus-revision task/run selection, and review/brief-to-current-run lookup;
real PostgreSQL `EXPLAIN` regressions verify those access paths over bounded
multi-revision history without asserting a wall-clock SLA. Tests seed a fixed
minimum cardinality and run `ANALYZE`; natural plans are observed without
requiring a small table to avoid sequential scan, while
`SET LOCAL enable_seqscan=off` plus catalog assertions proves the exact indexes
are usable.

All assigned participants can read one server-owned recovery projection:

```json
{
  "schema": "night-voyager.connected-journey-status.v1",
  "case_id": "<uuid>",
  "current_revision": 2,
  "phase": "revision_requested",
  "active_role": "student"
}
```

This read-only status contains no task, run, review, candidate, route,
Evidence, comparison, or other role-sensitive authority identifiers. It is
derived only from durable state, is hidden from unassigned/cross-tenant actors,
and lets student and parent recovery avoid treating browser storage as phase
authority.

The family-safe current brief also carries one server-derived revision context:

```json
{
  "schema": "night-voyager.family-revision-context.v1",
  "current_case_revision": 2,
  "planning_version": "revised",
  "advisor_authorization": "renewed_for_current_revision"
}
```

`planning_version` is `initial` for the original path and `revised` only when
the current revision has durable predecessor lineage. The renewed-authorization
marker is emitted only when the current DecisionBrief is bound to an advisor
approval for the exact current revision and current PlanningRun. Browser
recovery metadata, timestamps, or client comparison state cannot produce this
marker.

Problem responses keep the existing public error taxonomy and do not expose SQL
states, internal receipts, private paths, raw fact JSON, or cross-role content.

### Connected demo recovery contract

The connected demo advances to a closed revision-aware recovery schema.

The durable phases are:

```text
review_required
revision_requested
revision_fact_pending
replan_required
revision_task_active
revision_review_required
revision_blocked
family_review
plan_ready
terminal_task_failure
```

Recovery metadata may store bounded identifiers, cursor, role, phase, CSRF
material, and idempotency records. It is not authority.

On load, after every role rotation or mutation, and after a lost
acknowledgement, the browser first reads `ConnectedJourneyStatusV1`, then reads
only the role-safe detail projection for that status. The server projection
wins over browser state. A status/detail mismatch or unsupported/inconsistent
older envelope is cleared fail closed.

The visible role, phase, and action contract is closed:

| Server phase | Active role | Visible view | Authority explanation | Actions |
| --- | --- | --- | --- | --- |
| `review_required` | advisor | initial plan and review basis | The current plan still awaits advisor judgment. | Primary: approve current plan. Secondary: request revision. |
| `revision_requested` | student | current confirmed preference and bounded proposed target | The advisor requested a change, but no fact has changed yet. | Primary: submit change proposal. |
| `revision_fact_pending` | advisor | read-only before/proposed fact delta | Only the assigned advisor may confirm the proposal as a new fact revision. | Primary: confirm proposal. |
| `replan_required` | advisor | confirmed change plus retained-plan notice | The old plan is retained and non-current; a new plan does not exist yet. | Primary: create revised planning task. |
| `revision_task_active` | advisor | confirmed change, retained plan, and task progress | Worker execution cannot approve or choose the current plan. | No mutation action. |
| `revision_review_required` | advisor | changed fact and old/new comparison | Only a fresh approval for the current revision may continue. | Primary: approve revised plan. |
| `revision_blocked` | advisor | changed fact, comparison, and deterministic block reason | The current revision has no approvable route. | No approval or family-decision action; only a non-business recovery/navigation exit. |
| `family_review` | parent | current brief plus current revision and renewed-review context | The family decides only on the current re-reviewed version. | Primary: confirm current family decision. |
| `plan_ready` | parent | current receipt and timeline | The current decision is final for this bounded journey. | No mutation action. |
| `terminal_task_failure` | advisor | retained authoritative ledger and bounded failure | The failed task created no approval authority. | No business mutation; only the existing bounded recovery/navigation exit. |

The initial `review_required` approval remains the visual primary action.
`request_revision` is secondary and first expands an inline consequence
summary: the previous plan remains retained, the fact is not changed by the
request, and a new plan plus renewed advisor approval will be required.
Student copy says “submit change proposal”, never “confirm fact”. The student
view reads the current value from the role-safe confirmed-fact projection; only
the synthetic proposed target is fixed. Missing, malformed, out-of-order, or
unexpected current values disable submission and show a localized fail-closed
message.

### Browser journey

The public journey uses existing role-scoped sessions and APIs:

1. advisor observes the first reviewable plan;
2. advisor requests revision;
3. browser rotates to student;
4. student submits the preferred-country proposal;
5. browser rotates to advisor;
6. advisor confirms the fact;
7. advisor explicitly starts planning;
8. browser follows the existing SSE stream;
9. browser renders the old/new comparison;
10. advisor grants a new approval;
11. browser rotates to the assigned parent;
12. family decision produces receipt and timeline.

The interface must make these distinctions visible:

- retained previous plan;
- current revised plan;
- exact changed preference;
- removed Malaysia route;
- unchanged or changed Australia and Japan outcomes;
- new advisor authorization;
- current family decision.

The comparison page has one information hierarchy:

1. active role and authority;
2. changed-fact summary;
3. current-first old/new comparison;
4. current-plan approval action;
5. Evidence and bounded technical history.

Desktop renders a semantic
`country | previous result | current result | change` table. Mobile renders
the same semantic content as one country-keyed `<dl>` at a time, with a
`fieldset`/`legend` switcher and a visually hidden semantic table available to
assistive technology. The current result is visually primary; the predecessor
is explicitly “history, for comparison only”. `removed` displays “removed from
the revised plan” in the current column and `added` displays “not present in
the previous plan” in the previous column. These valid null cases must not use
an unavailable-state message. Delta meaning is always visible in text and is
never communicated by color alone.

The family view displays the server-owned current Case revision and
`renewed_for_current_revision` context. It cannot infer that statement from a
successful reload, browser storage, or the presence of a comparison.

The user-facing page does not expose raw UUIDs, internal JSON, SQL state, debug
receipts, or private file paths.

Both `zh-CN` and `en` must be first-class verified paths.

All product overlines, roles, authority copy, revision labels, history/current
labels, phases, disabled reasons, and recovery text come from the bilingual
catalog or closed code maps. The Chinese path must not retain hard-coded English
presentation copy; the English path must not fall back to Chinese copy.

Focus moves only after a user-triggered full-phase transition. SSE refresh,
reconnect, authoritative reload, and ignored stale events announce bounded
updates with `aria-live="polite"` and do not move focus. Only a blocking error
uses `role="alert"`. All interactive targets remain at least 44 by 44 CSS
pixels, the fact proposal uses `fieldset`/`legend`, reduced-motion preferences
are honored, and 320, 390, 768, and 1440 pixel layouts have no horizontal
overflow.

One dedicated screenshot flag may update only the new Chinese 1440px planning
revision asset. The existing portfolio-entry, advisor-ledger, and
family-receipt PNGs remain byte-identical. English 1440px, both 390px variants,
and blocked-state captures are review-only artifacts. The general portfolio
screenshot flag and the revision screenshot flag are mutually scoped by
architecture tests.

### SSE, restart, and recovery

The journey uses one EventSource at a time.

- Cursor is monotonic.
- Reconnect uses the stored last accepted cursor.
- Events for an old task cannot advance the current revision phase.
- Reload during an active revised task recovers the same task.
- Reload after terminal persistence does not require a new SSE request.
- Worker restart after the durable revised-task sentinel exercises lease
  expiry/reclaim and resumes the same task and predecessor.
- Request revision, fact confirmation, and revised task creation each have a
  committed-response-lost proof: server commit, aborted response, same-key
  retry, and authoritative journey-status reload reconcile the same record.
- No recovery path creates a second revision, task, run, review, or decision.

The visible asynchronous-state contract is also closed:

| State | Retained view | Mutation state | Announcement and recovery |
| --- | --- | --- | --- |
| Initial load | skeleton only; no stale authority | disabled | polite loading status |
| User mutation pending | last authoritative ledger | all business actions disabled | polite bounded busy copy |
| SSE connected/reconnecting | current ledger and task progress | phase-derived | polite connection copy; no focus move |
| Authoritative reload recovered | newly projected ledger | phase-derived | polite recovery copy; no focus move |
| Lost-ack reconciliation | last ledger until exact response reload | disabled | polite reconciliation copy |
| Stale/old-task event ignored | current ledger unchanged | unchanged | no focus move and no false phase advance |
| `terminal_task_failure` | ledger, changed fact, and bounded task failure | no business action | bounded recovery/navigation exit |
| `revision_blocked` | changed fact and comparison | no approval/family action | deterministic reason plus navigation exit |
| Blocking `recoverable_error` | safe bounded context only | disabled | `role="alert"` and exact reconnect action |

## Negative scenario: budget decrease

The provider-free negative scenario changes a family-owned budget fact after a
valid `request_revision`.

It proves:

- role policy requires the correct family actor and advisor confirmation;
- the new Case revision and predecessor lineage are still exact;
- deterministic planning produces a blocked revised run under the existing
  policy;
- comparison remains available;
- `approval_eligible=false`;
- advisor approval is rejected;
- no DecisionBrief, FamilyDecision, DecisionReceipt, or TimelinePlan exists;
- the previous run remains retained but non-authoritative.

This scenario is a test and operational proof, not the primary public journey.

## Idempotency and concurrency matrix

| Operation | Same key, same payload | Same key, different payload | Different-key overlap |
| --- | --- | --- | --- |
| Request revision | Replay same review | Public idempotency conflict | At most one review accepted |
| Submit fact proposal | Replay same candidate | Conflict | Existing collaboration policy |
| Confirm changed fact | Replay same fact/revision | Conflict | One revision successor only |
| Create revised task | Replay same task | Conflict | One current task per revision |
| Persist successor run | Reconcile same run | Conflict/lease loss | One successor per predecessor |
| Advisor approval | Replay same review | Conflict | One current approval |
| Family decision | Replay same receipt/timeline | Conflict | One current decision |

Transaction-scoped locks and database uniqueness remain the final authority.
Application pre-checks improve errors but cannot replace those constraints.
The request-revision path has a partial unique index for one request per run;
different-key races return one stable closed conflict and never leak a raw
uniqueness error.

## Failure taxonomy

The implementation must fail closed for:

- wrong tenant, actor, role, or Case assignment;
- stale Case revision;
- stale or non-current PlanningRun;
- request revision against a decided or plan-ready Case;
- `reject` confused with `request_revision`;
- active task during fact revision;
- malformed or role-ineligible fact proposal;
- missing or forged request-review lineage;
- missing, stale, or cross-Case predecessor;
- more than one successor;
- more than one current run;
- task predecessor different from revision predecessor;
- worker-time inferred predecessor;
- same idempotency key with a different payload;
- old review or DecisionBrief reused after revision;
- family decision against an old run;
- blocked revised run submitted for approval;
- malformed comparison;
- old-task SSE event applied to the new task;
- cursor rollback;
- partial write after process, lease, or connection failure;
- mixed DRA release/commit identity;
- wrong strict profile id, version, or proof schema;
- legacy readiness supplied to the strict path;
- a new provider or credential attempt.

No failure may delete the predecessor history or silently fall back to an
unversioned path.

## Security and privacy

- RLS and forced tenant isolation apply to all added columns and projections.
- SECURITY DEFINER functions retain fixed search paths and least-privilege
  grants.
- Worker roles cannot request revision, confirm facts, approve plans, or make
  family decisions.
- API roles cannot invoke internal transition helpers directly.
- Student, parent, and advisor projections remain role scoped.
- The comparison contains only closed, role-safe facts needed for the current
  journey.
- DRA artifact content remains ephemeral at the import boundary; durable
  candidate storage retains only bounded identity, bytes length, hash, selected
  Evidence, and authority receipts already allowed by the consumer contract.
- No credential, cookie, token, private path, or provider artifact content enters
  repository files, logs, PRs, screenshots, or public reports.

## Framework boundary

This design does not introduce LangChain, LangGraph, DeepAgents, or another
workflow runtime.

The existing PostgreSQL and domain services already provide:

- durable state;
- transaction authority;
- idempotency;
- leases and recovery;
- human approval;
- event and SSE projection;
- deterministic evaluation.

A framework checkpoint or HITL primitive would not own Night Voyager's fact,
lineage, review, or decision records. Reusing the current domain boundary is
smaller and more accurate than adding a parallel graph.

## Testing strategy

### Pull request 1

- strict producer-pin canonical model tests;
- legacy and strict tuple table constraints;
- trigger/RLS-safe legacy migration, injected rollback, and exact
  upgrade/downgrade catalog parity;
- legacy import wrapper plus strict overload signature, ACL, and replay parity;
- provider-free strict cited success;
- zero-cited pre-import rejection;
- request/profile/proof identity collision tests;
- candidate import and evaluation identity tests;
- readiness and freeze counterfactuals;
- immutable fixture and historical release checks.

### Pull request 2

- request-revision database and HTTP authority;
- same-key and different-key request-revision race closure;
- revision lineage migration and downgrade guard;
- fact confirmation atomicity;
- predecessor freeze in AgentTask;
- worker load and persist exact lineage;
- one-current-run and one-successor concurrency;
- idempotency and lost-ack recovery;
- revision-task lease expiry/reclaim and one execution winner;
- blocked revised-run authority;
- deterministic comparison canonicalization;
- complete predecessor/current `PlanningResult` reconstruction and
  state/reason/route/dimension/evidence-use tamper rejection;
- bounded two-run projection plus catalog and `EXPLAIN` access-path checks;
- default-V1/explicit-V2 read compatibility and participant-safe journey
  status across every role/phase;
- stale review, brief, and family-decision counterfactuals.

### Pull request 3

- connected ledger revision projection;
- session recovery and role rotation;
- `zh-CN` and `en` unit coverage;
- browser happy path;
- browser blocked-budget path;
- committed-response-lost recovery for request, confirmation, and task create;
- active-task reload and exact-cursor reconnect;
- worker restart durability;
- revision-only screenshot update with prior public PNG identity preservation;
- browser-to-database verifier for:
  - two Case revisions;
  - two retained PlanningRuns;
  - exact supersession;
  - one new AdvisorReview;
  - one current DecisionBrief;
  - one FamilyDecision;
  - one DecisionReceipt;
  - one TimelinePlan;
  - no duplicate task/run/review/decision.

### Required gates

Each pull request must run the repository gates appropriate to its actual diff.
The full stage must finish with:

```text
uv lock --check
Ruff
Pyright
frontend lint
frontend typecheck
frontend unit tests
frontend production build
make check
make proof
make compose-proof
make down
development release verifier
base-to-HEAD git diff --check
public/private-path/actual-sensitive-value scans
```

Required CI remains provider-free.

## Docker and Compose contract

Before every heavy Docker gate:

- record host filesystem availability;
- record Docker VM filesystem availability;
- require the default 8 GiB minimum without an override;
- record Compose projects, containers, images, BuildKit cache, networks, and
  volumes;
- identify the exact task-owned project;
- preserve `night-voyager_postgres-data` and shared cache/images.

The proof should reuse stable build layers and use one exact task-owned
`COMPOSE_PROJECT_NAME`.

Teardown must remove only task-owned:

- containers;
- networks;
- ephemeral volumes;
- local Compose images.

After teardown:

- exact task project is absent;
- default Compose inventory is empty;
- global container inventory is empty unless a separately owned task is
  positively identified;
- retained resources are enumerated;
- no broad prune or Docker Desktop, daemon, BuildKit, disk, or containerd change
  is made without separate authorization.

## Delivery sequence

### PR 1: strict DRA consumer prerequisite

Owns:

- migration `0011`;
- producer/request/candidate/readiness v2 or successor schemas;
- strict controller and provider-free fixtures;
- candidate import/evaluation/freeze regressions;
- DRA reference, operations, ADR, and current-status correction.

Does not own:

- fact revision;
- planning lineage;
- connected UI;
- provider execution.

Exit evidence:

- exact strict tuple retained through durable candidate projection;
- legacy history remains readable;
- provider-free required gates pass;
- no operational freeze or live attempt.

### PR 2: durable revision authority

Owns:

- migration `0012`;
- Case revision and task predecessor lineage;
- worker and PlanningRun persistence;
- complete-result-verified comparison projection;
- default-V1/explicit-V2 HTTP/read-model authority;
- participant-safe journey-status recovery;
- database concurrency, idempotency, and recovery.

Does not own:

- public browser journey;
- production deployment;
- provider execution.

Exit evidence:

- exact predecessor and successor survive restart;
- all stale/concurrent/counterfactual paths fail closed;
- no UI-specific authority is required.

### PR 3: revision journey and presentation

Owns:

- connected ledger evolution;
- role rotation and recovery;
- BFF opt-in to V2 plus status-first lost-ack reconciliation;
- request-revision and student-preference UI;
- deterministic comparison presentation;
- renewed advisor review and family decision;
- blocked-budget presentation/proof;
- bilingual browser and database verification;
- isolated revision screenshot evidence without prior asset drift;
- public design, operations, demo, and status documentation.

Exit evidence:

- full browser-to-database happy path;
- blocked negative path;
- reload, SSE, and restart durability;
- exact current-version decision authority;
- no stale history authority.

### Serial execution

The pull requests are intentionally serial:

```text
PR 1 merge
-> fresh main and migration head
-> PR 2 implementation and merge
-> fresh main and migration head
-> PR 3 implementation and merge
-> release decision
```

PR 2 depends on the migration head and identity boundary established by PR 1.
PR 3 depends on the durable lineage and comparison projection established by
PR 2. Parallel implementation would save little time and increase migration,
API, test, and documentation conflict risk.

## Release boundary

Each pull request must be independently GREEN and merged with normal repository
rules, but PR 1 and PR 2 do not receive separate releases by default.

After PR 3:

1. re-read clean merged main, exact hosted checks, documentation, and open risks;
2. decide whether the stage is release-worthy;
3. prepare one separate release pull request;
4. run merged-main release and Git-free archive gates;
5. publish one annotated tag and GitHub Release;
6. run public archive smoke.

The expected next version is `v0.1.4`, subject to a separate release decision.
This design does not authorize a version bump, tag, or Release and does not
justify `v0.2.0`.

An intermediate release is considered only if PR 3 is materially deferred and
PR 1 or PR 2 gains an independently useful external consumer. That is not the
default plan.

## Documentation impact

PR 1 updates:

- current DRA consumer reference;
- DRA operations and candidate-freeze runbook;
- ADR 0011 or its successor;
- current status in this index and the governed-live design;
- truthful two-attempt non-claims.

PR 2 updates:

- database and worker operations;
- task and planning references;
- state and projection matrices;
- a new ADR if migration authority cannot be explained by the existing
  planning ADR.

PR 3 updates:

- README and README_CN current development surface;
- DESIGN;
- docs index;
- connected-demo, collaboration, and fact-to-plan operations;
- presentation and browser proof documentation;
- this spec and implementation-plan statuses.

Published `v0.1.0` through `v0.1.3` release notes and verification guides remain
byte-identical.

## Acceptance criteria

The stage is complete only when:

1. Night Voyager pins the exact DRA commit and strict tuple without calling it a
   released v0.1.6 capability.
2. Legacy generic candidate history remains readable and immutable.
3. Required CI is offline and provider-free.
4. No third provider attempt occurs.
5. A valid `request_revision` review is required before the fact revision.
6. The new revision stores the exact request-review and predecessor run.
7. The new task freezes that predecessor before worker execution.
8. The successor run points to exactly that predecessor.
9. Old and new runs remain queryable while only the new run is current.
10. The comparison is deterministic, closed, country-keyed, role safe, and
    bound to both retained runs' reconstructed complete canonical output
    hashes.
11. The happy path changes preferred countries and requires renewed advisor
    approval.
12. The budget counterfactual is blocked and cannot reach family decision.
13. Old reviews and briefs cannot authorize the new revision.
14. Only the current revision produces the final family decision, receipt, and
    timeline.
15. Reload, SSE reconnect, worker restart, and lost acknowledgements create no
    duplicate authority records.
16. Existing read routes remain V1 by default, explicit V2 negotiation is
    closed, and every assigned role recovers phase/revision from the
    participant-safe server status.
17. Every revision phase exposes the exact active role, authority explanation,
    action hierarchy, disabled reason, and recovery behavior defined above.
18. The family brief identifies the current revision and renewed advisor
    authorization from the server-owned current chain.
19. `zh-CN` and `en` browser-to-database proofs pass, and the 320/390/768/1440
    presentation matrix has no mixed-language copy, horizontal overflow, focus
    theft, color-only delta, or sub-44px action target.
20. The revision screenshot is isolated and the three existing public proof
    PNGs remain byte-identical.
21. Docker task resources are fully torn down and retained resources are
    preserved.
22. Historical releases and migrations remain immutable.
23. Three serial pull requests are merged and exact merged-main checks pass.
24. Release remains a separate explicit decision.
25. Release verification preserves that the two prior 25/83-uncited live
    attempts remain failed history, no third provider attempt or strict live
    acceptance occurred, and the revision proof is controlled and
    provider-free.

## Public non-claims

This stage does not prove:

- successful DRA strict-profile live acceptance;
- source truth or citation correctness;
- complete institution coverage;
- provider or model quality;
- admissions outcome;
- production deployment;
- external users;
- distributed high availability;
- SLA or exactly-once execution;
- automatic fact, Evidence, planning, review, or family-decision authority.

Its bounded claim is:

> Night Voyager deterministically preserves the lineage between an explicitly
> revised confirmed fact, its retained predecessor plan, its successor plan, a
> server-owned comparison, renewed advisor authorization, and the current family
> decision, while consuming an exact-pinned provider-free DRA strict contract.
