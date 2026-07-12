# M3A Deterministic Planning Design

M3A adds a backend-only deterministic foundation on the accepted M2 identity
and RLS boundary. Immutable `StudentCase` revisions keep student and family
preferences separate. Versioned source packs bind declared paths and SHA-256
hashes to claim-level `EvidenceRef` records. Optional cost and ranking evidence
never represents an unknown value as zero.

Pure versioned schemas feed deterministic policy. Invalid authority or input
fails closed; recommendation cardinality and evidence completeness determine
`blocked` versus `review_required`. Narrative and ordering are non-authoritative.

Migration `0002` creates exactly eleven tenant-keyed tables with tenant-
preserving foreign keys, forced RLS, narrow API inserts/reads and column-level
pointer/run-state updates. The worker has reads only and no M3A write grant.
The migration contains no seed data. Public-safe stable fixtures are validated
without a database and explicitly seeded only in development/test demo mode.

The bounded synthetic snapshot is Australia as the only fully evidenced
`recommended_with_condition` route, Japan as a conditional high-risk
alternative, and Malaysia blocked for missing direct program-fit evidence.
This is not current study-abroad advice. Advisor review, family workflow,
worker/SSE execution and frontend integration remain deferred.
