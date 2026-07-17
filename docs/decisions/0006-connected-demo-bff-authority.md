# ADR 0006: Connected Demo and BFF Authority

## Status

Accepted. Implemented in M5.

## Context

Before M5, M2 through M4A provided synthetic identity, forced-RLS domain authority,
deterministic planning, advisor/family decisions, a durable worker, and authorized SSE.
Before M5, `/demo` was a disconnected M1 visual fixture. A browser-visible flow needed a
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
   family-safe Brief. The latter includes server-authoritative `decision_requirements`
   projected from the pinned Brief/PlanningRun/Case revision, accepted Australia cost
   Evidence, and existing M3B policy, including route identity, CNY pinned cost, hard
   ceiling, and required trade-offs. They add no table or business state.
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
   bounded bodies, streams SSE without interpretation, and uses a closed local problem
   allowlist for invalid request, Origin, residual-session recovery, body size, media type,
   unavailable, and timeout failures. It sends the server-configured fixed public Origin on
   every demo identity request, never reflects caller Origin, and appends each upstream
   `Set-Cookie` field separately without comma joining. FastAPI problem responses pass
   through unchanged.
8. Client state is display/recovery state only. Consequential transitions follow backend
   responses, and idempotency/stale recovery remains server-authoritative.
   The connected UI defaults a fresh walkthrough to advisor and offers no client-only role
   impersonation. Retained completion uses the real advisor-to-parent session transition,
   and `plan-ready` never creates a new task. This UI sequencing does not change the
   existing synthetic actor mint capability or advisor/student/parent family-safe read
   matrix; it adds no transition token or BFF phase authority.
9. `sessionStorage` role and CSRF metadata support same-tab reload only. Missing or
   inconsistent metadata exposes no mutation or parent presentation. The bootstrap BFF
   handler checks only whether the named HttpOnly session cookie is present; presence
   returns redacted `409 bff_session_recovery_required` before upstream access, while
   absence permits normal bootstrap. It never reads the value, resolves the session, or
   infers a role. M5 adds no identity endpoint, transition token, BFF role authority,
   `localStorage`, or revoke without CSRF.
10. M4B MKE candidates, DRA, OCR, OpenClaw, remote providers, share tokens, production
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

The checked-in fixture contract limits the pre-task synthetic input identity but does not
replace database authority. Existing forced-RLS PostgreSQL rows remain authoritative for
Case currentness, participants and roles, source-pack existence, tasks, runs, and results;
the read endpoints add no persistence and write no domain state.

The six-beat walkthrough controls presentation order, not backend role authorization. A
real parent session is required for the connected UI's complete parent presentation, while
the existing assigned advisor/student/parent current-Brief contract remains unchanged.

Decision input constraints remain server-authoritative rather than becoming fixture,
Compose, country-label, or client constants. Tab-scoped recovery metadata improves reload
continuity without turning a surviving opaque cookie or family-safe response into role
proof; ambiguous recovery fails closed.

The cookie-presence bootstrap guard is transport safety rather than identity authority. Its
closed `409` prevents an empty tab from accidentally reaching the existing session-rotation
path, while a genuinely cookie-free browser can still begin the synthetic walkthrough.

## Rejected alternatives

Direct browser-to-FastAPI access was rejected because it weakens the same-origin BFF,
cookie, deployment, and presentation boundary. A generic reverse proxy was rejected
because request-selected paths or upstreams expand SSRF and authority risk. Server
Actions as the primary orchestration layer were rejected because durable SSE and explicit
recovery are clearer through Web-standard Route Handlers and a client display state
machine. Separate advisor and parent demo URLs were rejected because they fragment the
single interview-visible workflow without adding real account isolation.
