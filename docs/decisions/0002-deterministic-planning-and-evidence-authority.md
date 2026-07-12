# ADR 0002: Deterministic planning and Evidence authority

Status: Accepted

M3A places immutable Case revisions, versioned source packs, claim-level
`EvidenceRef` records, and deterministic `PlanningRun` results behind the M2
`ActorContext` and forced-RLS boundary. Pure schemas and policy do not import
FastAPI, SQLAlchemy, Alembic, asyncpg, or Agent SDKs. PostgreSQL adapters may
depend inward on those contracts; the pure layer never depends outward.

Evidence authority is explicit: `untrusted_candidate` fails a run,
`accepted_synthetic_demo` is usable only as visibly synthetic local proof, and
`externally_verified` is reserved for evidence that passed an external
verification process. Confidence, narrative, fixture order, tool output, and
model output never grant authority.

Valid input with exactly one fully evidenced `recommended_with_condition`
route becomes `review_required`. Zero or multiple such routes become `blocked`.
Invalid schema, hash, tenant or version input, and accepted untrusted candidate
material become `failed`. Terminal output is immutable.

Migration `0002` follows `0001` as the single head and owns exactly eleven M3A
tables. It is seed-free, tenant-keyed, migrator-owned, forced-RLS protected,
and least-privilege granted. M3A excludes `AdvisorReview`, family briefs and
decisions, background tasks/SSE, frontend integration, and production claims.
