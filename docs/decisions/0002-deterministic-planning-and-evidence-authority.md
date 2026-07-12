# ADR 0002: Deterministic planning and Evidence authority

Status: Accepted

M3A places immutable Case revisions, versioned source packs, claim-level
`EvidenceRef` records, and deterministic `PlanningRun` results behind the M2
`ActorContext` and forced-RLS boundary. Pure schemas and policy do not import
FastAPI, SQLAlchemy, Alembic, asyncpg, or Agent SDKs. PostgreSQL adapters may
depend inward on those contracts; the pure layer never depends outward.

Evidence authority is explicit: `untrusted_candidate` fails a run and
`accepted_synthetic_demo` is usable only as visibly synthetic local proof.
`externally_verified` requires a separate trusted authority record and cannot
be self-asserted through the M3A input contract. Confidence, narrative, fixture
order, tool output, ranking, and model output never grant authority.

Policy—not the caller—derives route outcomes. Australia becomes the sole
`recommended_with_condition` only with program-fit, tuition, living-cost and FX
Evidence, complete period/intake cost facts, and total cost within the approved
elasticity and hard ceiling. Missing/refused/over-ceiling budget blocks it.
Japan is a conditional high-risk alternative only when its risk is accepted;
Malaysia remains blocked without exact direct program-fit Evidence.
Cost and ranking projections must bind each role to its exact claim; duplicate
claims and non-`AUD` M3A cost projections fail closed.
Invalid schema, hash, tenant or version input, and accepted untrusted candidate
material become `failed`. Terminal output is immutable.

Migration `0002` follows `0001` as the single head and owns exactly eleven M3A
tables. It is seed-free, tenant-keyed, migrator-owned, forced-RLS protected,
and exposed through narrow SECURITY DEFINER functions. Runtime roles receive no
direct M3A writes; CAS, allowed transitions, terminal immutability and relational
provenance are database-enforced.
The database atomically advances a current Case from `planning` to
`advisor_review` only when its current revision publishes a current
`review_required` run. Generic Case transition authority cannot perform that
handoff. M3A excludes `AdvisorReview`, family briefs and
decisions, background tasks/SSE, frontend integration, and production claims.
