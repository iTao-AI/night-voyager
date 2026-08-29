# Governed plan execution walkthrough

This walkthrough covers the existing independent deterministic execution scenarios
and the connected same-Case continuation in the advisor workspace. Both are local
synthetic, provider-free proofs. They are not a release, deployment, live
application workflow, admissions outcome, or successor-plan automation.

The independent Happy and Blocked paths do not continue the connected Case or
session from `/demo/collaboration` and `/demo`. The connected route is selected only
by `/demo/plan?case_id=<case_id>` from the current `plan_ready` action. Screenshots
are review evidence, while the semantic browser and database assertions remain
authoritative.

The current presentation authority is the [reference-driven presentation spec](../superpowers/specs/2026-08-14-reference-driven-presentation.md) and [implementation plan](../superpowers/plans/2026-08-14-reference-driven-presentation.md). The route uses the shared Midnight Editorial Advisor Workspace, but its scenario and authority remain independent.

## Routes and identities

- Connected Case: `http://127.0.0.1:3000/demo/plan?case_id=<case_id>`
- Happy: `http://127.0.0.1:3000/demo/plan`
- Blocked: `http://127.0.0.1:3000/demo/plan?scenario=blocked`

Connected mode accepts only one canonical lowercase Case UUID and derives its
current revision, decision, receipt, timeline, optional execution, active role,
and assignment on the server. Seeded mode accepts only `happy` or `blocked`; the
server maps the closed scenario and role to one exact synthetic principal. Happy
and Blocked use distinct assigned advisor/student/parent triads. Mixed, unknown, or
contradictory query identities fail closed. No browser request or stored envelope
selects arbitrary business identities.

Connected and seeded modes share one `PlanExecutionWorkspace`, reducer, mutation
service, receipt-then-GET reconciliation, and recovery implementation. Recovery
metadata binds the authority kind and exact Case or scenario, so source identities
cannot be crossed during reload or lost-ack replay.

## Evaluator paths

All paths require `make doctor` first. They are complementary:

| Path | Command | Expected phases | Stable success marker | Boundary |
| --- | --- | --- | --- | --- |
| Quick contract proof | `make proof` | snapshot hygiene, migration/config identity, isolated wheel | `proof wheel: isolated installed-wheel import and app factory passed` | provider-free configuration and installed-wheel contract; no browser journey |
| Human-readable walkthrough | `make demo`, then this page's Happy/Blocked steps | seed, connect, start, family attestation, advisor verification or reassessment, explicit `make down` | completed execution or `reassessment_required` remains after reload | functional review; screenshots are review evidence |
| Full browser-to-database proof | task-scoped `COMPOSE_PROJECT_NAME=... make compose-proof` | build/migrate/seed, exact `zh-CN`/`en` Happy/Blocked, recovery, PostgreSQL verification, teardown | `proof compose: PASS` | semantic assertions plus persisted browser-to-database authority |

`make proof` is the quick provider-free path. The full task-scoped Compose path is
the authority for browser, persistence, recovery, and teardown proof; command
duration and cache behavior are environment-dependent and are not product claims.

The quick path proves the proof configuration and installed-wheel contract
confirmed by its exact public markers. The manual path is for evaluator
understanding. Only the full path proves receipts, fresh GET order, browser
recovery, and durable rows.

## Connected same-Case continuation

From the connected `/demo` `plan_ready` state, choose the primary action to enter
`/demo/plan?case_id=<case_id>`. The server returns the exact current Case revision,
family decision, DecisionReceipt, TimelinePlan, optional execution, active role,
and assigned status. The browser carries only the Case route identity.

The connected proof starts execution through the existing family mutation, reloads
the same authority, replays a lost acknowledgement with the same receipt and
idempotency key, rotates to the assigned advisor, records a blocked checkpoint, and
reassesses the exact predecessor. Reassessment stops at
`pending_future_authorization`; it creates no automatic successor. Wrong-Case,
wrong-role, cross-Case, mixed-route, stale-session, and recovery-source mismatches
fail closed.

## Happy journey

In the independent seeded path, connect as Student, start, submit progress and completion, rotate to Advisor,
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

In the independent seeded path, connect as Student, start, select one closed blocker reason, and record the
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

If a public phase fails, retain only the command, public phase marker, public
problem code, expected/observed stable markers, available-space counts,
task-scoped Compose project name, and teardown result. Use the proof-failure
issue template; never upload raw logs containing secrets or content evidence.
After any failed or successful manual stack, run the same explicit project name
with `make down`, then verify `docker compose ps --all` is empty. Do not prune
shared images/cache or the protected `night-voyager_postgres-data` volume.
