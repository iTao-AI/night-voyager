# ADR 0011: DRA v0.1.6 live consumer boundary

## Status

Accepted. The provider-free PR A foundation and PR B Stage 1 controller are
implemented. Live provider proof was not run, and governed live acceptance remains
unimplemented.

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

## Consequences

- `make dra-check` can prove the exact v0.1.6 producer, projection, raw URL,
  reconciliation, fake transport, and evaluation contracts offline.
- `make db-check` proves `0009 -> 0010`, historical row readability, exact live-only
  new imports, API-only outcome projection, RLS/grant parity, and downgrade refusal
  when live history exists.
- The deterministic Compose governed-flow proof imports the v0.1.6 scenario
  candidate, but still uses checked-in synthetic bytes and no provider.
- PR B supplies the provider-free-tested Stage 1 execution controller. PR C remains
  approved but not implemented and must supply promotion-through-decision closure
  before capability completion can be claimed.

## Non-claims

This decision does not prove provider quality, source truth, production readiness,
admissions outcomes, real-user use, release completion, or deployment.
