# Documentation

- Evaluators: use the Docker-only sequence in the [English quick start](../README.md) or [中文快速开始](../README_CN.md).
- Interviewers: start with the README scope and current limits, then use the fixture-only `/demo` route and [design contract](../DESIGN.md) to review the advisor-to-family workflow without treating it as a connected backend.
- Contributors: follow the [change-to-test matrix and guardrails](../CONTRIBUTING.md).
- Maintainers: apply the [security policy](../SECURITY.md), CI gates, release verifier, and public-hygiene proof.
- Database reviewers: run `make db-check`, then inspect the [identity/RLS ADR](decisions/0001-identity-session-and-rls-boundary.md), [deterministic planning ADR](decisions/0002-deterministic-planning-and-evidence-authority.md), [advisor/family ADR](decisions/0003-advisor-family-decision-authority.md), [durable task ADR](decisions/0004-durable-agent-task-authority.md), [HTTP contract](reference/http-api-v1.md), [AgentTask/event reference](reference/agent-tasks-and-events.md), [role operations](operations/database-roles.md), and [worker/SSE operations](operations/worker-and-sse.md).
- MKE compatibility reviewers: inspect the [M4B design](superpowers/specs/2026-07-13-m4b-mke-readonly-consumer-design.md) and [MKE Evidence boundary ADR](decisions/0005-mke-readonly-evidence-boundary.md). M4B is design-approved but not implemented; the default evaluator and M4A runtime remain MKE-free.

M1 freezes the visual contract; M2 adds identity/session/RLS; M3A adds deterministic planning; M3B adds the local synthetic advisor-to-family backend proof; M4A adds a local deterministic durable worker and authorized SSE replay proof. M4B has an accepted read-only MKE Evidence boundary design but is not implemented. The fixture-only `/demo` remains disconnected.
