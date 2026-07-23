# Governed collaboration walkthrough

The complete governed walkthrough begins at `/demo/collaboration`. This local
synthetic route shows how a parent proposal becomes an authoritative Case fact only
after assigned advisor confirmation, then hands the same Case to the focused `/demo`
route. It is non-production proof, not messaging, admissions advice, or a claim
about real users.

The route server-renders exact `zh-CN`; the shared header can explicitly persist
exact `en` at `night-voyager:presentation-locale:v1`. Locale is presentation-only and
cannot alter the journey envelope, authority reads, idempotency, role rotation,
navigation, task count, or EventSource count/URL.

![Confirmed family fact and Case revision](../assets/collaboration-confirmed-fact.png)

## Run the walkthrough

```bash
make demo
```

Open `http://127.0.0.1:3000/demo/collaboration` and follow the seven visible stages:

1. Start the parent walkthrough and append the bounded budget message.
2. Explicitly turn that message into a typed parent proposal.
3. Reload the pending candidate, then use the real role switch: revoke the parent
   session and mint the assigned advisor session.
4. Record the advisor confirmation. A message or proposal alone is never authority.
5. Reload the confirmed fact and Case revision from PostgreSQL authority.
6. At `需要重新规划` (`Re-plan required`), choose `继续进入受治理规划`
   (`Continue to governed planning`). The route
   revalidates the current candidate, confirmed fact, Case revision, advisor ledger,
   and Skill inspector, then replaces the same-tab envelope and navigates once.
7. On `/demo`, confirm the continued same Case and revision, then use the explicit
   task action to start planning.

The handoff sends zero task POST requests, creates no `AgentTask`, and opens no
`EventSource`; the collaboration route does not use polling. It keeps the same
opaque advisor cookie, CSRF value, and Case; it
does not bootstrap, mint, revoke, or perform a client-only identity change. A
successful handoff performs one exact `schema_version=2` storage replacement and
one navigation. Standalone `/demo/collaboration` remains independently usable.

## Inspector and authority boundaries

The collapsed Planning Skill inspector consumes one server-owned, `no-store`
projection. It displays `not_created` on `/demo/collaboration` because this route
does not create a planning task. The task-owning `/demo` progresses from
`not_created` to `matched` after its real task is materialized; `legacy_unpinned`
remains an explicit historical status. The browser performs no client-side
relational join and has no Skill mutation authority.

Validation uses the existing `no-store` candidate, confirmed-facts, advisor-ledger,
and Skill-inspector BFF reads in sequence. Candidate, fact, revision, Case, and
advisor identity must still agree. Any active/review/terminal task identity is
adopted only from `advisor-ledger`; the collaboration envelope transports no task
inputs or Skill pin.

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

`handoff_validating` is transient and never persisted. A validation failure leaves
the original collaboration envelope byte-for-byte intact; retry re-reads authority.
If navigation is interrupted after replacement, `/demo` recovers the advisor-family
envelope for the same Case rather than substituting the default fixture.

Run the real browser-to-database proof with:

```bash
make compose-proof
make down
docker compose ps --all
```

Each Chromium lane uses the real PostgreSQL seed, FastAPI, BFF, opaque cookies,
Origin/CSRF checks, idempotency, worker, and SSE. The required gate proves the
same complete chain twice from isolated database baselines: the first lane uses
the deterministic Chinese default without locale injection, and the second uses
`PRESENTATION_LOCALE=en`. Both run the browser-to-database verifier after the
parent message, receipt, and timeline flow, with the explicit `/demo` task action
as the only task-creation point. They cover 1440, 768, and 390 px, keyboard focus,
semantic landmarks, at least 44 px action targets, and horizontal-overflow checks.
The screenshot above is the current Chinese capture from the same deterministic
Chromium flow. It preserves server-authored synthetic message/reason text verbatim,
while all presentation-owned labels follow the selected locale.

All fixtures are synthetic. Live providers, external message routing, production
deployment, and release publication remain outside this walkthrough.
