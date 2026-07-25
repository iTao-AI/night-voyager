# DRA v0.1.6 Live Closure PR A Implementation Plan

**Implementation status:** PR A implemented provider-free; PR B and PR C remain approved but not implemented.

> **For agentic workers:** REQUIRED PRIMARY CONTROLLER: use
> `superpowers:executing-plans`. This PR is one serial migration and contract
> authority chain; do not dispatch parallel agents. Every behavioral change follows
> test-first RED -> GREEN. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin new DRA candidate imports to immutable `v0.1.6`, strictly project the
real status/result/Evidence shapes, preserve raw source identity, and establish the
deterministic scenario and evaluation contracts used by later live-closure PRs.

**Architecture:** Migration `0010` wraps the existing candidate table and import
function with a closed two-generation producer contract: historical `v0.1.3` rows
remain readable, while every new import must use the exact `v0.1.6` tuple. Product
code separates upstream ownership-bearing envelopes from the existing six-field
consumer Evidence projection. Pure scenario, receipt, and evaluator models remain
provider-free and observe authority without creating it.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLAlchemy 2 async, asyncpg,
PostgreSQL 18, Alembic, pytest, httpx2, uv/Hatch, Docker Compose, existing Night
Voyager DRA candidate and release-verification surfaces.

## Global Constraints

- Start from the exact merged `main` selected at execution time and record it in the
  handoff. The approved design commit is an input, not permission to merge it with
  implementation history.
- PR A owns producer identity, migration `0010`, strict transport/projection,
  deterministic scenario and pure evaluation foundation only. It performs no
  provider call, live candidate import, promotion, planning, review, family decision,
  tag, release, or deployment.
- Keep `migrations/versions/0005_dra_candidate_promotion.py` byte-for-byte unchanged.
- Preserve the copied `dra.downstream-consumer.v1` fixture bytes and SHA-256
  `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157`.
- Historical producer identity remains exactly
  `v0.1.3@87b2a8e335385eb865086f7a69fe2b190567cfa2`; live identity is exactly
  `v0.1.6@7d43324b469cb5e445c2e8be83af3be4d841cf1c`, annotated tag object
  `9e0b0b443c435cf636dfce932c3c77d91d0a43e4`.
- The live transport uses `/health`, `/api/runs`, `/api/runs/{run_id}`, and
  `/api/runs/{run_id}/result`; it remains loopback-only, bounded, redirect-free, and
  `trust_env=False`.
- Required CI stays offline, deterministic, credential-free, and provider-free.
- Raw source identity is a bounded `str`; URL parsing is temporary validation only.
  No `HttpUrl`-normalized value may become persisted identity.
- Evaluation receipts contain identities, lengths, hashes, stage states, assertion
  results, cleanup facts, and non-claims only. They contain no artifact content,
  source bytes, raw provider payload, prompt, credential, cookie, token, header,
  private path, traceback, or real personal data.
- Stage explicit paths only. Before each commit run
  `git diff --cached --name-only` and `git diff --cached --check`.
- Before Docker-backed gates, record host and Docker VM free space plus project,
  container, image/cache, network, and volume inventory. Require at least
  `8,388,608 KiB` Docker VM free without override. Teardown only task-owned resources;
  retain `night-voyager_postgres-data`, shared images, and shared BuildKit cache.

## File Structure

- `migrations/versions/0010_dra_v0_1_6_live_consumer.py` — closed producer tuple,
  import-function replacement, downgrade refusal, and exact `0009` restoration.
- `src/night_voyager/dra/models.py` — closed historical/live producer identities,
  raw URL identity, and backward-compatible candidate models.
- `src/night_voyager/dra/live_models.py` — strict ownership-bearing upstream
  envelopes, frozen scenario/intent primitives, stage receipt schemas, and failure
  taxonomy.
- `src/night_voyager/dra/live_projection.py` — terminal projection, Evidence
  ownership checks, exact URL validation, unique human source selection, and
  content-free artifact identity.
- `src/night_voyager/dra/live_evaluation.py` — deterministic trajectory/outcome
  assertion models and canonical redacted report rendering.
- `src/night_voyager/adapters/dra_readonly.py` — exact public health path and
  allowlisted real status/result transport.
- `fixtures/dra/live-closure-scenario-v1.json` — versioned provider-free scenario
  referencing the immutable copied fixture and exact producer identity.
- Focused tests live under `tests/contracts/`, `tests/unit/dra/`,
  `tests/integration/dra/`, `tests/security/`, and `tests/architecture/`.

---

### Task A1: Freeze producer, scenario, and raw identity contracts

**Files:**
- Modify: `src/night_voyager/dra/models.py`
- Create: `src/night_voyager/dra/live_models.py`
- Create: `fixtures/dra/live-closure-scenario-v1.json`
- Modify: `src/night_voyager/dra/fixtures.py`
- Modify: `tests/contracts/test_dra_v1_contract.py`
- Create: `tests/contracts/test_dra_live_models.py`
- Modify: `tests/unit/dra/test_fixtures.py`
- Modify: `tests/architecture/test_dra_contract.py`

**Interfaces:**
- Produces `DraProducerPinV1`, which accepts only the exact historical or live tuple.
- Produces constants `DRA_HISTORICAL_PRODUCER` and `DRA_LIVE_PRODUCER`.
- Produces `DraLiveScenarioV1`, `DraLiveRunIntentV1`,
  `DraLiveFailurePhase`, `DraArtifactIdentityV1`, `DraSelectedEvidenceV1`,
  `DraCaptureReceiptV1`, and `DraFailureReceiptV1`.
- Produces `load_live_closure_scenario()` and
  `build_v0_1_6_scenario_candidate_import()` without mutating the copied fixture.

- [ ] **Step 1: Write failing closed-contract tests**

  Add tests that reject mixed release/commit/tag tuples, unknown producer releases,
  extra scenario fields, invalid lowercase SHA-256, duplicate stage names, receipt
  content fields, and normalized URL substitutions. Freeze the exact failure enum:

  ```python
  EXPECTED_FAILURE_PHASES = {
      "preflight_invalid",
      "producer_identity_invalid",
      "producer_unavailable",
      "run_acceptance_ambiguous",
      "run_poll_deadline_exhausted",
      "terminal_state_invalid",
      "artifact_contract_invalid",
      "evidence_ownership_invalid",
      "evidence_projection_invalid",
      "source_selection_invalid",
      "candidate_import_conflict",
      "candidate_authority_denied",
      "source_attestation_invalid",
      "promotion_conflict",
      "planning_task_conflict",
      "planning_execution_failed",
      "advisor_review_conflict",
      "family_decision_conflict",
      "outcome_projection_invalid",
      "cleanup_incomplete",
  }
  ```

  The scenario test must assert exact DRA release/commit/tag object, fixture digest,
  `profile_id=generic`, one bounded attempt, expected non-claims, and no credential or
  provider payload fields.

- [ ] **Step 2: Run focused RED**

  ```bash
  uv run pytest -q \
    tests/contracts/test_dra_v1_contract.py \
    tests/contracts/test_dra_live_models.py \
    tests/unit/dra/test_fixtures.py \
    tests/architecture/test_dra_contract.py
  ```

  Expected: collection or assertions fail because the live models, scenario, and
  closed two-generation producer identity do not exist.

- [ ] **Step 3: Implement the closed producer and scenario models**

  Keep one stored producer shape with a tuple validator rather than a free-form
  release:

  ```python
  class DraProducerPinV1(FrozenModel):
      name: Literal["decision-research-agent"] = "decision-research-agent"
      release: Literal["v0.1.3", "v0.1.6"]
      commit: Sha256
      contract_schema: Literal["dra.downstream-consumer.v1"]
      fixture_sha256: Literal[DRA_FIXTURE_SHA256]

      @model_validator(mode="after")
      def exact_supported_tuple(self) -> Self:
          if (self.release, self.commit) not in {
              ("v0.1.3", DRA_HISTORICAL_COMMIT),
              ("v0.1.6", DRA_LIVE_COMMIT),
          }:
              raise ValueError("dra_producer_identity_invalid")
          return self
  ```

  `DraLiveRunIntentV1` includes `schema_version`, `scenario_id`, `attempt_id`,
  producer including tag object, profile, bounded request identity, deadline policy,
  expected terminal contract, privacy policy, and receipt schema version. Its
  `intent_sha256` is canonical JSON with sorted keys and compact separators.

  Preserve `build_fixture_candidate_import()` as the historical fixture contract.
  Add a separate deterministic live-scenario builder that reuses the immutable
  fixture projection but replaces only the producer tuple with exact `v0.1.6`.

- [ ] **Step 4: Run focused GREEN**

  Run the Step 2 command. Expected: all tests pass and the copied fixture digest is
  unchanged.

- [ ] **Step 5: Commit the contract slice**

  ```bash
  git add \
    fixtures/dra/live-closure-scenario-v1.json \
    src/night_voyager/dra/models.py \
    src/night_voyager/dra/live_models.py \
    src/night_voyager/dra/fixtures.py \
    tests/contracts/test_dra_v1_contract.py \
    tests/contracts/test_dra_live_models.py \
    tests/unit/dra/test_fixtures.py \
    tests/architecture/test_dra_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: freeze DRA v0.1.6 live contracts"
  ```

### Task A2: Add migration `0010` producer authority

**Files:**
- Create: `migrations/versions/0010_dra_v0_1_6_live_consumer.py`
- Create: `tests/integration/dra/test_dra_live_migration.py`
- Modify: `tests/integration/dra/test_postgres_candidate_promotion.py`
- Modify: `tests/integration/tasks/test_planning_start_migration.py`
- Modify: `scripts/run_db_tests.sh`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `tests/security/test_dra_catalog.py`
- Modify: `tests/architecture/test_m4a_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`

**Interfaces:**
- Keeps the existing `app.import_dra_research_candidate(...)` SQL signature.
- Upgraded function admits only exact `v0.1.6`; table constraint permits historical
  `v0.1.3` rows and new `v0.1.6` rows.
- Downgrade refuses while any `v0.1.6` row exists and otherwise restores the exact
  `0009` function definition, owner, ACL, and historical constraint.

- [ ] **Step 1: Write migration RED tests**

  Cover:

  ```text
  0009 -> 0010 preserves an inserted v0.1.3 row
  new exact v0.1.6 import succeeds
  new v0.1.3 import fails
  every mixed tuple fails
  existing promotion still succeeds
  downgrade with v0.1.6 row refuses and remains at 0010
  empty/live-free downgrade restores exact 0009 definition and privileges
  re-upgrade restores exact 0010 definition and privileges
  ```

  Add an isolated `inside-dra-live-migration` node to `scripts/run_db_tests.sh`;
  do not weaken or delete existing database lanes. Inventory every current
  `alembic current`, `upgrade head`, downgrade, and exact-head assertion. Update
  repository-head expectations to `0010`, while tests that intentionally stop at
  `0009` must continue to say `0009`.

- [ ] **Step 2: Run focused real-PostgreSQL RED**

  ```bash
  COMPOSE_PROJECT_NAME=night-voyager-dra-live-a2-red \
    docker compose --profile db-test run --rm --build db-test \
    sh scripts/run_db_tests.sh inside-dra-live-migration
  ```

  Expected: failure because Alembic head `0010` and the isolated test file do not
  exist.

- [ ] **Step 3: Implement migration `0010`**

  Copy the exact `0009` import-function definition into a private restoration
  constant. The upgraded constraint must be equivalent to:

  ```sql
  CHECK (
    (producer_release='v0.1.3'
      AND producer_commit='87b2a8e335385eb865086f7a69fe2b190567cfa2')
    OR
    (producer_release='v0.1.6'
      AND producer_commit='7d43324b469cb5e445c2e8be83af3be4d841cf1c')
  )
  ```

  Keep schema and fixture checks exact in both branches. The upgraded import
  function rejects every tuple except exact `v0.1.6` before inserting. Downgrade
  first checks for any `v0.1.6` row and raises:

  ```text
  refusing downgrade: DRA v0.1.6 candidate history exists
  ```

  Do not update old rows and do not change promotion, RLS, table owner, grants, or
  function signature. The shared main database lane will contain a valid `v0.1.6`
  candidate after DRA tests, so its final downgrade-refusal assertion must expect the
  `0010` DRA-history refusal. Existing Skill and planning-start downgrade parity
  remains proven in their isolated projects; do not delete those lanes to make the
  main lane pass.

- [ ] **Step 4: Run migration GREEN and database security checks**

  ```bash
  COMPOSE_PROJECT_NAME=night-voyager-dra-live-a2-green \
    docker compose --profile db-test run --rm --build db-test \
    sh scripts/run_db_tests.sh inside-dra-live-migration
  uv run pytest -q \
    tests/security/test_database_catalog.py \
    tests/security/test_dra_catalog.py \
    tests/architecture/test_m4a_contract.py \
    tests/architecture/test_m5_contract.py
  ```

  Expected: isolated migration lifecycle and static authority checks pass.

- [ ] **Step 5: Commit the migration slice**

  ```bash
  git add \
    migrations/versions/0010_dra_v0_1_6_live_consumer.py \
    scripts/run_db_tests.sh \
    tests/integration/dra/test_dra_live_migration.py \
    tests/integration/dra/test_postgres_candidate_promotion.py \
    tests/integration/tasks/test_planning_start_migration.py \
    tests/security/test_database_catalog.py \
    tests/security/test_dra_catalog.py \
    tests/architecture/test_m4a_contract.py \
    tests/architecture/test_m5_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: enforce DRA v0.1.6 import authority"
  ```

### Task A3: Project real DRA status, artifact, and Evidence safely

**Files:**
- Modify: `src/night_voyager/adapters/dra_readonly.py`
- Create: `src/night_voyager/dra/live_projection.py`
- Modify: `src/night_voyager/dra/models.py`
- Modify: `tests/contracts/test_dra_transport.py`
- Create: `tests/contracts/test_dra_live_projection.py`
- Modify: `tests/contracts/test_dra_reconciliation.py`
- Modify: `tests/integration/dra/test_http_dra.py`

**Interfaces:**
- `Httpx2DraTransport.health()` calls `GET /health`.
- `get_run()` returns an ownership-bearing `DraLiveRunEnvelopeV1`.
- `get_result()` returns the strict canonical artifact envelope.
- `project_terminal_result(acceptance, run, result)` verifies accepted run/segment
  ownership before returning the six-field consumer Evidence projection.
- `select_cited_evidence(projection, declared_raw_url)` returns exactly one
  `DraSelectedEvidenceV1`.

- [ ] **Step 1: Write transport and projection RED tests**

  Add exact request-path assertions and table-driven counterexamples for:

  ```text
  nonterminal and contradictory state
  failure_cause present
  profile other than generic
  empty/oversized Evidence collection
  duplicate Evidence ID
  wrong run_id or segment_id
  unknown/wrong-typed ownership fields
  non-HTTPS, credentialed, localhost, .local, private/reserved IP
  case, slash, encoding, query, fragment, port, and punycode URL substitutions
  zero or multiple exact cited matches
  verification_status=verified not granting promotion
  artifact kind/media/length/hash/UTF-8 mismatch
  ```

  Include an explicit RED assertion that the old `/api/health` path is invalid.
  Add HTTP parsing tests proving `SourceAttestationV1.canonical_url` preserves the
  exact raw string and rejects normalization counterexamples before repository use.

- [ ] **Step 2: Run focused RED**

  ```bash
  uv run pytest -q \
    tests/contracts/test_dra_transport.py \
    tests/contracts/test_dra_live_projection.py \
    tests/contracts/test_dra_reconciliation.py
  ```

  Expected: failures for the old health path, normalized `HttpUrl` identity, missing
  ownership envelope, and missing selection function.

- [ ] **Step 3: Implement strict allowlisted transport and projection**

  The upstream Evidence model contains `evidence_id`, `run_id`, `segment_id`,
  `source_url`, `source_identity`, `retrieved_at`, `citation_status`, and
  `verification_status`. Reduce it only after:

  ```python
  if row.run_id != acceptance.run_id or row.segment_id != acceptance.segment_id:
      raise DraLiveContractError("evidence_ownership_invalid")
  ```

  Validate the raw string with `urllib.parse.urlsplit`, reject user info and unsafe
  hosts, but return and compare the original string:

  ```python
  parsed = urlsplit(raw_url)
  if parsed.scheme != "https" or parsed.hostname is None or parsed.username is not None:
      raise DraLiveContractError("source_url_invalid")
  if source_identity != raw_url:
      raise DraLiveContractError("source_identity_mismatch")
  ```

  Remove the existing automatic lost-ack replay. `DraRunReconciler.create()` returns
  acceptance once or raises `DraReconciliationRequired`; it never performs a second
  `create_run()` call. PR B will add a separately authorized exact-create
  reconciliation entry point using the frozen receipt.

- [ ] **Step 4: Run focused GREEN**

  Run the Step 2 command. Expected: all transport/projection/reconciliation tests
  pass, with raw string identity preserved byte-for-byte.

- [ ] **Step 5: Commit the projection slice**

  ```bash
  git add \
    src/night_voyager/adapters/dra_readonly.py \
    src/night_voyager/dra/models.py \
    src/night_voyager/dra/live_projection.py \
    tests/contracts/test_dra_transport.py \
    tests/contracts/test_dra_live_projection.py \
    tests/contracts/test_dra_reconciliation.py \
    tests/integration/dra/test_http_dra.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add strict DRA live projection"
  ```

### Task A4: Add deterministic evaluation foundation

**Files:**
- Create: `src/night_voyager/dra/live_evaluation.py`
- Create: `tests/unit/dra/test_live_evaluation.py`
- Modify: `tests/contracts/test_dra_live_models.py`

**Interfaces:**
- `evaluate_trajectory(scenario, receipts) -> tuple[AssertionResultV1, ...]`
- `evaluate_outcome(expected, projection) -> tuple[AssertionResultV1, ...]`
- `build_evaluation_report(...) -> DraLiveEvaluationReportV1`
- `canonical_report_bytes(report) -> bytes`
- Report schema version: `night-voyager.dra-live-evaluation.v1`.

- [ ] **Step 1: Write pure evaluator RED tests**

  Freeze stable assertion IDs for producer pin, one attempt, terminal transition,
  artifact identity, Evidence ownership/selection, candidate-before-promotion,
  explicit advisor action, promoted pack, Skill pin, task/execution/event/SSE/run,
  AdvisorReview, family decision, receipt/timeline, no auto-promotion, and no second
  provider run. Test reordered input, duplicate receipt, missing parent, forged child,
  content field, unknown assertion, and canonical JSON stability.

- [ ] **Step 2: Run focused RED**

  ```bash
  uv run pytest -q tests/unit/dra/test_live_evaluation.py \
    tests/contracts/test_dra_live_models.py
  ```

  Expected: collection fails because evaluator functions and report schema do not
  exist.

- [ ] **Step 3: Implement pure evaluation**

  Evaluators must be side-effect free. Each result has exact
  `assertion_id`, `status=passed|failed`, bounded `public_code`, and observed
  identity hashes only. Report status is derived:

  ```python
  status = "passed" if all(item.status == "passed" for item in assertions) else "failed"
  ```

  Never parse raw exceptions into reports. Reject any report payload containing
  content-bearing keys such as `content`, `body`, `prompt`, `headers`, or
  `environment`.

- [ ] **Step 4: Run focused GREEN**

  Run the Step 2 command. Expected: pure tests pass and repeated canonical renders
  are byte-identical.

- [ ] **Step 5: Commit the evaluator slice**

  ```bash
  git add \
    src/night_voyager/dra/live_evaluation.py \
    tests/unit/dra/test_live_evaluation.py \
    tests/contracts/test_dra_live_models.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add DRA live evaluation contracts"
  ```

### Task A5: Bind PR A into repository gates and documentation

**Files:**
- Modify: `Makefile`
- Modify: `scripts/run_db_tests.sh`
- Modify: `scripts/verify_release.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/architecture/test_dra_contract.py`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `tests/architecture/test_v0_1_3_release_contract.py`
- Modify: `scripts/verify_dra_governed_flow.py`
- Modify: `tests/unit/dra/test_proof_controller.py`
- Create: `docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md`
- Modify: `docs/reference/dra-governed-evidence.md`
- Modify: `docs/operations/dra-consumer-proof.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: the approved spec and this PR A plan status banner

**Interfaces:**
- `make dra-check` includes new provider-free model, transport, projection, scenario,
  and evaluator tests.
- `make db-check` includes the isolated `0010` migration lane.
- Release verifier requires one Alembic head `0010` and exact DRA live surface while
  preserving published release artifacts.

- [ ] **Step 1: Write repository-gate RED assertions**

  Assert `make dra-check` contains the new focused nodes, required CI contains only
  `make dra-check` and never the live command, database runner includes the isolated
  `0010` lane, release verifier recognizes one head `0010`, and docs state PR A is
  provider-free and not a governed-live success claim.

  The deterministic Compose governed-flow script must import the new `v0.1.6`
  scenario candidate rather than attempting a new historical `v0.1.3` insert. Keep
  `verify_dra_consumer.py fixture` as the byte-identical historical producer contract
  proof. Add a regression that these are two explicit paths, not an in-place rewrite
  of the copied fixture.

- [ ] **Step 2: Run gate RED**

  ```bash
  uv run pytest -q \
    tests/architecture/test_dra_contract.py \
    tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  ```

  Expected: failures for missing `0010` and missing DRA live evaluation surface.

- [ ] **Step 3: Update gates, ADR, reference, and operations**

  ADR `0011` records producer-versus-consumer authority, historical row
  compatibility, raw URL identity, evaluation-observes-only, and provider-free CI.
  Operations explicitly say no provider call was run and PR B/PR C remain
  unimplemented. Update current-development migration-head verifiers to `0010` while
  keeping published `v0.1.0`–`v0.1.3` release artifacts byte-identical.

- [ ] **Step 4: Run PR A verification**

  ```bash
  uv lock --check
  uv run ruff check .
  uv run pyright
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

  Expected: all commands exit zero; no live DRA endpoint is called; final task-owned
  Compose inventory is empty. Record pre/post Docker inventory and public-hygiene,
  private-path, secret, and historical-release digest scans.

- [ ] **Step 5: Commit PR A documentation and gates**

  Stage the exact files listed by this task, verify the staged allowlist, and commit:

  ```bash
  git commit -m "docs: publish DRA live projection authority"
  ```

## Final Plan-Review Corrections

These corrections are normative and supersede any earlier ambiguous task wording:

1. **Fake transport ownership stays in PR A.** Add
   `src/night_voyager/dra/live_fakes.py` and its tests in A3/A4. The versioned
   scenario must freeze the canonical provider-safe status envelope, terminal
   result/artifact envelope, and bounded ownership-bearing Evidence inventory, or
   one canonical factory that emits them. Fake and real transports must feed the
   same strict projection fields. PR B may extend only candidate-gateway behavior
   and injected recovery failures.
2. **Migration `0010` owns the final read boundary.** In addition to producer import
   authority, install one closed, RLS-preserving, read-only outcome projection
   callable through the existing API actor context. It exposes only the correlated
   identities/counts required by the final evaluator. It grants no table `SELECT`,
   DML, generic SQL, cross-tenant inspection, or new role. Add migration, forced-RLS,
   grant, cross-tenant, downgrade, and `0009` parity tests now; PR C supplies the
   adapter and full assertions without adding a second database authority surface.
3. **Frozen scenario means real envelope parity.** A1 tests must prove exact
   allowlisted status/result/Evidence shapes, ownership fields, unknown-field
   rejection, and fixture-to-fake parity, not only producer/profile identity.
4. **Canonical evaluation excludes ambient time.** All clocks are injected.
   Canonical JSON contains only frozen inputs and deterministic assertion results;
   wall-clock duration belongs only in a non-canonical readable report. Byte
   identity is required only for identical frozen inputs.

Update A2/A3/A4 file lists and exact staging commands to include the new fake
transport and outcome-projection migration tests. No historical migration may be
rewritten.

## PR A Completion Gate

- Final branch is clean and contains only PR A scope.
- Migration `0010` upgrade/downgrade/re-upgrade and grants are proven.
- Historical fixture bytes and published release artifacts are unchanged.
- Required CI remains offline/provider-free.
- No provider, candidate promotion, planning, review, family decision, release, or
  deployment was executed.
- Independent authority review and hosted CI remain separate later gates.
