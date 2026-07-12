# M3A Deterministic Planning Design

M3A adds a backend-only deterministic foundation on the accepted M2 identity
and RLS boundary. Immutable `StudentCase` revisions keep student and family
preferences separate. Versioned source packs bind declared paths and SHA-256
hashes to claim-level `EvidenceRef` records. Optional cost and ranking evidence
never represents an unknown value as zero.

Pure exact-version schemas feed deterministic policy. Callers provide typed
Case, budget, source-manifest, Evidence, complete Decimal cost/FX, and optional
ranking facts; they do not provide route outcomes or required claim sets.
Invalid authority, tenant, version, pack or hash binding fails closed. Narrative,
ranking, fixture ordering, and renamed claims cannot grant recommendation authority.

Migration `0002` creates exactly eleven tenant-keyed tables with tenant-
preserving foreign keys, forced RLS, runtime reads, and narrow SECURITY DEFINER
mutation functions. Runtime roles have no direct M3A table-write grant. Case
revision publication uses expected-version CAS; database triggers enforce run
transitions, terminal immutability, exact entry hashes and pinned-pack links.
The migration contains no seed data. Public-safe stable fixtures are validated
without a database and explicitly seeded only in development/test demo mode.

The bounded synthetic snapshot is Australia as the only fully evidenced
`recommended_with_condition` route, Japan as a conditional high-risk
alternative, and Malaysia blocked for missing direct program-fit evidence.
This is not current study-abroad advice. Advisor review, family workflow,
worker/SSE execution and frontend integration remain deferred.
