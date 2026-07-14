# Connected route map

`/demo` is the single connected product route. Eleven explicit same-origin BFF
handlers connect it to the existing FastAPI identity, task, review, decision,
SSE, and exactly two M5 read endpoints.

```text
/demo
  -> advisor bootstrap + mint
  -> Advisor Ledger: task-ready -> active-task -> review-required
  -> advisor review
  -> family-review: revoke advisor -> bootstrap -> mint parent
  -> Family Decision Brief
  -> family decision -> plan-ready receipt + TimelinePlan
```

The BFF is transport only: no catch-all, no role selector, no task/route/policy
authority, and no client-computed decision requirements. `/` remains the M0
bootstrap page. All connected state is local synthetic PostgreSQL state.
