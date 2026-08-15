# Projection matrix

This is the current authority map for the reference-driven presentation. The root
uses a static same-Case projection with `¥300,000–400,000`; the persisted connected
outcome remains `¥305,500–400,000`. `/demo/plan` is an independently seeded
execution scenario and does not consume the connected Case or session.

| Source concept | Advisor projection | Family projection | Authority |
| --- | --- | --- | --- |
| `EvidenceRef` | citation, status, provenance, gap | family-safe evidence note | current forced-RLS rows |
| `PlanningRun` | current route and review inputs | selected route provenance | current Case revision and run |
| `AdvisorReview` | required review and rationale | reviewed provenance | persisted review |
| `DecisionBrief` | current Brief identity/status | family-safe Brief and requirements | current or decision-linked Brief |
| `FamilyDecision` | completion status | confirmation and consequence | idempotent persisted mutation |
| `DecisionReceipt` | completion summary | full persistent receipt | unique non-null `family_decisions.receipt_id` |
| `TimelinePlan` | completion summary | dated next steps | existing timeline row |
| `AgentTask` | task phase and progress | absent from main narrative | durable task/event rows |
| revision predecessor/successor | exact current task/run and deterministic country-keyed comparison in V2 | participant-safe durable journey phase only | request review, Case revision lineage, task-owned predecessor, and two validated run hashes |
| revision recovery | terminal failure carries bounded recovery; `revision_blocked` carries none | no recovery action | closed V2 adapter and model invariants |
| pending changed planning fact | advisor V2 phase only; no candidate payload | same boolean-derived phase for assigned advisor/student/parent | API-only `read_connected_journey_fact_pending`; current revision loaded inside PostgreSQL |
| `MemoryCandidate` | current handoff candidate | absent | current no-store candidate projection |
| `ConfirmedFact` + Case revision | current confirmed facts, fact version, and revision | family-safe fact after role rotation | PostgreSQL current fact heads and Case |
| presentation locale | exact `zh-CN` or `en` labels over the same projection | exact `zh-CN` or `en` labels over the same projection | presentation-only `localStorage`; no business authority |
| `TimelineExecution` current action | milestone/state/due date/accountable role/risk/next handoff plus advisor controls | the same server-owned facts plus only the accountable family action | PostgreSQL projection, immutable receipt, and fresh GET |
| execution activity | localized bounded technical disclosure | localized bounded technical disclosure | latest 64 durable rows plus exact total/truncation from PostgreSQL |
| portfolio presentation | static route/story preview and public boundary copy | absent; no session, task, or API effect | presentation-only React projection |

Before task creation, the checked-in fixture contract only limits the canonical
synthetic input identity and must match the existing source-pack row. It is not
a second business authority. The BFF forwards these projections; the client may
retain display/recovery metadata but cannot derive route, budget, trade-off,
role, currentness, or policy facts.

The collaboration envelope carries only recovery identity. During handoff, candidate,
current confirmed facts, Case revision, ledger, and Skill inspector are re-read from
server authority. `/demo` then consumes `ledger.canonical_task_inputs`; it never
copies task inputs or pins from collaboration state.

Existing advisor-ledger and current-decision-brief routes return V1 by default;
one exact `contract_version=2` selects V2. `/journey-status` returns only Case,
revision, phase, and verified active role. The browser cannot submit or retain
predecessor, run hash, comparison, candidate, or renewed-authorization authority.
