# HTTP API v1

M2 adds a development/test-only synthetic identity bootstrap. Every mutation
requires an exact configured `Origin` and CSRF proof.

- `GET /api/v1/demo/session-bootstrap` returns a five-minute pre-session CSRF
  token and matching `night_voyager_csrf_bootstrap` cookie.
- `POST /api/v1/demo/sessions` accepts only `advisor`, `student`, or `parent`.
  It creates or rotates a 30-minute `night_voyager_session` cookie and returns
  public role/proof-mode data plus the session-bound CSRF token.
- `DELETE /api/v1/demo/session` revokes the current session and expires both
  cookies.

The session cookie is `HttpOnly`, `SameSite=Lax`, `Path=/`, and has
`Max-Age=1800`. `Secure` may be disabled only for loopback HTTP origins in
development/test when the explicit insecure-demo-cookie setting is enabled.
Failures are non-enumerating and never expose organization, actor, or session
identifiers. A wrong CSRF value remains an authentication failure and does not
fall back to minting. An unknown, expired, or revoked session returns the same
public error while expiring both identity cookies, after which the client may
bootstrap and mint again. Unexpected persistence and connectivity failures are
not normalized as authentication failures. M2 does not enable CORS; M5 connects
`/demo` through same-origin explicit BFF handlers without changing this identity authority.

## M3B advisor and family decision endpoints

M3B adds four backend-only endpoints for the local synthetic proof. Responses
use `Cache-Control: no-store`. Mutations require the opaque session, its
session-bound `X-CSRF-Token`, an exact configured `Origin`, and an
`Idempotency-Key`. Conflicts use RFC 9457-style `application/problem+json` and
authorization failures remain non-enumerating.

| Method and path | Assigned actor | Result |
| --- | --- | --- |
| `POST /api/v1/cases/{case_id}/advisor-reviews` | advisor | immutable approve/reject/revision review; approval alone creates a Brief |
| `GET /api/v1/decision-briefs/{brief_id}` | advisor/student/parent | family-safe projection and persistent receipt/timeline |
| `POST /api/v1/decision-briefs/{brief_id}/family-decisions` | student/parent | direct immutable decision, receipt, and timeline |
| `POST /api/v1/decision-briefs/{brief_id}/advisor-recorded-decisions` | advisor | assigned family member's `family_consultation` decision |

Requests use `schema_version=1` and expected versions. Australia requires
`budget_elasticity` and a CNY range compatible with pinned M3A facts. Blocked
Malaysia stays visible but unselectable. M3B adds no share-token or participant
management API.

After decision, the Brief read includes a family-safe typed receipt containing
the selected route, accepted budget range and currency, accepted trade-offs,
decision maker, recorder, and decision source, plus the persistent timeline.
Source paths, reviewer notes, raw tool/model output, provider errors, secrets,
and unrelated tenant metadata are never included.

## M4A assigned-advisor task endpoints

M4A adds a backend-only durable task surface. All reads and mutations require a
valid opaque session and assigned-advisor relationship. Mutations also require
exact configured `Origin`, session CSRF, and `Idempotency-Key`. Responses use
`Cache-Control: no-store`; authorization remains non-enumerating.

| Method and path | Result |
| --- | --- |
| `POST /api/v1/cases/{case_id}/agent-tasks` | `202` idempotent `generate_planning_run_v1` create |
| `GET /api/v1/tasks/{task_id}` | public task projection |
| `POST /api/v1/tasks/{task_id}/cancel` | expected-row-version, idempotent cancellation |
| `GET /api/v1/tasks/{task_id}/events` | authorized SSE replay/reconnect |

Create accepts schema version 1, expected Case revision, source-pack ID/version,
and `m3a-policy-v1`. It cannot select tenant, actor, adapter, worker, lease,
retry, or injected failure behavior. Public responses expose status, attempts,
sanitized code, and an optional PlanningRun ID/currentness; they do not expose
internal task state, dispatch, leases, tenant/session IDs, raw output, or worker
errors.

SSE uses task-local integer `event_sequence` as `id`. `Last-Event-ID` must be a
non-negative integer; a cursor ahead of the durable maximum is a conflict.
Fifteen-second heartbeat comments are not stored. The stream closes after all
events for a closing state have been delivered. See
[AgentTask and event reference](agent-tasks-and-events.md) for exact states and
bounds.

## M5 connected demo read endpoints

M5 adds exactly two read-only projections for the connected synthetic demo.
Both require the existing opaque session, return `schema_version=1`, use
`Cache-Control: no-store`, and preserve non-enumerating authorization failures.

| Method and path | Assigned actor | Result |
| --- | --- | --- |
| `GET /api/v1/cases/{case_id}/advisor-ledger` | advisor | phase-discriminated task, PlanningRun, route, evidence, review, and recovery projection |
| `GET /api/v1/cases/{case_id}/current-decision-brief` | advisor/student/parent | family-safe Brief plus server-derived decision requirements and, after decision, receipt/timeline |

The Ledger exposes canonical demo task inputs before task creation and persisted
pins afterward; mismatches fail closed. Decision requirements are projected from
the pinned run, Australia cost evidence, current Case revision, and M3B policy.
These endpoints add no write authority, persistence, migration, or client-owned
tenant, role, policy, route, task, run, Brief, receipt, or timeline selector.

## Governed DRA candidate endpoints

The optional DRA integration adds three assigned-advisor endpoints. Mutations
require the existing opaque session, exact configured `Origin`, session-bound
`X-CSRF-Token`, and a 16–200 character `Idempotency-Key`. All responses use
`Cache-Control: no-store`; authorization failures remain non-enumerating.

| Method and path | Result |
| --- | --- |
| `POST /api/v1/cases/{case_id}/dra-candidates` | `201` immutable `UNTRUSTED_CANDIDATE` import |
| `GET /api/v1/cases/{case_id}/dra-candidates/{candidate_id}` | bounded candidate and terminal-decision status |
| `POST /api/v1/cases/{case_id}/dra-candidates/{candidate_id}/verification-decisions` | `201` atomic approve/reject decision |

The import body contains the strict pinned producer projection and canonical
artifact input, but the response and persisted candidate exclude artifact
content. Tenant, Case, actor, role, authority, promoted identities, baseline
pins, credentials, and local paths are server-owned or fixed internally and
cannot be supplied by the caller.
The imported projection must contain exactly one promotable public Evidence.
One approve or reject decision makes the candidate terminal; subsequent review
requires a newly imported candidate.

Approval requires exact source attestation and atomically creates one derived
source-pack revision with exactly one `australia_program_fit` Evidence using
`externally_verified`; the remaining accepted facts copy the synthetic
baseline. Rejection creates neither source-pack nor Evidence. There is no
separate promotion command. Problems never include Markdown, source bytes,
credentials, or raw provider responses.

## M5 same-origin BFF

The connected browser uses eleven explicit `/api/demo/*` Route Handlers for
session bootstrap/create/delete, Ledger read, task create/read/cancel/events,
advisor review, current Brief read, and family decision. There is no catch-all
proxy. The BFF validates UUID path segments, bounded bodies and deadlines,
forwards direct SSE bytes, and maps only a closed set of public problems.

Every identity upstream request, including bootstrap GET, receives the
server-configured fixed public Origin. Mutations first validate the browser
Origin; caller Origin is not reflected. Multiple upstream `Set-Cookie` fields
are appended independently rather than comma-joined. BFF responses are
`Cache-Control: no-store`.

The current Brief `decision_requirements` contains the eligible Australia route
identity, `currency=CNY`, pinned cost, hard ceiling, and exact one-element
`required_trade_offs=["budget_elasticity"]`. These values come from current
PostgreSQL rows and deterministic policy, not fixture labels or client constants.
