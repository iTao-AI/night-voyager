# M5 Connected Advisor-to-Family Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> to implement this plan task-by-task in an isolated worktree. Every behavioral,
> security, transport, and UI slice follows test-first RED -> GREEN. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the existing synthetic identity, deterministic planning,
durable task/SSE, advisor review, family decision, receipt, and timeline into one
browser-visible `/demo` walkthrough without moving authority into Next.js or the
client.

**Architecture:** FastAPI adds two role-scoped read models backed only by existing
forced-RLS PostgreSQL rows and a validated server-owned synthetic input contract.
Explicit Next.js Route Handlers form a same-origin transport-only BFF; a pure
client reducer and focused React components render backend state and perform only
the already-approved mutations. The existing Compose `compose` lane runs the real
browser-to-database golden flow.

**Tech Stack:** Python 3.12.13, Pydantic v2, FastAPI/Starlette, SQLAlchemy async,
asyncpg, PostgreSQL 18.4, Next.js 16.2.10 App Router, React 19.2.3, TypeScript
5.9.3, Vitest 4.1.10, Testing Library, Playwright 1.58.2, Docker Compose.

## Global Constraints

- Begin from the latest clean `main` that contains the accepted M5 spec, ADR
  `0006`, and this implementation plan; use a short-lived `codex/` branch in an
  isolated linked worktree.
- Preserve the exact migration graph `0001 -> 0002 -> 0003 -> 0004`; M5 adds no
  migration, table, index, database function, ownership change, grant, role, RLS
  policy, or business state.
- Add exactly two FastAPI read endpoints:
  `GET /api/v1/cases/{case_id}/advisor-ledger` and
  `GET /api/v1/cases/{case_id}/current-decision-brief`.
- Preserve all existing identity, M3A, M3B, M4A, and M4B mutation, policy,
  idempotency, lease/fencing, Evidence, role, and currentness semantics.
- The only connected Case is the explicit synthetic task-ready Case
  `40000000-0000-0000-0000-000000000002`; migrations remain seed-free.
- Before task creation, task inputs come only from the validated checked-in M3A
  fixture, project `POLICY_VERSION`, and an exactly matching existing PostgreSQL
  source-pack row. After task creation, persisted task/run pins must match that
  canonical contract or the read model fails closed.
- The family decision requirements come from the pinned Brief/PlanningRun/Case
  revision, Australia cost Evidence, and existing M3B policy facts. The client
  must not hard-code budget bounds, `budget_elasticity`, eligibility, or route
  authority.
- The BFF uses only explicit Route Handlers, server-only
  `NIGHT_VOYAGER_API_INTERNAL_URL` and `NIGHT_VOYAGER_PUBLIC_ORIGIN`, fixed
  methods/path shapes, canonical UUIDs, 32 KiB JSON bodies, header allowlists,
  fixed Origin forwarding, separate `Set-Cookie` fields, bounded non-SSE
  deadlines, direct SSE streams, and no catch-all proxy.
- Same-tab reload may recover role and CSRF from `sessionStorage`. Missing or
  inconsistent recovery metadata with an opaque cookie fails closed: no guessed
  role, parent presentation, mutation, silent rotate, or silent revoke.
- Keep MKE, DRA, OCR, OpenClaw, remote providers, credentials, real student data,
  share tokens, participant-management APIs, production tenancy, release,
  deployment, and production claims outside M5.
- Add no Python or frontend dependency, UI library, CSS framework, remote font,
  new required check name, new Compose business service, or browser reset action.
- Keep public documents, screenshots, fixtures, test output, commit messages, and
  PR content public-neutral and synthetic-proof precise.

---

### Task 1: Freeze M5 executable contracts and canonical demo input authority

**Files:**
- Create: `src/night_voyager/connected_demo/__init__.py`
- Create: `src/night_voyager/connected_demo/models.py`
- Create: `src/night_voyager/connected_demo/fixtures.py`
- Create: `src/night_voyager/connected_demo/errors.py`
- Create: `tests/architecture/test_m5_contract.py`
- Create: `tests/unit/connected_demo/test_models.py`
- Create: `tests/unit/connected_demo/test_fixtures.py`
- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `scripts/seed_demo.py`
- Modify: `tests/unit/identity/test_m3b_seed.py`
- Modify: `tests/unit/tasks/test_m4a_seed_proof.py`

**Interfaces:**
- Consumes: `validate_planning_fixture()`, `POLICY_VERSION`, the existing M4A
  task-ready Case ID, `TaskViewStatus`, M3A route/Evidence facts, and M3B
  family-safe DTOs.
- Produces: `DemoPhase`, `CanonicalDemoSourceContract`,
  `CanonicalDemoTaskInputs`, `AdvisorLedgerV1`, `CurrentDecisionBriefV1`,
  `FamilyDecisionRequirements`, `resolve_canonical_demo_source_contract()`, and
  one shared `CONNECTED_DEMO_CASE_ID` constant.

- [ ] **Step 1: Add failing architecture and model tests**

  Add exact assertions that the three M5 public records exist, only four
  migrations remain, no M5 database DDL/grants exist, the two backend paths and
  eleven BFF paths are frozen, pure `connected_demo` modules import no FastAPI or
  SQLAlchemy, and every phase rejects impossible placeholder authority.

  ```python
  def test_m5_keeps_the_existing_database_graph() -> None:
      assert [path.name for path in sorted(Path("migrations/versions").glob("*.py"))] == [
          "0001_identity_and_rls.py",
          "0002_case_evidence_planning.py",
          "0003_advisor_family_decision.py",
          "0004_agent_tasks_executions_events.py",
      ]

  def test_task_ready_phase_rejects_a_fabricated_run() -> None:
      with pytest.raises(ValueError, match="task-ready projection"):
          AdvisorLedgerV1.model_validate({**task_ready_payload(), "planning_run": run_payload()})
  ```

- [ ] **Step 2: Run the focused tests and record RED**

  Run:

  ```bash
  uv run pytest tests/architecture/test_m5_contract.py tests/unit/connected_demo -q
  ```

  Expected: collection fails because `night_voyager.connected_demo` and its
  contracts do not exist.

- [ ] **Step 3: Implement exact frozen read-model contracts**

  Define the public shapes in `models.py` with `ConfigDict(frozen=True,
  extra="forbid")` and a phase validator:

  ```python
  class DemoPhase(StrEnum):
      TASK_READY = "task-ready"
      ACTIVE_TASK = "active-task"
      REVIEW_REQUIRED = "review-required"
      FAMILY_REVIEW = "family-review"
      PLAN_READY = "plan-ready"
      TERMINAL_TASK_FAILURE = "terminal-task-failure"

  class CanonicalDemoTaskInputs(FrozenModel):
      schema_version: Literal[1] = 1
      operation: Literal["generate_planning_run_v1"]
      case_id: UUID
      expected_case_revision: PositiveInt
      source_pack_id: UUID
      source_pack_version: PositiveInt
      policy_version: Literal["m3a-policy-v1"]

  class FamilyDecisionRequirements(FrozenModel):
      schema_version: Literal[1] = 1
      eligible_route_id: UUID
      currency: Literal["CNY"]
      pinned_cost_minor: PositiveInt
      hard_ceiling_minor: PositiveInt
      required_trade_offs: tuple[Literal["budget_elasticity"], ...]

  class PublicTaskProjection(FrozenModel):
      task_id: UUID
      row_version: PositiveInt
      status: TaskViewStatus
      public_code: str | None
      attempt_count: NonNegativeInt
      planning_run_id: UUID | None
      updated_at: datetime

  class PublicPlanningRunProjection(FrozenModel):
      planning_run_id: UUID
      state: Literal["review_required"]
      source_pack_id: UUID
      source_pack_version: PositiveInt
      policy_version: Literal["m3a-policy-v1"]
      source_snapshot_date: date

  class ComparisonDimensionProjection(FrozenModel):
      key: str
      outcome: str
      reason_code: str

  class CostProjection(FrozenModel):
      source_currency: Literal["AUD"]
      tuition_minor: NonNegativeInt
      living_minor: NonNegativeInt
      fx_rate: Decimal
      cny_total_minor: PositiveInt
      fx_source: str
      fx_date: date

  class RankingProjection(FrozenModel):
      ranking_system: str
      rank: PositiveInt
      publication_year: PositiveInt

  class EvidenceDisclosure(FrozenModel):
      claim: str
      role: str
      publisher: str
      institution: str
      snapshot_date: date
      authority: Literal["accepted_synthetic_demo"]
      limitation: str
      known_gaps: tuple[str, ...]

  class AdvisorRouteProjection(FrozenModel):
      route_id: UUID
      country: Country
      outcome: RouteOutcome
      reason_code: str
      eligible: bool
      dimensions: tuple[ComparisonDimensionProjection, ...]
      cost: CostProjection | None
      ranking: RankingProjection | None
      required_claims: tuple[str, ...]
      known_gaps: tuple[str, ...]

  class RiskAcceptanceOption(FrozenModel):
      evidence_id: UUID
      kind: EvidenceRiskKind
      reason: str

  class AdvisorReviewInputs(FrozenModel):
      planning_run_id: UUID
      expected_case_revision: PositiveInt
      eligible_route_ids: tuple[UUID, ...]
      risk_acceptance_options: tuple[RiskAcceptanceOption, ...]

  class PublicRecoveryProjection(FrozenModel):
      code: str
      retry_allowed: bool
      guidance: str

  class AdvisorLedgerV1(FrozenModel):
      schema_version: Literal[1] = 1
      proof_mode: Literal["synthetic-demo"]
      phase: DemoPhase
      case_id: UUID
      case_revision: PositiveInt
      case_state: str
      canonical_task_inputs: CanonicalDemoTaskInputs | None
      task: PublicTaskProjection | None
      planning_run: PublicPlanningRunProjection | None
      routes: tuple[AdvisorRouteProjection, ...]
      evidence: tuple[EvidenceDisclosure, ...]
      review_inputs: AdvisorReviewInputs | None
      current_brief_id: UUID | None
      recovery: PublicRecoveryProjection | None

  class CurrentDecisionBriefV1(FrozenModel):
      schema_version: Literal[1] = 1
      proof_mode: Literal["synthetic-demo"]
      phase: Literal[DemoPhase.FAMILY_REVIEW, DemoPhase.PLAN_READY]
      case_id: UUID
      brief_id: UUID
      brief_version: PositiveInt
      source_snapshot_date: date
      family_safe_projection: DecisionBriefProjection
      decision_requirements: FamilyDecisionRequirements
      receipt: DecisionReceiptProjection | None
      timeline: TimelinePlan | None
  ```

  `EvidenceDisclosure` does not expose an Evidence ID. IDs required for an
  explicit review mutation appear only in `RiskAcceptanceOption`. The phase
  validator must enforce the approved availability matrix, including
  `receipt/timeline is None` for `family-review` and both present for
  `plan-ready`.

- [ ] **Step 4: Implement the server-owned fixture resolver**

  Move the connected Case constant into `identity/demo_seed.py`, keep the script
  import-compatible, and return an internal contract that includes the manifest
  hash but never exposes it as client authority:

  ```python
  CONNECTED_DEMO_CASE_ID = UUID("40000000-0000-0000-0000-000000000002")

  @dataclass(frozen=True, slots=True)
  class CanonicalDemoSourceContract:
      source_pack_id: UUID
      source_pack_version: int
      manifest_sha256: str
      policy_version: Literal["m3a-policy-v1"]

  def resolve_canonical_demo_source_contract() -> CanonicalDemoSourceContract:
      fixture = validate_planning_fixture()
      pack = fixture.planning_input.source_pack
      return CanonicalDemoSourceContract(
          source_pack_id=pack.pack_id,
          source_pack_version=pack.version,
          manifest_sha256=fixture.manifest_sha256,
          policy_version=POLICY_VERSION,
      )
  ```

  Tests must mutate the manifest/hash/version/policy and prove fail-closed
  validation rather than caller-selected fallback.

- [ ] **Step 5: Re-run focused tests and commit**

  Run:

  ```bash
  uv run pytest tests/architecture/test_m5_contract.py tests/unit/connected_demo tests/unit/identity/test_m3b_seed.py tests/unit/tasks/test_m4a_seed_proof.py -q
  uv run ruff check src/night_voyager/connected_demo src/night_voyager/identity/demo_seed.py scripts/seed_demo.py tests/architecture/test_m5_contract.py tests/unit/connected_demo
  uv run pyright src/night_voyager/connected_demo src/night_voyager/identity/demo_seed.py scripts/seed_demo.py
  ```

  Expected: all focused tests pass, Ruff passes, and Pyright reports zero errors.

  Commit:

  ```bash
  git add src/night_voyager/connected_demo src/night_voyager/identity/demo_seed.py scripts/seed_demo.py tests/architecture/test_m5_contract.py tests/unit/connected_demo tests/unit/identity/test_m3b_seed.py tests/unit/tasks/test_m4a_seed_proof.py
  git commit -m "feat: 冻结 M5 connected demo 合同"
  ```

### Task 2: Add read-only application ports and PostgreSQL projections

**Files:**
- Create: `src/night_voyager/connected_demo/ports.py`
- Create: `src/night_voyager/connected_demo/application.py`
- Create: `src/night_voyager/connected_demo/postgres.py`
- Create: `tests/unit/connected_demo/test_application.py`
- Create: `tests/integration/connected_demo/test_postgres_read_models.py`
- Modify: `scripts/seed_demo.py`
- Modify: `tests/integration/identity/test_m4a_task_seed.py`

**Interfaces:**
- Consumes: `ActorContext`, canonical source contract, existing forced-RLS rows,
  `project_task_status()`, existing Brief/receipt/timeline models, and the three
  stable synthetic actors.
- Produces: `ConnectedDemoRepository`, `ConnectedDemoService.advisor_ledger()`,
  `ConnectedDemoService.current_decision_brief()`, and
  `PostgresConnectedDemoRepository`; all methods are read-only.

- [ ] **Step 1: Write fake-port and real PostgreSQL RED tests**

  Freeze these signatures:

  ```python
  class ConnectedDemoRepository(Protocol):
      async def advisor_ledger(
          self, context: ActorContext, case_id: UUID,
          source: CanonicalDemoSourceContract,
      ) -> AdvisorLedgerV1 | None: ...

      async def current_decision_brief(
          self, context: ActorContext, case_id: UUID,
      ) -> CurrentDecisionBriefV1 | None: ...

  class ConnectedDemoService:
      async def advisor_ledger(
          self, context: ActorContext, case_id: UUID,
      ) -> AdvisorLedgerV1 | None: ...

      async def current_decision_brief(
          self, context: ActorContext, case_id: UUID,
      ) -> CurrentDecisionBriefV1 | None: ...
  ```

  Real-role tests must cover task-ready, active task, review-required,
  family-review, plan-ready, terminal failure, source-contract mismatch, stale
  task/run pins, second tenant, unassigned/wrong role, missing context, no
  forbidden fields, pool cleanup, and unchanged catalog/grants.

- [ ] **Step 2: Run RED without weakening the database gate**

  Run:

  ```bash
  uv run pytest tests/unit/connected_demo/test_application.py -q
  make db-check
  ```

  Expected: the unit test fails for missing ports/service and the database lane
  fails collecting the new read-model integration test.

- [ ] **Step 3: Extend only the explicit synthetic seed**

  Make the task-ready Case idempotently receive all three existing participants:

  ```python
  await connection.execute(
      text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
      {
          "org": DEMO_ORG,
          "case": CONNECTED_DEMO_CASE_ID,
          "advisor": ACTORS[0][1],
          "student": ACTORS[1][1],
          "parent": ACTORS[2][1],
      },
  )
  ```

  Keep migration code seed-free and do not reset retained task/run/decision rows.

- [ ] **Step 4: Implement the read-only repository and phase projection**

  Use short transaction-scoped reads under the resolved API actor context. Query
  the Case/participant first, verify the exact source-pack row and manifest hash,
  then load only the rows required by the current phase. The implementation must:

  ```python
  if source_row is None or source_row.manifest_sha256 != source.manifest_sha256:
      raise DemoContractUnavailableError("canonical demo source contract unavailable")

  if task_row is not None and (
      task_row.source_pack_id != source.source_pack_id
      or task_row.source_pack_version != source.source_pack_version
      or task_row.policy_version != source.policy_version
  ):
      raise DemoContractUnavailableError("persisted task pins do not match canonical inputs")
  ```

  Build `decision_requirements` from the pinned Brief run, Australia cost row,
  Case revision hard ceiling, and the existing M3B-required trade-off. Validate
  `pinned_cost_minor <= hard_ceiling_minor`; return a redacted contract error on
  impossible/stale facts. Never read from `scripts/verify_*` or client fixtures.

- [ ] **Step 5: Prove runtime-role and authority behavior GREEN**

  Run:

  ```bash
  uv run pytest tests/unit/connected_demo -q
  make db-check
  ```

  Expected: focused unit tests pass; the database lane proves all six phases,
  two tenants, exact pins, decision requirements, forced RLS, no new DDL/grants,
  repeated seed, and `0004 -> 0003 -> 0004` plus `0004 -> 0001 -> 0004`.

- [ ] **Step 6: Commit the application/database slice**

  ```bash
  git add src/night_voyager/connected_demo scripts/seed_demo.py tests/unit/connected_demo/test_application.py tests/integration/connected_demo/test_postgres_read_models.py tests/integration/identity/test_m4a_task_seed.py
  git commit -m "feat: 添加 M5 role-scoped read models"
  ```

### Task 3: Expose the two FastAPI read endpoints

**Files:**
- Create: `src/night_voyager/interfaces/http/connected_demo.py`
- Create: `tests/integration/connected_demo/test_http_read_models.py`
- Modify: `src/night_voyager/api.py`
- Modify: `tests/unit/test_api.py`
- Modify: `docs/reference/http-api-v1.md`

**Interfaces:**
- Consumes: existing opaque session resolution, transaction-local
  `ActorContext`, `ConnectedDemoService`, and the common RFC 9457 problem helper.
- Produces: exactly the two approved `GET /api/v1/cases/{case_id}/*` endpoints,
  schema version 1, `Cache-Control: no-store`, non-enumerating `404`, and redacted
  `503 demo_contract_unavailable` for canonical/persisted authority mismatch.

- [ ] **Step 1: Write real FastAPI/PostgreSQL failing tests**

  Test the exact response keys, phase-specific absence, role matrix, assignment,
  tenant isolation, invalid UUID, stale pins, family decision requirements,
  forbidden-field absence, and headers. The current Brief read must remain
  available to assigned advisor/student/parent; Ledger remains advisor-only.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest tests/integration/connected_demo/test_http_read_models.py -q
  ```

  Expected: both routes return `404` because the router is absent.

- [ ] **Step 3: Implement a narrow read-only router**

  Use this route shape and the existing session resolver:

  ```python
  @router.get("/cases/{case_id}/advisor-ledger", response_model=AdvisorLedgerV1)
  async def advisor_ledger(case_id: UUID, response: Response, raw_session: str | None = Cookie(...)):
      async with session_factory() as session, session.begin():
          context = await read_context(session, raw_session)
          projection = await ConnectedDemoService(
              PostgresConnectedDemoRepository(session)
          ).advisor_ledger(context, case_id)
      if projection is None:
          return problem(404, "resource_unavailable", "resource unavailable")
      response.headers["Cache-Control"] = "no-store"
      return projection
  ```

  Implement the current Brief route with the same transaction/session pattern.
  Do not accept organization, actor, role, source-pack, policy, task, run, Brief,
  receipt, or timeline IDs from query/body fields.

- [ ] **Step 4: Run HTTP and regression GREEN**

  ```bash
  make db-check
  uv run pytest tests/unit/test_api.py tests/unit/identity tests/unit/tasks -q
  uv run ruff check src/night_voyager/interfaces/http/connected_demo.py src/night_voyager/api.py tests/integration/connected_demo
  uv run pyright src/night_voyager/interfaces/http/connected_demo.py src/night_voyager/api.py
  ```

  Expected: the new HTTP tests and existing identity/task/decision regressions pass.

- [ ] **Step 5: Commit the HTTP slice**

  ```bash
  git add src/night_voyager/interfaces/http/connected_demo.py src/night_voyager/api.py tests/integration/connected_demo/test_http_read_models.py tests/unit/test_api.py docs/reference/http-api-v1.md
  git commit -m "feat: 暴露 M5 connected demo read API"
  ```

### Task 4: Add the explicit transport-only Next.js BFF

**Files:**
- Create: `web/lib/demo-bff/config.ts`
- Create: `web/lib/demo-bff/problem.ts`
- Create: `web/lib/demo-bff/transport.ts`
- Create: `web/tests/unit/demo-bff.test.ts`
- Create: `web/app/api/demo/session-bootstrap/route.ts`
- Create: `web/app/api/demo/sessions/route.ts`
- Create: `web/app/api/demo/session/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/advisor-ledger/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/agent-tasks/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/advisor-reviews/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/current-decision-brief/route.ts`
- Create: `web/app/api/demo/tasks/[taskId]/route.ts`
- Create: `web/app/api/demo/tasks/[taskId]/cancel/route.ts`
- Create: `web/app/api/demo/tasks/[taskId]/events/route.ts`
- Create: `web/app/api/demo/decision-briefs/[briefId]/family-decisions/route.ts`
- Modify: `web/vitest.config.ts`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `tests/architecture/test_compose_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`

**Interfaces:**
- Consumes: Web `Request`/`Response`, Next.js 16 Promise-based dynamic params,
  Node 24 `Headers.getSetCookie()`, fixed server environment, and existing
  FastAPI routes.
- Produces: `loadDemoBffConfig()`, `forwardDemoJson()`, `forwardDemoSse()`,
  `requireCanonicalUuid()`, and eleven fixed Route Handlers.

- [ ] **Step 1: Write transport security RED tests**

  In a Node Vitest environment, cover exact method/path mapping, Promise params,
  invalid UUID before fetch, no catch-all, 32 KiB stream bound, media type,
  request/response header allowlists, fixed Origin, CSRF/idempotency, no caller
  upstream, unchanged FastAPI problem status/body, exact
  `bff_upstream_unavailable`/`bff_upstream_timeout` redaction, abort propagation,
  SSE byte identity, cursor precedence, and separate cookies.

  ```ts
  it("forwards every Set-Cookie field separately", async () => {
    const upstreamHeaders = new Headers();
    upstreamHeaders.append("Set-Cookie", "night_voyager_session=a; Path=/; HttpOnly");
    upstreamHeaders.append("Set-Cookie", "night_voyager_csrf_bootstrap=; Max-Age=0; Path=/");
    mockFetch(new Response("{}", { status: 201, headers: upstreamHeaders }));
    const response = await forwardDemoJson(request("POST"), route("/api/v1/demo/sessions"));
    expect(response.headers.getSetCookie()).toEqual(upstreamHeaders.getSetCookie());
  });
  ```

- [ ] **Step 2: Run RED**

  ```bash
  npm --prefix web ci
  npm --prefix web run test -- demo-bff
  ```

  Expected: Vitest cannot import `demo-bff/transport` or any handler.

  Update `vitest.config.ts` to include both
  `tests/unit/**/*.test.ts` and `tests/unit/**/*.test.tsx`; BFF tests use the
  `// @vitest-environment node` directive while React tests remain in jsdom.

- [ ] **Step 3: Implement fail-closed server configuration**

  ```ts
  export interface DemoBffConfig {
    apiOrigin: string;
    publicOrigin: string;
    jsonTimeoutMs: number;
    maxJsonBytes: number;
  }

  export function loadDemoBffConfig(env: NodeJS.ProcessEnv = process.env): DemoBffConfig {
    const api = new URL(requireEnv(env, "NIGHT_VOYAGER_API_INTERNAL_URL"));
    const publicUrl = new URL(requireEnv(env, "NIGHT_VOYAGER_PUBLIC_ORIGIN"));
    if (!["http:", "https:"].includes(api.protocol) || api.username || api.password || api.pathname !== "/") {
      throw new Error("invalid internal API origin");
    }
    if (publicUrl.origin !== publicUrl.href.replace(/\/$/, "")) {
      throw new Error("invalid public origin");
    }
    return { apiOrigin: api.origin, publicOrigin: publicUrl.origin, jsonTimeoutMs: 10_000, maxJsonBytes: 32 * 1024 };
  }
  ```

  Set the Compose web environment to
  `NIGHT_VOYAGER_API_INTERNAL_URL=http://api:8000` and
  `NIGHT_VOYAGER_PUBLIC_ORIGIN=http://127.0.0.1:3000`. Remove the unused
  `API_BASE_URL` name rather than supporting aliases.

- [ ] **Step 4: Implement bounded JSON and direct SSE transport**

  Read request bodies incrementally and cancel when the accumulated size exceeds
  32 KiB. Build a new allowlisted `Headers`, use the fixed public Origin for all
  identity calls and validated mutations, and copy response fields explicitly:

  ```ts
  const responseHeaders = new Headers();
  copyIfPresent(upstream.headers, responseHeaders, "Content-Type");
  copyIfPresent(upstream.headers, responseHeaders, "Cache-Control");
  for (const cookie of upstream.headers.getSetCookie()) {
    responseHeaders.append("Set-Cookie", cookie);
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
  ```

  Non-SSE fetches combine the browser abort signal with a 10-second timer. SSE
  uses only the browser signal, returns `upstream.body` directly, preserves
  `Content-Type`, `Cache-Control`, and `X-Accel-Buffering`, and never parses
  events. Map validated `after` to `Last-Event-ID` only when the inbound header is
  absent.

  Every handler exports `dynamic = "force-dynamic"`; every JSON and SSE response
  is `Cache-Control: no-store`. The transport must not forward hop-by-hop,
  `Server`, trace, debug, upstream URL, framework, or unknown headers.

- [ ] **Step 5: Add all eleven explicit handlers**

  Each dynamic handler awaits its Promise params and passes a literal upstream
  path. Example:

  ```ts
  export async function GET(
    request: Request,
    { params }: { params: Promise<{ caseId: string }> },
  ) {
    const { caseId } = await params;
    return forwardDemoJson(request, {
      method: "GET",
      upstreamPath: `/api/v1/cases/${requireCanonicalUuid(caseId)}/advisor-ledger`,
      mutation: false,
    });
  }
  ```

  No handler may accept an upstream host/path/method from request data.

- [ ] **Step 6: Run BFF GREEN and commit**

  ```bash
  npm --prefix web run test -- demo-bff
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  docker compose config --quiet
  uv run pytest tests/architecture/test_compose_contract.py tests/architecture/test_m5_contract.py -q
  ```

  Expected: transport tests pass, Next builds all fixed handlers, and Compose
  configuration resolves only the two server-owned URL settings.

  ```bash
  git add web/lib/demo-bff web/tests/unit/demo-bff.test.ts web/app/api/demo web/vitest.config.ts compose.yaml .env.example tests/architecture/test_compose_contract.py tests/architecture/test_m5_contract.py
  git commit -m "feat: 添加 M5 transport-only BFF"
  ```

### Task 5: Add the pure client state, recovery, and API layer

**Files:**
- Create: `web/lib/connected-demo/contracts.ts`
- Create: `web/lib/connected-demo/api.ts`
- Create: `web/lib/connected-demo/idempotency.ts`
- Create: `web/lib/connected-demo/reducer.ts`
- Create: `web/lib/connected-demo/session-storage.ts`
- Create: `web/lib/connected-demo/use-connected-demo.ts`
- Create: `web/tests/unit/connected-demo-reducer.test.ts`
- Create: `web/tests/unit/connected-demo-api.test.ts`
- Create: `web/tests/unit/connected-demo-recovery.test.tsx`

**Interfaces:**
- Consumes: only same-origin `/api/demo/*`, schema-version-1 read models, native
  `EventSource`, Web Crypto, and approved sessionStorage fields.
- Produces: exhaustive `DemoDisplayState`/`DemoEvent`, runtime response guards,
  `ConnectedDemoApi`, request-bound idempotency helpers, and
  `useConnectedDemo()`; none establishes business authority.

- [ ] **Step 1: Write exhaustive reducer and recovery RED tests**

  Freeze the display states:

  ```ts
  export type DemoDisplayState =
    | { value: "bootstrapping" }
    | { value: "advisor_ready"; ledger: AdvisorLedger }
    | { value: "task_creating"; ledger: AdvisorLedger }
    | { value: "task_streaming"; ledger: AdvisorLedger; taskId: string; after: number }
    | { value: "advisor_review"; ledger: AdvisorLedger }
    | { value: "review_submitting"; ledger: AdvisorLedger }
    | { value: "role_switching"; caseId: string }
    | { value: "family_review"; brief: CurrentDecisionBrief }
    | { value: "decision_submitting"; brief: CurrentDecisionBrief }
    | { value: "plan_ready"; brief: CurrentDecisionBrief }
    | { value: "recoverable_error"; code: RecoveryCode }
    | { value: "terminal_task_failure"; ledger: AdvisorLedger };

  export type DemoEvent =
    | { type: "ADVISOR_SESSION_READY"; ledger: AdvisorLedger }
    | { type: "CREATE_TASK" }
    | { type: "TASK_ACCEPTED"; taskId: string }
    | { type: "TASK_REFRESHED"; ledger: AdvisorLedger; after: number }
    | { type: "REVIEW_SUBMIT" }
    | { type: "REVIEW_ACCEPTED"; caseId: string }
    | { type: "PARENT_SESSION_READY"; brief: CurrentDecisionBrief }
    | { type: "DECISION_SUBMIT" }
    | { type: "DECISION_ACCEPTED"; brief: CurrentDecisionBrief }
    | { type: "AUTHORITATIVE_RELOAD"; ledger?: AdvisorLedger; brief?: CurrentDecisionBrief }
    | { type: "RECOVERABLE_FAILURE"; code: RecoveryCode }
    | { type: "TERMINAL_TASK"; ledger: AdvisorLedger };
  ```

  Test every legal transition and representative illegal promotion. Prove that
  missing role/CSRF metadata, mismatched role, malformed schema, hard-coded
  client budget/trade-off substitutions, session expiry, stale conflict, and
  failed advisor revoke never enable a mutation or parent presentation.
  Terminal coverage must include `needs_evidence`, `timed_out`, `failed`,
  `cancelled`, and `outdated`.

- [ ] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- connected-demo
  ```

  Expected: imports fail because the connected client modules are absent.

- [ ] **Step 3: Implement strict response guards and API calls**

  Use closed runtime guards that reject extra/missing keys and unsupported schema
  versions. `ConnectedDemoApi` must expose only:

  ```ts
  interface ConnectedDemoApi {
    bootstrap(): Promise<{ csrf_token: string }>;
    mint(role: "advisor" | "parent", csrf: string): Promise<SessionProjection>;
    revoke(csrf: string): Promise<void>;
    advisorLedger(caseId: string): Promise<AdvisorLedger>;
    createTask(caseId: string, body: CreateTaskBody, csrf: string, key: string): Promise<TaskProjection>;
    task(taskId: string): Promise<TaskProjection>;
    cancelTask(taskId: string, body: CancelTaskBody, csrf: string, key: string): Promise<TaskProjection>;
    review(caseId: string, body: AdvisorReviewBody, csrf: string, key: string): Promise<ReviewResult>;
    currentBrief(caseId: string): Promise<CurrentDecisionBrief>;
    decide(briefId: string, body: FamilyDecisionBody, csrf: string, key: string): Promise<DecisionResult>;
  }
  ```

  Bodies must be created only from server projections and explicit form input.
  Generate a Web Crypto SHA-256 fingerprint for the canonical request and store
  only `{ fingerprint, idempotencyKey }`, never the request body. An explicit
  retry of the same canonical request reuses its key; a changed request requires
  renewed confirmation before replacing the stored fingerprint/key pair.

- [ ] **Step 4: Implement recovery orchestration and SSE reconnect**

  Same-tab reload uses stored role/CSRF/case/task/brief/cursor metadata, then
  fetches the authoritative projection before enabling actions. Initial SSE uses
  `?after=<stored sequence>`; native reconnect owns subsequent
  `Last-Event-ID`. Event handlers only trigger a task/Ledger refresh; they do not
  synthesize business state.

  If recovery metadata is absent/inconsistent while reads indicate an existing
  session, set `recoverable_error` and expose no mutation. Session expiry clears
  local metadata and requires an explicit reconnect action. Never automatically
  replay a mutation after `401` or `409`.

- [ ] **Step 5: Run client GREEN and commit**

  ```bash
  npm --prefix web run test -- connected-demo
  npm --prefix web run lint
  npm --prefix web run typecheck
  ```

  Expected: reducer, API, idempotency, reload, stale, session-loss, and no-client-
  authority tests pass.

  ```bash
  git add web/lib/connected-demo web/tests/unit/connected-demo-*.test.ts web/tests/unit/connected-demo-*.test.tsx
  git commit -m "feat: 添加 M5 client recovery state"
  ```

### Task 6: Replace the fixture page with the connected advisor-to-family UI

**Files:**
- Create: `web/components/connected-demo/ConnectedDemo.tsx`
- Create: `web/components/connected-demo/AdvisorLedger.tsx`
- Create: `web/components/connected-demo/TaskProgress.tsx`
- Create: `web/components/connected-demo/EvidenceDisclosure.tsx`
- Create: `web/components/connected-demo/FamilyDecisionBrief.tsx`
- Create: `web/components/connected-demo/DecisionReceiptTimeline.tsx`
- Create: `web/components/connected-demo/RecoveryNotice.tsx`
- Create: `web/tests/unit/connected-demo-ui.test.tsx`
- Modify: `web/app/demo/page.tsx`
- Modify: `web/app/styles.css`
- Modify: `web/tests/unit/design-contract.test.tsx`

**Interfaces:**
- Consumes: `useConnectedDemo()`, server route/Evidence/review/decision
  projections, and the existing M1 design tokens.
- Produces: one connected six-beat `/demo` with one primary action per phase,
  real advisor-to-parent rotation, persistent receipt/timeline, and responsive
  accessible presentation.

- [ ] **Step 1: Rewrite the fixture expectations as connected RED tests**

  Mock only the same-origin BFF responses. Test task-ready, active task,
  review-required, family-review, plan-ready, terminal failure, Malaysia blocked,
  Evidence disclosure, confirmation summaries, disabled reasons, advisor revoke
  failure, missing recovery metadata, stale refresh, and role-specific content.

  ```tsx
  expect(screen.getByRole("heading", { name: /Advisor Ledger/i })).toBeVisible();
  expect(screen.getByRole("button", { name: /Create planning task/i })).toBeEnabled();
  expect(screen.getByRole("button", { name: /Choose Malaysia/i })).toBeDisabled();
  expect(screen.queryByText(/lease owner|organization_id|reviewer notes/i)).toBeNull();
  ```

- [ ] **Step 2: Run RED against the disconnected M1 page**

  ```bash
  npm --prefix web run test -- connected-demo-ui design-contract
  ```

  Expected: tests fail because `/demo` still renders static Japan fixture frames
  and no real actions.

- [ ] **Step 3: Implement the advisor phases**

  Preserve `Advisor Ledger x Global Journey`, semantic table/mobile switcher,
  first-screen lifecycle stage, Evidence disclosure, blocked Malaysia row, and
  secondary task trail. Render costs, rankings, eligibility, pins, review inputs,
  and task status only from the Ledger response. Advisor approval must show the
  exact server-selected Australia route and required risk choices before submit.

- [ ] **Step 4: Implement real role rotation and family phases**

  On approved `family-review` or retained `plan-ready`, the single action runs:

  ```ts
  await api.revoke(advisorCsrf);
  clearAdvisorSessionStorage();
  const bootstrap = await api.bootstrap();
  const parent = await api.mint("parent", bootstrap.csrf_token);
  storeSessionMetadata({ role: "parent", csrf: parent.csrf_token, caseId });
  const brief = await api.currentBrief(caseId);
  ```

  Stop immediately on revoke failure. The family form displays the server-derived
  pinned cost, hard ceiling, CNY currency, and required trade-offs. It may prefill
  the pinned cost as the minimum and hard ceiling as the maximum, but submission
  requires explicit confirmation. Persistent receipt/timeline replaces the form
  after success.

- [ ] **Step 5: Complete responsive and accessibility behavior**

  Preserve semantic landmarks/table, 44 px targets, visible focus, reduced
  motion, live-region status announcements, reading order, disabled reasons, and
  no horizontal overflow at 1440, 768, and 390 px. Do not add cards, KPI strips,
  chat, control tower, remote fonts, or automatic approval.

- [ ] **Step 6: Run frontend GREEN and commit**

  ```bash
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  ```

  Expected: all Vitest suites pass and Next production build includes `/demo` and
  the explicit `/api/demo/*` handlers.

  ```bash
  git add web/app/demo/page.tsx web/app/styles.css web/components/connected-demo web/tests/unit/connected-demo-ui.test.tsx web/tests/unit/design-contract.test.tsx
  git commit -m "feat: 连接 M5 advisor-to-family demo"
  ```

### Task 7: Add the real Compose Playwright golden flow

**Files:**
- Create: `web/e2e/connected-demo.spec.ts`
- Create: `web/playwright.compose.config.ts`
- Create: `web/Dockerfile.e2e`
- Modify: `compose.yaml`
- Modify: `scripts/verify_compose.sh`
- Modify: `tests/architecture/test_compose_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`

**Interfaces:**
- Consumes: the real Compose web/API/PostgreSQL/migrator/demo-seed/worker stack,
  Playwright 1.58.2, and the existing required `compose` workflow job.
- Produces: a Docker-contained Chromium proof, no host Node requirement for the
  evaluator lane, full walkthrough/recovery evidence, and unchanged required
  check name `compose`.

- [ ] **Step 1: Add failing Compose/Playwright architecture tests**

  Require a profile-scoped `browser-proof` service, existing pinned Node and
  Playwright package versions, no new npm dependency, a real connected test, and
  execution inside `scripts/verify_compose.sh` before teardown.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest tests/architecture/test_compose_contract.py tests/architecture/test_m5_contract.py -q
  ```

  Expected: assertions fail because the browser-proof target and connected E2E
  file do not exist.

- [ ] **Step 3: Add a bounded browser-proof image and profile**

  `web/Dockerfile.e2e` uses root build context, a
  `node:24.18.0-bookworm-slim` base, the locked `npm ci`, and installs only
  Chromium for the already-locked Playwright `1.58.2`. It copies the web test
  source under `/workspace/web`, creates `/workspace/docs/assets` for an explicit
  capture run, and executes as a non-root user. The Compose service uses profile
  `browser-proof`, depends on healthy web, sets
  `PLAYWRIGHT_BASE_URL=http://web:3000`, and has no database/API credentials.

- [ ] **Step 4: Implement the real golden and negative paths**

  The Playwright test must prove:

  ```text
  advisor bootstrap/mint
  -> task create
  -> worker/SSE/reconnect
  -> review-required Ledger
  -> Australia advisor approval
  -> advisor revoke
  -> parent bootstrap/mint
  -> family-safe Brief
  -> server-derived budget/trade-off confirmation
  -> family decision
  -> persistent DecisionReceipt/TimelinePlan
  -> page reload persistence
  ```

  In the same run, prove wrong-role denial, Malaysia disabled, stale/idempotency
  recovery, `Last-Event-ID`, keyboard flow, landmarks/live regions, and zero
  horizontal overflow at 1440, 768, and 390 px.

- [ ] **Step 5: Integrate without inventing a hosted check name**

  Extend the existing `make compose-proof` path through
  `scripts/verify_compose.sh` to run the profile-scoped browser proof after the
  M3B/M4A/restart probes. The existing GitHub workflow already invokes that
  command in the `compose` job and needs no edit. Keep its `if: always()`
  `make down` step and do not add another required context before a successful
  hosted run.

- [ ] **Step 6: Run the full real proof and commit**

  ```bash
  make doctor MODE=dev
  make compose-proof
  make down
  docker compose ps --all
  ```

  Expected: all services/probes/browser steps pass, and the final Compose listing
  is empty.

  ```bash
  git add web/e2e/connected-demo.spec.ts web/playwright.compose.config.ts web/Dockerfile.e2e compose.yaml scripts/verify_compose.sh tests/architecture/test_compose_contract.py tests/architecture/test_m5_contract.py
  git commit -m "test: 证明 M5 browser-to-database flow"
  ```

### Task 8: Update public documentation and capture real connected screenshots

**Files:**
- Create: `docs/operations/connected-demo.md`
- Create: `docs/assets/m5-advisor-ledger.png`
- Create: `docs/assets/m5-family-receipt-timeline.png`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `DESIGN.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/operations/worker-and-sse.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `docs/design/route-map.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `tests/architecture/test_m5_contract.py`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: the verified real connected flow and two Playwright capture points.
- Produces: public-neutral evaluator/runbook/reference/design material and two
  screenshots that depict actual synthetic behavior.

- [ ] **Step 1: Add documentation/screenshot RED assertions**

  Require the bilingual entry points to identify M5 as implemented, link the
  connected runbook, reference exactly two screenshots, preserve synthetic/local
  limits, and remove stale “fixture-only `/demo`” current-state claims. Require
  PNG signatures and public-hygiene scan coverage without asserting unstable
  pixel hashes.

- [ ] **Step 2: Run documentation RED**

  ```bash
  uv run pytest tests/architecture/test_m5_contract.py -q
  ```

  Expected: failures identify stale docs and missing screenshot files.

- [ ] **Step 3: Capture screenshots from the real Compose flow**

  Run the explicit capture mode only after the real browser proof is GREEN. Keep
  the capture container until both files have been copied, then remove it:

  ```bash
  docker compose --profile browser-proof run --name night-voyager-m5-capture -e UPDATE_M5_SCREENSHOTS=1 browser-proof npm run test:e2e -- --config playwright.compose.config.ts --grep "connected golden flow"
  docker cp night-voyager-m5-capture:/workspace/docs/assets/m5-advisor-ledger.png docs/assets/m5-advisor-ledger.png
  docker cp night-voyager-m5-capture:/workspace/docs/assets/m5-family-receipt-timeline.png docs/assets/m5-family-receipt-timeline.png
  docker rm night-voyager-m5-capture
  ```

  Capture the 1440 px Advisor Ledger after `review-required` and the parent
  receipt/timeline after `plan-ready`. Inspect both images visually before
  staging; reject private paths, IDs outside the public synthetic contract,
  debug panels, browser chrome, secrets, or fixture-only Japan claims.

- [ ] **Step 4: Update documents to actual behavior**

  Document the exact two read endpoints, eleven BFF routes, fixed Origin and
  cookie semantics, six phases, role rotation, same-tab recovery boundary,
  server-derived decision requirements, SSE reconnect, protected reset, Compose
  proof, and public claim limits. Preserve M1 as historical design context while
  making connected Australia the current `/demo` story.

- [ ] **Step 5: Run docs/release GREEN and commit**

  ```bash
  uv run pytest tests/architecture/test_m5_contract.py -q
  uv run python scripts/verify_release.py --tree-mode development
  git diff --check
  ```

  Expected: docs and screenshot contracts pass, the public-hygiene scan accepts
  the complete tree, and the diff has no whitespace errors.

  ```bash
  git add README.md README_CN.md CONTRIBUTING.md DESIGN.md docs/README.md docs/reference/http-api-v1.md docs/operations/connected-demo.md docs/operations/worker-and-sse.md docs/design/demo-storyboard.md docs/design/projection-matrix.md docs/design/route-map.md docs/design/state-and-interaction-matrix.md docs/assets/m5-advisor-ledger.png docs/assets/m5-family-receipt-timeline.png tests/architecture/test_m5_contract.py scripts/verify_release.py
  git commit -m "docs: 完成 M5 connected demo 证据"
  ```

### Task 9: Fresh verification, authority self-review, and local closeout

**Files:**
- Review: every path changed from the implementation branch merge base.
- Modify only: files required to fix evidence-backed findings discovered in this
  closeout.

**Interfaces:**
- Consumes: all M5 task commits.
- Produces: a clean local branch/worktree and complete evidence for independent
  authority branch-diff review; no remote side effect.

- [ ] **Step 1: Run fresh focused and non-database suites**

  ```bash
  uv lock --check
  uv run pytest tests/architecture/test_m5_contract.py tests/unit/connected_demo -q
  uv run pytest -q -m "not database and not mke"
  uv run ruff check .
  uv run pyright
  uv build --build-constraints build-constraints.txt --require-hashes
  ```

  Expected: all tests/checks pass and the constrained sdist/wheel build succeeds.

- [ ] **Step 2: Run fresh frontend gates**

  ```bash
  npm --prefix web ci
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  ```

  Expected: lint/typecheck/Vitest/build all pass with no dependency or lock drift.

- [ ] **Step 3: Run database, proof, and browser gates serially**

  ```bash
  make doctor MODE=dev
  make db-check
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  ```

  Expected: database/currentness/RLS gates, installed-wheel proof, M3B/M4A
  regressions, connected Playwright flow, restart/recovery, and teardown all pass;
  no project container remains.

- [ ] **Step 4: Review the complete branch diff**

  Inspect:

  ```bash
  git diff --check "$(git merge-base HEAD origin/main)"..HEAD
  git diff --stat "$(git merge-base HEAD origin/main)"..HEAD
  git diff "$(git merge-base HEAD origin/main)"..HEAD
  ```

  Check exact scope, no migration/grant/dependency drift, no catch-all proxy,
  fixed URL/Origin, separate cookies, phase absence, no client authority,
  decision requirements, RLS/role behavior, SSE byte identity, screenshot truth,
  public claims, private paths, secrets, generated noise, and MKE/DRA/OCR/OpenClaw
  exclusion.

- [ ] **Step 5: Close findings through focused RED -> GREEN**

  For each real finding, first add or identify a regression that reaches the
  actual typed/runtime/browser path, make the minimum correction, rerun targeted
  tests, then rerun all affected fresh gates. Do not broaden architecture or add
  a migration/grant/dependency to bypass a failing proof; return to design
  authority if the approved contract cannot be satisfied.

- [ ] **Step 6: Create the final local commit and stop**

  Stage exact reviewed paths, create one coherent follow-up commit only when
  needed, and verify:

  ```bash
  git status --short
  git log --oneline "$(git merge-base HEAD origin/main)"..HEAD
  docker compose ps --all
  ```

  Expected: clean worktree, ordered local commits, and no running project
  containers. Report branch/worktree, base/HEAD, complete diff, RED -> GREEN,
  actual commands, documentation impact, remaining risk, and deferred work.
  Stop without push, PR, merge, tag, release, deployment, Dependabot work, or
  branch/worktree cleanup.

## Plan Self-Review Checklist

- [x] Every approved spec section maps to at least one task and one verification
  obligation.
- [x] The plan contains no unresolved placeholder token, deferred implementation, guessed
  required check, or unstated interface.
- [x] Python and TypeScript type names remain consistent across tasks.
- [x] Exactly two FastAPI read endpoints and eleven explicit BFF handlers exist.
- [x] No migration, table, grant, dependency, UI framework, remote provider, or
  product-path MKE work enters the plan.
- [x] Pre-task source authority, post-task pin consistency, decision requirements,
  fixed Origin, separate cookies, role rotation, recovery metadata, SSE, and
  idempotency each have a real test path.
- [x] The final evidence supports only a local synthetic connected demo, not
  production adoption, real users, business outcomes, SLA, or distributed HA.
