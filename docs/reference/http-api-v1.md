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
not normalized as authentication failures. M2 does not enable CORS or connect
the fixture-only `/demo` page.

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
