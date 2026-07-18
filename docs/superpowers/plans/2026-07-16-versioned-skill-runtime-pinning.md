# Versioned Skill Governance and Runtime Pinning Implementation Plan

**Implementation status:** Implemented locally and verified as the unreleased PR B
backend boundary. All non-Compose gates below pass. `make compose-proof` remains
blocked on Alpine/ARM64 because the native Next.js SWC binding is unavailable;
authority review and an integration decision remain pending. The tasks below remain
the approved execution record; push, PR, merge, release, deployment, live-provider
proof, and PR C remain separately gated.

> **For agentic workers:** REQUIRED PRIMARY CONTROLLER: use
> `superpowers:dispatching-parallel-agents` only for the isolated lanes declared
> below; otherwise use `superpowers:executing-plans`. Use exactly one primary
> controller for this PR. Every behavior, migration, authority, pinning, worker,
> HTTP, and proof slice follows test-first RED -> GREEN. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Add a closed, immutable Skill catalog with deterministic evaluation,
owner-controlled activation and rollback, and a five-field SkillVersion pin that is
resolved when each planning task is created, copied to every execution, and validated
against checked-in runtime code before any adapter starts.

**Architecture:** Migration `0008` adds five forced-RLS Skill authority tables and
relational pin columns on `agent_tasks` and `agent_executions`. A packaged strict
`SkillRuntimeRegistry` remains the executable-code authority; PostgreSQL stores only
immutable identities, hashes, evaluation evidence, activation history, and task pins.
The same PR closes the synthetic adapter's fixture-Case seam by materializing the
exact persisted Case revision and filtering product projections to the selected
country subset.

**Tech Stack:** Python 3.12.13, Pydantic 2.13.4, FastAPI 0.139.2 lock with
`fastapi>=0.139,<0.140` runtime constraint, SQLAlchemy 2.0.51 async, asyncpg 0.31.0,
PostgreSQL 18.4, Alembic, pytest 9, Hatch/uv, Docker Compose, and the existing fenced
AgentTask/worker/opaque-session boundary.

## Global Constraints

- Begin only from the retained, authority-reviewed PR A baseline containing migration
  `0007`, ADR `0008`, and the revoked whole-revision API seam. Record the actual base
  SHA. Do not branch directly from the original design-doc baseline.
- PR B owns exactly migration `0008_versioned_skills.py`, exactly five new Skill
  tables, ADR `0009`, five-field task/execution pins, and persisted Case
  materialization. It does not add collaboration UI, a new queue, a new worker,
  provider transport, live proof, dependency, release, or deployment.
- Every commit stages the explicit file paths named by its Task. Recursive directory
  staging is forbidden. Before each commit, run `git diff --cached --name-only` and
  `git diff --cached --check`; the staged set must equal that commit's reviewed
  allowlist.
- The closed catalog has exactly six keys:
  `student-profile-intake`, `study-destination-compare`, `evidence-research`,
  `document-evidence-retrieval`, `family-decision-brief`, and
  `application-timeline-guard`.
- Only `study-destination-compare` has `binding_kind=planning_runtime`. The other five
  are `catalog_only`; they may be versioned and evaluated but cannot be activated,
  rolled back, task-pinned, or represented as executable.
- The executable bridge is the packaged, checked-in
  `fixtures/skills/runtime-manifest-v1.json`. It is installed into the wheel and read
  with `importlib.resources`; runtime behavior must not depend on the current working
  directory or an operator-supplied manifest.
- Database rows never contain executable code, prompt text, import path, shell
  command, arbitrary tool name, package URL, or user-defined schema. Candidate HTTP
  input never supplies executor, adapter, contract hash, dataset result, tool scope,
  binding digest, or evaluation pass/fail.
- Supported planning bindings are exactly:
  `planning_adapter_router@v1`, with
  `generate_planning_run_v1 -> deterministic_planning@m4a-v1` and
  `generate_governed_mixed_planning_run_v1 -> governed_mixed_planning@dra-mixed-v1`.
  The complete two-operation map participates in `runtime_binding_sha256`.
- Canonical seed contains six definitions, exactly six `1.0.0` versions, six
  deterministic `1.0.0` seed evaluations, and one
  `study-destination-compare@1.0.0` seed activation. Version `1.0.1` is checked into
  the packaged registry but is not inserted by default seed.
- A separate migrator-owned maintenance command loads one exact supported registry
  tuple into PostgreSQL. The v1 proof uses it to register
  `study-destination-compare@1.0.1` before candidate creation. It is not a browser,
  API, migration, or implicit seed side effect; unknown/unpackaged versions fail.
- The only nullable candidate `base_version_id` is the exact migrator-owned canonical
  `1.0.0` seed candidate. Every runtime candidate has a non-null base equal to the
  current active version for the runtime Skill or the latest registered version for a
  catalog-only Skill.
- Activation/evaluation evidence is not browser authority. Evaluation is computed by
  the checked-in deterministic evaluator. Seed and explicit registration store its
  trusted expected canonical projection on the immutable SkillVersion; the API-role
  mutation requires complete projection equality before persisting evaluation
  evidence. Activation and rollback require the designated owner advisor and append
  immutable events.
- A new planning task resolves the active Skill under the same transaction that owns
  idempotency replay, effective-task uniqueness, task insert, and dispatch insert.
  Activation/rollback affects only tasks created after the new event.
- The complete server-resolved pin is exactly
  `skill_definition_id`, `skill_version_id`, `skill_activation_event_id`,
  `skill_activation_sequence`, and `runtime_binding_sha256`.
- Claim copies all five fields to `agent_executions`. Python validates the copied pin,
  actual operation leaf, and complete binding hash after claim/load and before
  `start_agent_task`. Invalid pin calls the existing fenced non-retryable failure path
  with `skill_pin_invalid`; it never starts, calls an adapter, or enters a reclaim
  loop.
- Canonical execution `input_sha256` hashes exactly `{request, five_field_pin}`. The
  leaf adapter remains separately recorded as execution audit fact.
- The synthetic adapter must read the exact persisted organization/Case/revision.
  `preferred_countries` is a non-empty sorted unique subset of
  `australia|japan|malaysia`; route, cost, ranking, and route-to-Evidence product
  projections contain only selected countries. The canonical all-three seed result
  remains unchanged.
- All five Skill tables are migrator-owned, tenant-keyed, immutable, forced-RLS, and
  deny runtime direct DML/TRUNCATE. API receives narrow functions/projections. Worker
  receives only the pin/snapshot projections necessary to execute an already-created
  task. `PUBLIC` receives no authority.
- Public problem codes are frozen to `resource_unavailable`,
  `skill_version_unavailable`, `skill_candidate_stale`,
  `skill_candidate_terminal`, `skill_evaluation_failed`,
  `skill_activation_stale`, `skill_scope_expansion`,
  `skill_rollback_unsupported`, `skill_pin_invalid`, `idempotency_conflict`, and
  `persistence_unavailable`.
- SQLSTATE mapping is frozen to existing `NV007` non-enumerating authorization and
  `NV008` idempotency mismatch, plus `NV015` Skill version unavailable, `NV016`
  candidate stale, `NV017` candidate terminal, `NV018` deterministic evaluation
  failed, `NV019` activation CAS stale, `NV020` scope expansion, `NV021` unsupported
  rollback target, and `NV022` relational task pin invalid. Python registry failure
  uses the same public `skill_pin_invalid` without inventing a database error. Unknown
  SQLSTATE, permission, serialization, connection, or result-shape errors remain
  bounded persistence failures; adapters never parse raw SQL messages.
- Keep required hosted contexts named `python`, `frontend`, and `compose`. Preserve
  all PR A, M1-M5, DRA, MKE, task/SSE, and v0.1.1 release contracts.
- Keep all files, errors, logs, commits, PR text, and docs public-neutral. Never store
  or print credentials, cookies, CSRF values, raw SQL, prompts, provider payloads,
  tracebacks, local paths, or private execution metadata.

## File Ownership and Lane Boundaries

The integration owner exclusively owns:

- `migrations/versions/0008_versioned_skills.py`
- task/worker shared files and migration signatures
- `src/night_voyager/api.py`, `src/night_voyager/worker.py`
- `src/night_voyager/adapters/{protocols,router}.py`
- `pyproject.toml`, `src/night_voyager/tasks/policy.py`, shared architecture tests
- seed ordering, `Makefile`, CI, release/catalog verification, shared docs
- all PostgreSQL, Docker, Compose, downgrade, and full verification gates

Bounded lane B1 owns pure Skill contracts only:

- `src/night_voyager/skills/{__init__,models,registry,evaluation}.py`
- `fixtures/skills/runtime-manifest-v1.json`
- `fixtures/skills/eval-manifest-v1.json`
- pure/unit/contract Skill tests

Bounded lane B2 owns persisted planning materialization only:

- `src/night_voyager/planning/{models,policy,mixed,synthetic,synthetic_postgres}.py`
- `src/night_voyager/adapters/deterministic_planning.py`
- focused planning/materializer tests

The integration owner applies the small `tasks/policy.py` projection change after
lane B2 freezes its selected-country contract; lane B2 does not edit task files.

Bounded lane B3 starts after B1 freezes public interfaces and may own:

- `src/night_voyager/skills/{errors,ports,application,postgres}.py`
- `src/night_voyager/interfaces/http/skills.py`
- focused fake-repository and HTTP tests

No lane edits the migration, task/worker shared files, API wiring, Make/CI, shared
docs, or another lane's files. The integration owner performs all merges and final
branch review.

---

### Task B1: Freeze strict Skill models and packaged runtime registry

**Files:**
- Create: `src/night_voyager/skills/__init__.py`
- Create: `src/night_voyager/skills/models.py`
- Create: `src/night_voyager/skills/registry.py`
- Create: `fixtures/skills/runtime-manifest-v1.json`
- Create: `tests/contracts/test_skill_runtime_registry.py`
- Create: `tests/unit/skills/__init__.py`
- Create: `tests/unit/skills/test_models.py`
- Create: `tests/unit/skills/test_registry.py`
- Create (integration owner): `tests/architecture/test_skills_contract.py`
- Modify (integration owner): `pyproject.toml`

**Interfaces:**
- Produces strict `SkillKey`, `SkillBindingKind`, `SkillChangeProvenance`,
  `SkillEvaluationStatus`, `SkillActivationKind`, `SkillRuntimePin`,
  `SkillLeafBindingV1`, `SkillRuntimeManifestEntryV1`,
  `SkillRuntimeManifestV1`, and `SkillRuntimeRegistry`.
- The registry exposes `load_packaged()`, `get()`,
  `supported_planning_bindings()`, and `validate_pin()`.

- [x] **Step 1: Write RED contract tests**

  Test exact six keys, strict semantic-version regex, `extra="forbid"`, lowercase
  SHA-256, sorted unique tools/scopes, catalog-only absence of executable fields,
  planning-runtime complete two-operation map, stable canonical hashes, unknown
  version rejection, exact `1.0.0` versus `1.0.1` resolution even when both versions
  share the same runtime-binding digest, and packaged-resource loading from an
  installed wheel.

  ```python
  @pytest.mark.parametrize("value", ["1", "1.0", "01.0.0", "1.0.0-rc1", " 1.0.0"])
  def test_semantic_version_is_exact_major_minor_patch(value: str) -> None:
      with pytest.raises(ValidationError):
          SkillRuntimeManifestEntryV1.model_validate(valid_entry(version=value))

  def test_catalog_only_entry_rejects_runtime_binding() -> None:
      payload = catalog_entry()
      payload["executor_id"] = "planning_adapter_router"
      with pytest.raises(ValidationError):
          SkillRuntimeManifestEntryV1.model_validate(payload)
  ```

- [x] **Step 2: Run focused RED**

  ```bash
  uv run pytest tests/unit/skills/test_models.py tests/unit/skills/test_registry.py \
    tests/contracts/test_skill_runtime_registry.py \
    tests/architecture/test_skills_contract.py -q
  ```

  Expected: collection fails because the Skill package and packaged manifest do not
  exist.

- [x] **Step 3: Implement strict models and registry**

  Use strict frozen Pydantic models. `SkillRuntimeRegistry.validate_pin()` accepts
  the persisted five-field pin, trusted worker-resolved `skill_key` and semantic
  version, task operation, and actual selected leaf, then resolves by the exact
  key/version pair and returns the supported manifest entry or raises a typed
  incompatibility. It never selects an entry from a database UUID or
  `runtime_binding_sha256` alone because compatible versions may share that binding
  digest.

  ```python
  class SkillRuntimePin(FrozenModel):
      skill_definition_id: UUID
      skill_version_id: UUID
      skill_activation_event_id: UUID
      skill_activation_sequence: PositiveInt
      runtime_binding_sha256: Sha256

  class SkillLeafBindingV1(FrozenModel):
      operation: PlanningOperation
      adapter_id: Literal["deterministic_planning", "governed_mixed_planning"]
      adapter_version: Literal["m4a-v1", "dra-mixed-v1"]
  ```

  After lane B1 is integrated, the integration owner adds this exact Hatch mapping so
  one checked-in source is available to editable
  execution and the installed wheel without maintaining a second manifest copy:

  ```toml
  [tool.hatch.build.targets.wheel.force-include]
  "fixtures/skills/runtime-manifest-v1.json" = "night_voyager/skills/data/runtime-manifest-v1.json"
  ```

  Load them only with
  `importlib.resources.files("night_voyager.skills").joinpath("data", filename)`.
  Tests must cover editable execution, sdist-to-wheel build, and an isolated installed
  wheel; production code has no repository-path fallback.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/skills tests/contracts/test_skill_runtime_registry.py \
    tests/architecture/test_skills_contract.py -q
  uv run ruff check src/night_voyager/skills tests/unit/skills \
    tests/contracts/test_skill_runtime_registry.py
  uv run pyright src/night_voyager/skills tests/unit/skills
  uv build --build-constraints build-constraints.txt --require-hashes
  ```

  Expected: tests and static checks pass; the wheel contains and loads the manifest.

  ```bash
  git add pyproject.toml fixtures/skills/runtime-manifest-v1.json \
    src/night_voyager/skills/__init__.py src/night_voyager/skills/models.py \
    src/night_voyager/skills/registry.py tests/unit/skills/__init__.py \
    tests/unit/skills/test_models.py tests/unit/skills/test_registry.py \
    tests/contracts/test_skill_runtime_registry.py \
    tests/architecture/test_skills_contract.py
  git commit -m "feat: add versioned Skill runtime registry"
  ```

### Task B2: Add deterministic Skill evaluation evidence

**Files:**
- Create: `fixtures/skills/eval-manifest-v1.json`
- Create: `src/night_voyager/skills/evaluation.py`
- Create: `tests/unit/skills/test_evaluation.py`
- Modify (integration owner): `tests/architecture/test_skills_contract.py`
- Modify (integration owner): `pyproject.toml`

**Interfaces:**
- Produces strict evaluation manifest/projection models and one deterministic
  evaluator that invokes existing pure product policies without provider, model,
  shell, database, or browser-supplied pass/fail authority.

- [x] **Step 1: Write evaluator RED tests**

  Freeze stable assertion IDs and exact dataset identity for all six Skills. Include
  pass and mutation counterfactuals for typed profile facts, destination comparison,
  governed Evidence, MKE no-match, advisor-reviewed Brief creation, and deterministic
  timeline guard. Include `study-destination-compare@1.0.1` compatibility and its
  added deterministic negative assertions without changing product output. Reject
  missing/extra/duplicate assertion IDs, forged result status,
  dataset hash drift, and unknown Skill/version.

- [x] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/skills/test_evaluation.py \
    tests/architecture/test_skills_contract.py -q
  ```

  Expected: evaluator and eval manifest are absent.

- [x] **Step 3: Implement deterministic evaluation**

  The evaluator loads only the packaged, checked-in manifest and pure policies. It
  returns the complete canonical assertion projection, failed assertion IDs, status,
  and output digest. It never accepts status or assertion output from an HTTP DTO.
  After the pure evaluator slice is integrated, the integration owner extends the
  Hatch force-include table with exactly:

  ```toml
  "fixtures/skills/eval-manifest-v1.json" = "night_voyager/skills/data/eval-manifest-v1.json"
  ```

  Load it through the same `importlib.resources` package-data path and add editable,
  sdist-to-wheel, and isolated-wheel assertions; no repository-path fallback exists.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/skills/test_evaluation.py \
    tests/architecture/test_skills_contract.py -q
  uv run ruff check src/night_voyager/skills/evaluation.py \
    tests/unit/skills/test_evaluation.py
  uv run pyright src/night_voyager/skills/evaluation.py \
    tests/unit/skills/test_evaluation.py
  uv build --build-constraints build-constraints.txt --require-hashes
  ```

  ```bash
  git add pyproject.toml fixtures/skills/eval-manifest-v1.json \
    src/night_voyager/skills/evaluation.py tests/unit/skills/test_evaluation.py \
    tests/architecture/test_skills_contract.py
  git commit -m "feat: add deterministic Skill evaluation evidence"
  ```

### Task B3: Materialize persisted Case revisions and country subsets

**Files:**
- Create: `src/night_voyager/planning/synthetic.py`
- Create: `src/night_voyager/planning/synthetic_postgres.py`
- Modify: `src/night_voyager/planning/models.py`
- Modify: `src/night_voyager/planning/policy.py`
- Modify: `src/night_voyager/planning/mixed.py`
- Modify: `src/night_voyager/adapters/deterministic_planning.py`
- Modify (integration owner): `src/night_voyager/tasks/policy.py`
- Create: `tests/unit/planning/test_synthetic.py`
- Modify: `tests/unit/planning/test_policy.py`
- Modify: `tests/unit/planning/test_mixed.py`
- Modify: `tests/contracts/test_deterministic_planning_adapter.py`

**Interfaces:**
- Produces a worker-only `PersistedSyntheticSnapshotRepository`, exact
  organization/Case/revision materialization, and selected-country product
  projection for both synthetic and governed mixed operations.

- [x] **Step 1: Write RED tests**

  Cover Australia-only, Japan-only, Australia+Japan, all-three canonical seed, and
  empty/duplicate/unsorted/unsupported rejection. Prove confirmed budget, intake,
  Japan-risk and countries reach actual adapter input; fixture Case values cannot
  overwrite persisted facts. Assert unselected routes/cost/ranking/eligible-review
  rows are absent while baseline Evidence may remain an input record.

  ```python
  def test_selected_country_subset_filters_product_projection() -> None:
      result = evaluate_planning_run(snapshot(countries=(Country.JAPAN,)))
      assert tuple(route.country for route in result.routes) == (Country.JAPAN,)
      assert {row.country for row in result.costs} == {Country.JAPAN}
      assert {row.country for row in result.rankings} == {Country.JAPAN}
  ```

- [x] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/planning/test_synthetic.py \
    tests/unit/planning/test_policy.py tests/unit/planning/test_mixed.py \
    tests/contracts/test_deterministic_planning_adapter.py -q
  ```

  Expected: persisted materializer is absent and existing policy emits all three
  routes regardless of the stored preference.

- [x] **Step 3: Implement the bounded materializer and projection**

  Validate `preferred_countries` at the model edge. Load the exact revision using a
  worker-only SQL projection. Combine those facts with the existing fixed synthetic
  Evidence/source/cost/FX/ranking baseline, then filter result rows to selected
  countries. Preserve current policy decisions and all-three golden hashes where the
  input is unchanged.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/planning/test_synthetic.py \
    tests/unit/planning/test_policy.py tests/unit/planning/test_mixed.py \
    tests/contracts/test_deterministic_planning_adapter.py -q
  uv run ruff check src/night_voyager/planning \
    src/night_voyager/adapters/deterministic_planning.py tests/unit/planning \
    tests/contracts/test_deterministic_planning_adapter.py
  uv run pyright src/night_voyager/planning \
    src/night_voyager/adapters/deterministic_planning.py tests/unit/planning
  ```

  ```bash
  git add src/night_voyager/planning/synthetic.py \
    src/night_voyager/planning/synthetic_postgres.py \
    src/night_voyager/planning/models.py src/night_voyager/planning/policy.py \
    src/night_voyager/planning/mixed.py \
    src/night_voyager/adapters/deterministic_planning.py \
    tests/unit/planning/test_synthetic.py tests/unit/planning/test_policy.py \
    tests/unit/planning/test_mixed.py \
    tests/contracts/test_deterministic_planning_adapter.py
  git commit -m "feat: materialize persisted planning revisions"

  # Integration owner applies the frozen projection only after lane B2 is merged.
  git add src/night_voyager/tasks/policy.py
  git commit -m "feat: bind task policy to selected countries"
  ```

### Task B4: Add migration `0008`, Skill storage, pins, and downgrade

**Files:**
- Create: `migrations/versions/0008_versioned_skills.py`
- Create: `tests/security/test_skills_catalog.py`
- Create: `tests/integration/skills/__init__.py`
- Create: `tests/integration/skills/test_postgres_skills.py`
- Create: `tests/integration/skills/test_skill_downgrade.py`
- Create: `tests/integration/skills/test_persisted_planning_materialization.py`
- Modify: `src/night_voyager/tasks/models.py`
- Create: `scripts/run_skill_db_tests.sh`
- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `scripts/seed_demo.py`
- Modify: `tests/unit/identity/test_seed_demo.py`
- Modify: `Makefile`
- Modify: `tests/architecture/test_skills_contract.py`
- Modify: `scripts/run_db_tests.sh`
- Modify: `scripts/verify_release.py`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `tests/security/test_dra_mixed_catalog.py`
- Modify: `tests/architecture/test_m4a_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`
- Modify: `tests/architecture/test_collaboration_contract.py`

**Interfaces:**
- Produces five exact Skill tables, four runtime mutation functions, migrator-only
  seed, narrow reads, five-field pin columns/FKs/index, task/worker signature
  extensions, and exact `0008 -> 0007` downgrade.

- [x] **Step 1: Build and self-test the isolated database runner**

  First add architecture assertions that require the exact `skills-db-check` target,
  script path, suite names, `-o addopts='' -m database`, isolated project/volume, and
  teardown trap. Run them to observe RED while the runner is absent, implement only
  the Make/script routing, then rerun GREEN. Also invoke an unknown suite and assert
  it fails before any Docker resource is created.

  ```bash
  uv run pytest tests/architecture/test_skills_contract.py -q
  make skills-db-check SUITE=unknown
  ```

  Expected: the first command is GREEN after runner wiring; the second exits nonzero
  with a bounded usage message and leaves no Compose project.

- [x] **Step 2: Write migration/catalog/materializer RED tests**

  Freeze exact tables, migrator ownership, forced RLS, tenant policies, immutable
  triggers, function signatures, fixed `search_path`, PUBLIC revocation, runtime
  grants, all-null/all-non-null pin checks, composite FKs, effective-task index, and
  downgrade refusal/restore contracts. In the real persisted-materialization file,
  freeze the worker-only snapshot projection for exact organization/Case/revision and
  current budget/intake/Japan risk/country facts, including missing, stale,
  cross-tenant, malformed, unsupported-country, and pin-mismatch failures.

- [x] **Step 3: Run product RED**

  ```bash
  make skills-db-check SUITE=catalog
  ```

  Expected: migration, tables, functions, pin columns, and restore path are absent.

  `skills-db-check` must create an isolated Compose project/volume, upgrade/seed with
  migration credentials, invoke Pytest with `-o addopts='' -m database`, and always
  tear down. It never relies on host database URLs or the default non-database pytest
  marker. Freeze the suite map:

  - `catalog`: `tests/security/test_skills_catalog.py`,
    `tests/integration/skills/test_postgres_skills.py`, and
    `tests/integration/skills/test_skill_downgrade.py`,
    `tests/integration/skills/test_persisted_planning_materialization.py`, plus host-side
    `tests/unit/identity/test_seed_demo.py`;
  - `worker`: `tests/integration/skills/test_task_pins.py`,
    `tests/integration/skills/test_persisted_planning_materialization.py`,
    `tests/integration/connected_demo/test_postgres_read_models.py`,
    `tests/integration/tasks/test_http_tasks.py`,
    `tests/integration/tasks/test_postgres_tasks.py`,
    `tests/integration/tasks/test_sse.py`,
    `tests/integration/tasks/test_worker.py`,
    `tests/integration/tasks/test_worker_authority.py`,
    `tests/integration/tasks/test_worker_capacity.py`, and
    `tests/integration/tasks/test_mixed_downgrade.py`;
  - `lifecycle`: `tests/integration/skills/test_skill_lifecycle.py`,
    `tests/integration/skills/test_http_skills.py`,
    `tests/integration/skills/test_persisted_planning_materialization.py`,
    `tests/integration/skills/test_postgres_skills.py`, and
    `tests/integration/skills/test_skill_downgrade.py`.

  Unknown or empty `SUITE` values fail before Docker starts. Each suite logs the
  selected files and proves its owned Compose project is empty after teardown.

- [x] **Step 4: Implement exact schema and relational pin proof**

  Create:

  ```text
  app.skill_definitions
  app.skill_versions
  app.skill_change_candidates
  app.skill_evaluation_results
  app.skill_activation_events
  ```

  Add composite keys that prove a task's version belongs to its definition, its
  activation references the same definition/version/sequence, and its binding digest
  equals the immutable version. Add the same five fields to executions with a
  composite FK/equality guard to the parent task. New tasks require all fields;
  pre-`0008` history may be all-null only under the migration rule.

  Each version also stores the migrator-owned expected canonical evaluation
  projection produced by the packaged evaluator. Candidate evaluation persists only
  an exact full-projection match; partial assertion-shape checks cannot grant passing
  authority.

  `skill_definitions.owner_actor_id` has an exact composite FK to an organization
  advisor membership. Activation sequence is unique and monotonic per definition;
  current activation is derived only from the latest append-only event. Catalog-only
  definitions cannot satisfy any activation or pin FK path.

- [x] **Step 5: Implement narrow mutation/read functions**

  Runtime mutations are exactly:

  ```text
  create_skill_change_candidate(...)
  record_skill_candidate_evaluation(...)
  promote_skill_change_candidate(...)
  rollback_skill_activation(...)
  ```

  Add migrator-only `seed_demo_skill_registry(...)` and bounded projections for
  catalog, candidate evaluation context, inspector, worker pin, and synthetic
  snapshot. Candidate creation receives a server-loaded manifest projection and
  compares every immutable field to a pre-registered version; it never inserts a
  version. The synthetic snapshot projection must make the Step 2 real PostgreSQL
  materializer assertions GREEN before worker integration begins.

  The trusted application passes the full registry-resolved immutable projection to
  `create_agent_task(...)`. SQL compares it to the registered row before resolving
  the pin; the browser/task DTO never supplies that projection.

  Add the exact canonical default seed in the same slice so later HTTP/worker tests
  have a valid active pin: six definitions, six `1.0.0` versions, six deterministic
  seed evaluation records, and one `study-destination-compare@1.0.0` seed activation.
  Default seed does not register `1.0.1` and remains idempotent.

- [x] **Step 6: Extend task creation and claim under one lock protocol**

  For a new task, the SQL order is:

  ```text
  idempotency replay
  -> skill definition FOR SHARE
  -> latest activation
  -> complete registered tuple validation
  -> resolve exact five-field pin
  -> effective-task lookup/index
  -> task insert
  -> dispatch insert
  -> idempotency response
  ```

  Activation/rollback uses `FOR UPDATE` on the same definition. Claim validates the
  relational pin and copies it to the execution before returning worker input.

- [x] **Step 7: Implement exact upgrade/downgrade behavior**

  Upgrade cancels only active legacy-unpinned `queued|leased|running` tasks with
  bounded code `legacy_unpinned`, closes active executions, clears lease/dispatch,
  and preserves `waiting_review`/terminal history as inspector-visible
  `legacy_unpinned`. The exact PR A active-task negative fixture is
  `waiting_review`; a migration/runtime regression proves it remains unchanged and
  continues to make candidate confirmation return `active_task_blocks_revision`
  after `0008` upgrade.

  Downgrade succeeds only with the exact six-definition/six-`1.0.0` canonical seed
  and no task/execution pin. It refuses any explicitly registered non-seed version
  (including `1.0.1`), non-seed candidate/evaluation, promote/rollback event, active
  pin, and terminal pin. On the allowed path it restores exact `0007` task/worker
  function signatures, effective index, grants, and verifier contract before
  dropping Skill structures.

- [x] **Step 8: Run focused GREEN and commit**

  ```bash
  make skills-db-check SUITE=catalog
  uv run ruff check migrations/versions/0008_versioned_skills.py \
    scripts/run_skill_db_tests.sh tests/security/test_skills_catalog.py \
    tests/integration/skills
  ```

  ```bash
  git add migrations/versions/0008_versioned_skills.py src/night_voyager/tasks/models.py \
    Makefile scripts/run_skill_db_tests.sh tests/security/test_skills_catalog.py \
    src/night_voyager/identity/demo_seed.py scripts/seed_demo.py \
    tests/unit/identity/test_seed_demo.py tests/integration/skills/__init__.py \
    tests/integration/skills/test_postgres_skills.py \
    tests/integration/skills/test_skill_downgrade.py \
    tests/integration/skills/test_persisted_planning_materialization.py \
    tests/architecture/test_skills_contract.py scripts/run_db_tests.sh \
    scripts/verify_release.py tests/security/test_database_catalog.py \
    tests/security/test_dra_mixed_catalog.py \
    tests/architecture/test_m4a_contract.py \
    tests/architecture/test_m5_contract.py \
    tests/architecture/test_collaboration_contract.py
  git commit -m "feat: add Skill governance database authority"
  ```

### Task B5: Add Skill application services and closed FastAPI surface

**Files:**
- Create: `src/night_voyager/skills/errors.py`
- Create: `src/night_voyager/skills/ports.py`
- Create: `src/night_voyager/skills/application.py`
- Create: `src/night_voyager/skills/postgres.py`
- Create: `src/night_voyager/interfaces/http/skills.py`
- Create: `tests/unit/skills/test_application.py`
- Create: `tests/unit/skills/test_http.py`
- Modify: `src/night_voyager/api.py`
- Modify: `tests/unit/test_api.py`

**Interfaces:**
- Produces catalog reads, candidate/evaluate/activate/rollback services, strict DTOs,
  exact owner checks delegated to PostgreSQL, RFC 9457 problems, and advisor-only
  planning Skill inspector.

  The exact HTTP surface is:

  ```text
  GET  /api/v1/skills
  GET  /api/v1/skills/{skill_key}
  POST /api/v1/skills/{skill_key}/change-candidates
  POST /api/v1/skill-change-candidates/{candidate_id}/evaluations
  POST /api/v1/skill-change-candidates/{candidate_id}/activations
  POST /api/v1/skills/{skill_key}/rollbacks
  GET  /api/v1/cases/{case_id}/planning-skill-inspector
  ```

  Both catalog GETs allow organization advisors. Candidate/evaluate/activate/rollback
  require the designated owner advisor. Inspector GET requires the assigned Case
  advisor. Every response is `no-store`; wrong tenant, unassigned actor, wrong owner,
  unknown Skill/version/candidate/Case, and catalog-only activation are
  non-enumerating where applicable.

- [x] **Step 1: Write service/HTTP RED tests**

  Cover owner/non-owner, catalog-only behavior, exact DTO fields, registered-version
  requirement, server-computed evaluation, failed evaluation, scope expansion,
  stale activation, rollback target, replay/conflict, exact Origin/CSRF/session,
  no-store, and non-enumerating 404.

  Request bodies are frozen to:

  ```text
  POST /skills/{skill_key}/change-candidates
    schema_version, proposed_version, provenance, reason, reference?
  POST /skill-change-candidates/{id}/evaluations
    schema_version
  POST /skill-change-candidates/{id}/activations
    schema_version, expected_active_version, expected_activation_sequence, reason
  POST /skills/{skill_key}/rollbacks
    schema_version, target_version, expected_active_version,
    expected_activation_sequence, reason
  ```

- [x] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/skills/test_application.py \
    tests/unit/skills/test_http.py tests/unit/test_api.py -q
  ```

  Expected: services, adapter, router, and OpenAPI paths are absent.

- [x] **Step 3: Implement ports, adapter, and router**

  Service IDs and canonical request hashes are product-owned. PostgreSQL owns actor,
  owner, version, evaluation, activation, CAS, and replay authority. Map expected
  SQLSTATEs to separate typed errors; unknown DB/shape/permission/connection failures
  remain bounded persistence failures and are never misclassified as stale or 404.
  The exact mapping is: `NV007 -> resource_unavailable`, `NV008 ->
  idempotency_conflict`, `NV015 -> skill_version_unavailable`, `NV016 ->
  skill_candidate_stale`, `NV017 -> skill_candidate_terminal`, `NV018 ->
  skill_evaluation_failed`, `NV019 -> skill_activation_stale`, `NV020 ->
  skill_scope_expansion`, `NV021 -> skill_rollback_unsupported`, and `NV022 ->
  skill_pin_invalid`.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/skills/test_application.py \
    tests/unit/skills/test_http.py tests/unit/test_api.py -q
  uv run ruff check src/night_voyager/skills \
    src/night_voyager/interfaces/http/skills.py tests/unit/skills
  uv run pyright src/night_voyager/skills \
    src/night_voyager/interfaces/http/skills.py tests/unit/skills
  ```

  ```bash
  git add src/night_voyager/skills/errors.py src/night_voyager/skills/ports.py \
    src/night_voyager/skills/application.py src/night_voyager/skills/postgres.py \
    src/night_voyager/interfaces/http/skills.py \
    tests/unit/skills/test_application.py tests/unit/skills/test_http.py
  git commit -m "feat: expose governed Skill lifecycle"

  # Integration owner wires the frozen router only after the lane commit.
  git add src/night_voyager/api.py tests/unit/test_api.py
  git commit -m "feat: wire governed Skill HTTP routes"
  ```

### Task B6: Pin task creation, execution, and worker validation

**Files:**
- Modify: `src/night_voyager/tasks/models.py`
- Modify: `src/night_voyager/tasks/ports.py`
- Modify: `src/night_voyager/tasks/application.py`
- Modify: `src/night_voyager/tasks/postgres.py`
- Modify: `src/night_voyager/tasks/policy.py`
- Modify: `src/night_voyager/tasks/worker.py`
- Modify: `src/night_voyager/worker.py`
- Modify: `src/night_voyager/interfaces/http/tasks.py`
- Modify: `src/night_voyager/adapters/protocols.py`
- Modify: `src/night_voyager/adapters/router.py`
- Create: `tests/unit/adapters/test_router.py`
- Create: `tests/integration/skills/test_task_pins.py`
- Modify: `tests/integration/skills/test_persisted_planning_materialization.py`
- Modify: `tests/unit/tasks/test_application.py`
- Modify: `tests/unit/tasks/test_policy.py`
- Modify: `tests/unit/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_http_tasks.py`
- Modify: `tests/integration/tasks/test_postgres_tasks.py`
- Modify: `tests/integration/tasks/test_worker.py`
- Modify: `tests/integration/tasks/test_worker_authority.py`
- Modify: `tests/integration/tasks/test_worker_capacity.py`
- Modify: `tests/integration/tasks/test_mixed_downgrade.py`
- Modify: `tests/integration/tasks/test_sse.py`
- Modify: `tests/integration/connected_demo/test_postgres_read_models.py`

**Interfaces:**
- Adds `skill_pin: SkillRuntimePin` and `leaf_binding: SkillLeafBindingV1` to worker
  input, task/response projections, and audit-safe inspector output. The trusted
  worker-only database projection additionally joins the pinned definition/version
  rows and returns the exact `skill_key` and semantic version used to select the
  packaged manifest entry; these values are not accepted from the browser or task
  request.

- [x] **Step 1: Write task/worker RED tests**

  Cover task create/replay around activation, complete pin equality, claim copy,
  actual leaf validation, input hash, old task preservation, missing/mismatched/
  catalog-only pin, invalid-pin terminal audit, no adapter/start/reclaim, retry attempt
  pin equality, activation/create race, effective uniqueness across versions, and a
  configured-router leaf that drifts from the packaged manifest. Extend the real
  persisted-materialization test before wiring the worker: both operations must load
  the exact persisted revision, invoke the resolved adapter, and persist only selected
  route/cost/ranking/Evidence/eligibility rows; canonical all-three output remains
  stable and unselected product rows remain absent. Update the existing connected-demo
  read-model and SSE database tests so they no longer call the restored pre-`0008`
  `create_agent_task` signature or construct an adapter-only worker. Both must use the
  real pinned application/API path and registry-aware worker, and must distinguish
  exact `1.0.0` from `1.0.1` even when their runtime-binding digests are equal.

- [x] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/tasks tests/unit/adapters/test_router.py -q
  make skills-db-check SUITE=worker
  ```

  Expected: task/worker projections lack pins, invalid pin can reach the adapter, and
  both legacy direct-SQL/adapter-only integration paths fail until converted to the
  pinned authority path.

- [x] **Step 3: Implement worker order and input hash**

  Add `PlanningAdapterRouter.resolve(operation)` returning the actual configured
  immutable adapter identity and adapter object. Treat the execution row's existing
  `adapter_id`/`adapter_version` as `claimed_execution_leaf` and the router result as
  `resolved_router_leaf`. Before start, require exact three-way equality among the
  claimed leaf, resolved leaf, and packaged registry leaf for the task operation.
  Any mismatch uses the fenced non-retryable `skill_pin_invalid` path. The successful
  execution audit keeps the claimed pair unchanged and invokes the exact resolved
  object that was compared. Database operation mapping is never treated as the
  executable router authority.

  Execute exactly:

  ```text
  claim
  -> load request + execution pin + trusted joined Skill key/version + claimed execution leaf
  -> resolve router leaf
  -> SkillRuntimeRegistry.validate_pin(pin, skill_key, semantic_version, operation, leaf)
  -> prove exact key/version manifest tuple and binding digest
  -> prove claimed leaf = resolved leaf = registry leaf
  -> invalid: fenced fail(skill_pin_invalid, retryable=false)
  -> valid: start(input_sha256=sha256({request,five_field_pin}))
  -> adapter
  -> validate payload against registry-resolved leaf
  -> finalize
  ```

  `validate_adapter_payload()` receives the registry-resolved leaf rather than
  maintaining a second hard-coded operation map.

- [x] **Step 4: Run GREEN and commit**

  ```bash
  uv run pytest tests/unit/tasks tests/unit/adapters/test_router.py -q
  make skills-db-check SUITE=worker
  uv run ruff check src/night_voyager/tasks src/night_voyager/worker.py \
    src/night_voyager/interfaces/http/tasks.py src/night_voyager/adapters \
    tests/integration/skills/test_task_pins.py tests/unit/adapters/test_router.py
  uv run pyright src/night_voyager/tasks src/night_voyager/worker.py \
    src/night_voyager/interfaces/http/tasks.py src/night_voyager/adapters
  ```

  ```bash
  git add src/night_voyager/tasks/models.py src/night_voyager/tasks/ports.py \
    src/night_voyager/tasks/application.py src/night_voyager/tasks/postgres.py \
    src/night_voyager/tasks/policy.py src/night_voyager/tasks/worker.py \
    src/night_voyager/worker.py src/night_voyager/interfaces/http/tasks.py \
    src/night_voyager/adapters/protocols.py src/night_voyager/adapters/router.py \
    tests/unit/adapters/test_router.py tests/unit/tasks/test_application.py \
    tests/unit/tasks/test_policy.py tests/unit/tasks/test_worker.py \
    tests/integration/skills/test_task_pins.py \
    tests/integration/skills/test_persisted_planning_materialization.py \
    tests/integration/connected_demo/test_postgres_read_models.py \
    tests/integration/tasks/test_http_tasks.py \
    tests/integration/tasks/test_postgres_tasks.py \
    tests/integration/tasks/test_worker.py \
    tests/integration/tasks/test_worker_authority.py \
    tests/integration/tasks/test_worker_capacity.py \
    tests/integration/tasks/test_mixed_downgrade.py \
    tests/integration/tasks/test_sse.py
  git commit -m "feat: pin planning tasks to active Skill versions"
  ```

### Task B7: Seed the full lifecycle and prove runtime/downgrade authority

**Files:**
- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `scripts/seed_demo.py`
- Modify: `scripts/run_db_tests.sh`
- Create: `scripts/register_skill_version.py`
- Create: `tests/integration/skills/test_skill_lifecycle.py`
- Create: `tests/integration/skills/test_http_skills.py`
- Modify: `tests/integration/skills/test_persisted_planning_materialization.py`
- Modify: `tests/integration/skills/test_postgres_skills.py`
- Modify: `tests/integration/skills/test_skill_downgrade.py`
- Modify: `tests/security/test_skills_catalog.py`

- [x] **Step 1: Write lifecycle/runtime RED tests**

  Prove repeated exact seed, dual tenant isolation, designated-owner enforcement,
  catalog-only activation denial, candidate/evaluation immutability, one-winner
  concurrent activation, rollback CAS, every consequential write rollback,
  API/worker/PUBLIC grants, pool cleanup, `1.0.1` candidate/evaluate/promote, old task
  preserved, new task new pin, rollback, and another new task restored to `1.0.0`.
  Through real task execution and result persistence, also prove one- and two-country
  Case revisions create only selected route/cost/ranking/Evidence-link projections
  and no unselected Australia advisor-eligibility row.

  Add real PostgreSQL/HTTP coverage for both planning operations, current persisted
  budget/intake/Japan risk/countries, missing/stale/cross-tenant/malformed revision,
  unsupported countries, pin mismatch, strict DTOs, owner/assignment matrix,
  no-store/non-enumeration, and worker/API/PUBLIC projection grants.

- [x] **Step 2: Run lifecycle RED on real PostgreSQL**

  ```bash
  make skills-db-check SUITE=lifecycle
  ```

  Expected: exact assertions for the explicit registration command, full lifecycle,
  real HTTP, worker persistence, or non-seed downgrade refusal fail before this task
  changes implementation.

- [x] **Step 3: Verify canonical seed and add explicit supported-version registration**

  ```text
  identity and participants
  -> six definitions and six registered 1.0.0 versions
  -> six canonical 1.0.0 candidates/evaluations
  -> study-destination-compare@1.0.0 seed activation
  -> task-ready Cases
  -> preserve PR A waiting_review active-task negative fixture without re-seeding it
  ```

  Migration remains seed-free. The default seed function is migrator-only and
  idempotent. Add a separate maintenance command:

  ```bash
  uv run --no-editable python scripts/register_skill_version.py \
    --skill-key study-destination-compare --version 1.0.1
  ```

  It requires the migration database URL, loads the exact packaged registry tuple,
  inserts only that immutable pre-supported row, is idempotent for an exact match,
  and fails closed on any mismatch. The default seed and Compose bootstrap never call
  it. Unit/architecture tests scan both paths to prove that absence. The lifecycle
  test invokes it explicitly before creating the `1.0.1` candidate.

- [x] **Step 4: Run GREEN on real PostgreSQL**

  ```bash
  make skills-db-check SUITE=lifecycle
  make db-check
  ```

  Expected: all runtime-role, lifecycle, concurrency, rollback, and migration graph
  tests pass.

- [x] **Step 5: Commit runtime proof**

  ```bash
  git add src/night_voyager/identity/demo_seed.py scripts/seed_demo.py \
    scripts/register_skill_version.py scripts/run_db_tests.sh \
    tests/integration/skills/test_skill_lifecycle.py \
    tests/integration/skills/test_http_skills.py \
    tests/integration/skills/test_persisted_planning_materialization.py \
    tests/integration/skills/test_postgres_skills.py \
    tests/integration/skills/test_skill_downgrade.py \
    tests/security/test_skills_catalog.py
  git commit -m "test: prove Skill activation and runtime pin authority"
  ```

### Task B8: Integrate ADR, tooling, public docs, and local closeout

**Files:**
- Create: `docs/decisions/0009-versioned-skill-runtime-pinning.md`
- Create: `docs/reference/versioned-skills-and-runtime-pins.md`
- Create: `docs/operations/skill-governance.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DESIGN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/operations/worker-and-sse.md`
- Modify: `docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md`
- Modify: `docs/superpowers/plans/2026-07-16-versioned-skill-runtime-pinning.md`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify_release.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `tests/security/test_skills_catalog.py`
- Modify: `tests/architecture/test_skills_contract.py`
- Modify: `tests/architecture/test_collaboration_contract.py`
- Modify: `tests/architecture/test_m4a_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`

- [x] **Step 1: Write docs/tooling RED tests**

  Assert accepted ADR, installed manifest, exact seed/version counts, pin/grant
  contract, `skills-check` target, CI routing under existing context names, docs links
  and status, inspector projection, and unchanged v0.1.1 identity.

- [x] **Step 2: Run RED**

  ```bash
  uv run pytest tests/unit/test_release_surface.py \
    tests/architecture/test_skills_contract.py -q
  ```

  Expected: ADR/docs/target/release-verifier assertions fail.

- [x] **Step 3: Implement public docs and proof routing**

  `make skills-check` runs pure/contract/architecture Skill tests. Add it to the
  existing `python` job without renaming required checks. Document catalog-only vs
  runtime-bound status, owner/evaluation/activation/rollback, task/execution pin,
  legacy-unpinned migration, persisted revision materialization, and deferred PR C.

- [ ] **Step 4: Run fresh final verification**

  ```bash
  make doctor MODE=dev
  uv lock --check
  make skills-check
  uv run pytest -q -m "not database and not mke"
  uv run ruff check .
  uv run pyright
  uv build --build-constraints build-constraints.txt --require-hashes
  make db-check
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  git diff --check 69e08dd80723e8e1244fd8d6a66cc5c1de0fbc42..HEAD
  ```

  Expected: all commands exit 0, Compose has no project containers, installed-wheel
  registry loading passes, and existing collaboration/DRA/M5/browser flows remain
  green without frontend changes.

  Latest result: every listed gate except `make compose-proof` passes. The Compose
  build exits non-zero on Alpine/ARM64 after `@next/swc-linux-arm64-gnu` fails to load,
  `@next/swc-linux-arm64-musl` is unavailable, and Turbopack rejects the WASM-only
  fallback. No frontend, Compose, Dockerfile, or package-file workaround was applied.
  `make down` succeeds and `docker compose ps --all` reports no project containers.

- [x] **Step 5: Review and commit**

  Review full base-to-HEAD diff for exact five tables, pin FKs, grants, migration
  restore signatures, manifest packaging, code/DB hash equality, country projection,
  public claims, secrets/private paths, and unrelated changes. Rerun affected tests
  after any fix. If review requires a code or test correction, stage its exact file
  allowlist and create a separate focused follow-up commit before this documentation
  commit; never sweep it into the final docs commit.

  ```bash
  git add README.md README_CN.md CONTRIBUTING.md DESIGN.md Makefile \
    .github/workflows/ci.yml \
    docs/decisions/0009-versioned-skill-runtime-pinning.md \
    docs/reference/versioned-skills-and-runtime-pins.md \
    docs/operations/skill-governance.md docs/README.md \
    docs/reference/http-api-v1.md docs/reference/agent-tasks-and-events.md \
    docs/operations/database-roles.md docs/operations/worker-and-sse.md \
    docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md \
    docs/superpowers/plans/2026-07-16-versioned-skill-runtime-pinning.md \
    scripts/verify_release.py tests/unit/test_release_surface.py \
    tests/security/test_database_catalog.py tests/security/test_skills_catalog.py \
    tests/architecture/test_skills_contract.py \
    tests/architecture/test_collaboration_contract.py \
    tests/architecture/test_m4a_contract.py tests/architecture/test_m5_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "docs: complete versioned Skill runtime proof"
  ```

- [x] **Step 6: Stop at local authority-review handoff**

  Report exact base/branch/worktree/HEAD/ordered commits, diff, RED -> GREEN evidence,
  registry and installed-wheel identity, catalog/grants, seed/lifecycle/concurrency/
  rollback/downgrade proof, full commands, documentation impact, inventory, and
  remaining risks. Keep the worktree clean. Do not push, create PR, merge, tag,
  release, deploy, start PR C, or run live-provider proof.

## PR B Acceptance Checklist

- [x] Default seed creates exactly six definitions and six `1.0.0` versions; only
  the runtime-bound Skill has one seed activation. `1.0.1` enters PostgreSQL only
  through the explicit migrator-owned registration proof and begins unactivated.
- [x] Browser/API cannot invent a version, evaluator output, executable binding,
  scope, tool, hash, or activation authority.
- [x] Five Skill tables and all pin relationships are tenant-safe, immutable,
  forced-RLS, migrator-owned, and inaccessible by runtime direct DML/TRUNCATE.
- [x] Candidate/evaluation/activation/rollback is deterministic, owner-controlled,
  replay-safe, CAS-protected, and concurrency/rollback proven.
- [x] Every new task has a complete relational pin; every execution copies it;
  worker validates it before start; invalid pin never reaches an adapter or retry.
- [x] Persisted Case facts, not fixture Case facts, feed both planning operations;
  selected countries bound routes/cost/ranking/eligible projections.
- [ ] Canonical seed behavior, PR A collaboration, M1-M5, DRA, MKE, task/SSE,
  frontend, Compose, and v0.1.1 release contracts remain green.
- [x] Canonical-seed/no-pin downgrade succeeds and restores exact `0007`; explicitly
  registered `1.0.1`, any other non-seed governance, or active/terminal pin refuses
  without deleting history.
