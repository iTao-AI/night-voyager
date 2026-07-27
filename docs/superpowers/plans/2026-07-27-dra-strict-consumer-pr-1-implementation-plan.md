# DRA Strict Consumer Prerequisite PR 1 Implementation Plan

**Goal:** Replace the Night Voyager live consumer's new-work `generic` identity with an immutable provider-free pin to DRA `generic-strict-citation@1`, while preserving all historical generic rows and prohibiting another live-provider attempt.

**Architecture:** Separate the consumer-owned exact-commit pin, outbound request identity, and producer-observed profile manifest, then evolve the existing DRA candidate ledger through migration `0011` so commit-referenced strict candidates and release-referenced legacy candidates are distinct authority branches. Reconcile and persist that identity through provider-free scenario, controller, projection, import, outcome evaluation, and readiness code without changing DRA, calling a provider, or creating a second candidate workflow.

**Tech Stack:** Python 3.12, Pydantic 2, SQLAlchemy 2, PostgreSQL 18, Alembic, pytest, FastAPI, existing Night Voyager DRA fake transport and verification scripts.

**Plan status:** Implementation complete locally; awaiting Career authority review.

## Implementation authority correction

After Task 1, an audit of the real command and transport chain found that the
original exact-file lists omitted the existing port, application, and HTTP
transport surfaces required to carry the already approved v2 strict identity.
The corrected lists below close that implementation gap. They do not add an
endpoint, business workflow, provider attempt, or product claim.

A second bounded catalog review found one stale test that assumed a function
name identifies exactly one PostgreSQL function. Task 2 now includes that test
so the approved legacy and strict overloads are checked by exact argument
identity instead. Task 5 must apply the same overload-safe identity rule to
`scripts/verify_release.py`. This correction does not change either overload
or expand the production contract.

A third bounded current/historical phrase review found one active unit
regression that still treated the historical
`Live provider proof was not run` sentence as current runbook authority. Task 5
now includes that exact test so current-surface non-claim regressions distinguish
the historical sentence from the two-attempt safe-stop boundary. Historical
release artifacts, verification guides, specs, plans, and their tests remain
unchanged.

A final current-head versus historical-`0010` scan found four active tests whose
current repository assertions stopped at migration `0010`, the old downgrade
refusal wording, or the provider-free PR A/B/C boundary. Task 5 now includes
those exact tests so current-head assertions require `0011` and the strict
consumer prerequisite while preserving the intentional historical `0007`,
`0009`, and `0010` lanes and ownership records.

## Global Constraints

- Exact repository: `https://github.com/iTao-AI/decision-research-agent`.
- Exact immutable producer commit: `01ba21f2996769e68cbc88f4bb0596740df27f6b`.
- Exact profile tuple: `generic-strict-citation`, version `1`, proof schema `dra.strict-citation-profile.v1`.
- Exact downstream contract: `dra.downstream-consumer.v1`.
- Exact fixture SHA-256: `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157`.
- Do not describe the strict profile as part of DRA release `v0.1.6`.
- Do not modify Decision Research Agent.
- Do not call a provider, read credentials, issue an operational candidate freeze, or authorize another live attempt.
- Required CI remains offline, deterministic, and provider-free.
- Migrations `0005` and `0010`, fixture bytes, and published `v0.1.0` through `v0.1.3` release artifacts remain unchanged.
- Historical v1 generic records remain readable; v1 readiness and import are not accepted for new strict work.
- Do not introduce a dependency, endpoint, table, queue, or orchestration framework.
- Every task uses RED before implementation, targeted GREEN after implementation, and a semantic local commit.
- If implementation needs a file outside the exact task lists or changes an approved contract, stop for authority review instead of silently expanding scope.

## Execution Preflight and Commit Protocol

Before Task 1, bind the authority-supplied base and fail closed:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
: "${EXPECTED_BASE_SHA:?authority-approved base SHA required}"
test "$(git rev-parse HEAD)" = "$EXPECTED_BASE_SHA"
make doctor MODE=dev
uv sync --locked
test "$(uv run alembic heads | awk '{print $1}')" = "0010"
rg -F "01ba21f2996769e68cbc88f4bb0596740df27f6b" \
  docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md
rg -F "generic-strict-citation" \
  docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md
```

Record `EXPECTED_BASE_SHA` as `BASE_SHA`. Any dirty tree, base drift, migration
head mismatch, or strict producer/profile mismatch stops before RED.

Before every task commit, run `git diff --check`, review the exact task paths,
stage only the listed paths, then run `git diff --cached --name-only`,
`git diff --cached --check`, and `git diff --cached`. After the final commit,
review `BASE_SHA..HEAD` and require a clean worktree. A RED run is valid only
when the intended assertion fails after successful collection; zero selection,
collection errors, and environment failures are stop conditions.

Before and after every Docker-backed gate, run the default
`make doctor MODE=dev` and record:

```bash
docker compose ls --all --format json
docker ps -a --no-trunc --format json
docker image ls --digests --no-trunc --format json
docker buildx du --format json
docker network ls --no-trunc --format json
docker volume ls --format json
```

Use one inline `COMPOSE_PROJECT_NAME` on every project-scoped command; do not
export it. Teardown with
`docker compose down --volumes --remove-orphans --rmi local`, verify the exact
project has no container, network, volume, or local image residue, then
separately verify the default Compose inventory. Preserve
`night-voyager_postgres-data`, shared images, and shared BuildKit cache.

---

### Task 1: Freeze the strict producer and request contracts

**Files:**
- Modify: `src/night_voyager/dra/models.py`
- Modify: `src/night_voyager/dra/live_models.py`
- Modify: `src/night_voyager/dra/__init__.py`
- Create: `fixtures/dra/live-closure-scenario-v2.json`
- Modify: `tests/unit/dra/test_models.py`
- Modify: `tests/contracts/test_dra_live_models.py`
- Modify: `tests/unit/dra/test_fixtures.py`

**Interfaces:**
- Produces: `DRA_STRICT_REPOSITORY`, `DRA_STRICT_COMMIT`, `DRA_STRICT_PROFILE_ID`, `DRA_STRICT_PROFILE_VERSION`, `DRA_STRICT_PROOF_SCHEMA`.
- Produces: `DraProducerPinV2`, `DraRunRequestIdentityV2`,
  `DraObservedProfileManifestV1`, `DraStrictConsumerIdentityV2`, and
  `DraLiveScenarioV2`.
- Produces: `DRA_STRICT_PRODUCER`, used by Tasks 2-4.
- Preserves: `DraProducerPinV1`, `DraRunRequestIdentityV1`, `DraLiveScenarioV1` as historical-read contracts.

- [x] **Step 1: Add failing producer-pin model tests**

Add tests that require the closed tuple and reject release overloading:

```python
def test_strict_producer_pin_is_exact_commit_identity() -> None:
    pin = DraProducerPinV2()
    assert pin.model_dump(mode="json") == {
        "schema": "night-voyager.dra-producer-pin.v2",
        "repository": "https://github.com/iTao-AI/decision-research-agent",
        "ref_kind": "commit",
        "ref": "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "commit": "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "consumer_contract_schema": "dra.downstream-consumer.v1",
        "consumer_fixture_sha256": DRA_FIXTURE_SHA256,
        "profile_id": "generic-strict-citation",
        "profile_version": "1",
        "proof_schema": "dra.strict-citation-profile.v1",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ref_kind", "release"),
        ("ref", "v0.1.6"),
        ("commit", DRA_LIVE_COMMIT),
        ("profile_id", "generic"),
        ("profile_version", "2"),
        ("proof_schema", "dra.downstream-consumer.v1"),
    ],
)
def test_strict_producer_pin_rejects_mixed_identity(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        DraProducerPinV2.model_validate(DraProducerPinV2().model_dump() | {field: value})
```

- [x] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
uv run pytest -q \
  tests/unit/dra/test_models.py \
  tests/contracts/test_dra_live_models.py \
  -k "strict_producer or request_identity_v2 or live_scenario_v2"
```

Expected: test collection succeeds, then assertions fail because the v2
constants and models do not exist. If the new imports cannot collect, add only
the minimal empty module/export surface needed for collection, rerun, and
record the assertion RED; an import or collection error is not RED evidence.

- [x] **Step 3: Implement the closed v2 identity models**

Add exact constants and models:

```python
DRA_STRICT_REPOSITORY = "https://github.com/iTao-AI/decision-research-agent"
DRA_STRICT_COMMIT = "01ba21f2996769e68cbc88f4bb0596740df27f6b"
DRA_STRICT_PROFILE_ID = "generic-strict-citation"
DRA_STRICT_PROFILE_VERSION = "1"
DRA_STRICT_PROOF_SCHEMA = "dra.strict-citation-profile.v1"


class DraProducerPinV2(FrozenModel):
    schema: Literal["night-voyager.dra-producer-pin.v2"] = (
        "night-voyager.dra-producer-pin.v2"
    )
    repository: Literal[
        "https://github.com/iTao-AI/decision-research-agent"
    ] = DRA_STRICT_REPOSITORY
    ref_kind: Literal["commit"] = "commit"
    ref: Literal[
        "01ba21f2996769e68cbc88f4bb0596740df27f6b"
    ] = DRA_STRICT_COMMIT
    commit: Literal[
        "01ba21f2996769e68cbc88f4bb0596740df27f6b"
    ] = DRA_STRICT_COMMIT
    consumer_contract_schema: Literal["dra.downstream-consumer.v1"] = (
        DRA_CONTRACT_SCHEMA
    )
    consumer_fixture_sha256: Literal[
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    ] = DRA_FIXTURE_SHA256
    profile_id: Literal["generic-strict-citation"] = DRA_STRICT_PROFILE_ID
    profile_version: Literal["1"] = DRA_STRICT_PROFILE_VERSION
    proof_schema: Literal["dra.strict-citation-profile.v1"] = (
        DRA_STRICT_PROOF_SCHEMA
    )


class DraRunRequestIdentityV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-run-request-identity.v2"]
    profile_id: Literal["generic-strict-citation"]
    request_sha256: Sha256


class DraObservedProfileManifestV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-observed-profile-manifest.v1"]
    profile_id: Literal["generic-strict-citation"]
    profile_version: Literal["1"]


class DraStrictConsumerIdentityV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-strict-consumer-identity.v2"]
    producer: DraProducerPinV2
    request: DraRunRequestIdentityV2
    observed_profile: DraObservedProfileManifestV1
```

Use validators to require the requested, observed, and pinned profile id to
match and the observed manifest version to equal the pinned version. The proof
schema remains a consumer-owned exact-commit pin; do not model it as a DRA
request, manifest, status, or result field.

- [x] **Step 4: Add and validate the provider-free v2 scenario**

Create `fixtures/dra/live-closure-scenario-v2.json` with:

- the exact strict producer tuple;
- `profile_id="generic-strict-citation"`;
- a provider-free projection of
  `GET /api/profiles/generic-strict-citation` whose
  `profile.profile_id="generic-strict-citation"` and
  `profile.version="1"`;
- one cited public HTTPS Evidence row;
- one canonical artifact whose exact URL is present in the report;
- the existing four non-claims;
- no provider credential, trace, or content outside the synthetic fixture.

Add a `DraLiveScenarioV2` validator that rejects:

```python
if (
    self.status.profile_id != self.producer.profile_id
    or self.profile_manifest.profile_id != self.producer.profile_id
    or self.profile_manifest.profile_version != self.producer.profile_version
):
    raise ValueError("dra_strict_profile_identity_invalid")
```

Reject a local proof-schema mismatch against `DraProducerPinV2` separately.
The fixture must not imply that DRA returned `proof_schema`.

- [x] **Step 5: Run focused GREEN**

Run:

```bash
uv run pytest -q \
  tests/unit/dra/test_models.py \
  tests/contracts/test_dra_live_models.py \
  tests/unit/dra/test_fixtures.py
```

Expected: all selected tests pass and the historical v1 fixture digest remains unchanged.

- [x] **Step 6: Commit the contract slice**

```bash
git add \
  src/night_voyager/dra/models.py \
  src/night_voyager/dra/live_models.py \
  src/night_voyager/dra/__init__.py \
  fixtures/dra/live-closure-scenario-v2.json \
  tests/unit/dra/test_models.py \
  tests/contracts/test_dra_live_models.py \
  tests/unit/dra/test_fixtures.py
git commit -m "feat: freeze DRA strict consumer identity"
```

### Task 2: Add migration `0011` and durable strict candidate authority

**Files:**
- Create: `migrations/versions/0011_dra_strict_consumer_identity.py`
- Modify: `src/night_voyager/dra/ports.py`
- Modify: `src/night_voyager/dra/postgres.py`
- Modify: `tests/integration/dra/test_dra_live_migration.py`
- Create: `tests/integration/dra/test_dra_strict_migration.py`
- Modify: `tests/integration/dra/test_live_outcome_projection.py`
- Modify: `tests/integration/dra/test_postgres_mixed_snapshot.py`
- Modify: `tests/security/test_dra_catalog.py`
- Modify: `tests/security/test_rls_isolation.py`
- Modify: `tests/architecture/test_dra_contract.py`
- Modify: `tests/architecture/test_bootstrap_contract.py`
- Modify: `scripts/run_db_tests.sh`

**Interfaces:**
- Consumes: `DraStrictConsumerIdentityV2`.
- Produces: migration head `0011`.
- Produces: a strict overload of the existing
  `app.import_dra_research_candidate(...)` function that carries repository,
  ref kind/ref, profile version, and proof schema.
- Produces: an updated `app.project_dra_live_outcome(...)` that carries the
  complete durable candidate identity into evaluation.
- Preserves: existing v1 import call and legacy rows through an explicit legacy branch.
- Produces: a closed strict import command carrying
  `DraStrictConsumerIdentityV2`, alongside the explicit legacy v1 command
  branch.

- [x] **Step 1: Freeze migration and catalog failures**

Add RED tests that require:

```python
STRICT_COLUMNS = {
    "producer_repository",
    "producer_ref_kind",
    "producer_ref",
    "profile_version",
    "proof_schema",
}


def test_strict_candidate_identity_is_durable(catalog) -> None:
    assert STRICT_COLUMNS <= catalog.columns("app.dra_research_candidates")


def test_strict_candidate_rejects_release_overload(repository) -> None:
    with pytest.raises(DBAPIError, match="NV011"):
        repository.import_candidate(strict_command(producer_release="v0.1.6"))
```

Add command-shape RED coverage proving that:

- the legacy branch accepts only `DraProducerPinV1` and
  `DraRunRequestIdentityV1`;
- the strict branch requires a complete `DraStrictConsumerIdentityV2`;
- mixed legacy/strict producer, request, or observed-profile tuples fail
  closed;
- unknown and extra fields fail closed.

Add upgrade/downgrade tests for:

- legacy v0.1.3 row;
- legacy v0.1.6 generic row;
- strict commit row;
- mixed tuple;
- downgrade with and without strict history.
- exact strict outcome projection and exact `0010` outcome shape after safe
  downgrade.
- upgrade from real `0010` legacy rows while the immutable trigger and FORCE
  RLS are enabled;
- exact before/after catalog parity when a downgrade refusal is expected.

In the same test-first change, add the closed outer mode
`scripts/run_db_tests.sh dra-strict-migration` and its exact inside mode. The
inside command must use:

```bash
PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
  tests/integration/dra/test_dra_live_migration.py \
  tests/integration/dra/test_dra_strict_migration.py \
  tests/security/test_rls_isolation.py
```

The outer mode uses one disposable task project, starts from migration `0010`,
and tears down its exact volume and local images. An unknown mode exits `2`
before Docker mutation; it must never fall through to the full database suite.

- [x] **Step 2: Run the migration RED lane**

Run:

```bash
uv run pytest -q \
  tests/security/test_dra_catalog.py \
  tests/architecture/test_bootstrap_contract.py
COMPOSE_PROJECT_NAME="night-voyager-dra-strict-pr-1-red-$$" \
  scripts/run_db_tests.sh dra-strict-migration
```

Expected: successful collection followed by failures for missing migration
`0011`, columns, constraints, and repository arguments. Zero selected tests,
collection errors, and Docker/environment failures are not valid RED evidence.

- [x] **Step 3: Implement migration `0011`**

The migration must run its ledger evolution in one Alembic transaction. It must
take an `ACCESS EXCLUSIVE` lock on `app.dra_research_candidates`, temporarily
set only that table to `NO FORCE ROW LEVEL SECURITY`, and disable only the
`dra_research_candidates_immutable` trigger before changing existing rows. It
must then:

1. add the five identity columns;
2. backfill only those five new fields on legacy rows with exact repository,
   `ref_kind="release"`, and `ref=producer_release`, preserving every prior
   column byte-for-byte;
3. allow `producer_release` to be null only for the strict commit branch;
4. add a closed branch constraint;
5. retain the current 20-argument
   `app.import_dra_research_candidate(...)` as the explicit legacy wrapper and
   add a strict expanded overload;
6. redefine `app.project_dra_live_outcome` to return candidate id,
   repository, ref kind, ref, release-or-null, commit, contract schema, fixture
   hash, profile id, profile version, proof schema, and
   `request_identity_sha256`;
7. freeze both import overloads through exact `to_regprocedure`, fixed search
   path, ACL, replay, and API/worker/PUBLIC authority tests;
8. re-enable the immutable trigger and restore FORCE RLS before the transaction
   completes;
9. fail downgrade when strict rows exist;
10. remove the strict overload and restore the exact `0010` legacy import,
    outcome-function, and constraint shape on safe downgrade.

Privilege and catalog assertions for overloaded functions must bind
`oidvectortypes(p.proargtypes)`, or an equivalent exact argument identity,
rather than assume `proname` cardinality. The worker authority assertion must
cover the exact legacy and strict
`app.import_dra_research_candidate(...)` signatures with `EXECUTE=false`, plus
the exact `app.verify_and_promote_dra_candidate(...)` signature, while
preserving the existing API/worker authority boundary.

Tests must assert `tgenabled='O'` and `relforcerowsecurity=true` after success
and after any injected migration failure. The failure lane must prove the
schema, rows, trigger, RLS, function bodies, grants, and Alembic version all
roll back together.

Extend `scripts/run_db_tests.sh` with an isolated strict-migration lane that
starts at `0010`, executes the new upgrade/downgrade parity tests, and finishes
at `0011`. Update only current-head assertions to `0011`; retain the explicit
historical `0009` and `0010` checkpoints used by older migration lanes.

The strict branch condition must be equivalent to:

```sql
producer_repository =
  'https://github.com/iTao-AI/decision-research-agent'
AND producer_ref_kind = 'commit'
AND producer_ref =
  '01ba21f2996769e68cbc88f4bb0596740df27f6b'
AND producer_release IS NULL
AND producer_commit = producer_ref
AND profile_id = 'generic-strict-citation'
AND profile_version = '1'
AND proof_schema = 'dra.strict-citation-profile.v1'
```

The legacy branch must preserve the two existing release/commit pairs and require
`profile_id="generic"`, `profile_version IS NULL`, and `proof_schema IS NULL`.

Before and after every refusal case, capture and exact-compare:

- `alembic_version`;
- relevant columns, constraints, and indexes;
- `pg_get_functiondef`, `proacl`, and `proconfig`;
- RLS and trigger flags;
- all affected candidate rows.

Run a separate empty-history safe downgrade/re-upgrade round trip. A refusal
case cannot substitute for safe downgrade proof.

- [x] **Step 4: Update the PostgreSQL adapter**

Keep the current legacy command and adapter branch explicit. Add a separate
closed strict command/adapter branch carrying `DraStrictConsumerIdentityV2`.
Only the strict branch may extend the import parameter map with:

```python
{
    "producer_repository": command.consumer_identity.producer.repository,
    "producer_ref_kind": command.consumer_identity.producer.ref_kind,
    "producer_ref": command.consumer_identity.producer.ref,
    "profile_version": command.consumer_identity.observed_profile.profile_version,
    "proof_schema": command.consumer_identity.producer.proof_schema,
}
```

The adapter must not duck-type commands, infer a strict tuple from a v1
command, or accept mixed identity.

- [x] **Step 5: Run database GREEN**

Run:

```bash
COMPOSE_PROJECT_NAME="night-voyager-dra-strict-pr-1-green-$$" \
  scripts/run_db_tests.sh dra-strict-migration
uv run pytest -q \
  tests/integration/dra/test_live_outcome_projection.py \
  tests/security/test_dra_catalog.py
make db-check
```

Expected: full migration graph, RLS, grants, downgrade, and strict import tests pass.

- [x] **Step 6: Commit the database slice**

```bash
git add \
  migrations/versions/0011_dra_strict_consumer_identity.py \
  src/night_voyager/dra/ports.py \
  src/night_voyager/dra/postgres.py \
  tests/integration/dra/test_dra_live_migration.py \
  tests/integration/dra/test_dra_strict_migration.py \
  tests/integration/dra/test_live_outcome_projection.py \
  tests/integration/dra/test_postgres_mixed_snapshot.py \
  tests/security/test_dra_catalog.py \
  tests/security/test_rls_isolation.py \
  tests/architecture/test_dra_contract.py \
  tests/architecture/test_bootstrap_contract.py \
  scripts/run_db_tests.sh
git commit -m "feat: persist DRA strict consumer identity"
```

### Task 3: Thread the strict identity through the provider-free live controller

**Files:**
- Modify: `src/night_voyager/dra/models.py`
- Modify: `src/night_voyager/dra/live_ports.py`
- Modify: `src/night_voyager/dra/live_http.py`
- Modify: `src/night_voyager/adapters/dra_readonly.py`
- Modify: `src/night_voyager/dra/live_controller.py`
- Modify: `src/night_voyager/dra/live_projection.py`
- Modify: `src/night_voyager/dra/live_fakes.py`
- Modify: `src/night_voyager/dra/fixtures.py`
- Modify: `src/night_voyager/dra/application.py`
- Modify: `src/night_voyager/interfaces/http/dra.py`
- Modify: `tests/unit/dra/test_models.py`
- Modify: `tests/unit/dra/test_application.py`
- Modify: `tests/unit/dra/test_live_capture_controller.py`
- Modify: `tests/contracts/test_dra_live_projection.py`
- Modify: `tests/contracts/test_dra_transport.py`
- Modify: `tests/integration/dra/test_http_dra.py`
- Modify: `tests/integration/dra/test_live_capture_rehearsal.py`
- Modify: `tests/integration/dra/test_governed_closure.py`

**Interfaces:**
- Consumes: `DraLiveScenarioV2`, `DraRunRequestIdentityV2`,
  `DraObservedProfileManifestV1`, and strict producer constants.
- Produces: a strict create payload with exact `profile_id` and effective-query bytes.
- Produces: a bounded read of the existing single-profile manifest, a strict
  terminal projection, and `DraCandidateImportV2`.
- Produces: `DraCandidateImportV2` in `models.py` and a closed application
  conversion into the strict port command.
- Preserves: the existing
  `/api/v1/cases/{case_id}/dra-candidates` endpoint through a closed,
  discriminated v1/v2 request contract; no endpoint is added.
- Preserves: v1 fake/fixture tests as historical compatibility only.

- [x] **Step 1: Add request and projection RED tests**

Require the fake transport to observe:

```python
assert transport.create_requests == [
    {
        "profile_id": "generic-strict-citation",
        "query": expected_effective_query,
    }
]
```

Add counterfactuals for:

- returned `profile_id="generic"`;
- observed profile-manifest `version="2"`;
- wrong proof schema in local identity;
- status/result run mismatch;
- cited Evidence URL absent from canonical artifact;
- zero cited rows.

Add RED coverage for:

- application conversion from `DraCandidateImportV2` to the closed strict port
  command;
- HTTP v1 compatibility and HTTP v2 strict success on the existing candidate
  endpoint;
- mixed-version, unknown-version, and extra-field HTTP failures;
- actual v2 transport through `NightVoyagerAuthorityGateway`, the live port,
  controller, and fake.

- [x] **Step 2: Run focused RED**

Run:

```bash
uv run pytest -q \
  tests/unit/dra/test_live_capture_controller.py \
  tests/contracts/test_dra_live_projection.py \
  tests/contracts/test_dra_transport.py \
  -k "strict or profile or cited or request_identity"
```

Expected: failures because the controller still sends `generic` and builds v1 import models.

- [x] **Step 3: Implement strict create and terminal projection**

Extend `DraLiveTransportPort`, the read-only HTTP adapter, and the fake with a
bounded allowlisted read of:

```text
GET /api/profiles/generic-strict-citation
```

Project only `profile.profile_id` and `profile.version` into
`DraObservedProfileManifestV1`. Do not add an endpoint, enumerate profiles, or
make a provider call. Replace new-work literals with scenario-owned strict
identity:

```python
create_payload = {
    "profile_id": scenario.producer.profile_id,
    "query": effective_query.decode("utf-8"),
}
```

Validate terminal status `profile_id` against the request, validate the
manifest id/version against the consumer pin, and validate `proof_schema` only
from the checked-in exact-commit pin/source contract. Do not claim the terminal
response or manifest returned a proof schema.

Build `DraCandidateImportV2` only after:

- one exact selected Evidence row;
- cited status;
- public HTTPS URL;
- exact URL present in the canonical artifact;
- same run and segment;
- exact request and producer identity.

- [x] **Step 4: Preserve zero-cited safe stop**

The provider-free zero-cited fake must emit the existing bounded
`source_selection_invalid` failure and prove:

```python
assert candidate_repository.import_calls == []
assert promotion_repository.calls == []
assert planning_repository.calls == []
```

It must not fall back to `generic`, select an uncited row, or invent a URL.

- [x] **Step 5: Run controller and rehearsal GREEN**

Run:

```bash
uv run pytest -q \
  tests/unit/dra/test_live_capture_controller.py \
  tests/contracts/test_dra_live_projection.py \
  tests/contracts/test_dra_transport.py \
  tests/integration/dra/test_live_capture_rehearsal.py \
  tests/integration/dra/test_governed_closure.py
```

Expected: strict success and zero-cited stop are both deterministic and provider-free.

- [x] **Step 6: Commit the controller slice**

```bash
git add \
  src/night_voyager/dra/models.py \
  src/night_voyager/dra/live_ports.py \
  src/night_voyager/dra/live_http.py \
  src/night_voyager/adapters/dra_readonly.py \
  src/night_voyager/dra/live_controller.py \
  src/night_voyager/dra/live_projection.py \
  src/night_voyager/dra/live_fakes.py \
  src/night_voyager/dra/fixtures.py \
  src/night_voyager/dra/application.py \
  src/night_voyager/interfaces/http/dra.py \
  tests/unit/dra/test_models.py \
  tests/unit/dra/test_application.py \
  tests/unit/dra/test_live_capture_controller.py \
  tests/contracts/test_dra_live_projection.py \
  tests/contracts/test_dra_transport.py \
  tests/integration/dra/test_http_dra.py \
  tests/integration/dra/test_live_capture_rehearsal.py \
  tests/integration/dra/test_governed_closure.py
git commit -m "feat: project DRA strict live candidates"
```

### Task 4: Version readiness, evaluation, and freeze contracts without running live acceptance

**Files:**
- Modify: `src/night_voyager/dra/live_evaluation.py`
- Modify: `src/night_voyager/dra/live_outcome.py`
- Modify: `src/night_voyager/dra/live_outcome_postgres.py`
- Modify: `src/night_voyager/dra/live_storage.py`
- Modify: `scripts/verify_dra_live_closure.py`
- Modify: `scripts/run_dra_lane.sh`
- Modify: `tests/unit/dra/test_live_evaluation.py`
- Modify: `tests/unit/dra/test_live_candidate_freeze.py`
- Modify: `tests/unit/dra/test_live_cli_authority.py`
- Modify: `tests/unit/dra/test_live_storage.py`
- Modify: `tests/unit/dra/test_live_outcome_evaluation.py`
- Modify: `tests/unit/dra/test_live_outcome_postgres.py`
- Modify: `tests/integration/dra/test_live_outcome_projection.py`

**Interfaces:**
- Consumes: strict v2 candidate and request identity.
- Produces: the successor closed readiness schema carrying the exact strict tuple.
- Produces: `DraLiveOutcomeProjectionV2` and an evaluation report bound to the
  database candidate, readiness, request, and outcome digests.
- Produces: provider-free CLI and evaluation coverage.
- Explicitly does not execute `freeze-candidate` against real retained evidence.

- [x] **Step 1: Add readiness and evaluation RED tests**

Require a strict readiness model equivalent to:

```python
assert readiness.producer == DraProducerPinV2()
assert readiness.request_identity.profile_id == "generic-strict-citation"
assert readiness.observed_profile.profile_version == "1"
assert readiness.producer.proof_schema == "dra.strict-citation-profile.v1"
```

Reject:

- old readiness schema;
- generic request identity;
- mismatched producer commit;
- missing proof schema;
- evaluation report whose candidate tuple differs from readiness.
- database outcome whose profile version, proof schema, or request hash differs
  from the readiness tuple.

- [x] **Step 2: Run focused RED**

Run:

```bash
uv run pytest -q \
  tests/unit/dra/test_live_evaluation.py \
  tests/unit/dra/test_live_candidate_freeze.py \
  tests/unit/dra/test_live_cli_authority.py \
  tests/unit/dra/test_live_storage.py \
  tests/unit/dra/test_live_outcome_evaluation.py \
  tests/unit/dra/test_live_outcome_postgres.py \
  tests/integration/dra/test_live_outcome_projection.py \
  -k "strict or readiness or producer"
```

Expected: failures because current readiness and evaluation schemas bind the generic producer.

- [x] **Step 3: Implement closed strict readiness**

Version only schemas whose canonical bytes contain producer or request identity.
The new readiness must include:

```python
class DraLiveCandidateReadinessV3(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-candidate-readiness.v3"]
    status: Literal["INCOMPLETE_PENDING_LIVE_ACCEPTANCE"]
    producer: DraProducerPinV2
    request_identity: DraRunRequestIdentityV2
    observed_profile: DraObservedProfileManifestV1
    authorization: Literal["PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"]
```

Keep Docker evidence v3 and recovery evidence v2 unchanged unless their bytes
actually contain the producer tuple.

Add `DraLiveOutcomeProjectionV2`. The PostgreSQL inspector must populate its
candidate identity only from `app.project_dra_live_outcome`; evaluation may
compare scenario/readiness data but must never refill missing durable fields.
The evaluation report binds:

- `candidate_id`;
- canonical durable-candidate identity SHA-256;
- readiness SHA-256;
- request-identity SHA-256;
- canonical outcome-projection SHA-256.

Add field-by-field counterfactuals for candidate, readiness, outcome, and
evaluation profile version, proof schema, and request hash.

- [x] **Step 4: Close CLI command boundaries**

Update provider-free CLI modes to accept only:

- checked-in scenario v2;
- externally supplied provider-free evidence where already required;
- the exact closed command allowlist.

Add a regression that monkeypatches the provider create port and proves:

```python
with pytest.raises(SystemExit):
    main(["freeze-candidate", "--readiness", "legacy-v2.json"])
assert provider_create_calls == []
```

Do not add or execute a new live command.

- [x] **Step 5: Run the full DRA lane**

Run:

```bash
make dra-check
```

Expected: all historical generic, current provider-free closure, strict success,
zero-cited stop, evaluation, readiness, and recovery tests pass.

- [x] **Step 6: Commit the readiness slice**

```bash
git add \
  src/night_voyager/dra/live_evaluation.py \
  src/night_voyager/dra/live_outcome.py \
  src/night_voyager/dra/live_outcome_postgres.py \
  src/night_voyager/dra/live_storage.py \
  scripts/verify_dra_live_closure.py \
  scripts/run_dra_lane.sh \
  tests/unit/dra/test_live_evaluation.py \
  tests/unit/dra/test_live_candidate_freeze.py \
  tests/unit/dra/test_live_cli_authority.py \
  tests/unit/dra/test_live_storage.py \
  tests/unit/dra/test_live_outcome_evaluation.py \
  tests/unit/dra/test_live_outcome_postgres.py \
  tests/integration/dra/test_live_outcome_projection.py
git commit -m "test: bind DRA strict readiness authority"
```

### Task 5: Reconcile public documentation and run the complete prerequisite gates

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DESIGN.md`
- Modify: `docs/README.md`
- Modify: `docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md`
- Modify: `docs/operations/dra-consumer-proof.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/reference/dra-governed-evidence.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/superpowers/specs/2026-07-25-dra-v0-1-6-governed-live-closure-design.md`
- Modify: `docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md`
- Modify: `docs/superpowers/plans/2026-07-27-dra-strict-consumer-pr-1-implementation-plan.md`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `tests/architecture/test_dra_contract.py`
- Modify: `tests/architecture/test_collaboration_contract.py`
- Modify: `tests/architecture/test_m4a_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`
- Modify: `tests/unit/dra/test_proof_controller.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: implemented strict provider-free contract and migration head `0011`.
- Produces: truthful current documentation and final PR 1 evidence.
- Preserves: published release documents and the no-third-attempt boundary.

- [x] **Step 1: Add documentation-governance RED assertions**

Require current docs to say all of:

```text
DRA strict profile is pinned to exact post-release commit
generic-strict-citation@1
dra.strict-citation-profile.v1
two bounded live attempts stopped before candidate import
no third provider attempt is authorized
strict live acceptance remains incomplete
```

Require docs not to say the strict profile is included in DRA `v0.1.6`.
Current runbook assertions must reject the stale sentence
`Live provider proof was not run` while leaving historical surfaces unchanged.

- [x] **Step 2: Run documentation RED**

Run:

```bash
uv run pytest -q \
  tests/architecture/test_documentation_governance.py \
  tests/architecture/test_dra_contract.py
```

Expected: stale current-status and missing strict-identity assertions fail.

- [x] **Step 3: Update current public documentation**

Synchronize ADR, operations, reference, design, root discovery, and plan/spec
status. Preserve historical checklist text as historical where necessary; add a
clearly labelled current-runtime correction rather than rewriting the past.
Update `scripts/verify_release.py` to identify both import overloads by exact
argument identity without collapsing rows by `proname`.
Document the existing candidate endpoint's closed v1/v2 request contract,
migration `0011` as the current head, strict overload grants/RLS, and safe
downgrade boundary.
Before the final documentation commit, run one targeted `document-release`
audit over README discoverability, ADR/reference/operations accuracy, exact
commands, relative links, and the no-third-attempt/non-release claims. Record
the result in the PR `Documentation impact`. The operations documentation must
also expose the focused `dra-strict-migration` database mode and its exact
scope.

- [x] **Step 4: Run all local gates**

The focused commands above are diagnostic evidence. This block is the
authoritative final non-Compose evidence for PR 1:

```bash
uv lock --check
uv run ruff check .
uv run pyright
make dra-check
make db-check
make check
make proof
uv run python scripts/verify_release.py --tree-mode development
git diff --check "$(git merge-base HEAD origin/main)"..HEAD
```

Expected: all commands exit zero.

- [x] **Step 5: Run one normal task-scoped Compose proof**

Preflight host and Docker VM space, then run:

```bash
COMPOSE_PROJECT_NAME="night-voyager-dra-strict-pr-1-$$" make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-dra-strict-pr-1-$$" \
  docker compose --profile browser-proof \
  down --volumes --remove-orphans --rmi local
COMPOSE_PROJECT_NAME="night-voyager-dra-strict-pr-1-$$" \
  docker compose ps --all
docker compose ps --all
```

Expected:

- no proxy/source/config override;
- strict provider-free DRA lane passes;
- default and task project inventories are empty after teardown;
- `night-voyager_postgres-data`, shared images, and cache remain.

Record the global pre/post inventories defined in the execution protocol and
confirm the exact task project plus default Compose inventories are empty.

- [x] **Step 6: Verify immutable boundaries**

Confirm:

- migration `0005` digest unchanged;
- `fixtures/dra/downstream-consumer-contract-v1.json` digest unchanged;
- `docs/releases/v0.1.0.md` through `docs/releases/v0.1.3.md` unchanged;
- corresponding verification guides unchanged;
- no dependency or lockfile change;
- no provider, credential, live readiness, tag, release, or deploy action.

- [x] **Step 7: Commit documentation and verification**

```bash
git add \
  README.md README_CN.md DESIGN.md docs/README.md \
  docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md \
  docs/operations/dra-consumer-proof.md docs/operations/database-roles.md \
  docs/reference/dra-governed-evidence.md docs/reference/http-api-v1.md \
  docs/superpowers/README.md \
  docs/superpowers/specs/2026-07-25-dra-v0-1-6-governed-live-closure-design.md \
  docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md \
  docs/superpowers/plans/2026-07-27-dra-strict-consumer-pr-1-implementation-plan.md \
  tests/architecture/test_collaboration_contract.py \
  tests/architecture/test_documentation_governance.py \
  tests/architecture/test_dra_contract.py \
  tests/architecture/test_m4a_contract.py \
  tests/architecture/test_m5_contract.py \
  tests/unit/dra/test_proof_controller.py \
  tests/unit/test_release_surface.py \
  scripts/verify_release.py
git commit -m "docs: publish DRA strict consumer prerequisite"
```

## PR 1 Completion Gate

Stop for authority review with:

- exact base and final HEAD;
- ordered commits;
- exact changed-file list and diff stat;
- RED and GREEN evidence per task, including selected/passed/failed counts;
- full gate results, including selected/passed/failed counts; elapsed time is
  diagnostic only;
- migration upgrade/downgrade evidence;
- strict and legacy identity matrix;
- historical digest evidence;
- Docker before/after inventory;
- explicit confirmation that provider attempts remain unchanged and no operational
  candidate freeze occurred.

Do not push or create a pull request until separate publication authorization.
