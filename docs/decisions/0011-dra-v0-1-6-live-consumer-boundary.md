# ADR 0011: DRA v0.1.6 live consumer boundary

## Status

Accepted. PR A, PR B, and PR C are implemented provider-free. Live provider proof
was not run, and governed live acceptance remains
`INCOMPLETE_PENDING_LIVE_ACCEPTANCE`.

## Context

Night Voyager already owns candidate import, human source verification, atomic
Evidence promotion, governed mixed planning, advisor review, and family decision
authority. The historical copied `dra.downstream-consumer.v1` fixture pins DRA
`v0.1.3` and remains the immutable compatibility proof.

DRA `v0.1.6` adds the producer identity and live status/result/Evidence surface
needed by a later bounded acceptance. Night Voyager must consume that surface
without allowing producer metadata, URL normalization, model output, or evaluation
code to create product authority.

## Decision

1. Migration `0010` keeps historical exact `v0.1.3` rows readable but admits new
   candidate imports only from exact
   `v0.1.6@7d43324b469cb5e445c2e8be83af3be4d841cf1c`.
2. The historical fixture bytes and migration `0005` remain unchanged.
3. The loopback transport uses the public `/health` path and allowlists only the
   ownership, terminal state, artifact, and Evidence fields required by the
   consumer.
4. Evidence is reduced to the consumer projection only after exact accepted
   `run_id` and `segment_id` ownership checks.
5. Public HTTPS validation may parse a URL temporarily, but comparison and durable
   identity use the original bounded string byte-for-byte.
6. An ambiguous create never triggers automatic replay. A separate authorization is
   required to replay the exact request and idempotency key.
7. Migration `0010` exposes one API-only, actor-context-bound, read-only outcome
   projection. It adds no generic SQL, table grant, DML grant, or runtime role.
8. Evaluation is pure and observes redacted receipts plus authoritative
   projections. It cannot import, promote, plan, review, decide, or repair state.
   Canonical JSON excludes clocks and duration; duration is non-canonical report
   metadata.
9. Required CI uses only the checked-in scenario and fake transport. It performs no
   provider call and makes no governed-live success claim.
10. Stage 1 is a two-step boundary. `capture-live` stops at
    `operator_action_required`; only provider-free `select-and-import` accepts the
    operator's URL-only selection and imports an `UNTRUSTED_CANDIDATE`.
11. Ambiguous create replay requires separate exact authorization. Late polling
    resumes only the same run. There is no automatic retry or remote cancellation.
12. Receipts use descriptor-bound create-once storage and retain bounded identities
    only. Artifact bytes span inspection/import and are removed on success, handled
    failure, or interrupt; orphaned bytes block recovery until acknowledged cleanup.
13. Stage 2 validates a separately supplied private snapshot through descriptor-bound
    no-follow traversal, binds its exact bytes and original selected URL, and deletes
    the task-owned copy on every handled exit before retaining only identity metadata.
14. Stage 3 and Stage 4 reuse the existing AgentTask/worker/SSE, AdvisorReview,
    family decision, DecisionReceipt, and TimelinePlan authorities. Every mutation
    has a domain-separated key and authoritative lost-ack reconciliation.
15. Outcome evaluation reads only `app.project_dra_live_outcome(...)`. A family
    decision yields `decision_recorded`; only the complete provider-free evaluator
    can yield `closure_passed`.
16. Provider-free Stage 2–4 and evaluation rehearsal crosses a real subprocess
    boundary at every stage. Each process reopens durable receipts and receives
    only its role-specific ephemeral authority.
17. Mutation transport loss becomes a bounded ambiguous outcome at the HTTP POST
    boundary. Task and AdvisorReview reconciliation use narrow actor/key-bound
    reads over existing idempotency authority rather than process-local caches.
18. Candidate freeze independently re-runs or re-queries recovery, Docker,
    exact-head hosted checks, merged-PR, and approved-review evidence; closed JSON
    shape and caller-written terminal strings are insufficient.

## Consequences

- `make dra-check` can prove the exact v0.1.6 producer, projection, raw URL,
  reconciliation, fake transport, and evaluation contracts offline.
- `make db-check` proves `0009 -> 0010`, historical row readability, exact live-only
  new imports, API-only outcome projection, RLS/grant parity, and downgrade refusal
  when live history exists.
- The deterministic Compose governed-flow proof imports the v0.1.6 scenario
  candidate, but still uses checked-in synthetic bytes and no provider.
- PR A, PR B, and PR C supply the provider-free implementation and deterministic
  recovery proof. Candidate freeze, separately authorized live acceptance, and its
  terminal evaluation remain outstanding.

## Non-claims

This decision does not prove provider quality, source truth, production readiness,
admissions outcomes, real-user use, release completion, or deployment.
