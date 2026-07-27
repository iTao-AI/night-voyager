# ADR 0011: DRA v0.1.6 live consumer boundary

## Status

Accepted. PR A, PR B, PR C, and the post-release strict-consumer prerequisite are
implemented provider-free. Two bounded live attempts projected 25 and 83
same-run Evidence rows, all `uncited`, and stopped safely before candidate
import with no Night Voyager business mutation. Strict live acceptance remains
incomplete and the capability remains `INCOMPLETE_PENDING_LIVE_ACCEPTANCE`.

## Current runtime correction

The numbered `0010` decision below records the historical DRA v0.1.6 boundary.
Current migration `0011` preserves that release-referenced legacy branch and
adds a separate commit-referenced strict branch. The DRA strict profile is pinned
to exact post-release commit
`01ba21f2996769e68cbc88f4bb0596740df27f6b`, profile
`generic-strict-citation@1`, proof schema
`dra.strict-citation-profile.v1`, and the unchanged copied downstream contract.
It is not a DRA v0.1.6 release capability.

The existing candidate endpoint accepts only a discriminated v1 legacy or v2
strict request. The application converts the v2 shape to the strict PostgreSQL
overload; mixed and extra-field shapes fail closed. Both exact import overloads
and the verification function remain API-only, while the worker and `PUBLIC`
have `EXECUTE=false`. Forced RLS and the no-direct-DML boundary are unchanged.
Downgrade to `0010` refuses before mutation when strict commit-referenced history
exists; an empty or legacy-only database can downgrade safely.

The two bounded live attempts stopped before candidate import. No third provider
attempt is authorized, so provider-free readiness and evaluation evidence do
not establish strict live acceptance.

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
18. Candidate freeze rejects an unapproved recovery command before subprocess
    execution, independently runs the default-threshold host/VM preflight, binds
    the canonical task project's complete before/after Docker inventories, and
    re-queries exact-head hosted checks, final merged-PR head, and reviewed/merge
    tree equality. Docker evidence v3 hashes a closed, deterministically ordered
    semantic projection of all six inventories rather than raw CLI presentation
    bytes; unordered labels and parent sets are normalized, display-relative time
    fields are excluded, and malformed or duplicate identities fail closed.
    Recorded and live host/VM availability are independently checked against the
    fixed thresholds rather than compared to each other. The doctor semantic hash
    normalizes only those two numeric observations while retaining the complete
    closed pass-marker contract. Recovery evidence v2 binds the exact allowlisted
    command to a positive pytest passed count; freeze reruns it with `check=True`
    and ignores elapsed-time presentation only. Superseded Docker v1/v2 and
    recovery v1 evidence fail closed.
    Independent human review authority is an explicit closed v2 attestation
    binding the exact reviewed head, `CLEAN` verdict, opaque review record
    identity and SHA-256, and a fixed human acknowledgement. It is not inferred
    from PR text, merge state, automation, or GitHub Review state. Missing,
    malformed, stale, cross-head, non-`CLEAN`, wrongly acknowledged, or
    extra-field attestations fail closed; superseded v1 evidence shapes are
    rejected.
19. The current provider request uses
    `night-voyager.dra-live-effective-query.v2`. Night Voyager deterministically
    composes one operator-supplied bounded base business query with a code-owned
    citation clause. The clause requires at least one public HTTPS source actually
    returned by `internet_search` and admitted by the current source-admission
    contract to appear in the final canonical report as its exact raw URL; it
    forbids inventing, altering, normalizing, or guessing a URL. Candidate readiness,
    frozen intent, provider create bytes, candidate request identity, and
    pre-provider revalidation bind the same effective query hash. Legacy v1
    readiness/intent identities, reserved-marker injection, clause replacement,
    CR/LF, empty input, hash drift, and post-composition oversize fail closed.

## Consequences

- `make dra-check` can prove the exact v0.1.6 producer, projection, raw URL,
  reconciliation, fake transport, and evaluation contracts offline.
- `make db-check` proves the ordinary fresh graph through `0011`; the focused
  `scripts/run_db_tests.sh dra-strict-migration` lane proves exact legacy/strict
  overload identity, historical row readability, RLS/grant parity, strict-history
  downgrade refusal, and safe empty-history downgrade/re-upgrade.
- The deterministic Compose governed-flow proof imports the v0.1.6 scenario
  candidate, but still uses checked-in synthetic bytes and no provider.
- PR A, PR B, PR C, and strict-consumer PR 1 supply provider-free implementation
  and deterministic recovery proof. Both bounded attempts remain safe-stop
  evidence; no third provider attempt, operational strict candidate freeze, or
  successful terminal acceptance was performed.

## Non-claims

This decision does not prove provider quality, source truth, production readiness,
admissions outcomes, real-user use, release completion, or deployment.
