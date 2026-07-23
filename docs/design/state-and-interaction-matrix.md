# State and interaction matrix

Presentation state is orthogonal to both lifecycles. Exact `zh-CN` is the SSR,
missing, invalid, and storage-failure default; exact `en` is explicitly selectable.
Switching writes only `night-voyager:presentation-locale:v1` and leaves lifecycle
state, requests, idempotency, journey storage, EventSource, and navigation unchanged.

| Phase | Visible truth | Primary action | Forbidden action |
| --- | --- | --- | --- |
| `task-ready` | current Case and canonical inputs; no task/run | create task | approve or derive pins |
| `active-task` | latest non-terminal task and SSE progress | follow stream | create another task |
| `review-required` | completed task, current run/routes/Evidence | advisor review | fabricate review inputs |
| `family-review` | current family-safe Brief identity | real advisor-to-parent rotation | decide as advisor |
| `plan-ready` | completion status or parent receipt/timeline | continue as family/read result | create a task |
| `terminal-task-failure` | public failure and recovery guidance | explicit retry/remediation | synthesize success |

The task-free collaboration route has its own closed lifecycle:

| Phase | Visible truth | Primary action | Forbidden action |
| --- | --- | --- | --- |
| `bootstrapping_parent` | no inferred identity or thread | start parent walkthrough | guess role or authority |
| `thread_ready` | shared thread and current parent-safe messages | append the bounded message or explicitly propose it | treat message as fact |
| `message_submitting` | exact append fingerprint and key persisted | reconcile authority; retry only after an unknown outcome | generate a new body or key |
| `proposal_pending` | typed parent-safe candidate survives reload | real parent-to-advisor role switch | mutate the Case |
| `switching_to_advisor` | stored parent phase coordinated against the server role projection | complete the real revoke/bootstrap sequence or recover explicitly | trust the stored role over server authority |
| `advisor_reviewing` | advisor-safe candidate projection | confirm once | confirm as parent |
| `confirmation_submitting` | exact verification fingerprint and key persisted | reconcile candidate, confirmed facts, and advisor ledger; explicitly retry only if still pending | infer success from a mutation response |
| `replan_required` | confirmed fact and Case revision | start read-only same-Case handoff | create a task implicitly |
| `handoff_validating` | transient candidate/fact/revision/ledger/inspector validation | replace the envelope and navigate once, or return to `replan_required` unchanged | persist the transient phase or send a task POST |
| `recoverable_error` | closed public recovery category | explicit retry or re-auth | expose raw error detail |

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
After a successful handoff, `/demo` re-reads the continued Case and adopts task
identity only from its advisor ledger. The destination keeps one active EventSource
and the existing monotonic cursor/recovery precedence.
