# State and interaction matrix

| Phase | Visible truth | Primary action | Forbidden action |
| --- | --- | --- | --- |
| `task-ready` | current Case and canonical inputs; no task/run | create task | approve or derive pins |
| `active-task` | latest non-terminal task and SSE progress | follow stream | create another task |
| `review-required` | completed task, current run/routes/Evidence | advisor review | fabricate review inputs |
| `family-review` | current family-safe Brief identity | real advisor-to-parent rotation | decide as advisor |
| `plan-ready` | completion status or parent receipt/timeline | continue as family/read result | create a task |
| `terminal-task-failure` | public failure and recovery guidance | explicit retry/remediation | synthesize success |

The secondary collaboration route has its own closed lifecycle:

| Phase | Visible truth | Primary action | Forbidden action |
| --- | --- | --- | --- |
| `bootstrapping_parent` | no inferred identity or thread | start parent walkthrough | guess role or authority |
| `parent_composing` | shared thread, no proposal | append the bounded message | treat message as fact |
| `parent_proposing` | persisted message | create the typed budget candidate | mutate the Case |
| `awaiting_advisor` | pending candidate survives reload | real parent-to-advisor role switch | client-only role flip |
| `advisor_reviewing` | advisor-safe candidate projection | confirm once | confirm as parent |
| `reloading_authority` | committed response may have been lost | reload with the same fingerprint | invent success |
| `replan_required` | confirmed fact and Case revision | return to primary `/demo` | create a task implicitly |
| `recoverable_error` | closed public recovery category | explicit retry or re-auth | expose raw error detail |
| `blocked` | stale, expired, or active-task conflict | stop safely | weaken currentness gates |

The fresh UI defaults to advisor and offers no client-only role selector. Normal
family transition requires successful revoke, cookie expiry, bootstrap, and
parent mint. The backend identity API retains its existing synthetic role
capability; UI sequencing does not add a transition token or BFF business state.

`sessionStorage` holds only same-tab role/CSRF/recovery metadata. With an opaque
cookie but missing or inconsistent metadata, the UI fails closed and cannot
mutate, guess identity, silently rotate, or use a family-safe read as parent
proof. A protected reset or natural expiry remains the recovery boundary.

The envelope is `schema_version=2` with the closed journey union
`advisor-family|collaboration`; one tab never runs both journeys concurrently. The
inspector is read-only and server-owned: `/demo` progresses `not_created -> matched`,
while `/demo/collaboration` stays `not_created` because it creates no planning task.
