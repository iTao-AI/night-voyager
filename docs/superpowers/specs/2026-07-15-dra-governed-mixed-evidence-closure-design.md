# DRA Governed Mixed-Evidence Closure Design

**Status:** Approved design source. Night Voyager's existing planning and
review window owns the public specification, implementation plan, execution,
and authoritative review. The Decision Research Agent runtime and public
contract remain unchanged in this stage.

## Goal

Night Voyager consumes one released Decision Research Agent canonical result as
untrusted research material, requires an assigned advisor to verify one exact
official source for one bounded claim, and then reuses the existing durable
planning, AdvisorReview, and family-decision workflow.

```text
DRA canonical generic result + run-level Evidence
  -> Night Voyager DraResearchCandidate
       authority = untrusted_candidate
  -> assigned-advisor verification and approve-time promotion
       one atomic PostgreSQL authority gate
  -> new immutable source-pack revision
       exactly one externally_verified australia_program_fit
       all other accepted facts remain the exact synthetic baseline
  -> generate_governed_mixed_planning_run_v1
  -> existing AgentTask lease / retry / fencing / SSE
  -> existing deterministic planning policy
  -> existing AdvisorReview
  -> existing family decision, receipt, and timeline
```

This capability is a local, mixed-evidence, human-governed proof. It does not
claim production deployment, current admissions coverage, applicant
eligibility, live institutional completeness, external users, or business
outcomes.

## Verified Baseline

The design is based on these released and executable contracts:

| Surface | Exact baseline |
| --- | --- |
| Night Voyager release | `v0.1.0` |
| Night Voyager release commit | `af24ca64599aa07765042120aeef271057363df1` |
| Night Voyager planning policy | `m3a-policy-v1` |
| Night Voyager synthetic source-pack ID/version | `50000000-0000-0000-0000-000000000001` / `1` |
| Night Voyager M3A fixture file SHA-256 | `5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25` |
| Night Voyager canonical source-manifest SHA-256 | `84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28` |
| DRA release | `v0.1.3` |
| DRA release commit | `87b2a8e335385eb865086f7a69fe2b190567cfa2` |
| DRA downstream fixture schema | `dra.downstream-consumer.v1` |
| DRA downstream fixture SHA-256 | `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157` |

The DRA downstream fixture proves an offline compatibility boundary. It does
not prove a live provider run, claim-level Evidence, source verification, or a
Night Voyager business decision.

The Night Voyager v0.1.0 planning adapter reads the checked-in M3A fixture. Its
PostgreSQL schema persists source-pack entries and Evidence references, but it
does not persist a reusable cost/ranking input-fact model. Cost and ranking rows
are currently PlanningRun result children. This design therefore does not claim
or build a generic persisted-input planning platform.

## Product Decision

The approved stage is a governed mixed-evidence closure:

- DRA supplies research execution, canonical artifact identity, and run-level
  Evidence metadata.
- Night Voyager imports only a strict, bounded candidate projection.
- Candidate import never creates accepted Evidence or advances a Case.
- One assigned advisor may verify one exact public source and approve one
  bounded `australia_program_fit` mapping.
- Human verification and approve-time Evidence promotion are the same atomic
  PostgreSQL authority gate.
- The promoted planning path uses the exact M3A synthetic baseline for all
  other evidence, cost, FX, and ranking facts.
- The existing deterministic policy, durable task, AdvisorReview, family
  decision, receipt, and timeline remain authoritative.

The stage is intentionally narrower than a general DRA-to-domain mapping
system. It demonstrates that external Agent output can enter a real product
workflow without allowing the Agent, transport client, browser, or caller to
grant business authority.

## Scope

### Included

- strict Night Voyager-owned models for the supported DRA v1 health, run,
  result, artifact, and run-level Evidence projection;
- bounded keyed run creation and lost-acknowledgement reconciliation;
- an optional DRA REST transport used only by explicit proof tooling;
- immutable `DraResearchCandidateV1` persistence and bounded read projection;
- assigned-advisor source verification with approve/reject decisions;
- atomic approve-time creation of one new source-pack revision and one
  `externally_verified australia_program_fit` Evidence reference;
- a closed mixed-authority planning contract;
- the additive `generate_governed_mixed_planning_run_v1` AgentTask operation;
- reuse of the existing task queue, lease, retry, generation fencing, event,
  SSE, PlanningRun, AdvisorReview, DecisionBrief, FamilyDecision,
  DecisionReceipt, and TimelinePlan paths;
- deterministic offline fixture proof in required CI;
- public-neutral reference, operations, ADR, and proof documentation.

### Excluded

- DRA runtime, API, schema, profile, Evidence, review, publication, or canonical
  result changes;
- parsing Markdown into typed claims, dates, limitations, conflicts, cost,
  ranking, eligibility, or route outcomes;
- automatic Evidence verification or promotion;
- more than one promotable external claim;
- externally verified tuition, living cost, FX, ranking, eligibility, or
  intake availability;
- a generic persisted-input planning system or new source-fact platform;
- MKE, OCR, OpenClaw, remote message channels, or multiple external adapters;
- browser/BFF integration or changes to the connected `/demo`;
- public registration, production tenancy, deployment, release, or SLA work;
- a live provider execution without separate authorization.

## Authority Model

| Authority | Owns | Does not own |
| --- | --- | --- |
| DRA application database | ResearchRun, run-level Evidence, artifact, review/delivery state | Night Voyager claim mapping, Case, source-pack, planning, advisor, or family state |
| Night Voyager candidate ledger | exact producer/request/run/artifact/Evidence projection and import identity | accepted Evidence, source truth, route outcome, or Case transition |
| Night Voyager verification row | assigned-advisor decision over one exact candidate source and one bounded mapping | DRA state, provider truth, or admissions eligibility |
| Night Voyager atomic promotion function | source-pack revision and trusted external Evidence identity | planning result, AdvisorReview, or family decision |
| Night Voyager deterministic policy | route eligibility from a validated mixed PlanningInput | source verification or human approval |
| Night Voyager AgentTask | durable scheduling, lease, retry, fencing, result finalization, and SSE | verification, promotion, advisor approval, or family decision |
| AdvisorReview / FamilyDecision | existing human decision gates | Evidence collection or automatic source promotion |

Framework runtime, checkpoints, traces, transport clients, model output, and
proof scripts are never Night Voyager business authority.

## Invariants

The implementation must preserve all of these invariants:

1. A DRA result can create only an `untrusted_candidate`.
2. Candidate import has no source-pack, Evidence, task, planning, advisor, or
   family side effect.
3. DRA `verification_status` never grants Night Voyager authority.
4. Caller-provided JSON cannot construct `externally_verified` Evidence.
5. Only an assigned advisor for the exact tenant and Case may invoke the
   verification/promotion gate.
6. An `approve` decision and its source-pack/Evidence promotion either commit
   together or leave no state.
7. A `reject` decision records no source-pack revision or Evidence reference.
8. The only external mapping is
   `australia_program_fit -> program_fit`.
9. The mixed planning operation requires exactly one trusted external
   `australia_program_fit` Evidence reference.
10. Every other Evidence reference remains `accepted_synthetic_demo` and is
    derived from the exact baseline.
11. External Evidence cannot satisfy tuition, living-cost, FX, ranking,
    eligibility, or intake claims.
12. Promotion does not create an AgentTask or PlanningRun.
13. Planning does not approve itself; existing AdvisorReview and family gates
    remain mandatory.
14. The original `generate_planning_run_v1` synthetic operation remains
    behaviorally compatible.
15. Required CI never needs DRA runtime, provider credentials, or network
    access.

## DRA Consumer Boundary

### Strict projection

Night Voyager owns strict models for the supported DRA v1 projection. It
accepts only:

- health `status` and canonical `service` identity;
- keyed run-creation acknowledgement, `thread_id`, `run_id`, `segment_id`, and
  `idempotent_replay` when a key is used;
- run `execution_status`, `review_status`, `delivery_status`, and bounded state
  identity required by the released fixture;
- stable result status/code;
- generic artifact ID, kind, media type, exact UTF-8 bytes, size, and SHA-256;
- ordered run-level Evidence fields:
  `evidence_id`, `source_url`, `source_identity`, `retrieved_at`,
  `citation_status`, and `verification_status`.

The canonical artifact must be `research-report.md` with kind
`research_report_markdown`, media type `text/markdown`, non-empty UTF-8 content,
and at most 1 MiB. The exact content hash must match the bytes received.

Fallback artifacts, `completed_with_fallback`, review-required, blocked,
failed, unavailable, unsafe, oversized, empty, unknown-kind, and hash-mismatched
results cannot produce an importable candidate.

Unknown fields are discarded before strict candidate construction and never
become business input. Unknown states or invalid combinations fail closed.
Night Voyager does not import DRA runtime modules or treat a copied fixture as
a runtime SDK.

### Keyed run creation and reconciliation

The optional live client uses one canonical request and one high-entropy
`Idempotency-Key`. It preserves both across ambiguous outcomes.

| Observation | Disposition |
| --- | --- |
| first keyed acceptance | retain exact identities and poll |
| same-request keyed replay | require original identities and poll |
| keyed request conflict | block |
| invalid key | block |
| idempotency unavailable | block; never downgrade to unkeyed create |
| client deadline | stop polling; do not claim server cancellation |
| unknown transport outcome before safe replay | `reconciliation_required` |

Polling uses a fixed interval, fixed total deadline, bounded reads, and no
automatic provider retry. The live client accepts only an explicitly configured
loopback DRA base URL without userinfo, path, query, or fragment.

The optional DRA API key is read from an environment variable, redacted, never
accepted as a command argument, and never persisted. Provider configuration
remains entirely inside DRA.

## Untrusted Candidate Contract

`DraResearchCandidateV1` is an immutable Night Voyager-owned record containing:

- schema version and candidate ID;
- organization, Case ID, and expected Case revision;
- producer name, DRA release tag, exact commit, and contract schema;
- canonical request hash and bounded request identity;
- DRA run ID;
- artifact ID, kind, media type, byte length, and SHA-256;
- ordered allowlisted Evidence metadata;
- server-computed import request hash;
- `authority = untrusted_candidate`;
- created timestamp.

It excludes raw credentials, raw exceptions, trace/checkpoint data, snippets,
provider payloads, token/cost data, local paths, and canonical Markdown bytes.
The operator may inspect canonical Markdown in a temporary local file, but the
candidate ledger persists only its bounded identity and hash.

Candidate import is idempotent through the existing hashed idempotency
boundary. Same key and same canonical request return the same candidate. Same
key with different content returns a conflict without disclosing the prior
candidate. Candidate identity is server generated; a caller cannot choose the
business record ID.

Import requires an assigned advisor, a Case whose exact current revision is in
`planning`, the expected producer/fixture pins, Origin/CSRF protection, and the
existing non-enumerating tenant/session boundary. Import does not require or
imply source verification.

## Atomic Human Verification and Promotion

### Meaning of `externally_verified`

Within this feature, `externally_verified` means:

> An assigned Night Voyager advisor attested that one exact public source
> snapshot supports the bounded `australia_program_fit` claim for the current
> Case, subject to recorded gaps.

It does not mean that DRA verified the source, that the institution endorsed
the decision, that the applicant is eligible, that an intake is open, or that
Night Voyager automatically proved source truth.

The field representing the human assertion is named and documented as an
advisor attestation. Public copy must not describe it as third-party
certification or automated fact checking.

### Closed mapping allowlist

The only approved external mapping is:

```text
claim = australia_program_fit
evidence_role = program_fit
authority = externally_verified
redistribution_class = link_only
evidence_class = institutional | government
```

The selected DRA Evidence must have:

- a non-null public HTTPS `source_url` without userinfo;
- exact normalized `source_identity` equal to the URL identity;
- `citation_status = cited`;
- an Evidence ID present in the imported candidate;
- the same ordered projection and candidate hash imported earlier.

Its DRA `verification_status` is retained only as non-authoritative provenance.

The approved source metadata must include:

- exact canonical public URL equal to the candidate source URL;
- publisher and institution;
- source snapshot date;
- positive freshness days;
- `link_only` redistribution;
- institutional or government evidence class;
- a traversal-free logical relative path;
- positive snapshot byte length and lowercase SHA-256;
- known gaps containing at least applicant eligibility and intake availability.

The API does not fetch the source or read an arbitrary caller path. An opt-in
proof controller may validate bytes under one declared local root before
submitting the decision. The database records the advisor attestation and
exact hash; it does not claim independent server-side source acquisition.

### One authority command

One narrow PostgreSQL function owns both the human decision and approve-time
promotion. Conceptually:

```text
verify_and_promote_dra_candidate(
  tenant context,
  assigned advisor,
  exact Case revision,
  exact candidate and Evidence source,
  decision ID and idempotency identity,
  approve | reject,
  bounded reason,
  allowlisted source metadata,
  exact baseline pack identity and hashes
)
```

For both decisions it validates tenant context, participant assignment, actor
role, an exact current Case revision still in `planning`, candidate-to-Case
binding, producer pins, selected DRA Evidence, request hash, and idempotency.

For `reject`, it inserts one immutable verification row and returns. It creates
no source-pack revision, source entry, Evidence reference, task, or planning
state.

For `approve`, the same transaction:

1. locks and verifies the exact baseline source-pack ID/version, fixture file
   hash, canonical manifest hash, and current Case revision;
2. computes deterministic IDs for the new pack version, copied Evidence, new
   external source entry, and promoted Evidence reference;
3. creates the next immutable source-pack version;
4. copies baseline synthetic source entries while removing
   `australia_program_fit` from the old synthetic entry coverage;
5. copies every accepted synthetic Evidence reference except the prior
   synthetic `australia_program_fit`, using deterministic new Evidence IDs;
6. adds one link-only external source entry whose coverage is exactly
   `australia_program_fit`;
7. creates one `externally_verified` Evidence reference tied to the approved
   verification row and exact source hash;
8. inserts the immutable verification row containing the resulting pack
   version, external entry ID, promoted Evidence ID, and provenance hashes;
9. commits all rows together.

Any stale state, invalid metadata, duplicate conflict, unexpected pack version,
hash mismatch, source mismatch, constraint failure, or concurrent approval
rolls back the whole command. There is no intermediate approved-without-pack or
pack-without-verification state.

The decision is terminal for the exact candidate Evidence mapping. A rejected
or incorrectly attested source requires a new candidate or a separately
designed correction flow; v1 does not edit or supersede an accepted row.

## Persistence Design

### `app.dra_research_candidates`

The candidate table is tenant-keyed and immutable. It stores the bounded
candidate contract, ordered Evidence projection as validated JSON, exact
producer/request/artifact hashes, and created identity. It does not store raw
Markdown, snippets, credentials, or provider payloads.

Required constraints include:

- exact candidate schema and `untrusted_candidate` authority;
- lowercase SHA-256 fields;
- positive artifact size bounded to 1 MiB;
- canonical producer/release/commit/fixture pins;
- organization/Case foreign keys;
- one deterministic import request identity;
- forced RLS and no runtime direct writes.

### `app.external_evidence_verifications`

The verification table is tenant-keyed, append-only, and terminal per exact
candidate Evidence mapping. It stores:

- decision and request identity;
- candidate, Case, revision, actor, DRA Evidence ID, source URL/identity;
- fixed claim/role/authority values;
- approve/reject and bounded reason;
- approve-only source metadata and advisor-attested snapshot identity;
- exact baseline pack/version/hashes;
- nullable promoted pack version, external source entry ID, and promoted
  Evidence ID, which are required for approval and forbidden for rejection;
- created timestamp.

The verification row is also the promotion audit record. A separate promotion
table is not introduced because v1 permits exactly one promotion result for one
approval and has no independent promotion lifecycle.

Foreign keys bind approved result identities to the actual source-pack entry
and Evidence reference. Exact check constraints make approve and reject row
shapes mutually exclusive.

### Existing tables

The feature reuses:

- `student_cases`, revisions, participants, actors, and memberships;
- `source_packs`, `source_pack_entries`, and `evidence_refs`;
- `idempotency_records`;
- `agent_tasks`, executions, dispatch, and events;
- `planning_runs` and existing result children;
- existing advisor/family tables.

The migration expands the `evidence_refs.authority` database check to include
`externally_verified`, but API/worker runtime roles still cannot directly
insert or update Evidence rows. Only the narrow atomic promotion function can
create the trusted external reference.

All new tenant tables use `ENABLE/FORCE ROW LEVEL SECURITY`, explicit
`USING/WITH CHECK`, migrator ownership, runtime-equivalent grants, fixed
`search_path`, PUBLIC execute revocation, and no DELETE/TRUNCATE/broad update
grant.

## Governed Mixed-Evidence Planning Operation

### Why this is not generic persisted planning

Night Voyager v0.1.0 does not persist a reusable source-level cost/ranking
input model. Building that model would add new domain tables and a general
source-fact architecture unrelated to the bounded consumer proof.

The new operation is therefore explicitly named:

```text
generate_governed_mixed_planning_run_v1
```

It is an additive, closed operation. The original
`generate_planning_run_v1` remains the synthetic fixture operation.

### Materialization contract

A product-owned mixed planning adapter receives only trusted task pins:

- organization and Case ID;
- exact current Case revision;
- promoted source-pack ID/version;
- `m3a-policy-v1`;
- `generate_governed_mixed_planning_run_v1`.

The adapter never calls DRA, a model, LangChain, DeepAgents, LangGraph, or
LangSmith. Research has already completed.

The adapter:

1. loads the exact Case revision from PostgreSQL;
2. loads the promoted source pack, entries, Evidence references, and atomic
   verification relationship under tenant context;
3. verifies the pack is derived from the exact approved synthetic baseline;
4. requires exactly one externally verified Evidence reference whose claim is
   `australia_program_fit` and whose ID/hash matches the approval row;
5. requires every other baseline claim exactly once with
   `accepted_synthetic_demo` authority;
6. loads and validates the checked-in exact M3A baseline fixture by file hash,
   canonical manifest hash, schema, and policy version;
7. copies only the baseline synthetic cost, FX, ranking, and unchanged
   comparison facts, replacing their Evidence IDs through the deterministic
   old-to-new claim mapping from the promoted pack;
8. constructs a trusted internal mixed `PlanningInput`;
9. returns a strict payload to the existing task worker.

The adapter may not accept caller-provided Evidence bytes, authority, cost,
ranking, route outcome, decision result, or policy output.

### Domain model boundary

The public/caller-validated `EvidenceRef` path continues to reject
`externally_verified`. Implementation introduces a separate trusted internal
materialization type or constructor that can only be reached from the
PostgreSQL verification/promotion join.

The planning policy accepts mixed authority only under the new closed
contract:

- exactly one `externally_verified australia_program_fit`;
- all other Evidence exactly match the accepted synthetic baseline;
- no untrusted candidate Evidence;
- no external Evidence in cost, FX, or ranking roles;
- exact tenant, pack/version, entry hash, coverage, claim uniqueness, and
  evidence-role relationships.

The original synthetic operation retains its stricter all-synthetic contract.
Policy and adapter tests must prove the two operations cannot be confused.

### Durable execution

The new operation reuses the existing AgentTask table, worker, dispatch,
lease, heartbeat, retry, generation fencing, events, SSE, terminal result
transaction, and currentness rules. It adds no second queue or workflow
engine.

Task creation continues to require an assigned advisor, exact current Case
revision, exact promoted pack identity, Origin/CSRF protection, an
`Idempotency-Key`, and the current policy version.

A successful mixed task produces the existing typed `review_required`
PlanningRun. It cannot approve itself. Existing AdvisorReview creates the
family-safe Brief, and the existing family decision creates the receipt and
timeline.

## Public API and Command Surface

The capability adds these FastAPI routes:

- `POST /api/v1/cases/{case_id}/dra-candidates`
  - assigned-advisor candidate import;
- `GET /api/v1/cases/{case_id}/dra-candidates/{candidate_id}`
  - assigned-advisor bounded candidate/verification projection;
- `POST /api/v1/cases/{case_id}/dra-candidates/{candidate_id}/verification-decisions`
  - assigned-advisor atomic verify/reject and approve-time promotion.

The existing task endpoint accepts the additive operation
`generate_governed_mixed_planning_run_v1` only after the promoted pack exists.

Every mutation uses existing opaque session, tenant, role, Origin, CSRF,
idempotency, stale-version, non-enumeration, `no-store`, and RFC 9457-style
problem conventions.

No BFF route or browser UI is added. The existing connected `/demo` remains the
stable synthetic portfolio walkthrough.

The command surface is:

- `make dra-check`
  - required deterministic offline fixture, contract, migration, policy, and
    proof checks;
- `make dra-consumer-proof`
  - opt-in live proof controller requiring separately authorized inputs.

Default `make check`, `make proof`, Compose, and the connected demo remain
usable without DRA, a provider, or credentials.

Deterministic and live proof tooling uses a separate explicit synthetic Case in
a disposable database. It does not reuse, reset, or reinterpret the M5
connected-demo golden Case. Migrations remain seed-free; any proof Case is
created only by the existing explicit demo/proof seed boundary.

## Error and Failure Contract

Public errors use closed, bounded groups:

- DRA health or contract incompatibility;
- keyed-create reconciliation required/conflict/unavailable;
- polling deadline, transport, or response limit;
- terminal, fallback, review, delivery, result, artifact, or Evidence
  rejection;
- candidate schema/import/idempotency/Case-binding failure;
- source attestation/path/hash/metadata/mapping failure;
- verification actor/tenant/stale/idempotency/decision failure;
- atomic promotion/source-pack/provenance failure;
- mixed adapter pin/schema/baseline/provenance failure;
- planning, advisor, family, or proof-check failure.

Unknown causes remain unknown. Errors never include credentials, cookies,
CSRF values, local paths, raw exceptions, tracebacks, SQL, provider payloads,
canonical Markdown, snippets, or snapshot bytes.

Transport failure does not imply DRA cancellation. Candidate import failure
does not imply promotion. Promotion failure creates no accepted Evidence.
Planning failure does not roll back an already committed human verification;
it produces the existing bounded task/planning failure state and requires an
explicit newer corrective action.

## Deterministic Fixture and Required CI

Required CI consumes a reviewed copy of the released DRA downstream fixture
under a Night Voyager manifest that records:

- producer repository, release, exact commit, and fixture URL;
- fixture schema and exact SHA-256;
- Night Voyager projection/candidate schema;
- expected candidate and failure dispositions;
- exact Night Voyager synthetic baseline identities and hashes.

Required tests cover:

### DRA contract and candidate

- canonical health identity;
- keyed create, same-request replay, conflict, invalid key, unavailable, and
  lost-acknowledgement reconciliation;
- pending/running wait behavior;
- canonical generic artifact acceptance;
- fallback, review-required, blocked, failed, unavailable, unsafe, oversized,
  empty, unknown-kind, and hash mismatch rejection;
- exact Evidence allowlist, ordering, URL safety, and additive-field discard;
- candidate import idempotency and zero authority side effects.

### Verification and promotion

- assigned advisor, wrong role, unassigned actor, second tenant, missing
  context, and cross-tenant hiding;
- approve/reject row shapes and idempotent replay;
- stale Case/candidate/baseline, source mismatch, hash/metadata failure, and
  conflicting decision;
- concurrent approvals produce one result or a typed conflict;
- rejection creates no pack/Evidence;
- approval creates exactly one new pack version and one trusted external
  Evidence;
- injected failure at each write boundary rolls back all approve-time rows;
- caller, API role, and worker role cannot directly assert
  `externally_verified` or mutate authority tables;
- forced RLS, grants, ownership, fixed `search_path`, PUBLIC revoke, pool
  cleanup, downgrade/re-upgrade, and fresh-volume behavior.

### Mixed planning and existing closure

- exact synthetic baseline file/canonical-manifest/policy pins;
- exactly one external program-fit allowlist;
- duplicate, missing, wrong-role, wrong-claim, wrong-pack, untrusted, external
  cost/FX/ranking, or baseline drift failures;
- mutation removing or changing the promoted program-fit Evidence prevents a
  review-required result;
- original synthetic task remains compatible;
- durable task lease/retry/fencing/SSE and finalization remain unchanged;
- candidate import and promotion do not skip AdvisorReview or family gates;
- the existing advisor approval and family decision complete to receipt and
  timeline in a disposable PostgreSQL/Compose proof.

Live-provider tests are excluded from required CI.

## Delivery Plan

The deterministic capability is split into two independently reviewable code
changes. A live evidence change is optional and separately authorized.

### PR 1 — governed candidate and atomic promotion

Includes:

- strict DRA projection and optional transport;
- copied fixture manifest and offline compatibility checks;
- candidate contract and persistence;
- atomic verification/promotion authority;
- migration `0005` with the two new tables and trusted Evidence path;
- candidate/verification API;
- ADR, reference, operations, and deterministic proof documentation.

`main` remains valid after PR 1. It can import and govern a candidate into a
new source-pack revision, but it does not yet expose the new planning operation.

### PR 2 — governed mixed planning closure

Includes:

- additive task operation and trusted mixed materializer;
- migration `0006` for operation/function constraints when required;
- domain/policy changes for the single external allowlist;
- durable task and existing advisor/family closure proof;
- full database, Compose, documentation, and release-verifier integration.

PR 2 starts only from merged and hosted-verified PR 1. Unmerged stacking is not
used.

### Optional PR 3 — pinned live evidence

This step exists only after separate authorization and one successful bounded
provider run. It contains sanitized proof artifacts and public documentation,
not runtime or contract changes.

One failed, fallback, review-required, blocked, unavailable, ambiguous, unsafe,
or hash-mismatched live attempt is retained as a failed attempt and is not
automatically retried.

## Live Proof Authorization Gate

No live provider run is authorized by this design or its implementation plan.
Before a live attempt, the operator must separately approve:

- exact DRA and Night Voyager merged commits;
- DRA loopback base URL and authentication environment;
- provider/model configuration inside DRA;
- public-safe query text and hash;
- one-attempt maximum;
- polling deadline;
- provider cost estimate or upper bound;
- selected official source snapshot and lawful link-only representation;
- sanitized output/report location and disclosure boundary.

The live report may record only bounded identities, hashes, statuses, source
URLs, promotion relationships, and explicit limitations. It excludes artifact
content, snippets, credentials, cookies, local paths, provider payloads,
trace/checkpoint data, snapshot bytes, stack traces, and raw exceptions.

## Framework Reuse Decision

The implementation reuses existing owners:

- Pydantic strict models for bounded external contracts;
- FastAPI session/CSRF/Origin/error conventions;
- SQLAlchemy/asyncpg and PostgreSQL functions, transactions, constraints, RLS,
  and grants;
- the existing AgentTask worker, lease, retry, fencing, SSE, and planning
  finalization;
- the existing deterministic planning policy and human decision workflow.

No Agent framework belongs in the Night Voyager consumer/promotion path.
LangChain, DeepAgents, LangGraph, and LangSmith remain inside DRA. Framework
HITL cannot replace Night Voyager source attestation, Evidence promotion,
AdvisorReview, or family decision.

Before implementation, verify the installed Pydantic, FastAPI, SQLAlchemy,
asyncpg, and optional HTTP-client versions and the current official
documentation for the behavior actually used. Framework or library reuse must
not weaken deterministic authority, testability, or default offline operation.

## Documentation Impact

The two capability PRs update, as applicable:

- bilingual README scope and limitations;
- architecture and dependency direction;
- HTTP API reference;
- Evidence/source-manifest reference;
- AgentTask/worker reference;
- database-role and migration operations;
- one accepted ADR for DRA candidate verification and atomic promotion;
- deterministic DRA proof runbook and evidence index;
- release `Unreleased` notes only if the repository currently maintains them.

Public documentation must use `local mixed-evidence human-governed proof` or
equivalent precise language. It must not claim production deployment, real
students, automated admissions advice, complete live evidence, provider
accuracy, current institutional coverage, business outcomes, or exactly-once
cross-service execution.

No release number is precommitted. Version and publication decisions occur
only after the deterministic capability is merged and any separately approved
live evidence is evaluated.

## Stop Conditions

Stop implementation and return to design if any of these becomes necessary:

- a DRA endpoint, field, schema, profile, canonical artifact, or runtime change;
- Markdown parsing to create typed domain facts;
- more than one external claim or any external cost/ranking/eligibility fact;
- a generic persisted source-fact or PlanningInput snapshot platform;
- server-side arbitrary path access, general upload, crawler, or automatic
  source fetching;
- automatic promotion, advisor approval, or family decision;
- DRA/framework state becoming Night Voyager business authority;
- a second queue, workflow engine, Evidence enum, or decision ledger;
- changing existing tenant identity, AdvisorReview, or FamilyDecision
  authority;
- combining DRA and MKE in one proof;
- live provider execution before separate authorization;
- more than one live attempt without new authorization;
- source bytes or metadata that cannot be represented safely and lawfully;
- required CI depending on credentials, network access, or a live DRA service.

If run-level Evidence and human source inspection cannot support the bounded
mapping without parsing prose into domain facts, record that exact blocker and
design a generic structured DRA outcome separately. Do not expand this feature
in place.

## Acceptance Criteria

### Deterministic capability

The feature is complete only when:

1. Night Voyager pins and validates the released DRA v1 fixture without a live
   producer.
2. Keyed create and lost-response reconciliation preserve one DRA run identity
   and fail closed on conflict or unavailability.
3. Canonical, fallback, review, blocked, failed, unavailable, unsafe,
   oversized, empty, unknown-kind, and hash-mismatch paths have deterministic
   dispositions.
4. A valid canonical result creates only an immutable untrusted candidate.
5. Candidate import creates no accepted Evidence or decision state.
6. Human verification and approve-time promotion execute through one atomic
   authority gate.
7. Rejection and every stale, unauthorized, mismatched, conflicting, or
   concurrent failure leave no partial promotion.
8. Approval creates exactly one source-pack revision and exactly one
   externally verified `australia_program_fit` Evidence reference.
9. The new mixed planning operation consumes that exact external Evidence and
   the exact synthetic baseline, while the original synthetic operation stays
   compatible.
10. Removing or mutating the external program-fit Evidence prevents the
    expected review-required planning outcome.
11. Existing AdvisorReview and family decision gates remain mandatory.
12. Migration, RLS, grants, idempotency, concurrency, API, worker, policy,
    docs, public-safety, full local gates, and hosted required checks pass.

### Optional live closure

The live closure is complete only when:

1. one separately authorized provider-backed DRA run reaches a canonical
   non-fallback ready result within the approved deadline and cost bound;
2. the observed projection passes the released DRA v1 contract;
3. the exact merged Night Voyager consumer imports one untrusted candidate;
4. an assigned advisor attests one exact official source for the bounded claim;
5. the atomic gate creates one promoted external Evidence and no automatic
   planning or decision side effect;
6. the governed mixed task, deterministic policy, AdvisorReview, family
   decision, receipt, and timeline complete through existing authorities;
7. mutation proof demonstrates that the external program-fit Evidence is
   materially required;
8. a sanitized report pins exact producer/consumer commits and states all
   mixed-evidence and non-production limitations.

## Alternatives Rejected

### Candidate-only compatibility proof

This is smaller but stops before Night Voyager Evidence, planning, and human
decision authority. It does not demonstrate the desired product closure.

### Generic persisted-input planning platform

Night Voyager does not yet persist a reusable source-level cost/ranking input
model. Adding generalized source-fact tables or arbitrary PlanningInput
snapshots would expand architecture and delivery time without improving the
bounded proof. It is deferred until a real second use case requires it.

### Direct DRA planning adapter

DRA generic Markdown and run-level Evidence are research material, not a typed
Night Voyager PlanningInput. Letting DRA produce route outcomes or policy facts
would bypass source manifests and deterministic policy.

### Treat DRA verification as Night Voyager verification

DRA verification has a different authority domain. It may remain provenance,
but it cannot substitute for the assigned Night Voyager advisor and exact Case
mapping.

### Automatic source fetch and verification

Automatic fetching adds network, content-safety, redirect, storage, copyright,
and truth-evaluation concerns. The v1 proof instead records an explicit human
attestation over a bounded link-only source snapshot.

### Browser integration

The connected `/demo` is already a stable synthetic portfolio walkthrough.
Adding another UI lane would increase scope without strengthening the core
cross-project authority proof.
