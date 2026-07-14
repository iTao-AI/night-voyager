# ADR 0006: Connected Demo and BFF Authority

## Status

Accepted for M5 design. Implementation has not started.

## Context

M2 through M4A provide synthetic identity, forced-RLS domain authority, deterministic
planning, advisor/family decisions, a durable worker, and authorized SSE. The public
`/demo` remains a disconnected M1 visual fixture. A browser-visible flow needs a
same-origin transport boundary and resumable read projections without moving business
authority into Next.js or combining the old Japan fixture with the Australia backend
proof.

## Decision

1. M5 uses one connected `/demo` and one task-ready synthetic Case for advisor-to-parent
   flow. Role change revokes and remints the real synthetic session. M5 adds no Case
   source-pack/policy binding or migration.
2. FastAPI/PostgreSQL remain the only authority for tenant, role, Case, task, Evidence,
   eligibility, review, decision, receipt, timeline, idempotency, and currentness.
3. Two read-only role-scoped endpoints expose the current Advisor Ledger and current
   family-safe Brief. They add no table or business state.
4. Next.js App Router Route Handlers form an explicit transport-only BFF. There is no
   catch-all proxy or caller-selected upstream.
5. A server-owned resolver derives canonical demo task inputs only from the validated
   checked-in M3A manifest, project `POLICY_VERSION`, and an exactly matching existing
   PostgreSQL source-pack row. Before task creation they are not Case-persisted pins;
   afterward task/run pins must match them or projection fails closed.
6. The Ledger has explicit task-ready, active-task, review-required, family-review,
   plan-ready, and terminal-task-failure phases. Absent task/run/route/review data remains
   absent rather than becoming placeholder authority.
7. The BFF forwards only allowlisted request/response fields, validates exact Origin and
   bounded bodies, streams SSE without interpretation, and emits only redacted upstream
   unavailable/timeout problems of its own. It sends the server-configured fixed public
   Origin on every demo identity request, never reflects caller Origin, and appends each
   upstream `Set-Cookie` field separately without comma joining.
8. Client state is display/recovery state only. Consequential transitions follow backend
   responses, and idempotency/stale recovery remains server-authoritative.
   New browser sessions start as advisor; retained completion requires a real
   advisor-to-parent session transition, and `plan-ready` never creates a new task.
9. M4B MKE candidates, DRA, OCR, OpenClaw, remote providers, share tokens, production
   accounts, release, and deployment remain outside M5.

## Consequences

The repository gains a coherent full-stack synthetic product proof while preserving the
existing authority and trust boundaries. A future adapter can change backend Evidence
inputs without teaching the browser an upstream contract. The BFF adds code and security
tests, but it remains bounded, observable, and replaceable because it owns no business
state.

The connected demo requires current read models and explicit recovery semantics. Browser
visibility cannot substitute for RLS, role checks, idempotency, or policy tests. The
current M1 Japan fixture is no longer active connected state after implementation; its
design history remains documented.

Canonical demo inputs remain server-owned without adding Case state. Phase discrimination,
fixed-Origin forwarding, and separate cookie-field forwarding add implementation and test
obligations but prevent the BFF or client from inventing authority during partial or
retained workflows.

## Rejected alternatives

Direct browser-to-FastAPI access was rejected because it weakens the same-origin BFF,
cookie, deployment, and presentation boundary. A generic reverse proxy was rejected
because request-selected paths or upstreams expand SSRF and authority risk. Server
Actions as the primary orchestration layer were rejected because durable SSE and explicit
recovery are clearer through Web-standard Route Handlers and a client display state
machine. Separate advisor and parent demo URLs were rejected because they fragment the
single interview-visible workflow without adding real account isolation.
