# M5 Connected Advisor-to-Family Demo Design

## Goal

M5 connects the existing synthetic identity, deterministic planning, durable task,
human review, family decision, and timeline boundaries into one browser-visible flow:

```text
advisor session
  -> create AgentTask
  -> worker + durable SSE
  -> Advisor Ledger
  -> advisor approval
  -> revoke advisor session
  -> bootstrap parent session
  -> Family Decision Brief
  -> parent decision
  -> DecisionReceipt + TimelinePlan
```

The connected route remains a local synthetic proof. It demonstrates a complete
application workflow without claiming real student data, current study-abroad facts,
production use, external-provider execution, or business outcomes.

## Scope

M5 adds:

- one connected `/demo` flow with explicit synthetic advisor and parent roles;
- two role-scoped FastAPI read models for the current Advisor Ledger and current
  family-safe Decision Brief;
- explicit Next.js App Router Route Handlers as a narrow same-origin BFF;
- a client display/recovery state machine driven only by backend responses;
- direct SSE streaming and authorized reconnect through the BFF;
- real session revoke/bootstrap/mint when changing roles;
- a responsive Advisor Ledger, Evidence disclosure, approval confirmation, linear
  Family Brief, persistent DecisionReceipt, and Australia TimelinePlan;
- real Compose/Playwright proof across the full browser-to-database path;
- public-neutral reference, operations, bilingual entry-point, design, and screenshot
  updates during implementation.

M5 does not add or change:

- M3A planning policy, Evidence authority, route outcomes, or PlanningRun terminal
  semantics;
- M3B advisor/family authority, decision policy, receipt, timeline, or Case transitions;
- M4A task states, retry, lease, fencing, worker, event, or SSE authority;
- M4B candidate acceptance, MKE-backed planning, or any default MKE dependency;
- DRA, OCR, OpenClaw, remote model/provider calls, provider credentials, or
  cross-repository CI;
- share tokens, participant-management APIs, real registration, production tenancy,
  billing, deployment, release, or production claims.

## Authoritative connected Case

The M4A task-ready synthetic Case becomes the only M5 connected golden Case. Its
explicit demo seed gains assigned student and parent participants while retaining the
existing advisor and deterministic Case revision. M5 adds no Case binding or migration;
migrations remain seed-free.

The prior M3B precomputed proof Case remains valid backend regression evidence, but the
browser does not combine it with the task-ready Case. The M1 Japan visual fixture remains
historical design evidence and test reference; it no longer represents active connected
`/demo` state after M5. The connected story uses the backend-authoritative Australia
decision flow, keeps Japan visible as an audited conditional alternative, and keeps
Malaysia visible but blocked.

A checked-in web contract may contain the public synthetic connected Case ID only. A
server-owned synthetic demo input resolver accepts only the checked-in M3A manifest after
the existing fixture validator succeeds, the project `POLICY_VERSION`, and the existing
PostgreSQL source-pack row that exactly matches that validated manifest. Before task
creation these values are `canonical demo task inputs`, not Case-persisted pins. After
task creation, source-pack and policy pins come from the latest relevant AgentTask and
current PlanningRun and must match the canonical inputs or the projection fails closed.
Case revision, task/run state, review inputs, Brief identity, decision, and timeline must
come from role-scoped backend reads and mutations. The client may only consume this
backend projection; client constants cannot supply, derive, or establish pin authority.

## Architecture

```text
Browser /demo
  -> explicit /api/demo/* Route Handlers
  -> FastAPI /api/v1/*
  -> application services
  -> PostgreSQL forced-RLS authority

Browser EventSource
  -> streaming Route Handler
  -> authorized FastAPI SSE
  -> short PostgreSQL event reads
```

The BFF is a transport boundary, not an application service. It does not own Case,
task, Evidence, review, decision, receipt, or timeline state. It cannot compute route
eligibility, normalize backend authority, mint CSRF/session values, generate idempotency
results, select an upstream URL, or create an SSE event.

## Role-scoped backend read models

M5 adds exactly two read endpoints:

| Method and path | Actor | Result |
| --- | --- | --- |
| `GET /api/v1/cases/{case_id}/advisor-ledger` | assigned advisor | current Case/task/run, route/Evidence disclosure, and review inputs |
| `GET /api/v1/cases/{case_id}/current-decision-brief` | assigned advisor/student/parent | current family-safe Brief, receipt, and timeline |

Both responses use schema version 1, `Cache-Control: no-store`, existing opaque session
resolution, forced RLS, tenant-preserving joins, and non-enumerating authorization.
Missing, cross-tenant, unassigned, and wrong-role resources return the same public `404`.

The Advisor Ledger projection includes only:

- public synthetic proof mode;
- Case ID, current revision, and public lifecycle state;
- canonical demo task inputs before task creation, or task/run-persisted source-pack and
  policy pins after creation, subject to exact consistency checks;
- the latest relevant public AgentTask projection, when one exists;
- the current `review_required` PlanningRun identity and source snapshot date;
- Australia, Japan, and Malaysia route projections with country, outcome, public
  rationale, cost/ranking comparison, required claims, known gaps, and eligibility;
- bounded Evidence disclosures containing claim/role, publisher, institution, snapshot
  date, accepted synthetic authority, limitation, and known gaps;
- server-produced review inputs: PlanningRun ID, expected Case revision, exact eligible
  route IDs, and any explicit risk-acceptance options.

The Ledger uses a discriminated phase and never fills an absent task, run, route, Brief,
or review input with placeholder authority:

| Phase | Available projection | Single primary action | Forbidden action |
| --- | --- | --- | --- |
| `task-ready` / no task | Case revision and canonical demo task inputs; task, run, routes, and review inputs are explicitly absent | create the first AgentTask | review, decide, or derive pins in the client |
| `active-task` | Case, canonical inputs, and latest non-terminal task; run/routes/review inputs are absent until persisted | follow the durable task/SSE stream | create another task or approve |
| `review-required` | completed task, current `review_required` PlanningRun, routes, Evidence disclosure, and exact review inputs | submit advisor review | create another task or fabricate review inputs |
| `family-review` | advisor completion plus current family-safe Brief identity; advisor-only review inputs are absent | perform the real advisor-to-parent session switch | create a task or submit a family decision as advisor |
| `plan-ready` | completed workflow summary for advisor; full receipt/timeline only for an authorized parent projection | switch through real revoke/bootstrap/mint to parent, or view the plan as parent | create a task or select parent role in client state |
| `terminal-task-failure` | terminal task status and public recovery guidance; run/routes/review inputs are explicitly absent | perform the allowed explicit retry or remediation | approve, decide, or synthesize successful state |

It excludes tenant/session/actor identity, database ownership, source paths, raw
provider/tool/model output, prompts, reviewer notes, internal task state, dispatch,
lease owner/generation, worker errors, stack traces, credentials, private paths, and
unbounded Evidence text.

The current Decision Brief projection discovers the current Brief by authorized Case and
returns the existing family-safe projection, Brief version, persistent receipt, and
timeline. It must not expose advisor-only Evidence detail, reviewer notes, internal IDs
that are not required for a subsequent mutation, or unrelated tenant metadata. The
existing direct Brief-by-ID endpoint remains supported; M5 adds no share token.

These endpoints read existing tables only. M5 introduces no migration, table, generic
dashboard endpoint, or new state authority. Implementation must prove that the existing
API read grants and forced-RLS policies are sufficient. If they are not, implementation
stops and returns to authority design instead of adding an ad hoc function, grant,
ownership change, or RLS bypass.

## Explicit BFF route matrix

The browser uses only these same-origin handlers:

| Browser route | Upstream route |
| --- | --- |
| `GET /api/demo/session-bootstrap` | `GET /api/v1/demo/session-bootstrap` |
| `POST /api/demo/sessions` | `POST /api/v1/demo/sessions` |
| `DELETE /api/demo/session` | `DELETE /api/v1/demo/session` |
| `GET /api/demo/cases/{case_id}/advisor-ledger` | `GET /api/v1/cases/{case_id}/advisor-ledger` |
| `POST /api/demo/cases/{case_id}/agent-tasks` | `POST /api/v1/cases/{case_id}/agent-tasks` |
| `GET /api/demo/tasks/{task_id}` | `GET /api/v1/tasks/{task_id}` |
| `POST /api/demo/tasks/{task_id}/cancel` | `POST /api/v1/tasks/{task_id}/cancel` |
| `GET /api/demo/tasks/{task_id}/events` | `GET /api/v1/tasks/{task_id}/events` |
| `POST /api/demo/cases/{case_id}/advisor-reviews` | `POST /api/v1/cases/{case_id}/advisor-reviews` |
| `GET /api/demo/cases/{case_id}/current-decision-brief` | `GET /api/v1/cases/{case_id}/current-decision-brief` |
| `POST /api/demo/decision-briefs/{brief_id}/family-decisions` | `POST /api/v1/decision-briefs/{brief_id}/family-decisions` |

There is no catch-all proxy. Every handler fixes its method and upstream path shape.
Dynamic IDs must be canonical UUIDs before interpolation. The server-only upstream base
comes from `NIGHT_VOYAGER_API_INTERNAL_URL`; request data cannot override its scheme,
host, port, path, credentials, or DNS target.

Request forwarding is limited to the exact relevant subset of `Cookie`, `Content-Type`,
`Origin`, `X-CSRF-Token`, `Idempotency-Key`, `Last-Event-ID`, and body bytes. Mutation
Origin must exactly match the configured public application origin. The BFF sends that
server-configured fixed public origin on every upstream `/api/v1/demo/*` identity request,
including bootstrap `GET`; mutations validate the browser Origin first and then send the
same fixed value. A caller Origin is never trusted, selected, or reflected. JSON bodies
are bounded to 32 KiB and require the expected media type.

Response forwarding is limited to status, body, `Set-Cookie`, `Content-Type`,
`Cache-Control`, and the required SSE buffering header. Hop-by-hop, server, upstream URL,
debug, trace, and framework headers are not exposed. All handlers are dynamic and
`no-store`. Every upstream `Set-Cookie` field is appended separately to the browser
response; cookie fields are never comma-joined.

FastAPI problem status/body pass through unchanged. The BFF owns only two redacted RFC
9457-style failures:

- `503` with code `bff_upstream_unavailable`;
- `504` with code `bff_upstream_timeout`.

Neither contains an upstream URL, exception, stack trace, private path, credential, or
provider output. Non-SSE calls use fixed deadlines. An aborted browser request aborts the
upstream fetch.

## SSE transport

The SSE handler returns the upstream `ReadableStream` directly. It does not parse,
buffer, reorder, deduplicate, persist, or synthesize event data, IDs, or heartbeats.
FastAPI/PostgreSQL retain cursor, ordering, authorization, page, terminal-close, and
heartbeat authority.

Normal native `EventSource` reconnect uses inbound `Last-Event-ID`. For an initial page
reload only, the browser may provide a validated non-negative `after` query value. The
BFF maps `after` to upstream `Last-Event-ID` only when the inbound header is absent; a
native reconnect header takes precedence. Invalid cursors fail before upstream access.

## Client state and storage

The connected client reducer has these display/recovery states:

```text
bootstrapping
-> advisor_ready
-> task_creating
-> task_streaming
-> advisor_review
-> review_submitting
-> role_switching
-> family_review
-> decision_submitting
-> plan_ready
```

`recoverable_error` covers expired session, bounded BFF unavailability, SSE disconnect,
and stale conflict. `terminal_task_failure` covers `needs_evidence`, `timed_out`,
`failed`, `cancelled`, and `outdated`.

The reducer cannot promote business state. Every consequential transition must follow a
validated session, task/SSE, Advisor Ledger, review, current Brief, decision, receipt, or
timeline response. Client-side button visibility is not authorization.

A new browser session can mint only the advisor role. Reload first resolves the
server-reported phase: `task-ready` offers task creation; `active-task` resumes task/SSE;
`review-required` offers review; `family-review` offers the real role switch;
`terminal-task-failure` offers only its explicit recovery; and `plan-ready` never creates
a new task. For retained completed data, the advisor sees completion and may initiate the
real revoke -> bootstrap -> parent mint sequence. The client cannot select parent directly,
and only a parent session receives the full Receipt/Timeline presentation.

`sessionStorage` may contain only the current synthetic role, session-bound CSRF token,
public synthetic Case ID, opaque task/Brief IDs, canonical-mutation idempotency keys, and
last durable event sequence. It must not contain the session cookie/token, database
identity, Evidence text, reviewer notes, provider output, raw errors, credentials, or
private paths. The session token remains an `HttpOnly`, `SameSite=Lax` cookie.

## Session, idempotency, and recovery

Advisor-to-parent switching is an ordered security transition:

1. revoke the current advisor session;
2. accept the response that expires identity cookies;
3. clear advisor CSRF and advisor-only client state;
4. request a new pre-session bootstrap;
5. mint the parent session;
6. read the current family-safe Brief under parent authority.

If revoke fails, the client stops and does not mint another role. It never treats a
React label change as a role change.

On reload, the client reads the role-scoped current projection before showing a mutation.
If the opaque session is expired, revoked, or unknown, the backend expires cookies and the
client clears recovery state. Rebootstrap is an explicit user action. A mutation is never
automatically replayed after session loss.

Each consequential user action has one stored idempotency key bound to its canonical
request. An explicit retry reuses that key and exact request. A changed request gets a new
key only after user confirmation. A `409` stale/currentness response triggers a read-model
refresh and renewed confirmation; it is not silently retried.

## User experience and accessibility

M5 preserves the M1 `Advisor Ledger x Global Journey` design direction. The first screen
shows one current lifecycle stage, one required human decision, and one primary action.
The technical task/event trail stays in secondary disclosure rather than becoming an
infrastructure dashboard.

The advisor view presents the comparison ledger, Evidence disclosures, limitations,
eligible Australia route, audited Japan alternative, blocked Malaysia path, and an
approval confirmation summary. The frontend renders server eligibility and does not
derive it from country labels or fixture constants.

The parent view is a linear Family Decision Brief. It hides advisor-only and technical
material, explains Australia budget elasticity, records the accepted CNY range and
trade-off, and keeps the persistent DecisionReceipt and TimelinePlan visible after
completion. Malaysia remains visible as an explained blocked alternative but cannot be
selected.

Desktop, tablet, and mobile preserve semantic reading order. Mobile uses a country
switcher while retaining an assistive semantic comparison. The implementation preserves
keyboard-visible focus, landmarks, status/live-region announcements, 44 px targets,
reduced motion, contrast, disabled reasons, and no horizontal overflow at 1440, 768, and
390 px.

No UI library, CSS framework, remote font, chat surface, KPI dashboard, match percentage,
generic control tower, or automatic approval is added.

## Verification

Backend tests cover both read models, currentness, two tenants, assigned and unassigned
actors, wrong roles, missing context, forced RLS, pool cleanup, current task/run/Brief/
receipt/timeline, and explicit absence of forbidden fields.

BFF tests cover every exact route, method, UUID/path validation, request/response header
allowlists, body bound, exact Origin, CSRF, idempotency, backend RFC 9457 passthrough,
unavailable/timeout redaction, no arbitrary upstream URL, SSE streaming, abort propagation,
and cursor mapping. They prove bootstrap `GET` without an inbound browser Origin still
sends the fixed configured Origin upstream, and separately prove multi-field `Set-Cookie`
round trips for session creation, successful deletion, and stale-session cleanup without
comma joining.

Frontend tests cover all legal and illegal reducer transitions, role switch, refresh,
session expiry, same-request replay, stale conflict, SSE reconnect, task terminal states,
role-specific content, Evidence disclosure, disabled reasons, and accessibility semantics.

Playwright runs against the real Compose web, API, PostgreSQL, migrator, demo seed, and
worker. It proves advisor session -> task -> worker -> SSE -> Ledger -> approval -> parent
session -> Brief -> decision -> persisted Receipt/Timeline, plus refresh recovery,
Last-Event-ID continuity, wrong-role denial, Malaysia blocked selection, keyboard flow,
landmarks/live regions, and no horizontal overflow at 1440, 768, and 390 px.

The browser golden flow joins the existing required `compose` context; M5 does not invent
a required check name before a successful hosted run. Existing Python, frontend, database,
Compose, installed-wheel, release-tree, and public-hygiene gates remain required. Final
teardown leaves no project containers or isolated proof volume.

## Documentation and presentation

Implementation updates the bilingual READMEs, docs index, HTTP and operations references,
design projection, Compose proof, and affected contributor guidance. README includes two
public-safe screenshots captured from the real connected synthetic flow: Advisor Ledger
and Family Decision Receipt/Timeline.

`make demo` exposes the connected route at `http://127.0.0.1:3000/demo`. A retained
completed demo first resolves the real role and phase; only a parent session renders the
full receipt/timeline. Replaying from the beginning uses the existing explicit protected
reset procedure; M5 adds no browser reset or silent data deletion.

## Cross-project boundary

M5 does not install, import, invoke, or checkout MKE, DRA, OCR, or OpenClaw. Required CI
and Compose remain fully self-contained. M4B stays an optional read-only compatibility
proof and its output remains `UNTRUSTED_CANDIDATE`.

A future accepted MKE or DRA result must first pass Night Voyager-owned acceptance,
persistence, policy, and role-scoped projection. The browser and BFF never consume an
upstream project contract directly. This keeps future adapter work from requiring a new
frontend authority model.

## Acceptance

M5 is accepted only when:

- the single connected Case completes the six-beat advisor-to-family story through real
  BFF, API, worker, SSE, PostgreSQL, review, decision, receipt, and timeline boundaries;
- session rotation, role denial, tenant isolation, Evidence disclosure, Malaysia block,
  stale/idempotency recovery, SSE reconnect, and refresh persistence are proven;
- 1440, 768, and 390 px browser checks and accessibility assertions pass;
- all existing local and hosted `python`, `frontend`, and `compose` gates pass;
- screenshots and public documentation match actual connected behavior;
- no upstream checkout, provider credential, real student data, MKE acceptance, release,
  deployment, or production claim enters the diff.

The supported claim is limited to a local synthetic connected demo with a transport-only
same-origin BFF, durable PostgreSQL task/SSE execution, explicit human review, role-bound
family decision, and persistent receipt/timeline. It is not evidence of real users,
production SLA, distributed HA, current study-abroad facts, or business outcomes.
