# Projection matrix

| Source concept | Advisor projection | Family projection | Authority |
| --- | --- | --- | --- |
| `EvidenceRef` | citation, status, provenance, gap | family-safe evidence note | current forced-RLS rows |
| `PlanningRun` | current route and review inputs | selected route provenance | current Case revision and run |
| `AdvisorReview` | required review and rationale | reviewed provenance | persisted review |
| `DecisionBrief` | current Brief identity/status | family-safe Brief and requirements | current or decision-linked Brief |
| `FamilyDecision` | completion status | confirmation and consequence | idempotent persisted mutation |
| `DecisionReceipt` | completion summary | full persistent receipt | existing receipt row |
| `TimelinePlan` | completion summary | dated next steps | existing timeline row |
| `AgentTask` | task phase and progress | absent from main narrative | durable task/event rows |

Before task creation, the checked-in fixture contract only limits the canonical
synthetic input identity and must match the existing source-pack row. It is not
a second business authority. The BFF forwards these projections; the client may
retain display/recovery metadata but cannot derive route, budget, trade-off,
role, currentness, or policy facts.
