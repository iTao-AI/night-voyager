# Worker and SSE operations

M4A runs one local asyncio worker using the non-owner
`night_voyager_worker` database role. The default Compose adapter is
deterministic, credential-free, and network-free. The router accepts the
original all-synthetic adapter and the governed mixed adapter; both reuse the
same task, lease, retry, fencing, event, and SSE machinery. Migration `0008`
pins both operations to the active `study-destination-compare` SkillVersion and
requires packaged-registry validation before either adapter starts.

## Start and prove the local stack

```bash
make demo
make compose-proof
make down
```

`make compose-proof` uses an isolated Compose project and volume. It retains the
identity and M3B decision probes, first closes the dedicated governed DRA Case
from fixture candidate through mixed task and family decision, then creates the
separate synthetic task-ready Case task via HTTP, observes the worker persist a
current `review_required` `PlanningRun`,
checks ordered SSE replay and `Last-Event-ID` reconnect, restarts API and worker,
rechecks the same durable task, then runs the connected advisor-to-parent browser
flow in real Chromium at 1440, 768, and 390 px before removing isolated containers
and volumes.

## Runtime behavior

The worker globally claims only payload-free dispatch identity, then loads
tenant-pinned input, the claim-time execution Skill pin, trusted Skill key/version,
and claimed adapter leaf in a short tenant-scoped transaction. Adapter execution
runs outside a transaction. Start, heartbeat, retry, and finalize each use a
fresh short transaction and the current lease owner plus generation.

Before start the worker resolves the configured router leaf and validates the exact
packaged manifest entry, complete operation map, five-field execution pin, and
`runtime_binding_sha256`. The claimed execution leaf, resolved router leaf, and
packaged leaf must be equal. A valid start records the canonical hash of
`{request, five_field_pin}`; the leaf remains a separate normalized execution audit
fact.

Missing, mismatched, unsupported, catalog-only, stale, or malformed pins fail through
the generation-fenced `skill_pin_invalid` path with `retryable=false`. The worker does
not call `start_agent_task`, invoke an adapter, or leave the task in a reclaim loop.
It never treats a database operation string or UUID as executable router authority.

For `generate_governed_mixed_planning_run_v1`, the worker alone executes the
PostgreSQL mixed snapshot function. The snapshot must contain exactly one
`australia_program_fit` external Evidence and exact synthetic baseline facts for
all other accepted claims. Pin, policy, authority, or baseline drift fails
closed; the adapter never calls DRA or reads operator source files.

For both planning operations the worker materializes the exact persisted
organization, Case, revision, source pack, source-pack version, and policy. Persisted
budget, intake, Japan-risk acceptance, and preferred countries reach the actual
adapter. Route, cost, ranking, route-to-Evidence, and advisor-eligibility product
rows are filtered to the selected non-empty country subset; fixture Case values cannot
overwrite the requested revision.

The worker polls once per second when idle. A lease lasts 60 seconds and is
renewed every 15 seconds. An expired lease can be reclaimed; stale generation
output is discarded. Allowlisted transient failures retry up to three total
attempts. An exhausted expired lease closes the third execution as failed and
does not schedule a fourth attempt. Started executions retain only normalized
audit facts: canonical input/output hashes, fallback and retry facts,
non-negative duration, result reference, public code, and deterministic
`not_applicable` cost status. Waiting and terminal tasks hold no lease.

## Recovery checks

- Restarting API or worker does not lose tasks, executions, events, or results;
  PostgreSQL remains authoritative.
- SSE clients reconnect with the last durable `id` in `Last-Event-ID`.
- The M5 BFF streams upstream SSE bytes directly and maps `after` to
  `Last-Event-ID` only when that header is absent.
- A cursor ahead of the task log is a conflict and must not be silently reset.
- Heartbeats are SSE comments, not `agent_task_events` rows.
- A client that loses assignment or session authorization receives the same
  non-enumerating unavailable response as an unknown task.

Use `make db-check` for fresh migration, role, forced-RLS, dispatch privacy,
lease/reclaim/fencing/retry/cancel, SSE pagination, reconnect concurrency,
capacity, downgrade/re-upgrade, and connection-pool cleanup evidence.
Use `make skills-db-check SUITE=worker` for the focused task/execution pin,
registry-leaf, persisted-revision, selected-country, and invalid-pin proof.

## Troubleshooting

Inspect bounded service logs with `docker compose logs api worker postgres`.
Do not place credentials, adapter output, tenant payload, or raw Evidence in
proof output. If a retained local demo volume has schema drift, stop the stack
and use the explicit guarded reset command only when deleting local demo data is
intended:

```bash
RESET_DEMO=1 make reset-demo
```

M4A/M5 and the governed mixed closure do not provide distributed failover, remote provider integration,
production monitoring, or an availability SLA. The connected frontend controls
only the approved local synthetic workflow.
