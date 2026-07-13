# ADR 0003: Advisor and family decision authority

Status: Accepted

M3B keeps M3A planning output immutable and represents advisor and family
authority as append-only records. A terminal `review_required` `PlanningRun`
does not transition again. Only a current, revision-pinned run may be reviewed,
and only an assigned advisor may create that review.

Approval atomically produces a current family-safe `DecisionBrief` and advances
the Case to `family_review`. Reject and request-revision records produce no brief
and return the Case to `planning`; a superseding run is required before another
review. Family decisions require an assigned student or parent, or an assigned
advisor explicitly recording an assigned family member's consultation decision.

PostgreSQL is the authority boundary. Migration `0003` owns eight tenant-keyed,
forced-RLS tables and narrow `SECURITY DEFINER` commands. Expected versions,
currentness constraints, participant checks, typed SQLSTATE conflicts, canonical
idempotency hashes, and append-only guards make stale and concurrent operations
fail closed. Runtime roles receive no broad writes, DELETE, ownership, or RLS
bypass; the worker receives no M3B mutation authority.

Decision transactions deterministically validate the selected route, budget,
and required trade-offs, then create an immutable receipt, structured timeline,
and audit events while advancing the Case to `plan_ready`. Date arithmetic is
pure deterministic code. Model or Agent output cannot approve Evidence, grant
authority, select a route, or change dates.

M3B is a local synthetic backend proof. It does not add share tokens, participant
management, production tenancy, frontend integration, live advice, or automatic
human decisions. The fixture-only M1 `/demo` remains disconnected.
