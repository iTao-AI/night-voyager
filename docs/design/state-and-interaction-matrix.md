# State and interaction matrix

| Phase | Visible truth | Primary action | Forbidden action |
| --- | --- | --- | --- |
| `task-ready` | current Case and canonical inputs; no task/run | create task | approve or derive pins |
| `active-task` | latest non-terminal task and SSE progress | follow stream | create another task |
| `review-required` | completed task, current run/routes/Evidence | advisor review | fabricate review inputs |
| `family-review` | current family-safe Brief identity | real advisor-to-parent rotation | decide as advisor |
| `plan-ready` | completion status or parent receipt/timeline | continue as family/read result | create a task |
| `terminal-task-failure` | public failure and recovery guidance | explicit retry/remediation | synthesize success |

The fresh UI defaults to advisor and offers no client-only role selector. Normal
family transition requires successful revoke, cookie expiry, bootstrap, and
parent mint. The backend identity API retains its existing synthetic role
capability; UI sequencing does not add a transition token or BFF business state.

`sessionStorage` holds only same-tab role/CSRF/recovery metadata. With an opaque
cookie but missing or inconsistent metadata, the UI fails closed and cannot
mutate, guess identity, silently rotate, or use a family-safe read as parent
proof. A protected reset or natural expiry remains the recovery boundary.
