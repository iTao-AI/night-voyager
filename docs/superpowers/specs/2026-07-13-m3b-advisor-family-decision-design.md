# M3B Advisor and Family Decision Design

M3B adds a backend-only, local synthetic proof for the human authority steps
after M3A. A current immutable `review_required` `PlanningRun` remains the
planning output; M3B records human actions in separate immutable records and
never mutates that terminal result.

An assigned advisor may approve, reject, or request revision. Approval pins the
current Case revision, run, policy, source pack, Evidence projection, output,
review version, and source snapshot date. It creates one current immutable
family-safe `DecisionBrief` and advances the Case from `advisor_review` to
`family_review`. Reject and revision actions create no brief, close the attempt,
and return the Case to `planning`; another review requires a superseding run.

The family-safe projection contains route outcomes, eligible route IDs,
comparison facts, explicit accepted Evidence risks, and synthetic-proof labels.
It excludes source paths, raw provider/tool/model output, provider exceptions,
reviewer-only notes, secrets, and unrelated tenant metadata. Blocked routes stay
visible but cannot be eligible or selected. Risk acceptance is restricted to
explicit optional, stale, or unverified Evidence and cannot waive missing
required Evidence, blocked routes, budget elasticity, or language/exam risks.

An assigned student or parent makes a direct family decision. An assigned
advisor may separately record a decision only for an assigned student or parent
and only with source `family_consultation`. The decision pins the current brief,
selected eligible route, accepted CNY range, trade-offs, decision maker, recorder,
and source. Australia additionally requires the explicit budget-elasticity
trade-off and a range compatible with pinned M3A Case and cost facts. Malaysia
remains blocked. Japan remains an audited alternative and contributes no dates
to an Australia timeline.

The consequential transaction creates the immutable decision receipt, a
deterministic structured `TimelinePlan`, append-only audit events, and advances
the Case through `decided` to `plan_ready`. Exact expected versions and a single
current brief/decision make concurrent decisions deterministic. Idempotency is
scoped by organization, actor, operation, and key; it stores a canonical request
hash and immutable response reference, never the key as a secret or a response
body.

Migration `0003` follows `0002`, is seed-free, and owns exactly eight tenant
tables. All use tenant-preserving keys, forced RLS, explicit policies, and narrow
`SECURITY DEFINER` functions with fixed search paths and revoked PUBLIC execute.
Only the API role receives specific execution authority; the worker receives no
M3B writes. Generic table mutation cannot perform authority transitions.

The HTTP v1 surface contains advisor review, family-safe brief read, direct
family decision, and advisor-recorded decision endpoints. Mutations reuse the
opaque demo session, exact Origin, CSRF, and `Idempotency-Key` boundary. Responses
are `no-store`; errors use non-enumerating RFC 9457-style problem documents and
typed 409 conflicts. M3B adds neither share tokens nor participant-management
HTTP APIs. The M1 `/demo` remains fixture-only and disconnected.
