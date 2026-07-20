# Connected route map

`/demo` remains the primary connected product route. Eleven explicit same-origin BFF
handlers connect it to the existing FastAPI identity, task, review, decision, SSE,
and exactly two M5 read endpoints. `/demo/collaboration` is a secondary governed
memory walkthrough with seven explicit BFF route files exposing exactly eight HTTP
methods for frozen collaboration and Skill-inspector reads/mutations.

```text
/demo
  -> advisor bootstrap + mint
  -> Advisor Ledger: task-ready -> active-task -> review-required
  -> advisor review
  -> family-review: revoke advisor -> bootstrap -> mint parent
  -> Family Decision Brief
  -> family decision -> plan-ready receipt + TimelinePlan

/demo/collaboration
  -> parent bootstrap + shared thread
  -> parent message -> typed budget candidate
  -> revoke parent -> mint assigned advisor
  -> advisor confirmation -> ConfirmedFact + Case revision
  -> re-plan required; no AgentTask, polling, or EventSource
```

The BFF is transport only: no catch-all, no role selector, no task/route/policy
authority, and no client-computed decision requirements. The shared planning Skill
inspector is a server-owned `no-store` projection; it performs no client-side
relational join and grants no mutation authority. `/` remains the M0 bootstrap page.
All connected state is local synthetic PostgreSQL state.
