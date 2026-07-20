# Governed collaboration walkthrough

`/demo/collaboration` is Night Voyager's secondary local synthetic walkthrough. It
shows how a parent proposal becomes an authoritative Case fact only after assigned
advisor confirmation. It is non-production proof, not messaging, admissions advice,
or a claim about real users.

![Confirmed family fact and Case revision](../assets/collaboration-confirmed-fact.png)

## Run the walkthrough

```bash
make demo
```

Open `http://127.0.0.1:3000/demo/collaboration` and follow the six visible stages:

1. Start the parent walkthrough and append the bounded budget message.
2. Explicitly turn that message into a typed parent proposal.
3. Reload the pending candidate, then use the real role switch: revoke the parent
   session and mint the assigned advisor session.
4. Record the advisor confirmation. A message or proposal alone is never authority.
5. Reload the confirmed fact and Case revision from PostgreSQL authority.
6. Stop at `Re-plan required`; return to the primary `/demo` to start planning.

The secondary route does not create an `AgentTask`, open an `EventSource`, or use
polling. It has no role selector and no client-only identity change. Same-tab
recovery uses the shared `schema_version=2` journey envelope; an existing other
journey must be explicitly revoked before collaboration starts.

## Inspector and authority boundaries

The collapsed Planning Skill inspector consumes one server-owned, `no-store`
projection. It displays `not_created` on `/demo/collaboration` because this route
does not create a planning task. The primary `/demo` progresses from `not_created`
to `matched` after its real task is materialized; `legacy_unpinned` remains an
explicit historical status. The browser performs no client-side relational join and
has no Skill mutation authority.

Seven explicit BFF route modules expose exactly eight HTTP methods. They proxy only
the frozen collaboration and inspector endpoints; there is no catch-all, dynamic
upstream, arbitrary header forwarding, or cookie joining. FastAPI and PostgreSQL
retain participant, currentness, idempotency, fact, revision, activation, task, and
pin authority.

## Recovery and verification

An expired or missing session maps to bounded re-authentication. Stale, expired, or
active-task-blocked candidates stop safely. Lost acknowledgement retries reuse the
exact idempotency fingerprint, while a conflicting payload is rejected. Public
errors remain closed to the documented seven browser categories.

Run the real browser-to-database proof with:

```bash
make compose-proof
make down
docker compose ps --all
```

The Chromium lane uses the real PostgreSQL seed, FastAPI, BFF, opaque cookies,
Origin/CSRF checks, and idempotency. It covers 1440, 768, and 390 px, keyboard focus,
semantic landmarks, at least 44 px action targets, and horizontal-overflow checks.
The screenshot above is captured at 1440 px after authoritative fact/revision reload.

All fixtures are synthetic. Live providers, external message routing, production
deployment, and release publication remain outside this walkthrough.
