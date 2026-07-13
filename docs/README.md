# Documentation

- Evaluators: use the Docker-only sequence in the [English quick start](../README.md) or [中文快速开始](../README_CN.md).
- Interviewers: start with the README scope and current limits, then use the fixture-only `/demo` route and [design contract](../DESIGN.md) to review the advisor-to-family workflow without treating it as a connected backend.
- Contributors: follow the [change-to-test matrix and guardrails](../CONTRIBUTING.md).
- Maintainers: apply the [security policy](../SECURITY.md), CI gates, release verifier, and public-hygiene proof.
- Database reviewers: run `make db-check`, then inspect the [identity/RLS ADR](decisions/0001-identity-session-and-rls-boundary.md), [deterministic planning ADR](decisions/0002-deterministic-planning-and-evidence-authority.md), [HTTP contract](reference/http-api-v1.md), and [role operations](operations/database-roles.md).

M1 freezes the product-flow and visual contract in [DESIGN.md](../DESIGN.md) and [docs/design/](design/). M2 adds identity/session/RLS; M3A adds deterministic Case, source-pack, Evidence and PlanningRun persistence. Neither backend is connected to fixture-only `/demo`. The M1 page and `accepted_synthetic_demo` records are synthetic proof, not production or external-verification claims.
