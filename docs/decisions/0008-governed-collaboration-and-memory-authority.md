# ADR 0008: Govern collaboration and confirmed-fact authority

- Status: Accepted
- Date: 2026-07-17
- Implementation status: Implemented by migration `0007` and the PR A backend
  boundary; unreleased after `v0.1.1`

## Context

Night Voyager already owns tenant identity, Case revisions, planning, human review,
family decisions, and durable tasks. It did not previously preserve how an assigned
student or parent communicated a material profile change, how that statement became
a reviewable proposal, or which confirmed proposal informed a later Case revision.

A generic chat or automatically extracted memory would weaken the existing authority
model. Message text, provider confidence, repeated wording, and worker output cannot
be allowed to change a Case. The collaboration boundary must preserve shared
communication while keeping fact promotion explicit, deterministic, tenant-scoped,
and human-gated.

## Decision

PostgreSQL is the business authority for governed collaboration. Migration `0007`
adds exactly these six migrator-owned, tenant-keyed tables:

- `collaboration_threads`;
- `message_events`;
- `memory_candidates`;
- `memory_candidate_verifications`;
- `confirmed_facts`;
- `case_revision_confirmed_fact_refs`.

Every table has enabled and forced row-level security, a tenant `USING` and
`WITH CHECK` policy, immutable-row protection, and composite tenant/Case lineage
constraints. Runtime roles receive no direct table DML or `TRUNCATE` authority.
`night_voyager_api` may execute only four mutation functions and four role-scoped
read projections. `night_voyager_worker` and `PUBLIC` receive no collaboration
function authority.

The records have deliberately different meanings:

1. A `MessageEvent` is an immutable shared communication record. It grants no Case
   authority.
2. A `MemoryCandidate` is one strict, revision-pinned proposal created only by the
   student or parent who authored its source message. It is not a fact.
3. A `ConfirmedFact` is created only by an assigned advisor's explicit confirmation.
   It retains the candidate, message, subject, advisor, value, version, and
   supersession lineage.

Candidate status is derived, not updated in place. The precedence is terminal
`confirmed|rejected`, then `stale`, then `expired`, otherwise `pending`. Expiry uses
the PostgreSQL clock and a fixed seven-day interval.

Advisor verification is one atomic authority transaction. Rejection creates one
terminal verification, audit event, and idempotency response, but no fact or Case
revision. Confirmation locks the Case, candidate, current fact head, and current
PlanningRun in the approved order, then creates the terminal verification,
ConfirmedFact, next `StudentCaseRevision`, complete current fact references, Case
revision compare-and-swap, applicable PlanningRun currentness change, audit event,
and idempotency response. All writes commit or all roll back. Confirmation is
allowed only for a current candidate while the Case is in `intake` or `planning`
and no task is `queued`, `leased`, `running`, or `waiting_review`.

The API role can no longer execute the legacy whole-revision writer
`publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)`, and the Python
runtime revision-publication seam is removed. The function remains available only
to the migrator for explicit bootstrap and test setup. Runtime collaboration may
publish a new revision only through `verify_memory_candidate(...)`.

FastAPI exposes exactly eight `/api/v1` collaboration endpoints. Mutations reuse the
opaque session, exact Origin, session-bound CSRF, canonical request hashing, and
`Idempotency-Key` boundary. Reads are assigned-participant projections, responses
are `no-store`, authorization failures are non-enumerating, and error bodies use a
closed bounded vocabulary. Advisors receive provenance and history; students and
parents receive current facts and only their own proposal status without internal
IDs, source digests, verification reasons, or supersession history.
All current fact heads are returned independently of the advisor history bound.
Advisor-only superseded history uses a keyset cursor bound to the Case revision
visible on the first page. Successor verification revisions at or below that immutable
high-water mark define the cursor chain, so later commits cannot enter its history;
participant responses expose neither history nor cursor metadata.

The message thread remains capped at 1000 events. Same-key replay is resolved before
the cap; a different-key append after capacity returns the typed `409
collaboration_thread_full` problem. Existing `NV012` is mapped by operation:
append capacity and terminal candidate decisions remain distinct, while unexpected
uses fail closed rather than being broadly classified.

The explicit synthetic seed owns one primary collaboration Case and three negative
fixtures: active-task, stale-candidate, and expired-candidate. The seed is
idempotent, uses fixed public-safe identities through migrator-owned setup
functions, and does not change the existing default `/demo` Case.

Downgrade from `0007` to `0006` succeeds only when the six-table boundary is empty
and the reused audit/idempotency ledgers contain no exact PR A discriminator.
Unrelated earlier history does not block downgrade. Any collaboration row or exact
collaboration audit/idempotency history refuses downgrade before data is removed.
An allowed downgrade restores the exact `0006` legacy writer grant, run guard, and
planning-result persistence function.

## Consequences

- Shared Case conversation is durable without becoming Case authority.
- Human confirmation has complete fact-level provenance and cannot partially publish
  a revision.
- Tenant, assignment, source-author, currentness, terminal, active-task, and
  idempotency checks remain in PostgreSQL rather than UI or model output.
- Advisor verification and worker planning-result persistence both lock the Case
  before changing current PlanningRun state, eliminating their reverse lock order.
- New planning work after confirmation must be created explicitly against the new
  revision; confirmation does not create an `AgentTask` or advance Case state.
- The capability is a local synthetic backend proof and an unreleased post-`v0.1.1`
  change. It is not evidence of production tenancy, real users, or admissions
  outcomes.

## Deferred and rejected alternatives

PR B's versioned Skill registry, evaluation, activation, rollback, and runtime pins
are not implemented by this decision. PR C's `/demo/collaboration` browser
walkthrough and technical inspector are also deferred. Live-provider execution and
external transports such as email, messaging platforms, webhooks, or OpenClaw are
not part of PR A and were not run as proof.

Generic team chat, private participant channels, autonomous memory extraction,
vector memory, advisor-authored participant proposals, attachment storage,
notifications, message SSE, a second queue, a new identity role, and automatic
planning are rejected for this boundary. Future adapters must consume these
contracts and cannot replace PostgreSQL or advisor authority.
