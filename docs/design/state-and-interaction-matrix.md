# State and interaction matrix

| Frame/state | Visible truth | Human decision | Primary action | Consequence/recovery |
|---|---|---|---|---|
| `advisor_review` | Japan is conditional; Malaysia has a blocking Evidence gap | Advisor decides whether evidence supports release | `Review evidence` | No mutation; fixture disclosure opens inline |
| `family_review` | Advisor-approved DecisionBrief is ready for family review | Family confirms the Japan route after reading trade-offs | `Confirm Japan route` is disabled | Disabled reason and confirmation summary remain visible |
| `decided` | Japan route has a persistent synthetic receipt | Decision is already recorded in this after-frame | No mutation action | Receipt and TimelinePlan persist; stale view copy says refresh and reconnect safely |
| `malaysia_blocked` | Required evidence is unresolved | Advisor must resolve evidence before route eligibility | `Choose Malaysia` is disabled | Blocking reason is explicit; no override control |

## Interaction rules

- The country switcher is a fixture-only responsive projection; M1 requires no client-side state change.
- Evidence details and task execution detail use native disclosure controls.
- Keyboard focus is visible. Disabled controls are paired with adjacent reason text rather than relying on native tooltip behavior.
- Confirmation copy names the selected route, known trade-offs, and the artifact that would be produced in a future mutation-enabled milestone.
