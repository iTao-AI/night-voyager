# Projection matrix

| Source concept | Advisor projection | Family projection | M1 fixture boundary |
|---|---|---|---|
| `EvidenceRef` | Citation, status, provenance note, Evidence gap | Plain-language evidence note | Static synthetic references |
| `PlanningRun` | Conditional route comparison | Recommended route and trade-offs | No agent execution |
| `AdvisorReview` | Required human approval and rationale | “Advisor reviewed” provenance | No mutation |
| `DecisionBrief` | Reviewable draft | Linear editorial brief | Static `family_review` frame |
| `FamilyDecision` | Confirmation requirements | Consequence summary | Disabled fixture action |
| `DecisionReceipt` | Durable audit result | Persistent receipt identifier | Static `decided` frame |
| `TimelinePlan` | Approved downstream sequence | Dated next steps | Static fixture dates |
| `AgentTask` / lease / adapter | Secondary disclosure only | Hidden from main narrative | No worker, lease, SSE, or adapter |

Country comparison is organized by dimensions: evidence status, annual-cost range, language pathway, visa uncertainty, and next human action. Desktop uses a semantic table. Mobile uses a labelled country switcher and repeats the dimensions for the selected fixture country; it must not mechanically stack desktop rows into three country cards.
