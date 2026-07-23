# ADR 0010: Make deterministic task creation the explicit planning-start authority

- Status: Accepted
- Date: 2026-07-22
- Implementation status: Implemented by migration `0009`, merged as PR #57, and
  released in `v0.1.3`

## Context

Advisor confirmation of a collaboration fact atomically publishes a new Case revision
but deliberately leaves the Case in `intake`. The existing deterministic worker can
consume that revision only after an assigned advisor explicitly creates a planning
task. Before migration `0009`, `app.create_agent_task(...)` accepted only a Case already
in `planning`, so the same-Case continuation required another authority for the state
transition.

Confirmation cannot own that transition because verification and planning start are
separate human decisions. A browser-owned state write or a separate planning-start
endpoint would split one business action across two transactions and could leave a
`planning` Case without the pinned task that justified the transition.

## Decision

The first deterministic task creation is the explicit planning-start authority.
Migration `0009` replaces only the existing
`app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text)`
function. Its public HTTP request and response contract remains unchanged.

After trusted advisor context is established, the function takes a transaction-scoped
advisory lock keyed by organization, actor, operation, and idempotency key before it
reads the idempotency ledger. Replay therefore remains before new-write validation even
when same-key requests overlap. It then locks the Case row and validates assignment,
operation, exact revision, source pack, active
SkillVersion, complete manifest, five-field runtime pin, and effective-task uniqueness.
It then accepts `intake` only for `generate_planning_run_v1`. In the same PostgreSQL
transaction it writes the `intake -> planning` transition, pinned `AgentTask`,
payload-free dispatch identity, first durable event, and idempotency response.

Existing task creation from `planning` remains supported. The governed mixed operation
from `intake` remains rejected because this decision does not alter DRA promotion or
mixed-planning sequencing. Confirmation alone creates neither a task nor a planning
transition, so there is no automatic planning and no separate planning-start endpoint.

The function remains owned by `night_voyager_migrator`. `PUBLIC` is revoked and only
`night_voyager_api` receives `EXECUTE`; `night_voyager_worker` receives no creation
authority or direct task DML. Migration `0009` also revokes the API grant on the legacy
`app.transition_case(uuid,uuid,text,text)` function, so no runtime role can submit
`intake -> planning` outside the complete task authority transaction. Existing
forced-RLS tables and tenant context remain the data boundary.

Downgrade to `0008` restores the exact prior task function definition, owner, signature,
and grant boundary plus the legacy API transition grant, without rewriting Case or task
history. Re-upgrade removes that legacy grant again and reapplies the same single-owner
`0009` authority.

## Consequences

- One assigned-advisor action either persists the complete planning-start authority set
  or rolls back the Case transition and every task-side write.
- Overlapping same-key requests serialize before ledger lookup. An identical request
  returns the original task with `replayed=true`; a changed request remains `NV008`.
- Concurrent first requests serialize on the Case row; exactly one may create the
  effective task.
- The worker still begins authority only at claim. It consumes the exact new Case
  revision and copies the same five-field Skill pin into `AgentExecution`.
- No endpoint, public error code, table, queue, provider, task operation, event kind, or
  automatic confirmation-to-planning path is added.

## Rejected alternatives

Starting planning during fact confirmation is rejected because it collapses two human
gates. A separate Case transition endpoint is rejected because it can commit without a
task. A browser-only transition is rejected because the browser is not business
authority. A second task operation or orchestration system is rejected because the
existing deterministic task contract already owns the required durable boundary.
