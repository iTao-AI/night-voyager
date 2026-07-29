# Connected demo operations

M5 connects the focused `/demo` route to the local synthetic FastAPI, worker, SSE, and PostgreSQL
paths. It proves an advisor-to-parent workflow; it is not production tenancy,
live institutional coverage, or admissions advice.

The shared presentation shell server-renders exact `zh-CN`. The header's labelled
`中文` / `English` control can persist exact `en` at
`night-voyager:presentation-locale:v1`; invalid or unavailable storage falls back to
Chinese. This preference changes only presentation copy and `html[lang]`. It does not
bootstrap, mint, revoke, fetch, mutate, retry, create a task, reconnect SSE, navigate,
or enter the `sessionStorage` journey envelope.

![Chinese advisor review state](../assets/m5-advisor-ledger.png)

![Chinese family receipt and timeline](../assets/m5-family-receipt-timeline.png)

![Chinese planning revision comparison](../assets/night-voyager-planning-revision.png)

The complete governed walkthrough begins at `/demo/collaboration` and is documented
in the [governed collaboration walkthrough](collaboration-walkthrough.md). It shares
the session envelope and read-only inspector. Its controlled handoff creates no task
or SSE connection; `/demo` owns both only after explicit advisor action.

## Run the walkthrough

```bash
make demo
```

Open `http://127.0.0.1:3000/demo` for the standalone seeded walkthrough, or continue
from `/demo/collaboration` after confirming a fact. In the continued journey,
`/demo` restores the same non-default Case, shows its current confirmed facts and
revision, and re-reads task inputs from `ledger.canonical_task_inputs`. Use the
explicit `创建规划任务` (`Create planning task`) action, wait for the durable stream
to reach review, approve Australia,
rotate into the parent session, confirm the server-derived trade-off, and retain the
resulting receipt and timeline. Stop the stack with `make down`.

The revision-aware backend phases expose one primary action:

| Phase | Projection | Primary action |
| --- | --- | --- |
| `task_ready` | canonical demo task inputs; task/run absent | create task |
| `active_task` | latest task; run/review absent until persisted | follow SSE |
| `review_required` | completed task, current run, routes/Evidence, review inputs | approve or request revision |
| `revision_requested` | retained predecessor and exact request review | rotate to the student proposal |
| `revision_fact_pending` | bounded student preferred-country change | assigned advisor confirmation |
| `replan_required` | current revision owns retained predecessor; no task | create explicit revision task |
| `revision_task_active` | exact revision task and durable SSE progress | follow SSE |
| `revision_review_required` | successor PlanningRun and deterministic old/new comparison | fresh advisor authorization |
| `revision_blocked` | comparison plus deterministic block reason | evidence/fact remediation only |
| `family_review` | current family-safe Brief plus renewed authorization | revoke advisor and mint parent |
| `plan_ready` | completed status plus persisted receipt/timeline | continue as family or read result |
| `terminal_task_failure` | public failure and explicit recovery guidance | allowed retry/remediation only |

Absent task, run, route, or review data is rendered as absent, never as placeholder
authority. The default UI mints an advisor first. Its normal role transition is
advisor revoke, cookie expiry, bootstrap, then parent mint; it stops if revoke
fails and never performs a client-only role flip.

## Authority and transport boundaries

FastAPI exposes three connected read endpoints:

- `GET /api/v1/cases/{case_id}/advisor-ledger`
- `GET /api/v1/cases/{case_id}/current-decision-brief`
- `GET /api/v1/cases/{case_id}/journey-status`

The Next.js BFF exposes twelve explicit handlers: bootstrap, session create,
session delete, Ledger read, task create/read/cancel/events, advisor review,
current Brief read, journey-status read, and family decision. There is no catch-all proxy. All
identity upstream calls use the server-configured fixed public Origin. Browser
mutations must first pass exact Origin validation; caller Origin is neither
trusted nor reflected. Each upstream `Set-Cookie` field is appended separately,
and every response is `no-store`.

PostgreSQL remains authoritative for tenant, participant, Case currentness,
task, PlanningRun, Brief, receipt, and timeline. Before task creation, the
checked-in validated fixture contract only restricts the canonical synthetic
input identity and must match the existing source-pack row. The BFF and browser
do not derive policy, route eligibility, or authority.

The same-Case continuation adds no BFF route. The destination reuses the existing
advisor-ledger, confirmed-facts, inspector, task, event, review, Brief, and decision
handlers. Every later read and mutation uses the continued Case. Task identity comes
only from `advisor-ledger`, never from the collaboration envelope or URL state.

The family Brief projects the selected Australia route, `CNY`, pinned cost, hard
ceiling, and the exact required trade-off `budget_elasticity` from persisted
rows and policy. The client may confirm these facts but cannot hard-code them.

The shared Planning Skill inspector is a server-owned, `no-store` projection. It
starts as `not_created` and becomes `matched` after the real planning task is
materialized; `legacy_unpinned` is explicit rather than inferred. The browser performs
no client-side relational join and has no Skill mutation authority.

## Recovery and proof

The browser reconnects SSE with the latest durable `Last-Event-ID`; heartbeat
comments are not stored events. Role and CSRF metadata in `sessionStorage`
support reload only in the same tab. If an opaque cookie exists while recovery
metadata is missing or inconsistent, the UI fails closed: it does not mutate,
guess a role, silently revoke, or show parent presentation.

The collaboration journey remains V2; advisor-family recovery uses the closed V3
envelope with snake_case phase, current revision/task/predecessor/run, cursor, and
pending mutation identity. An existing other journey must be explicitly revoked, so a
tab cannot run the two workflows concurrently. `/demo` preserves one active
`EventSource` and a monotonic durable cursor. The explicit task action creates
at most one task and opens exactly one initial `/events?after=0` stream. Reloads
recover the stored cursor, review state, parent rotation, receipt, and timeline for
the continued Case.

Run the real browser-to-database proof with:

```bash
make compose-proof
make down
```

For the v0.1.4 planning-revision lane, set
`NIGHT_VOYAGER_COMPOSE_PROOF_MODE=planning-revision`. The lane proves request
revision, the controlled student preferred-country change, retained predecessor,
successor PlanningRun, lost-ack recovery, deterministic comparison, renewed review,
only the current family decision, and the blocked budget counterfactual. The
dedicated asset is updated only with `UPDATE_PLANNING_REVISION_SCREENSHOT=1`;
`UPDATE_PORTFOLIO_SCREENSHOTS` remains scoped to the released portfolio captures.

Local Task 4 evidence used the exact host Playwright browser against Compose-served
PostgreSQL/API/worker state because the local containerized browser image could not
complete external Docker/apt transport. That controlled provider-free hybrid was
GREEN for both locales and the database verifier, but it is not formal Compose GREEN.
After publication, the exact-head hosted `python`, `frontend`, and `compose` checks
remain mandatory, and the hosted `compose` check must run the normal containerized
path successfully.

The proof exercises PostgreSQL roles/RLS, identity cookies and fixed Origin,
worker/SSE replay, advisor review, real role rotation, family decision,
idempotency/stale rejection, reload, 1440/768/390 layouts, keyboard focus, and
semantic landmarks in Chromium. The required gate runs that complete lane twice
from isolated database baselines: first without locale injection to prove the
deterministic Chinese default, then with `PRESENTATION_LOCALE=en` to prove the
explicit English path. Both lanes finish with the same browser-to-database
verifier. A stale retained local volume may be removed
only through the existing protected reset:

```bash
RESET_DEMO=1 make reset-demo
```

The demo uses synthetic data and local deterministic execution. DRA, OCR,
OpenClaw, remote providers, real student data, production deployment, and the
optional MKE consumer are outside this product path.
