# AgentTask and event reference

The backend supports two operations through the same durable task authority:
`generate_planning_run_v1` preserves the all-synthetic M4A behavior, while
`generate_governed_mixed_planning_run_v1` consumes an exact approved promoted
source pack. An assigned advisor creates either task against an exact Case
revision, source-pack version, `m3a-policy-v1`, and the current active
`study-destination-compare` SkillVersion. The mixed operation is
accepted only after the atomic human verification/promotion gate and can use
external authority only for `australia_program_fit`; every other accepted fact
must match the synthetic baseline. Both paths end at `review_required` and
still require the existing human advisor review.
Neither operation calls a remote provider. The mixed operation is a backend
authority path only and is not exposed through the connected `/demo` browser
flow.

## Durable records

- `app.agent_tasks` is the current task authority. It stores Case/source/policy
  pins, the exact five-field Skill runtime pin, state,
  attempt count, lease generation, sanitized terminal code, and an optional
  result `PlanningRun` reference.
- `app.agent_executions` records normalized attempts, an immutable claim-time copy
  of the task's five-field Skill pin, the actual selected adapter leaf, and
  generation-fenced outcomes. A started attempt stores the SHA-256 of its canonical
  request; completion stores a non-negative duration, retry/fallback facts,
  `not_applicable` cost status for the deterministic adapter, and an output hash
  plus result reference when a result is accepted. It does not store prompts,
  provider payloads, raw outputs, or stack traces.
- `app.agent_task_events` is the immutable, task-local replay log. Its
  `event_sequence` is the SSE event ID.
- `internal.agent_task_dispatch` contains only `task_id`, `organization_id`, and
  `available_at`. It contains no Case, Evidence, request, adapter, result, error,
  or raw payload.

The three application tables are migrator-owned and forced-RLS protected.
Runtime roles have no direct task write authority. Narrow functions perform
assigned-advisor creation/cancellation and worker lease transitions.

## Explicit planning start

Migration `0009` makes creation of the first deterministic planning task the assigned
advisor's explicit planning-start authority. When the current exact Case revision is in
`intake`, a valid `generate_planning_run_v1` request may atomically write the
`intake -> planning` transition, pinned task, payload-free dispatch identity, first
event, and idempotency result. The first deterministic planning task therefore cannot
exist without the transition, and the transition cannot commit without the complete
task authority set.

Idempotency replay remains before new-write validation and never repeats the transition.
Concurrent first requests serialize on the Case row and only one effective task may be
created. Confirmation alone still creates no task and does not enter `planning`; the
mixed operation from `intake` remains rejected. Planning never starts automatically,
and existing creation from `planning` keeps its prior behavior.

## Versioned Skill pin

Every planning task created after migration `0008` stores exactly:

```text
skill_definition_id
skill_version_id
skill_activation_event_id
skill_activation_sequence
runtime_binding_sha256
```

The complete five-field pin participates in effective-task identity. Task creation
resolves it in the same transaction as idempotency replay, effective uniqueness, task
insert, and dispatch insert. Replay returns the original task and pin even if a newer
version becomes active. Activation or rollback affects only later task creation.

Claim validates the relational pin and copies all five fields to AgentExecution.
Composite foreign keys and immutable guards require exact task/execution equality.
The execution separately retains `adapter_id` and `adapter_version` as the actual leaf
audit fact.

The worker loads the copied pin plus trusted joined Skill key/version, resolves the
configured router leaf, and requires equality with the packaged manifest operation
binding before start. The successful canonical execution input hash is exactly
`sha256({request, five_field_pin})`. Missing, mismatched, unsupported, catalog-only,
or malformed pins fail through the fenced non-retryable `skill_pin_invalid` path
without start, adapter invocation, or reclaim/retry.

Pre-`0008` active `queued|leased|running` tasks without a pin are cancelled during
upgrade with `legacy_unpinned`. Existing `waiting_review` and terminal history is
retained and projects `pin_status=legacy_unpinned`; new task creation never produces
an unpinned row.

## Persisted revision input

Both planning operations materialize the exact persisted organization, Case,
revision, source pack, source-pack version, and policy. Persisted budget, intake,
Japan-risk acceptance, and preferred countries reach the adapter; fixture Case values
cannot replace them. Preferred countries are a non-empty sorted unique subset of
Australia, Japan, and Malaysia. Route, cost, ranking, route-to-Evidence, and eligible
advisor-review product projections contain selected countries only.

## State projection

| Internal state | Public status |
| --- | --- |
| `queued`, `leased`, `running` | `preparing` |
| `waiting_review` | `needs_advisor_review` |
| current `succeeded` | `ready` |
| `blocked` | `needs_evidence` |
| `timed_out` | `timed_out` |
| `failed` | `failed` |
| `cancelled` | `cancelled` |
| non-current waiting/succeeded result | `outdated` |

Public task and event projections omit organization, actor, session, lease,
dispatch, internal error, and adapter-payload fields.

## Lease and retry contract

Leases last 60 seconds and are heartbeated every 15 seconds. Every accepted
claim increments a monotonic generation; worker writes require the current
owner and generation. Reclaim or cancellation therefore fences late output.
Only normalized transient adapter unavailability, transport interruption, and
expired-lease recovery may retry, with at most three total attempts. Unknown,
schema, pin, policy, authority, Evidence, fallback, and bounds failures fail
closed. If the third lease expires, its existing execution finishes as
`failed`, non-retryable, with `lease_expired`; no fourth execution or
`retry_scheduled` event is created.

## SSE contract

`GET /api/v1/tasks/{task_id}/events` is an authorized projection, not task
authority. It replays events in ascending `event_sequence`, reads at most 100
rows per database page, and accepts a non-negative integer `Last-Event-ID`.
Missing cursors replay from event 1; malformed cursors return `400`; cursors
ahead of the durable maximum return `409`. A reconnect resolves the current
session and assigned-advisor relationship again.

The stream sends a `: heartbeat` comment after 15 seconds without an event.
Comments are not durable rows. Once a closing state is reached and all durable
events are delivered, the connection closes. Each page uses a short database
transaction; waiting and yielding do not retain a session.

## Fixed bounds

- task payload: 1 MiB canonical JSON;
- narrative: 64 KiB;
- Evidence references: 20;
- countries: Australia, Japan, and Malaysia;
- replay page: 100 events;
- attempts: 3.

These are local safety bounds, not production throughput or availability
claims.
