# Approved Specs and Plans

These specs and plans are approved, public-neutral implementation history. They explain
intent and delivery sequencing but are not current runtime authority. When records
disagree, use this order:

1. executable code and tests;
2. accepted ADRs;
3. current reference and release documentation;
4. historical specs and plans.

Historical references to skills, subagents, or controllers record how work was planned at
the time. They do not override the current repository rules in [AGENTS.md](../../AGENTS.md).

| Scope | Status | Specs and plans |
| --- | --- | --- |
| M2 identity, session, and RLS | Implemented | [Spec](specs/2026-07-12-m2-identity-session-rls-design.md) · [Plan](plans/2026-07-12-m2-identity-session-rls.md) |
| M3A deterministic planning | Implemented | [Spec](specs/2026-07-12-m3a-deterministic-planning-design.md) · [Plan](plans/2026-07-12-m3a-deterministic-planning.md) |
| M3B advisor and family decision | Implemented | [Spec](specs/2026-07-13-m3b-advisor-family-decision-design.md) · [Plan](plans/2026-07-13-m3b-advisor-family-decision.md) |
| M4A durable AgentTask and SSE | Implemented | [Spec](specs/2026-07-13-m4a-durable-agent-task-sse-design.md) · [Plan](plans/2026-07-13-m4a-durable-agent-task-sse.md) |
| M4B MKE read-only consumer | Implemented | [Spec](specs/2026-07-13-m4b-mke-readonly-consumer-design.md) · [Plan](plans/2026-07-13-m4b-mke-readonly-consumer.md) |
| M5 connected advisor-to-family demo | Implemented | [Spec](specs/2026-07-14-m5-connected-advisor-family-demo-design.md) · [Plan](plans/2026-07-14-m5-connected-advisor-family-demo.md) |
| DRA governed candidate and mixed planning | Implemented and released in v0.1.1 | [Spec](specs/2026-07-15-dra-governed-mixed-evidence-closure-design.md) · [Plan](plans/2026-07-15-dra-governed-mixed-evidence-closure.md) |
| DRA v0.1.6 governed live closure | PR A/B/C and effective-query v2 released in v0.1.4 as provider-free Night Voyager consumer evidence; two live attempts safely stopped pre-import; acceptance incomplete | [Spec](specs/2026-07-25-dra-v0-1-6-governed-live-closure-design.md) · [PR A plan](plans/2026-07-25-dra-v0-1-6-live-closure-pr-a-implementation-plan.md) · [PR B plan](plans/2026-07-25-dra-v0-1-6-live-closure-pr-b-implementation-plan.md) · [PR C plan](plans/2026-07-25-dra-v0-1-6-live-closure-pr-c-implementation-plan.md) |
| DRA strict consumer and versioned planning revision | PR 1, PR 2, and PR 3 released in v0.1.4 as controlled provider-free evidence; strict live acceptance incomplete | [Spec](specs/2026-07-27-dra-strict-revision-lineage-design.md) · [PR 1 plan](plans/2026-07-27-dra-strict-consumer-pr-1-implementation-plan.md) · [PR 2 plan](plans/2026-07-27-versioned-planning-revision-pr-2-implementation-plan.md) · [ADR 0012](../decisions/0012-versioned-planning-revision-authority.md) · [PR 3 plan](plans/2026-07-27-planning-revision-journey-pr-3-implementation-plan.md) |
| Governed Collaboration Core v1 | Implemented and released in v0.1.2 | [Spec](specs/2026-07-16-governed-collaboration-core-design.md) · [PR A plan](plans/2026-07-16-governed-conversation-memory-authority.md) · [PR B plan](plans/2026-07-16-versioned-skill-runtime-pinning.md) · [PR C plan](plans/2026-07-16-collaboration-walkthrough-and-inspector.md) |
| Governed Fact-to-Plan Closure and bilingual presentation | Implemented and released in v0.1.3 | [Spec](specs/2026-07-22-governed-fact-to-plan-closure-design.md) · [PR 1 plan](plans/2026-07-22-explicit-planning-start-authority.md) · [PR 2 plan](plans/2026-07-22-governed-fact-to-plan-walkthrough.md) · [PR 3 plan](plans/2026-07-22-chinese-first-portfolio-presentation.md) |
| High-End Portfolio Entry v1 | Implemented and released in v0.1.3 | [Plan](plans/2026-07-23-high-end-portfolio-entry.md) |
