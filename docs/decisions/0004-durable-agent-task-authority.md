# ADR 0004: Durable AgentTask authority and SSE replay

Status: Accepted

M4A establishes these authority decisions:

1. PostgreSQL is the durable task and event authority. Provider traces, HTTP
   connections, SSE connections, and worker memory are not business state.
2. Global dispatch is payload-free and inaccessible as a runtime table. Tenant
   Case, request, Evidence, adapter, error, and result data remains in forced-RLS
   tables.
3. Lease owner plus monotonic generation fences every worker write. External
   adapter work runs outside short database transactions.
4. Task state changes and durable events are atomic. SSE is an authorized replay
   projection and never the authority.
5. Internal task states and public task statuses are distinct deterministic
   contracts; leases and internal failures are not public response fields.
6. Retry is allowlisted and bounded to three total attempts. Unknown, authority,
   schema, policy, and Evidence failures fail closed.
7. The only M4A adapter is deterministic and local synthetic. It cannot approve
   Evidence, an advisor review, or a family decision.
8. No queue product or remote runtime is introduced without a later accepted ADR
   and demonstrated need.

The sole operation is `generate_planning_run_v1` with policy `m3a-policy-v1`.
Its approved synthetic path produces a current `review_required` PlanningRun and
public `needs_advisor_review`; it cannot bypass existing M3A or M3B authority.

## Consequences

Migration `0004` owns `agent_tasks`, `agent_executions`, and
`agent_task_events` as tenant-keyed forced-RLS tables plus payload-free
`internal.agent_task_dispatch(task_id, organization_id, available_at)`. Runtime
roles receive no direct M4A DML or internal-table access. Narrow migrator-owned
`SECURITY DEFINER` functions with fixed search paths perform assigned-advisor
create/cancel and generation-fenced worker transitions.

The worker uses bounded 60-second leases, 15-second heartbeats, a 1-second idle
poll, and three total attempts. SSE replays at most 100 durable events per page,
uses a 15-second comment heartbeat, and reauthorizes each reconnect. Local
synthetic capacity evidence is not a production SLA.

## Rejected alternatives

Redis, Celery, Temporal, and Kafka are rejected for M4A because PostgreSQL
already provides the required durable record, transaction, lease, RLS, and
replay boundary; a second queue system would add authority and operational
complexity without demonstrated need. Provider-owned task state is rejected
because it cannot enforce Night Voyager tenant, Evidence, deterministic policy,
human-review, idempotency, or durable replay authority. In-memory queues and
SSE-only state are rejected because restart would lose business state.

M4B remote evidence consumption and M5 frontend/BFF integration remain separate
later decisions. M4A proves only a local synthetic deterministic worker path.
