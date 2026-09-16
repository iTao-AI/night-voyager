# Connected demo operations

M5 connects the focused `/demo` route to the local synthetic FastAPI, worker, SSE,
and PostgreSQL paths. It is the route-analysis segment of the advisor workspace and
proves advisor review followed by client confirmation. The current release boundary
continues that same Case from its receipt and TimelinePlan into the existing plan
execution workspace. The continuation is merged on the current default branch in PR #103; it remains local synthetic and provider-free, is included in v0.1.6, and is not deployed. Bare `/demo/plan` remains an independent seeded scenario. It is not production tenancy, live institutional coverage, or admissions advice.

The current shared presentation uses the reference-driven Midnight Editorial Advisor
Workspace: a dark product frame, warm decision surface, five-stage display rail,
authority plane, and default-closed technical evidence. These are presentation-only
surfaces over the existing server-owned projections.

The shared presentation shell server-renders exact `zh-CN`. The header's labelled
`中文` / `English` control can persist exact `en` at
`night-voyager:presentation-locale:v1`; invalid or unavailable storage falls back to
Chinese. This preference changes only presentation copy and `html[lang]`. It does not
bootstrap, mint, revoke, fetch, mutate, retry, create a task, reconnect SSE, navigate,
or enter the `sessionStorage` journey envelope.

![Chinese advisor review state](../assets/m5-advisor-ledger.png)

![Chinese family receipt and timeline](../assets/m5-family-receipt-timeline.png)

![Chinese planning revision comparison](../assets/night-voyager-planning-revision.png)

The current family receipt/timeline frame is refreshed review evidence for the
connected `/demo` `plan_ready` state. It includes the same-Case primary
continuation and the retained independent scenario entry; it is not PostgreSQL or
RLS proof.

| Asset | Before | After |
| --- | --- | --- |
| `m5-family-receipt-timeline.png` | `1440x1575`; SHA-256 `e37190c48af9ee299cfb29f50be538260dee4aa738af9d48b687560e78bc7741` | `1440x1566`; SHA-256 `377879a7b840504101953236b79b6a0477ba4fe3a2790e67958e18bfe626f255` |

Capture provenance: frozen source files were `ConnectedDemo.tsx` SHA-256
`b6abbfb3f5299a62824fa5ad2d490c17aca285ceecff9c30a9de8550922989f0`,
`PlanExecutionWorkspace.tsx` SHA-256
`0779e23e71cc85c1a467994fcb6a6285f1576dbb3bb1e09f7ec87681343ab12a`, and
`catalog.ts` SHA-256
`f3bd0c5645311ffa5c5bdb15c789161974576831d6442dcf63a7a0b697b58ba5`. The
capture used real Chromium through the repository Playwright CLI at `zh-CN`, a
`1440x900` viewport, and an explicit local synthetic `plan_ready` contract. No
Docker or database authority was used for this visual capture. Hosted
Compose/database/browser proof remains mandatory before merge.

The connected same-Case walkthrough begins at `/demo/collaboration` and is documented
in the [governed collaboration walkthrough](collaboration-walkthrough.md). It shares
the session envelope and read-only inspector. Its controlled handoff creates no task
or SSE connection; `/demo` owns both only after explicit advisor action. After the
family decision reaches `plan_ready`, its primary action carries only the current
`case_id` to `/demo/plan?case_id=<case_id>`, where the server re-derives the exact
execution context. The independently seeded Happy/Blocked execution scenario at
bare `/demo/plan` or `?scenario=blocked` is not a continuation of this Case or
session.

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
| `plan_ready` | completed status plus persisted receipt/timeline | continue this Case into execution or read result |
| `terminal_task_failure` | public failure and explicit recovery guidance | allowed retry/remediation only |

Absent task, run, route, or review data is rendered as absent, never as placeholder
authority. The default UI mints an advisor first. Its normal role transition is
advisor revoke, cookie expiry, bootstrap, then parent mint; it stops if revoke
fails and never performs a client-only role flip.

## Authority and transport boundaries

FastAPI exposes four connected read endpoints:

- `GET /api/v1/cases/{case_id}/advisor-ledger`
- `GET /api/v1/cases/{case_id}/current-decision-brief`
- `GET /api/v1/cases/{case_id}/journey-status`
- `GET /api/v1/cases/{case_id}/plan-execution-context`

The Next.js BFF exposes thirteen explicit handlers: bootstrap, session create,
session delete, Ledger read, task create/read/cancel/events, advisor review,
current Brief read, journey-status read, case-scoped plan-execution-context read,
and family decision. There is no catch-all proxy. All
identity upstream calls use the server-configured fixed public Origin. Browser
mutations must first pass exact Origin validation; caller Origin is neither
trusted nor reflected. Each upstream `Set-Cookie` field is appended separately,
and every response is `no-store`.

PostgreSQL remains authoritative for tenant, participant, Case currentness,
task, PlanningRun, Brief, receipt, and timeline. Before task creation, the
checked-in validated fixture contract only restricts the canonical synthetic
input identity and must match the existing source-pack row. The BFF and browser
do not derive policy, route eligibility, or authority.

The same-Case continuation adds one explicit read-only BFF route for its strict
case-scoped execution context. The destination otherwise reuses the existing
advisor-ledger, confirmed-facts, inspector, task, event, review, Brief, decision,
and timeline-execution handlers. Every later read and mutation uses the continued
Case. Task identity comes only from `advisor-ledger`, never from the collaboration
envelope or URL state; execution identity comes only from the server-derived context.

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

The collaboration journey now writes a closed V3 envelope with the immutable,
case-revision-bound budget intent. V2 is accepted only for an observed exact legacy
default-budget fingerprint; new amounts never fall back to old storage or mutation
records. Advisor-family recovery continues to use its existing closed V3 envelope
with snake_case phase, current revision/task/predecessor/run, cursor, and pending
mutation identity. An existing other journey must be explicitly revoked, so a tab
cannot run the two workflows concurrently. `/demo` preserves one active
`EventSource` and a monotonic durable cursor. The explicit task action creates
at most one task and opens exactly one initial `/events?after=0` stream. Reloads
recover the stored cursor, review state, parent rotation, receipt, timeline, and
case-scoped execution authority for the continued Case. The plan-execution envelope
binds its authority kind and exact Case or seeded scenario, so it never restores a
connected Case as a seeded scenario or a seeded scenario as a connected Case.

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
`UPDATE_PORTFOLIO_SCREENSHOTS` remains scoped to the current release captures;
these screenshots are review evidence for the current v0.1.6 local synthetic portfolio release;
they do not provide functional authority.

The current task-scoped Compose proof is the required containerized browser gate for
the Compose-served PostgreSQL/API/worker state. When available, it must cover both
locales, the presentation matrix, same-Case persistence, independent Happy/Blocked
execution, stale-tab and restart recovery, and database verification before removing
its task-owned resources. A local Docker omission does not replace the hosted
Compose/database/browser gate required before merge.

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
