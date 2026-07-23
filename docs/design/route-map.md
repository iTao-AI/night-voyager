# Connected route map

The complete governed walkthrough begins at `/demo/collaboration` and continues the
same Case into `/demo`. Seven explicit BFF route files expose exactly eight HTTP
methods for the collaboration and Skill-inspector reads/mutations. The read-only
same-Case handoff then composes the existing focused advisor-family/evidence route;
it adds no new BFF handler.

`/demo` also remains independently available as the focused advisor-family/evidence
route. Eleven explicit same-origin BFF handlers connect it to the existing FastAPI
identity, task, review, decision, SSE, and exactly two M5 read endpoints. Both demo
routes retain the warm-paper ledger visual system.

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
  -> read-only candidate/fact/ledger/inspector validation
  -> one envelope replacement -> /demo with the same Case and advisor session
  -> explicit task action -> pinned task -> one EventSource -> existing decision flow
```

The BFF is transport only: no catch-all, no role selector, no task/route/policy
authority, and no client-computed decision requirements. The shared planning Skill
inspector is a server-owned `no-store` projection; it performs no client-side
relational join and grants no mutation authority. `/` is the current static
Chinese-first Virtual Night Voyage portfolio entry and makes no API/session/task/SSE
request. Its responsive AVIF/WebP files are runtime imagery while the source PNG is
provenance only. All connected state is local synthetic PostgreSQL state.
