# Governed plan execution walkthrough

This walkthrough is a local synthetic, provider-free proof. It is not a release,
deployment, live application workflow, admissions outcome, or successor-plan
automation.

## Routes and identities

- Happy: `http://127.0.0.1:3000/demo/plan`
- Blocked: `http://127.0.0.1:3000/demo/plan?scenario=blocked`

Only `happy` and `blocked` are accepted. The server maps the closed scenario and
role to one exact synthetic principal. Happy and Blocked use distinct assigned
advisor/student/parent triads. No browser request or stored envelope selects an
arbitrary `case_id`.

## Happy journey

Connect as Student, start, submit progress and completion, rotate to Advisor,
request one update, return to Student for the replacement completion, and verify.
Repeat for application and visa. Arrival is owned by Parent and is finally
verified by Advisor. Reload must show the exact completed execution and immutable
activity.

Every accepted mutation follows `receipt -> fresh GET`. If the response is lost
after PostgreSQL commits, choose **Revalidate execution authority**. Recovery
replays the exact stored body with the same idempotency key, confirms the original
receipt, and then reads current authority. It never creates a new key
automatically.

## Blocked journey

Connect as Student, start, select one closed blocker reason, and record the
blocked attestation. Rotate to Advisor and request reassessment. The execution
stops at `reassessment_required`; the handoff retains predecessor identities and
states `pending_future_authorization`. No resume, successor planning run,
decision, timeline, execution, task, provider, or model action is created.

## Recovery boundaries

- Stale versions require a fresh server read before a new user action.
- Same-scenario role rotation uses the existing atomic session endpoint while
  holding the controller lock. A rejected rotation leaves the prior session
  intact; a successful shared-cookie rotation invalidates older in-flight
  generations and closes their later continuations to `session_changed`.
- Reload mints fresh CSRF in memory; session and CSRF values are never stored.
- Malformed, cross-scenario, or cross-Case envelopes are cleared and enable
  zero mutation.
- Activity returns the latest 64 rows plus exact total and truncation status.
- Overdue state comes only from PostgreSQL `CURRENT_DATE`; the browser does not
  calculate or submit an authority date.

Public recovery classification is closed: HTTP 401,
`authentication_failed`, `bff_session_recovery_required`, and explicit
`session_changed` enter `session_changed`; stale execution/checkpoint versions,
non-current checkpoints, and already-completed executions discard the rejected
slot and refresh authority; transport failures remain recoverable only through
the exact saved body/key replay.

## Verification and cleanup

```bash
COMPOSE_PROJECT_NAME=night-voyager-plan-execution-check \
  scripts/run_db_tests.sh timeline-execution journey

COMPOSE_PROJECT_NAME=night-voyager-plan-execution-proof \
  make compose-proof

COMPOSE_PROJECT_NAME=night-voyager-plan-execution-proof \
  make down
```

Compose proof runs exact `zh-CN` and `en` Happy/Blocked browser lanes, writes a
temporary identity-only proof JSON, verifies PostgreSQL rows, and removes the
proof file. The JSON contains only locale, scenario, Case/timeline/execution,
accepted receipt, checkpoint, and optional reassessment identities.
