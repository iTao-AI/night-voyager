# M3A Deterministic Planning Implementation Plan

**Implementation status:** Complete. The tasks below preserve the historical
implementation recipe.

**Goal:** Add the deterministic Case, source-pack, Evidence, and PlanningRun foundation.

**Architecture:** Keep versioned schemas, state transitions, and aggregation pure. Persist
immutable tenant-keyed records through migration-owned PostgreSQL structures behind M2 RLS.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL 18, pytest.

## Global Constraints

- Exact migration graph: `0001 -> 0002`, with one head and exactly eleven M3A tables.
- No M3B advisor/family authority, M4 worker/SSE, M5 frontend, or production claim.
- `accepted_synthetic_demo` is visibly synthetic and differs from externally verified Evidence.
- Every behavioral slice records observed RED before minimal GREEN.

## Execution tasks

1. Add failing architecture tests, then freeze this spec, plan, ADR, dependency direction,
   table cap, migration graph, exclusions, and verification surfaces.
2. Add failing schema/policy/transition tests, then implement immutable versioned values,
   exact reason codes, recommendation cardinality, evidence completeness, and terminal states.
3. Add failing catalog/RLS/integration tests, then implement seed-free migration `0002`,
   tenant-preserving keys, forced RLS, exact grants, CAS pointers, and immutable terminals.
4. Add failing fixture/validator tests, then add stable synthetic manifests, offline
   `--validate-only`, idempotent explicit seed, and deterministic snapshot verification.
5. Update affected bilingual entry points, domain/source/database references, run all focused
   and required fresh gates, inspect the full base diff, and make intentional local commits.
