# DRA Governed Mixed-Evidence Closure Implementation Plan

**Implementation status:** Complete. PR #26 delivered governed candidate import and
atomic human promotion; PR #27 delivered deterministic governed mixed planning. The
closure was released in v0.1.1. Live provider proof was not run. The unchecked tasks
below preserve the original approved implementation recipe rather than current progress.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> to implement this plan task-by-task in an isolated worktree. Every behavioral,
> authority, migration, transport, and proof slice follows test-first RED -> GREEN.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consume one released DRA canonical result as an immutable untrusted
candidate, atomically bind one assigned-advisor attestation to one promoted
`externally_verified australia_program_fit` Evidence reference, and close the
existing durable planning -> AdvisorReview -> family-decision workflow with an
exact synthetic baseline for every other fact.

**Architecture:** PR 1 adds a strict DRA v1 projection, optional loopback-only
transport, immutable candidate ledger, and one PostgreSQL authority function
that records the human decision and approve-time source-pack promotion in the
same transaction. After PR 1 is merged and hosted-verified, PR 2 adds the closed
`generate_governed_mixed_planning_run_v1` operation, a PostgreSQL-backed trusted
materializer, and routing through the existing AgentTask lease/retry/fencing/SSE
and AdvisorReview/family workflow. Required CI stays deterministic and offline;
live provider proof remains a separately authorized operation.

**Tech Stack:** Python 3.12.13, Pydantic 2.13.4, FastAPI 0.139.0,
Starlette 1.3.1, SQLAlchemy 2.0.51 async, asyncpg 0.31.0, PostgreSQL
18.4, httpx2 2.5.0 as an optional `dra` extra, Alembic, pytest 9,
Docker Compose, and the existing Night Voyager worker/SSE runtime.

## Global Constraints

- Begin from the latest clean `main` that contains the approved public spec
  and this implementation plan. Use a short-lived `codex/` branch in an
  isolated linked worktree.
- Public target paths are
  `docs/superpowers/specs/2026-07-15-dra-governed-mixed-evidence-closure-design.md`
  and
  `docs/superpowers/plans/2026-07-15-dra-governed-mixed-evidence-closure.md`.
- The design pins Night Voyager `v0.1.0` release commit
  `af24ca64599aa07765042120aeef271057363df1`, but implementation begins from
  the then-current clean `main` after the docs-only contract landing. Re-query
  and record the actual implementation base before editing.
- Pin DRA `v0.1.3`, commit
  `87b2a8e335385eb865086f7a69fe2b190567cfa2`, fixture schema
  `dra.downstream-consumer.v1`, and fixture SHA-256
  `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157`.
- Pin the M3A baseline to policy `m3a-policy-v1`, source-pack
  `50000000-0000-0000-0000-000000000001` version `1`, fixture file SHA-256
  `5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25`,
  and canonical manifest SHA-256
  `84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28`.
- The only external mapping is
  `australia_program_fit -> program_fit -> externally_verified`. External
  Evidence never supplies tuition, living cost, FX, ranking, eligibility, or
  intake availability.
- Human verification and approve-time promotion are one PostgreSQL transaction
  and one immutable audit row. There is no separate promotion table or later
  promotion command.
- Candidate import has zero source-pack, Evidence, task, PlanningRun,
  AdvisorReview, Brief, receipt, timeline, or Case-transition side effects.
- Approval creates exactly one derived source-pack revision and exactly one
  externally verified Evidence reference. Rejection creates neither.
- Caller-facing `EvidenceRef` continues to reject `externally_verified`.
  Trusted external Evidence is materialized only from the database join between
  an approved verification row, its promoted source entry, and its promoted
  Evidence row.
- Preserve `generate_planning_run_v1` as the all-synthetic operation. The new
  operation is exactly `generate_governed_mixed_planning_run_v1`; do not add a
  generic persisted-input planning operation or source-fact platform.
- Preserve the existing PostgreSQL tenant context, forced RLS, API/worker role
  separation, AgentTask lease/retry/fencing/events/SSE, PlanningRun finalization,
  AdvisorReview, FamilyDecision, receipt, and timeline authorities.
- Use a separate explicit synthetic DRA proof Case. Do not reuse, reset, or
  reinterpret the M5 connected-demo Case. Migrations remain seed-free.
- Required tests and `make check` must not need DRA runtime, network access,
  provider credentials, or a live model. The optional live command must fail
  closed unless its separate authorization acknowledgement and exact inputs are
  present.
- Do not modify DRA runtime, API, schema, profile, Evidence, canonical result,
  or release. Do not parse Markdown into typed domain facts.
- Do not add browser/BFF routes or change `/demo`. Do not add MKE, OCR,
  OpenClaw, a second queue/workflow engine, production tenancy, deployment,
  release, tag, or SLA work.
- Use the installed Pydantic/FastAPI/SQLAlchemy/asyncpg/httpx2 versions. Before
  code changes, record `uv run python` version output and re-check official
  documentation for Pydantic strict/frozen validators, SQLAlchemy async
  transaction framing, FastAPI request/error behavior, and the actual httpx2
  client API. Do not use `model_construct()` to bypass validation.
- Keep all public files, fixtures, logs, errors, commit messages, and PR content
  public-neutral. Never persist or print credentials, cookies, CSRF values,
  canonical Markdown, snippets, source bytes, raw exceptions, tracebacks,
  provider payloads, local paths, or token/cost data.
- PR titles use concise English Conventional Commit style. PR bodies use
  Simplified Chinese with English headings `Summary`, `Completion`,
  `Verification`, `Scope`, `Risk / Impact`, and `Documentation impact`.
- PR 2 starts only after PR 1 is squash-merged, hosted required checks pass,
  local `main` is fast-forwarded to `origin/main`, and the PR 2 worktree is
  created from that exact merged commit. Do not use an unmerged stack.

## Delivery Sequence

1. Mechanically land the approved spec and this plan in a docs-only branch;
   verify byte equality with the approved sources and obtain independent diff
   review.
2. Implement PR 1 — governed candidate and atomic promotion — and stop at a
   clean local branch for authority review.
3. After explicit publish/merge authorization, merge PR 1 and verify hosted
   `python`, `frontend`, and `compose` checks from the successful run.
4. Create a fresh PR 2 worktree from merged `main`; implement the governed
   mixed-planning closure and stop at a clean local branch for authority review.
5. Live provider execution remains outside both implementation PRs.

---

## PR 1 — Governed Candidate and Atomic Promotion

### Task 1: Freeze the strict DRA v1 projection and deterministic fixture

**Files:**
- Create: `src/night_voyager/dra/__init__.py`
- Create: `src/night_voyager/dra/models.py`
- Create: `src/night_voyager/dra/fixtures.py`
- Create: `fixtures/dra/downstream-consumer-contract-v1.json`
- Create: `fixtures/dra/manifest.json`
- Create: `fixtures/dra/sources/australia-program-fit.html`
- Create: `tests/contracts/test_dra_v1_contract.py`
- Create: `tests/unit/dra/__init__.py`
- Create: `tests/unit/dra/test_models.py`
- Create: `tests/unit/dra/test_fixtures.py`
- Create: `tests/architecture/test_dra_contract.py`

**Interfaces:**
- Consumes: the released DRA fixture and the exact DRA/M3A pins in Global
  Constraints.
- Produces: `DraProducerPinV1`, `DraRunRequestIdentityV1`,
  `DraRunAcceptanceV1`, `DraRunProjectionV1`, `DraEvidenceProjectionV1`,
  `DraCanonicalArtifactInputV1`, `DraCandidateImportV1`,
  `DraResearchCandidateV1`, `SourceAttestationV1`,
  `VerificationDecisionV1`, `load_dra_fixture()`, and
  `build_fixture_candidate_import()`.

- [ ] **Step 1: Write failing strict-contract tests**

  Assert exact producer pins, canonical-ready disposition, the six-field
  Evidence allowlist, nullable upstream source URLs, public HTTPS
  URL/no-userinfo rules for non-null URLs, rejection of localhost, loopback,
  private, link-local, and unspecified hosts, unique ordered Evidence IDs,
  canonical artifact identity, 1 MiB bound, exact UTF-8 byte length/hash,
  and rejection of fallback/review/blocked/failed/unavailable/unsafe/unknown
  states. Assert a nullable Evidence URL remains a valid upstream projection but
  cannot be selected for promotion. Assert additive upstream fields are
  discarded before strict candidate construction and never appear in
  `model_dump()`.

  ```python
  def test_canonical_artifact_hashes_exact_utf8_bytes() -> None:
      content = "# Synthetic Research Report\n\nPublic-safe contract proof."
      artifact = DraCanonicalArtifactInputV1(
          artifact_id="research-report.md",
          kind="research_report_markdown",
          media_type="text/markdown",
          content=content,
          content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
      )
      assert artifact.byte_length == len(content.encode("utf-8"))

  def test_external_authority_is_not_a_candidate_input() -> None:
      with pytest.raises(ValidationError):
          DraResearchCandidateV1.model_validate(
              {**candidate_payload(), "authority": "externally_verified"}
          )
  ```

- [ ] **Step 2: Run focused tests and record RED**

  Run:

  ```bash
  uv run pytest tests/contracts/test_dra_v1_contract.py tests/unit/dra \
    tests/architecture/test_dra_contract.py -q
  ```

  Expected: collection fails because `night_voyager.dra` and the fixture files
  do not exist.

- [ ] **Step 3: Implement the strict public and persistence models**

  Use `ConfigDict(frozen=True, extra="forbid")`, bounded strings, and explicit
  validators. Keep the artifact content only in the import DTO; the persisted
  candidate stores only identity, byte length, and hash.

  ```python
  DRA_RELEASE = "v0.1.3"
  DRA_COMMIT = "87b2a8e335385eb865086f7a69fe2b190567cfa2"
  DRA_CONTRACT_SCHEMA = "dra.downstream-consumer.v1"
  MAX_ARTIFACT_BYTES = 1024 * 1024

  # Pure validation only: reject localhost/local suffixes and require any IP
  # literal to be globally routable. Do not resolve DNS or fetch the URL.
  def is_public_source_host(host: str) -> bool:
      normalized = host.rstrip(".").lower()
      if (
          normalized == "localhost"
          or normalized.endswith(".localhost")
          or normalized.endswith(".local")
      ):
          return False
      literal = normalized.removeprefix("[").removesuffix("]")
      try:
          return ipaddress.ip_address(literal).is_global
      except ValueError:
          return "." in normalized

  class DraEvidenceProjectionV1(FrozenModel):
      evidence_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
      source_url: HttpUrl | None
      source_identity: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
      retrieved_at: AwareDatetime
      citation_status: Literal["cited"]
      verification_status: Literal["verified", "unverified"]

      @model_validator(mode="after")
      def exact_public_identity(self) -> Self:
          if self.source_url is None:
              return self
          url = str(self.source_url)
          if (
              self.source_url.scheme != "https"
              or self.source_url.username is not None
              or self.source_url.password is not None
              or not is_public_source_host(self.source_url.host)
          ):
              raise ValueError("dra_source_url_invalid")
          if self.source_identity != url:
              raise ValueError("dra_source_identity_mismatch")
          return self

  class DraCanonicalArtifactInputV1(FrozenModel):
      artifact_id: Literal["research-report.md"]
      kind: Literal["research_report_markdown"]
      media_type: Literal["text/markdown"]
      content: Annotated[str, StringConstraints(min_length=1)]
      content_hash: Sha256

      @computed_field
      @property
      def byte_length(self) -> int:
          return len(self.content.encode("utf-8"))

      @model_validator(mode="after")
      def exact_bytes(self) -> Self:
          encoded = self.content.encode("utf-8")
          if len(encoded) > MAX_ARTIFACT_BYTES:
              raise ValueError("dra_artifact_oversize")
          if hashlib.sha256(encoded).hexdigest() != self.content_hash:
              raise ValueError("dra_artifact_hash_mismatch")
          return self
  ```

  Candidate construction may retain nullable upstream Evidence for immutable
  reconciliation. `build_fixture_candidate_import()` and the promotion request
  must select exactly one Evidence row whose URL is non-null public HTTPS and
  whose `source_identity` equals that URL; no later layer may repair or infer a
  missing URL.

  `DraCandidateImportV1` must carry `expected_case_revision`, exact producer
  pins, bounded request identity, exact run/acceptance identity, artifact input,
  and ordered Evidence. `DraResearchCandidateV1` must replace artifact content
  with `artifact_byte_length`, preserve only the six allowlisted Evidence
  fields, and force `authority: Literal["untrusted_candidate"]`.

- [ ] **Step 4: Copy and lock the upstream fixture**

  Copy the exact DRA fixture bytes into
  `fixtures/dra/downstream-consumer-contract-v1.json`. Create a Night
  Voyager-owned `fixtures/dra/manifest.json` that records all producer pins,
  upstream fixture SHA, accepted case `canonical_ready`, every expected
  disposition, the exact M3A baseline pins, and the local synthetic source
  snapshot SHA/byte length.

  `load_dra_fixture()` must read only repository-owned paths, check the raw file
  SHA before JSON parsing, select the supported fields, validate the strict
  projection, and return the canonical import DTO plus deterministic negative
  dispositions. No arbitrary path argument is accepted.

- [ ] **Step 5: Run focused GREEN and commit**

  Run:

  ```bash
  uv run pytest tests/contracts/test_dra_v1_contract.py tests/unit/dra \
    tests/architecture/test_dra_contract.py -q
  uv run ruff check src/night_voyager/dra tests/contracts/test_dra_v1_contract.py \
    tests/unit/dra tests/architecture/test_dra_contract.py
  uv run pyright src/night_voyager/dra tests/contracts/test_dra_v1_contract.py \
    tests/unit/dra tests/architecture/test_dra_contract.py
  git diff --check
  ```

  Expected: all focused tests pass; Ruff, Pyright, and diff check pass.

  Commit exact paths:

  ```bash
  git add src/night_voyager/dra fixtures/dra tests/contracts/test_dra_v1_contract.py \
    tests/unit/dra tests/architecture/test_dra_contract.py
  git commit -m "feat: 冻结 DRA governed consumer 合同"
  ```

### Task 2: Add the optional loopback DRA transport and keyed reconciliation

**Files:**
- Create: `src/night_voyager/dra/reconciliation.py`
- Create: `src/night_voyager/adapters/dra_readonly.py`
- Create: `tests/contracts/test_dra_reconciliation.py`
- Create: `tests/contracts/test_dra_transport.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: `DraCandidateImportV1`, `DraRunRequestIdentityV1`, exact DRA REST
  paths, `DECISION_RESEARCH_AGENT_API_KEY`, a high-entropy keyed-create value,
  fixed polling interval, and fixed total deadline.
- Produces: `DraClientConfig`, `DraTransport`, `Httpx2DraTransport`,
  `DraRunReconciler`, `DraTransportError`, and `DraReconciliationRequired`.

- [ ] **Step 1: Write transport and reconciliation RED tests**

  Cover loopback-only URL acceptance, path/query/fragment/userinfo rejection,
  `trust_env=False`, `follow_redirects=False`, bounded response reads, API key
  from environment only, no key in repr/output, one keyed replay after an
  ambiguous first response, exact identity equality on replay, conflict,
  invalid/unavailable key handling, fixed polling, client deadline without
  server cancellation, and no provider retry.

  ```python
  @pytest.mark.parametrize(
      "url",
      (
          "https://example.com",
          "http://127.0.0.1:8000/path",
          "http://user@127.0.0.1:8000",
          "http://127.0.0.1:8000?x=1",
      ),
  )
  def test_dra_base_url_is_loopback_origin_only(url: str) -> None:
      with pytest.raises(ValueError, match="dra_base_url_invalid"):
          DraClientConfig(base_url=url, poll_seconds=1, deadline_seconds=30)

  async def test_lost_ack_replays_once_with_same_key_and_request() -> None:
      transport = FakeTransport([AmbiguousOutcome(), replayed()])
      acceptance = await DraRunReconciler(transport).create(request(), "key-12345678")
      assert acceptance.idempotent_replay is True
      assert transport.create_calls == [(request(), "key-12345678")] * 2
  ```

- [ ] **Step 2: Run focused tests and record RED**

  ```bash
  uv run pytest tests/contracts/test_dra_reconciliation.py \
    tests/contracts/test_dra_transport.py -q
  ```

  Expected: collection fails because reconciliation and transport modules do
  not exist.

- [ ] **Step 3: Implement pure reconciliation and optional HTTP transport**

  Add exact optional dependency:

  ```toml
  [project.optional-dependencies]
  dra = ["httpx2>=2.5,<2.6"]
  mke = ["mcp>=1.28.1,<2"]
  ```

  The transport creates `httpx2.AsyncClient(base_url=..., trust_env=False,
  follow_redirects=False, timeout=...)`, sends `X-API-Key` only when the
  environment value is non-empty, and exposes only bounded decoded JSON or
  exact artifact bytes. The client never logs URLs with query values, response
  bodies, credentials, or raw exceptions.

  `DraRunReconciler.create()` may replay exactly once only after an ambiguous
  transport outcome. The replay must return the same `thread_id`, `run_id`, and
  `segment_id`; otherwise raise `DraReconciliationRequired`. Polling stops at
  the fixed deadline and never calls a cancel endpoint.

- [ ] **Step 4: Lock dependency and release-verifier expectations**

  Run `uv lock`, then make `verify_release.py` require the exact optional
  `dra` range and locked `httpx2==2.5.0` while preserving the exact MKE optional
  contract. Assert the default installed-wheel proof still imports
  `night_voyager` without importing `httpx2`.

- [ ] **Step 5: Run GREEN and commit**

  ```bash
  uv lock --check
  uv run pytest tests/contracts/test_dra_reconciliation.py \
    tests/contracts/test_dra_transport.py tests/unit/test_release_surface.py -q
  uv run ruff check src/night_voyager/dra/reconciliation.py \
    src/night_voyager/adapters/dra_readonly.py tests/contracts/test_dra_reconciliation.py \
    tests/contracts/test_dra_transport.py scripts/verify_release.py
  uv run pyright src/night_voyager/dra/reconciliation.py \
    src/night_voyager/adapters/dra_readonly.py tests/contracts/test_dra_reconciliation.py \
    tests/contracts/test_dra_transport.py
  git diff --check
  ```

  ```bash
  git add pyproject.toml uv.lock scripts/verify_release.py \
    src/night_voyager/dra/reconciliation.py src/night_voyager/adapters/dra_readonly.py \
    tests/contracts/test_dra_reconciliation.py tests/contracts/test_dra_transport.py
  git commit -m "feat: 添加 bounded DRA keyed transport"
  ```

### Task 3: Add candidate and attestation application contracts

**Files:**
- Create: `src/night_voyager/dra/errors.py`
- Create: `src/night_voyager/dra/ports.py`
- Create: `src/night_voyager/dra/application.py`
- Create: `tests/unit/dra/test_application.py`

**Interfaces:**
- Consumes: `ActorContext`, `DraCandidateImportV1`,
  `DraResearchCandidateV1`, `SourceAttestationV1`, existing canonical request
  hashing, and server-side UUID factories.
- Produces: `ImportDraCandidateCommand`, `VerifyDraCandidateCommand`,
  `DraCandidateViewV1`, `DraVerificationViewV1`, `DraCandidateRepository`,
  `DraCandidateService`, and typed authorization/conflict errors.

- [ ] **Step 1: Write application RED tests**

  Cover advisor-only import/read/decision, server-generated candidate and
  decision identities, artifact content discarded before repository call,
  exact request hashing, source attestation approve/reject shape, required
  `applicant_eligibility` and `intake_availability` gaps, exact claim/role/
  authority constants, same-key replay, and non-enumerating authorization.

  ```python
  async def test_import_discards_markdown_before_persistence() -> None:
      repository = RecordingDraRepository()
      result = await DraCandidateService(repository, id_factory=fixed_candidate_id).import_candidate(
          advisor_context(), import_command(), "import-key-123"
      )
      assert result.candidate_id == fixed_candidate_id()
      assert repository.imported.artifact_content is None
      assert repository.imported.artifact_sha256 == expected_artifact_sha256

  def test_reject_forbids_source_attestation() -> None:
      with pytest.raises(ValidationError):
          VerifyDraCandidateCommand(
              candidate_id=CANDIDATE_ID,
              expected_case_revision=1,
              dra_evidence_id="ev-1",
              decision="reject",
              reason="source does not support the bounded claim",
              source_attestation=attestation(),
          )
  ```

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/dra/test_application.py -q
  ```

  Expected: imports fail because the application contracts do not exist.

- [ ] **Step 3: Implement the service boundary**

  The repository protocol is exact:

  ```python
  class DraCandidateRepository(Protocol):
      async def import_candidate(
          self,
          context: ActorContext,
          command: ImportDraCandidateCommand,
          candidate_id: UUID,
          idempotency_key: str,
      ) -> DraCandidateViewV1: ...

      async def get_candidate(
          self, context: ActorContext, case_id: UUID, candidate_id: UUID
      ) -> DraCandidateViewV1 | None: ...

      async def verify_and_promote(
          self,
          context: ActorContext,
          command: VerifyDraCandidateCommand,
          identities: PromotionIdentities,
          idempotency_key: str,
      ) -> DraVerificationViewV1: ...
  ```

  `PromotionIdentities` is built server-side with UUIDv5 from the decision ID,
  candidate ID, selected DRA Evidence ID, and claim. It contains the verification
  ID, external source-entry ID, promoted external Evidence ID, and one new
  Evidence ID for each copied baseline claim. Request bodies never contain these
  IDs.

- [ ] **Step 4: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/dra/test_application.py tests/unit/dra/test_models.py -q
  uv run ruff check src/night_voyager/dra tests/unit/dra
  uv run pyright src/night_voyager/dra tests/unit/dra
  git diff --check
  ```

  ```bash
  git add src/night_voyager/dra/errors.py src/night_voyager/dra/ports.py \
    src/night_voyager/dra/application.py tests/unit/dra/test_application.py
  git commit -m "feat: 添加 DRA candidate 应用边界"
  ```

### Task 4: Add migration 0005 and the atomic verification/promotion authority

**Files:**
- Create: `migrations/versions/0005_dra_candidate_promotion.py`
- Create: `tests/security/test_dra_catalog.py`
- Create: `tests/integration/dra/__init__.py`
- Create: `tests/integration/dra/test_postgres_candidate_promotion.py`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `scripts/verify_release.py`
- Modify: `scripts/run_db_tests.sh`

**Interfaces:**
- Consumes: M3A/M3B tables, `app.idempotency_records`, actor context,
  deterministic server-side UUIDs, and exact baseline pins.
- Produces: `app.dra_research_candidates`,
  `app.external_evidence_verifications`,
  `app.import_dra_research_candidate(...)`, and
  `app.verify_and_promote_dra_candidate(...)`.

- [ ] **Step 1: Write static migration/catalog RED tests**

  Assert graph `0004 -> 0005`, exactly two new tenant tables, forced RLS,
  immutable triggers, migrator ownership, no direct runtime DML, fixed search
  path, PUBLIC revoke, API-only execute, worker no execute, approved/rejected
  row-shape checks, partial uniqueness for one approved claim per exact Case
  revision, and `evidence_refs.authority` expansion to the three exact values.

  ```python
  TABLES = ("dra_research_candidates", "external_evidence_verifications")

  def test_0005_has_one_atomic_promotion_function() -> None:
      source = migration_source()
      assert source.count("CREATE FUNCTION app.verify_and_promote_dra_candidate") == 1
      assert "external_evidence_promotions" not in source
      assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in source
      assert "TO night_voyager_api" in execute_grant(source)
      assert "night_voyager_worker" not in execute_grant(source)
  ```

- [ ] **Step 2: Run static RED**

  ```bash
  uv run pytest tests/security/test_dra_catalog.py \
    tests/security/test_database_catalog.py -q
  ```

  Expected: migration `0005` and the two authority tables/functions are absent.

- [ ] **Step 3: Define the two exact tables**

  `dra_research_candidates` stores only bounded identities/hashes, ordered
  Evidence JSON, creator, and timestamp. It excludes artifact content, snippets,
  credentials, trace/checkpoint fields, provider payloads, token/cost fields,
  and paths.

  `external_evidence_verifications` stores the terminal decision, candidate/
  Case/actor/source binding, fixed claim/role/authority, approve-only source
  metadata, exact baseline pins, and approve-only promoted identities. Enforce:

  ```sql
  CHECK (claim = 'australia_program_fit'),
  CHECK (evidence_role = 'program_fit'),
  CHECK (authority = 'externally_verified'),
  CHECK (redistribution_class IS NULL OR redistribution_class = 'link_only'),
  CHECK (evidence_class IS NULL OR evidence_class IN ('institutional','government')),
  CHECK (
    (decision = 'approve' AND source_sha256 IS NOT NULL
      AND promoted_source_pack_version IS NOT NULL
      AND promoted_source_entry_id IS NOT NULL
      AND promoted_evidence_id IS NOT NULL)
    OR
    (decision = 'reject' AND source_sha256 IS NULL
      AND promoted_source_pack_version IS NULL
      AND promoted_source_entry_id IS NULL
      AND promoted_evidence_id IS NULL)
  )
  ```

  Add a unique terminal mapping key on `(organization_id, candidate_id,
  dra_evidence_id)` and a partial unique index on `(organization_id, case_id,
  case_revision, claim) WHERE decision='approve'`.

- [ ] **Step 4: Implement candidate import with zero authority side effects**

  `app.import_dra_research_candidate` validates exact actor context, assigned
  advisor, current Case/revision/state `planning`, candidate pins, hashes,
  request identity, and idempotency. Same key/same request returns the original
  candidate; same key/different request raises `NV008`. It inserts only the
  candidate and the existing idempotency row.

- [ ] **Step 5: Implement the one atomic verification/promotion function**

  Use one `SECURITY DEFINER` function with the exact decision, source metadata,
  baseline pins, request/key hashes, and server-generated identities. Inside one
  transaction it must:

  1. verify tenant/actor/assigned-advisor context and lock the current Case;
  2. verify candidate/Case/revision/producer/request/Evidence/source identity;
  3. replay or conflict through `app.idempotency_records`;
  4. for `reject`, insert one terminal row and one idempotency row, then return;
  5. for `approve`, lock the exact baseline source pack, verify both baseline
     hashes, and lock the one-approval-per-Case-revision key;
  6. allocate the next version of the same baseline pack ID;
  7. copy baseline entries, removing only `australia_program_fit` from the
     Australia synthetic entry coverage;
  8. copy every baseline synthetic Evidence except the old synthetic
     `australia_program_fit`, using the server-generated deterministic IDs;
  9. insert one link-only external entry whose coverage is exactly
     `["australia_program_fit"]` and whose known gaps include
     `applicant_eligibility` and `intake_availability`;
  10. insert one `externally_verified` Evidence row linked to that entry;
  11. insert the approve verification row with foreign keys to the actual pack,
      entry, and Evidence rows plus the idempotency row;
  12. return only after every write succeeds.

  Use typed SQLSTATE `NV011` for a closed candidate/source/baseline contract
  mismatch and `NV012` for a concurrent or already-terminal promotion conflict.
  Preserve existing meanings for `NV003`, `NV006`, `NV007`, and `NV008`.

  Use savepoint/injected-failure tests at each write boundary. Any exception must
  leave candidate state unchanged and create no verification, pack revision,
  entry, Evidence, task, PlanningRun, or Case transition.

- [ ] **Step 6: Run real PostgreSQL RED -> GREEN tests**

  Add runtime-role tests for assigned advisor, wrong role, unassigned actor,
  second tenant, missing context, stale Case, source mismatch, hash/path/metadata
  failure, reject, approve, same-key replay, conflicting replay, concurrent
  approvals, direct DML denial, caller/API/worker inability to insert external
  Evidence, pool cleanup, and transaction rollback.

  Run:

  ```bash
  make db-check
  ```

  Expected GREEN: the DRA database subset passes twice on a fresh disposable
  PostgreSQL volume; `0005 -> 0004 -> 0005` and `0005 -> 0001 -> 0005` pass;
  teardown removes the isolated volume.

- [ ] **Step 7: Commit**

  ```bash
  git add migrations/versions/0005_dra_candidate_promotion.py \
    tests/security/test_dra_catalog.py tests/security/test_database_catalog.py \
    tests/integration/dra/test_postgres_candidate_promotion.py \
    tests/integration/dra/__init__.py scripts/verify_release.py scripts/run_db_tests.sh
  git commit -m "feat: 建立 DRA candidate 原子 promotion authority"
  ```

### Task 5: Expose assigned-advisor candidate and verification APIs

**Files:**
- Create: `src/night_voyager/dra/postgres.py`
- Create: `src/night_voyager/interfaces/http/dra.py`
- Create: `tests/integration/dra/test_http_dra.py`
- Modify: `src/night_voyager/api.py`
- Modify: `tests/unit/test_api.py`
- Modify: `docs/reference/http-api-v1.md`

**Interfaces:**
- Consumes: existing session/Origin/CSRF/idempotency/problem conventions,
  `DraCandidateService`, and the two 0005 functions.
- Produces: the three exact `/api/v1/cases/{case_id}/dra-candidates...` routes
  and closed public error mappings.

- [ ] **Step 1: Write HTTP and repository RED tests**

  Cover OpenAPI route presence, exact strict bodies, server-generated IDs,
  201 import, bounded GET, 201 decision, no-store, exact Origin, session-bound
  CSRF, required idempotency key, replay, wrong role 404, cross-tenant 404,
  invalid input 422, stale/conflict 409, and absence of Markdown/source bytes in
  GET or problem responses.

  ```python
  def test_dra_routes_are_exact() -> None:
      paths = create_app().openapi()["paths"]
      assert "/api/v1/cases/{case_id}/dra-candidates" in paths
      assert "/api/v1/cases/{case_id}/dra-candidates/{candidate_id}" in paths
      assert (
          "/api/v1/cases/{case_id}/dra-candidates/{candidate_id}/verification-decisions"
          in paths
      )

  async def test_import_never_returns_artifact_content(api_client) -> None:
      response = await api_client.post(...)
      assert response.status_code == 201
      assert "content" not in json.dumps(response.json()).lower()
  ```

- [ ] **Step 2: Run RED**

  ```bash
  PYTEST_ADDOPTS= uv run pytest -q tests/integration/dra/test_http_dra.py \
    tests/unit/test_api.py
  ```

  Expected: routes/repository do not exist.

- [ ] **Step 3: Implement PostgreSQL adapter and SQLSTATE mapping**

  Use the existing `AsyncSession` transaction owned by the router. Map
  `NV003` to stale conflict, `NV006`/`NV011`/`NV012` to closed contract
  conflict, `NV007` to non-enumerating authorization, `NV008` to idempotency conflict,
  and `23505`/`40001` to bounded conflict. Connection, permission, and unknown
  database failures must propagate; do not turn them into 404/409.

- [ ] **Step 4: Implement the exact FastAPI routes**

  ```python
  @router.post("/cases/{case_id}/dra-candidates", status_code=201)
  async def import_candidate(...): ...

  @router.get("/cases/{case_id}/dra-candidates/{candidate_id}")
  async def get_candidate(...): ...

  @router.post(
      "/cases/{case_id}/dra-candidates/{candidate_id}/verification-decisions",
      status_code=201,
  )
  async def verify_candidate(...): ...
  ```

  Mutations resolve `resolve_mutation_actor_context`; GET resolves
  `resolve_actor_context`. Every successful response and problem response uses
  `Cache-Control: no-store`. The router never accepts claim, evidence role,
  authority, promoted IDs, baseline pins, credentials, or a local filesystem
  path from the request.

- [ ] **Step 5: Run GREEN and commit**

  ```bash
  PYTEST_ADDOPTS= uv run pytest -q tests/integration/dra/test_http_dra.py \
    tests/unit/dra/test_application.py tests/unit/test_api.py
  uv run ruff check src/night_voyager/dra/postgres.py \
    src/night_voyager/interfaces/http/dra.py src/night_voyager/api.py \
    tests/integration/dra/test_http_dra.py tests/unit/test_api.py
  uv run pyright src/night_voyager/dra/postgres.py \
    src/night_voyager/interfaces/http/dra.py src/night_voyager/api.py \
    tests/integration/dra/test_http_dra.py
  git diff --check
  ```

  ```bash
  git add src/night_voyager/dra/postgres.py src/night_voyager/interfaces/http/dra.py \
    src/night_voyager/api.py tests/integration/dra/test_http_dra.py \
    tests/unit/test_api.py docs/reference/http-api-v1.md
  git commit -m "feat: 暴露 governed DRA candidate API"
  ```

### Task 6: Add PR 1 deterministic proof, docs, and full closeout

**Files:**
- Create: `scripts/verify_dra_consumer.py`
- Create: `scripts/run_dra_lane.sh`
- Create: `scripts/seed_dra_proof.py`
- Create: `tests/unit/dra/test_proof_controller.py`
- Create: `docs/decisions/0007-dra-governed-mixed-evidence-boundary.md`
- Create: `docs/reference/dra-governed-evidence.md`
- Create: `docs/operations/dra-consumer-proof.md`
- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/domain-and-source-manifests.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: fixture candidate import, a dedicated `DRA_PROOF_CASE_ID`, the
  candidate/verification API, and optional DRA transport.
- Produces: `make dra-check`, guarded `make dra-consumer-proof`, PR 1 public
  documentation, and deterministic candidate -> approve/reject proof.

- [ ] **Step 1: Write proof/architecture/docs RED tests**

  Assert the proof Case differs from every existing demo Case, migrations remain
  seed-free, required CI uses only the copied fixture, `make dra-check` has no
  network/credential requirement, `make dra-consumer-proof` requires the exact
  authorization acknowledgement, and docs say PR 1 implements candidate/
  promotion but not the mixed planning operation.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/dra/test_proof_controller.py \
    tests/architecture/test_dra_contract.py tests/unit/test_release_surface.py -q
  ```

  Expected: proof commands, dedicated seed, ADR, and documentation are absent.

- [ ] **Step 3: Implement deterministic and guarded live command surfaces**

  `scripts/verify_dra_consumer.py fixture` validates the copied fixture,
  candidate import contract, synthetic source snapshot, and exact pins without
  network access. `scripts/verify_dra_consumer.py live` must require:

  ```text
  DRA_LIVE_PROOF_ACK=separately-authorized-one-attempt
  DECISION_RESEARCH_AGENT_API_KEY=<environment only>
  DRA_IDEMPOTENCY_KEY=<environment only>
  DRA_BASE_URL=http://127.0.0.1:<port>
  DRA_QUERY_FILE=<approved public-safe file>
  DRA_POLL_DEADLINE_SECONDS=<approved integer>
  ```

  It performs at most one keyed create plus the single allowed lost-ack replay,
  writes canonical Markdown only to an owned temporary file for operator
  inspection, and emits only bounded IDs/hashes/statuses. It does not submit the
  advisor decision without the separately supplied source-attestation
  acknowledgement and source metadata. Failure leaves no auto-retry.

- [ ] **Step 4: Add exact Make/CI gates**

  ```make
  dra-check:
	uv run pytest -q tests/contracts/test_dra_v1_contract.py \
	  tests/contracts/test_dra_reconciliation.py tests/unit/dra \
	  tests/architecture/test_dra_contract.py
	uv run python scripts/verify_dra_consumer.py fixture --json

  dra-consumer-proof:
	uv run --extra dra python scripts/verify_dra_consumer.py live --json
  ```

  Add `$(MAKE) dra-check` to `make check` and the hosted `python` job. Do not
  add the live command to CI, Compose, `make check`, or `make proof`.

- [ ] **Step 5: Update public-neutral docs**

  ADR 0007 records the authority decision, one external allowlist, atomic
  human gate, two-PR delivery, and rejection of generic persisted planning.
  Reference/operations docs record exact models, routes, functions, roles,
  errors, fixture pins, authorization gate, and privacy boundary. README files
  describe the capability as a local mixed-evidence human-governed proof in
  progress; they do not claim the planning closure until PR 2 merges.

- [ ] **Step 6: Run full PR 1 verification**

  ```bash
  make doctor MODE=dev
  uv lock --check
  make dra-check
  make db-check
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  git diff --check "$(git merge-base HEAD origin/main)"..HEAD
  ```

  Expected: all commands pass; both default and isolated Compose projects are
  empty after teardown. Inspect the complete branch diff for unrelated changes,
  generated noise, private paths, credentials, raw provider content, and
  over-claims.

- [ ] **Step 7: Commit and stop for independent authority review**

  ```bash
  git add scripts/verify_dra_consumer.py scripts/run_dra_lane.sh \
    scripts/seed_dra_proof.py src/night_voyager/identity/demo_seed.py Makefile \
    .github/workflows/ci.yml README.md README_CN.md CONTRIBUTING.md docs \
    tests/unit/dra/test_proof_controller.py scripts/verify_release.py
  git commit -m "docs: 完成 DRA candidate promotion proof"
  git status --short
  ```

  Stop with a clean local branch/worktree. Report branch, base, HEAD, ordered
  commits, actual diff, RED/GREEN evidence, exact commands, documentation impact,
  remaining risks, and deferred work. Do not push or create a PR.

### PR 1 merge checkpoint

- [ ] The independent planning/review authority reviews the actual branch diff
  against the approved spec/plan.
- [ ] Execution fixes verified findings and reruns targeted plus full gates.
- [ ] After explicit authorization, push and create Ready PR titled
  `feat: add governed DRA candidate promotion`.
- [ ] Confirm successful hosted `python`, `frontend`, and `compose` checks from
  the actual PR run, zero unresolved review threads, clean mergeability, and the
  live `main` ruleset before squash merge.
- [ ] After explicit merge authorization, verify the merge tree equals the
  reviewed head tree, wait for post-merge checks, fast-forward local `main`, and
  safely remove only the PR 1 worktree/branch.

---

## PR 2 — Governed Mixed-Planning Closure

### Task 7: Add trusted mixed-planning types and the closed authority policy

**Files:**
- Create: `src/night_voyager/planning/trusted.py`
- Create: `src/night_voyager/planning/mixed.py`
- Create: `tests/unit/planning/test_mixed.py`
- Modify: `src/night_voyager/planning/policy.py`
- Modify: `src/night_voyager/planning/__init__.py`
- Modify: `tests/unit/planning/test_policy.py`
- Modify: `tests/contracts/test_deterministic_planning_adapter.py`

**Interfaces:**
- Consumes: exact M3A fixture/policy pins, promoted source-pack projection, and
  the approved verification relationship.
- Produces: internal-only `TrustedEvidenceRef`,
  `GovernedMixedPlanningInput`, `GovernedMixedSnapshotV1`,
  `materialize_governed_mixed_input()`, and mixed-aware
  `evaluate_planning_run()` without weakening `PlanningInput`.

- [ ] **Step 1: Write mixed-policy RED tests**

  Cover exactly one external Australia program-fit Evidence, every remaining
  baseline claim exactly once as synthetic, no external cost/FX/ranking,
  no untrusted candidate, wrong role/claim/pack/hash/coverage rejection,
  duplicate/missing claim rejection, exact baseline drift failure, and original
  all-synthetic result compatibility.

  ```python
  def test_public_evidence_ref_still_rejects_external_authority() -> None:
      with pytest.raises(ValidationError):
          EvidenceRef.model_validate(external_evidence_payload())

  def test_mixed_policy_requires_one_external_program_fit() -> None:
      result = evaluate_planning_run(governed_mixed_input())
      assert result.state is RunState.REVIEW_REQUIRED
      assert external_program_fit_id() in evidence_ids(result)

  @pytest.mark.parametrize("claim", ("australia_tuition", "australia_fx", "australia_ranking"))
  def test_external_non_program_fit_claim_fails_closed(claim: str) -> None:
      result = evaluate_planning_run(mixed_input_with_external_claim(claim))
      assert (result.state, result.reason_code) == (
          RunState.FAILED,
          "mixed_evidence_authority_invalid",
      )
  ```

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/planning/test_mixed.py tests/unit/planning/test_policy.py \
    tests/contracts/test_deterministic_planning_adapter.py -q
  ```

  Expected: trusted mixed models/materializer do not exist and current policy
  rejects all external authority.

- [ ] **Step 3: Implement separate trusted internal models**

  Keep `PlanningInput.evidence: tuple[EvidenceRef, ...]` unchanged. Define a
  separate internal model:

  ```python
  class TrustedEvidenceRef(FrozenModel):
      schema_version: Literal[1]
      organization_id: UUID
      evidence_id: UUID
      claim: str
      source_pack_id: UUID
      source_pack_version: PositiveInt
      source_entry_id: UUID
      source_sha256: Sha256
      authority: Literal[
          EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO,
          EvidenceAuthority.EXTERNALLY_VERIFIED,
      ]

  class GovernedMixedPlanningInput(FrozenModel):
      schema_version: Literal[1]
      operation: Literal["generate_governed_mixed_planning_run_v1"]
      organization_id: UUID
      case: StudentCaseRevision
      source_pack: SourcePackManifestV1
      evidence: tuple[TrustedEvidenceRef, ...]
      costs: tuple[CostEvidence, ...]
      rankings: tuple[RankingEvidence, ...]
      narrative: str | None = None
  ```

  This type is constructed only by `materialize_governed_mixed_input()` from a
  validated database snapshot. Do not export a caller-facing request model and
  do not use `model_construct()`.

- [ ] **Step 4: Implement exact baseline remapping**

  Validate the checked-in M3A fixture file/canonical manifest/policy pins, map
  promoted Evidence by exact claim, copy baseline costs/rankings, and replace
  each old Evidence ID with the promoted pack's Evidence ID for the same claim.
  The only authority change is `australia_program_fit`.

- [ ] **Step 5: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/planning/test_mixed.py tests/unit/planning/test_policy.py \
    tests/contracts/test_deterministic_planning_adapter.py -q
  uv run ruff check src/night_voyager/planning tests/unit/planning \
    tests/contracts/test_deterministic_planning_adapter.py
  uv run pyright src/night_voyager/planning tests/unit/planning \
    tests/contracts/test_deterministic_planning_adapter.py
  git diff --check
  ```

  ```bash
  git add src/night_voyager/planning/trusted.py src/night_voyager/planning/mixed.py \
    src/night_voyager/planning/policy.py src/night_voyager/planning/__init__.py \
    tests/unit/planning/test_mixed.py tests/unit/planning/test_policy.py \
    tests/contracts/test_deterministic_planning_adapter.py
  git commit -m "feat: 添加 governed mixed Evidence policy"
  ```

### Task 8: Add migration 0006 and the worker-only mixed snapshot boundary

**Files:**
- Create: `migrations/versions/0006_governed_mixed_planning.py`
- Create: `tests/security/test_dra_mixed_catalog.py`
- Create: `tests/integration/dra/test_postgres_mixed_snapshot.py`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `scripts/run_db_tests.sh`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: approved verification rows and promoted source-pack/Evidence rows
  from migration 0005.
- Produces: the additive task/adapter checks, operation-aware
  `app.create_agent_task(...)`, operation-aware `app.claim_agent_task(text)`,
  and worker-only `app.load_governed_mixed_planning_snapshot(...)`.

- [ ] **Step 1: Write migration/catalog RED tests**

  Assert graph `0005 -> 0006`, no new table, two exact task operations, two
  exact adapter identity pairs, worker execute only on the snapshot loader and
  existing fenced task functions, API execute only on task creation/cancel,
  PUBLIC revoke, fixed search paths, no verification/promotion execute for
  worker, and downgrade restoration of the PR 1 graph/contracts.

- [ ] **Step 2: Run static RED**

  ```bash
  uv run pytest tests/security/test_dra_mixed_catalog.py \
    tests/security/test_database_catalog.py -q
  ```

  Expected: `0006`, mixed operation checks, and snapshot function are absent.

- [ ] **Step 3: Implement operation and execution audit constraints**

  Replace the task operation check with exactly:

  ```sql
  CHECK (operation IN (
    'generate_planning_run_v1',
    'generate_governed_mixed_planning_run_v1'
  ))
  ```

  Replace execution adapter checks with exact pairs:

  ```sql
  CHECK (
    (adapter_id='deterministic_planning' AND adapter_version='m4a-v1') OR
    (adapter_id='governed_mixed_planning' AND adapter_version='dra-mixed-v1')
  )
  ```

  The replacement `create_agent_task` accepts `p_operation`, preserves existing
  idempotency/current Case/participant/effective-task checks, and for the mixed
  operation additionally requires an approved verification row whose promoted
  pack ID/version and Case revision exactly match. It creates no planning result.

  The replacement `claim_agent_task` preserves lease/reclaim/attempt behavior
  byte-for-byte except selecting the adapter identity pair from the task
  operation when inserting `agent_executions`.

- [ ] **Step 4: Implement the bounded worker-only snapshot function**

  `app.load_governed_mixed_planning_snapshot(p_org,p_case,p_revision,p_pack,
  p_pack_version,p_policy)` must require worker tenant context, current Case in
  `planning`, policy `m3a-policy-v1`, one approved verification row, one exact
  external Evidence, all expected synthetic claims, and foreign-key-consistent
  pack/entry/Evidence hashes. It returns bounded JSON containing only Case
  revision data, source-pack entries, Evidence rows, and verification linkage.
  It excludes candidate Evidence metadata, Markdown, source bytes, credentials,
  actor display data, idempotency keys, and provider state.

- [ ] **Step 5: Run PostgreSQL RED -> GREEN and migration cycles**

  ```bash
  make db-check
  ```

  Expected GREEN: mixed snapshot succeeds only for the approved pack; stale,
  cross-tenant, wrong-role, mutated external Evidence, external cost/ranking,
  wrong baseline, and missing verification fail closed. `0006 -> 0005 -> 0006`
  and `0006 -> 0001 -> 0006` pass with exact grants restored.

- [ ] **Step 6: Commit**

  ```bash
  git add migrations/versions/0006_governed_mixed_planning.py \
    tests/security/test_dra_mixed_catalog.py \
    tests/integration/dra/test_postgres_mixed_snapshot.py \
    tests/security/test_database_catalog.py scripts/run_db_tests.sh \
    scripts/verify_release.py
  git commit -m "feat: 添加 governed mixed planning 数据库边界"
  ```

### Task 9: Route the new operation through the existing durable worker

**Files:**
- Create: `src/night_voyager/planning/mixed_postgres.py`
- Create: `src/night_voyager/adapters/governed_mixed_planning.py`
- Create: `src/night_voyager/adapters/router.py`
- Create: `tests/contracts/test_governed_mixed_planning_adapter.py`
- Modify: `src/night_voyager/adapters/protocols.py`
- Modify: `src/night_voyager/tasks/policy.py`
- Modify: `src/night_voyager/tasks/worker.py`
- Modify: `src/night_voyager/tasks/postgres.py`
- Modify: `src/night_voyager/worker.py`
- Modify: `tests/unit/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_worker_authority.py`

**Interfaces:**
- Consumes: `GovernedMixedSnapshotV1`, the worker-only snapshot function, exact
  task pins, and existing `TaskWorker`.
- Produces: `PostgresMixedPlanningRepository`,
  `GovernedMixedPlanningAdapter`, `PlanningAdapterRouter`, mixed payload
  validation, and unchanged worker lease/finalization behavior.

- [ ] **Step 1: Write adapter/router/worker RED tests**

  Cover exact routing by operation, unknown operation failure, database snapshot
  read, materializer pins, mixed adapter identity, payload size/schema limits,
  external Evidence mutation failure, original deterministic adapter unchanged,
  retry/fencing/heartbeat/lease-loss behavior, and worker inability to invoke
  candidate import or promotion functions.

  ```python
  async def test_router_selects_only_the_mixed_adapter_for_mixed_operation() -> None:
      router = PlanningAdapterRouter(synthetic=synthetic_spy, mixed=mixed_spy)
      await router.generate(mixed_request())
      assert mixed_spy.calls == [mixed_request()]
      assert synthetic_spy.calls == []

  async def test_mixed_adapter_rejects_mutated_external_evidence() -> None:
      outcome = await adapter_with_snapshot(mutated_external_hash()).generate(mixed_request())
      assert outcome == AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
  ```

- [ ] **Step 2: Run RED**

  ```bash
  PYTEST_ADDOPTS= uv run pytest -q \
    tests/contracts/test_governed_mixed_planning_adapter.py \
    tests/unit/tasks/test_worker.py tests/integration/tasks/test_worker.py \
    tests/integration/tasks/test_worker_authority.py
  ```

  Expected: mixed adapter/router and operation literals are absent.

- [ ] **Step 3: Extend exact protocol types without weakening pair validation**

  `PlanningAdapterRequest.operation` becomes the two-value literal. Adapter
  payload identity becomes a validated exact pair; `deterministic_planning` may
  only use `m4a-v1`, and `governed_mixed_planning` may only use `dra-mixed-v1`.

  `validate_adapter_payload()` selects `PlanningInput` only for the original
  operation and `GovernedMixedPlanningInput` only for the mixed operation. A
  cross-operation payload returns `invalid_schema` or `fallback_authority`, not
  a coerced success.

- [ ] **Step 4: Implement database materializer adapter and router**

  `PostgresMixedPlanningRepository.load()` calls only the worker snapshot
  function under a worker transaction. `GovernedMixedPlanningAdapter.generate()`
  validates exact request pins, loads one snapshot, calls the pure materializer,
  and returns strict JSON bytes. It never calls DRA or reads an operator file.

  `worker.run()` constructs:

  ```python
  adapter = PlanningAdapterRouter(
      synthetic=DeterministicPlanningAdapter(),
      mixed=GovernedMixedPlanningAdapter(
          session_factory=create_session_factory(engine)
      ),
  )
  ```

  No second worker, queue, dispatch table, retry policy, event stream, or
  finalization transaction is added.

- [ ] **Step 5: Run GREEN and commit**

  ```bash
  PYTEST_ADDOPTS= uv run pytest -q \
    tests/contracts/test_governed_mixed_planning_adapter.py \
    tests/contracts/test_deterministic_planning_adapter.py \
    tests/unit/tasks/test_worker.py tests/integration/tasks/test_worker.py \
    tests/integration/tasks/test_worker_authority.py
  uv run ruff check src/night_voyager/adapters src/night_voyager/planning \
    src/night_voyager/tasks src/night_voyager/worker.py tests/contracts \
    tests/unit/tasks tests/integration/tasks
  uv run pyright src/night_voyager/adapters src/night_voyager/planning \
    src/night_voyager/tasks src/night_voyager/worker.py tests/contracts \
    tests/unit/tasks tests/integration/tasks
  git diff --check
  ```

  ```bash
  git add src/night_voyager/planning/mixed_postgres.py \
    src/night_voyager/adapters/governed_mixed_planning.py \
    src/night_voyager/adapters/router.py src/night_voyager/adapters/protocols.py \
    src/night_voyager/tasks/policy.py src/night_voyager/tasks/worker.py \
    src/night_voyager/tasks/postgres.py src/night_voyager/worker.py \
    tests/contracts/test_governed_mixed_planning_adapter.py \
    tests/unit/tasks/test_worker.py tests/integration/tasks/test_worker.py \
    tests/integration/tasks/test_worker_authority.py
  git commit -m "feat: 接通 governed mixed AgentTask worker"
  ```

### Task 10: Expose mixed task creation without changing candidate authority

**Files:**
- Modify: `src/night_voyager/tasks/models.py`
- Modify: `src/night_voyager/tasks/application.py`
- Modify: `src/night_voyager/tasks/postgres.py`
- Modify: `src/night_voyager/interfaces/http/tasks.py`
- Modify: `tests/unit/tasks/test_application.py`
- Modify: `tests/integration/tasks/test_http_tasks.py`
- Modify: `tests/integration/tasks/test_postgres_tasks.py`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/reference/http-api-v1.md`

**Interfaces:**
- Consumes: approved promoted pack identity, exact current Case revision, and
  the operation-aware 0006 function.
- Produces: additive request support for
  `generate_governed_mixed_planning_run_v1` through the existing task endpoint.

- [ ] **Step 1: Write task API/persistence RED tests**

  Cover mixed task creation only after promotion, exact Case/revision/pack/policy
  pins, assigned advisor, same-key replay, conflict, stale promotion, synthetic
  operation compatibility, no task on candidate import/promotion, and identical
  GET/cancel/SSE response shapes.

- [ ] **Step 2: Run RED**

  ```bash
  PYTEST_ADDOPTS= uv run pytest -q tests/unit/tasks/test_application.py \
    tests/integration/tasks/test_http_tasks.py \
    tests/integration/tasks/test_postgres_tasks.py
  ```

  Expected: request/command models reject the new operation and repository uses
  the old function signature.

- [ ] **Step 3: Extend the existing command and repository call**

  ```python
  type PlanningOperation = Literal[
      "generate_planning_run_v1",
      "generate_governed_mixed_planning_run_v1",
  ]

  class CreateTaskCommand(FrozenModel):
      case_id: UUID
      operation: PlanningOperation
      expected_case_revision: PositiveInt
      source_pack_id: UUID
      source_pack_version: PositiveInt
      policy_version: Literal["m3a-policy-v1"] = "m3a-policy-v1"
  ```

  Pass `operation` into `app.create_agent_task`. Keep all existing response,
  status projection, cancel, SSE, and non-enumeration behavior unchanged.

- [ ] **Step 4: Run GREEN and commit**

  ```bash
  PYTEST_ADDOPTS= uv run pytest -q tests/unit/tasks/test_application.py \
    tests/integration/tasks/test_http_tasks.py \
    tests/integration/tasks/test_postgres_tasks.py
  uv run ruff check src/night_voyager/tasks src/night_voyager/interfaces/http/tasks.py \
    tests/unit/tasks/test_application.py tests/integration/tasks
  uv run pyright src/night_voyager/tasks src/night_voyager/interfaces/http/tasks.py \
    tests/unit/tasks/test_application.py tests/integration/tasks
  git diff --check
  ```

  ```bash
  git add src/night_voyager/tasks/models.py src/night_voyager/tasks/application.py \
    src/night_voyager/tasks/postgres.py src/night_voyager/interfaces/http/tasks.py \
    tests/unit/tasks/test_application.py tests/integration/tasks/test_http_tasks.py \
    tests/integration/tasks/test_postgres_tasks.py \
    docs/reference/agent-tasks-and-events.md docs/reference/http-api-v1.md
  git commit -m "feat: 暴露 governed mixed planning operation"
  ```

### Task 11: Prove the complete deterministic governed closure

**Files:**
- Create: `scripts/verify_dra_governed_flow.py`
- Create: `tests/integration/dra/test_governed_closure.py`
- Modify: `scripts/seed_dra_proof.py`
- Modify: `scripts/verify_dra_consumer.py`
- Modify: `scripts/verify_compose.sh`
- Modify: `scripts/run_db_tests.sh`
- Modify: `tests/integration/dra/test_http_dra.py`
- Modify: `tests/integration/decision/test_http_decision.py`
- Modify: `tests/integration/tasks/test_sse.py`

**Interfaces:**
- Consumes: dedicated proof Case, fixture candidate, advisor attestation,
  promoted pack, mixed task, worker, SSE, AdvisorReview, parent decision,
  receipt, and timeline.
- Produces: one deterministic offline PostgreSQL/Compose closure and the
  guarded full live proof path.

- [ ] **Step 1: Write end-to-end RED tests**

  Prove the exact sequence:

  ```text
  fixture canonical result
    -> candidate import (no authority side effects)
    -> assigned-advisor approve + atomic promotion
    -> mixed task create
    -> worker materializes promoted pack + exact synthetic baseline
    -> review_required PlanningRun + SSE
    -> existing advisor approval
    -> existing parent family decision
    -> receipt + timeline
  ```

  Add mutation counterfactuals: remove/change the promoted Evidence, alter its
  source hash, change authority, link it to cost/ranking, drift the M3A fixture,
  or use the synthetic operation. Every mutation must prevent the expected
  `review_required` result.

- [ ] **Step 2: Run database RED**

  ```bash
  make db-check
  ```

  Expected: mixed full-flow tests fail until the proof seed/controller and
  worker closure are connected.

- [ ] **Step 3: Implement the separate proof Case and controller**

  Seed the DRA proof Case only through `scripts/seed_dra_proof.py` under the
  existing explicit demo/proof gate. Use deterministic IDs distinct from the
  M3A canonical Case and M5 connected-demo Case. Repeated seed is idempotent.

  The deterministic controller uses the copied fixture and checked-in synthetic
  source bytes; it never calls DRA. The live controller reuses the same Night
  Voyager flow only after `DRA_LIVE_PROOF_ACK` and an additional exact
  `DRA_ADVISOR_ATTESTATION_ACK=source-inspected-for-bounded-program-fit` value.
  It validates source bytes under one declared root, refuses traversal/symlink
  escape, and never prints or persists the bytes/path.

- [ ] **Step 4: Add Compose proof without disturbing M5**

  Run `verify_dra_governed_flow.py --fixture` on the dedicated Case before the
  existing M4A/M5 browser reset lanes. Assert candidate/promotion/task/run/
  advisor/family identities persist and the existing M5 screenshots/browser
  route remain unchanged. Teardown must remove the isolated project and volume.

- [ ] **Step 5: Run GREEN**

  ```bash
  make db-check
  make compose-proof
  make down
  docker compose ps --all
  ```

  Expected: PostgreSQL suite, downgrade/re-upgrade, deterministic governed
  closure, M3B, M4A restart/SSE, M5 Chromium lanes, and teardown all pass.

- [ ] **Step 6: Commit**

  ```bash
  git add scripts/verify_dra_governed_flow.py scripts/seed_dra_proof.py \
    scripts/verify_dra_consumer.py scripts/verify_compose.sh scripts/run_db_tests.sh \
    tests/integration/dra tests/integration/decision/test_http_decision.py \
    tests/integration/tasks/test_sse.py
  git commit -m "test: 证明 DRA governed mixed decision closure"
  ```

### Task 12: Complete PR 2 documentation, release proof, and local closeout

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/README.md`
- Modify: `docs/decisions/0007-dra-governed-mixed-evidence-boundary.md`
- Modify: `docs/reference/dra-governed-evidence.md`
- Modify: `docs/reference/domain-and-source-manifests.md`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/operations/dra-consumer-proof.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/operations/worker-and-sse.md`
- Modify: `scripts/verify_release.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/architecture/test_dra_contract.py`

**Interfaces:**
- Consumes: the complete deterministic implementation and proof evidence.
- Produces: public-neutral implemented status, exact verification instructions,
  release-verifier contracts, and a clean local PR 2 branch for authority review.

- [ ] **Step 1: Write docs/release RED tests**

  Assert docs contain the exact producer/consumer pins, untrusted candidate,
  atomic human gate, one external allowlist, exact synthetic baseline, new task
  operation, original synthetic compatibility, offline/live separation,
  no-browser boundary, and non-production claims. Assert no text says DRA
  verified Night Voyager Evidence or that promotion is automatic.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/test_release_surface.py \
    tests/architecture/test_dra_contract.py -q
  ```

  Expected: PR 1 status text and release verifier do not yet describe the full
  mixed-planning closure.

- [ ] **Step 3: Update public documentation and executable proof contracts**

  Mark the deterministic governed mixed-evidence closure implemented while
  retaining `local mixed-evidence human-governed proof`. Document exact routes,
  tables/functions, task operation, roles, migration graph, commands, failure
  codes, privacy exclusions, and the fact that connected `/demo` remains the
  synthetic M5 walkthrough. Keep optional live proof unauthorized/unexecuted.

- [ ] **Step 4: Run fresh full verification**

  ```bash
  make doctor MODE=dev
  uv lock --check
  uv run pytest -q -m "not database and not mke"
  uv run ruff check .
  uv run pyright
  uv build --build-constraints build-constraints.txt --require-hashes
  npm --prefix web ci
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  make dra-check
  make db-check
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  uv run python scripts/verify_release.py --tree-mode development
  git diff --check "$(git merge-base HEAD origin/main)"..HEAD
  ```

  Expected: every command passes from the clean PR 2 branch; default and
  isolated Compose projects are empty. Record actual test counts and command
  outputs rather than copying expected counts from this plan.

- [ ] **Step 5: Perform final branch-diff authority self-review**

  Inspect every changed file against the approved spec and this plan. Confirm:

  - exactly two new authority tables from PR 1 and no PR 2 table;
  - exactly one human verification/promotion function;
  - exactly one external `australia_program_fit` Evidence;
  - exact synthetic baseline for all other facts;
  - no direct API/worker DML, automatic promotion, browser integration,
    Markdown parsing, DRA runtime import, second queue, or live provider proof;
  - no private paths, credentials, raw content, generated noise, or public claim
    beyond reproducible evidence.

- [ ] **Step 6: Commit and stop for independent authority review**

  ```bash
  git add README.md README_CN.md CONTRIBUTING.md docs scripts/verify_release.py \
    tests/unit/test_release_surface.py tests/architecture/test_dra_contract.py
  git commit -m "docs: 完成 DRA governed mixed closure"
  git status --short
  ```

  Stop with a clean local branch/worktree. Report base, branch, HEAD, ordered
  commits, full diff, RED/GREEN evidence, real PostgreSQL/Compose evidence,
  docs impact, remaining risks, and deferred live proof. Do not push or create a
  PR.

### PR 2 merge checkpoint

- [ ] The independent planning/review authority reviews the actual PR 2 branch
  diff.
- [ ] Execution verifies and fixes findings using targeted RED -> GREEN, then
  reruns the full gates above.
- [ ] After explicit authorization, push and create Ready PR titled
  `feat: close governed mixed-evidence planning`.
- [ ] Confirm successful hosted `python`, `frontend`, and `compose` checks from
  the actual PR run, zero unresolved review threads, clean mergeability, and the
  live `main` ruleset before squash merge.
- [ ] After explicit merge authorization, verify reviewed/merged tree equality,
  post-merge checks, local `main == origin/main`, clean checkout, and safe
  feature worktree/branch cleanup.

## Optional Live Evidence Change — Separately Authorized

No implementation task in PR 1 or PR 2 executes a provider-backed DRA run.
After both PRs merge, a separate authorization must pin:

- exact DRA and Night Voyager merged commits;
- loopback DRA base URL and environment-only authentication;
- provider/model configuration inside DRA;
- public-safe query file and SHA-256;
- one-attempt maximum and fixed poll deadline;
- provider cost estimate or upper bound;
- one official source snapshot and lawful link-only representation;
- advisor source-inspection acknowledgement;
- sanitized evidence report location and disclosure boundary.

The optional evidence change contains only bounded IDs, hashes, statuses,
source URL, promotion relationship, mutation result, and explicit limitations.
It contains no canonical Markdown, snippet, credential, cookie, CSRF value,
provider payload, trace/checkpoint data, source bytes, local path, raw exception,
or stack trace. A failed/fallback/review-required/blocked/unavailable/ambiguous/
unsafe/hash-mismatched attempt is recorded as failed and is not automatically
retried.

## Plan Self-Review Checklist

- [ ] Every design invariant maps to a task/test above.
- [ ] PR 1 remains useful and valid without PR 2.
- [ ] PR 2 starts only from merged PR 1 and reuses existing durable/human gates.
- [ ] Public caller models cannot assert `externally_verified`.
- [ ] Human decision and promotion cannot partially commit.
- [ ] External Evidence cannot enter cost/FX/ranking/eligibility/intake roles.
- [ ] Original all-synthetic operation remains compatible.
- [ ] Required CI remains offline and credential-free.
- [ ] No live provider run, release, or deployment is implied.
- [ ] The future public target contains no unresolved placeholder marker,
  private path, or private planning rationale.
