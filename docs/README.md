# Documentation

- Evaluators: use the Docker-only sequence in the [English quick start](../README.md) or [中文快速开始](../README_CN.md).
- Interviewers: start with the README scope and current limits, then use the fixture-only `/demo` route and [design contract](../DESIGN.md) to review the advisor-to-family workflow without treating it as a connected backend.
- Contributors: follow the [change-to-test matrix and guardrails](../CONTRIBUTING.md).
- Maintainers: apply the [security policy](../SECURITY.md), CI gates, release verifier, and public-hygiene proof.
- Database reviewers: run `make db-check`, then inspect the [identity/RLS ADR](decisions/0001-identity-session-and-rls-boundary.md), [HTTP contract](reference/http-api-v1.md), and [role operations](operations/database-roles.md).

M1 freezes the product-flow and visual contract in [DESIGN.md](../DESIGN.md) and [docs/design/](design/). M2 adds a verified backend identity/session/RLS foundation, but it is not connected to the fixture-only `/demo` and does not add later domain workflow tables. The M1 page remains a synthetic fixture proof and makes no production or adoption claim. Run `make db-check` for the M2 database security evidence.
