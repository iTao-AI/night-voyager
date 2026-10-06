# ADR 0016: Controlled intake revision source pins

Status: Accepted for local implementation. Full image/browser proof and hosted delivery remain separate gates.

## Context

A pre-consent synthetic family may defer the same Case from `2027-02` to
`2028-02`. Reusing the old intake's costs would make a different month look
supported without independent evidence. The existing fact, review, revision
and durable-task authorities already own the required state transitions.

## Decision

Migration `0017` extends those existing authorities with one closed intake
delta. Confirmation requires the assigned advisor's exact `request_revision`
review, an unfinalized current predecessor, the actual student proposal, and
the independently registered `50000000-0000-0000-0000-000000000017/v1` source.
Its manifest, all source metadata and accepted synthetic evidence must match
frozen pins. Unsupported or drifted evidence returns bounded
`409 intake_evidence_unavailable` (`NV027`) before publishing any revision.
Initial planning and the existing mixed-provider path retain their semantics.

The successor source is selected from the persisted intake delta and frozen
predecessor. Later non-intake revisions inherit that predecessor's source.
Caller-supplied Task pins must agree; worker loading repeats the authority
checks. There is no mutable current-intake source lookup or old-cost fallback.
The new pack remains outside the terminal retry allowlist introduced in `0016`.

An opt-in seed creates a separate unfinalized Case and complete initial intake
message/candidate/verification/ConfirmedFact lineage. Exact replay writes
nothing; conflicting source or Case data refuses atomically. Private helpers
are migrator-owned, use a fixed search path, and grant no direct execution to
PUBLIC, API or worker roles. Existing signatures, RLS and actor fences remain.

Downgrade checks all tenants using the existing migration guard pattern:
transactional exclusive locks, temporary table-owner inspection with FORCE
relaxed, and restoration of FORCE before any refusal. Persisted fixture,
intake lineage or new-source Tasks refuse downgrade. An empty downgrade
restores all five prior function bodies, OIDs and grants exactly.

The new source ships as wheel resources and through the existing image asset
layout. Comparison V2 and advisor ledger V3 explicitly expose the actual
intake and independently pinned cost; old country/budget read contracts remain
available. DecisionBrief V2 and the existing February date policy remain.

## Consequences

This is a closed local synthetic pilot with fixed as-of `2026-07-01`, rather
than current institutional pricing. The new cost is `32,640,000` CNY minor.
A fresh advisor review and explicit parent decision are still required.
Finalized Cases cannot be silently reopened. Historical runs, source packs,
reviews, decisions and published Release documents stay immutable.

See the [approved spec](../superpowers/specs/2026-10-06-controlled-intake-revision.md)
and [implementation plan](../superpowers/plans/2026-10-06-controlled-intake-revision.md)
for the fixed values, version negotiation and acceptance boundaries.
