# M4B MKE Read-Only Consumer Implementation Plan

**Implementation status:** Complete

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Do not use
> subagents unless the user separately requests them.

**Goal:** Add one exact-artifact, local, synthetic, read-only MKE v1 consumer proof that
maps locator-bearing results to a Night Voyager source manifest while preserving
`UNTRUSTED_CANDIDATE` authority and leaving the default deterministic product path MKE-free.

**Architecture:** Strict project-owned response and candidate models sit behind a pure
projection boundary. An optional official MCP SDK adapter performs bounded stdio reads; a
separate maintainer verifier owns wheel identity, temporary MKE installation/store setup,
real smoke orchestration, receipt emission, and cleanup. Nothing connects this consumer to
`PlanningAdapter`, AgentTask, PostgreSQL, HTTP, Compose, or `/demo`.

**Tech Stack:** Python 3.12.13, Pydantic 2, official `mcp` 1.x optional extra, `uv`, pytest,
Ruff, Pyright, existing Night Voyager proof infrastructure.

## Global Constraints

- Start implementation only from clean `main` after the M4B spec, ADR 0005, and this
  public implementation plan have merged. Do not stack implementation on the unmerged
  docs branch.
- The MKE prerequisite must already be merged and must have produced an independently
  verified exact wheel plus `mke.candidate_artifact_receipt.v1` from its clean merge commit.
- Re-query both repositories immediately before execution. Stop if consumed MKE v1
  schemas/runtime differ from the reviewed candidate receipt or if the Night Voyager spec
  has materially changed.
- `mcp>=1.28.1,<2` is an optional extra only. Default sync/import/API/worker/Compose/demo,
  installed-wheel proof, and required fixture tests remain functional without it.
- Default pytest selection is exactly `not database and not mke`; real database tests stay
  in `make db-check`; optional fake-process tests stay in `make mke-check`.
- M4B query limit is literal `1`; startup/tool deadlines are 60 seconds and the verifier
  total deadline is 5 minutes.
- Response bound is 1 MiB per call; selected text is at most 64 KiB per result and 1 MiB
  total; captured server stderr is at most 64 KiB.
- Candidate authority is always existing `EvidenceAuthority.UNTRUSTED_CANDIDATE`.
- No migrations, database grants, API routes, task modes, worker behavior, SSE, frontend,
  Compose service, M5, provider credentials, deployment, release, or production claim.
- The real artifact smoke is an explicit local acceptance gate, not a required hosted or
  cross-repository context. Required check names remain `python`, `frontend`, `compose`.
- Public failure stdout and proof receipts contain no paths, query/source text, random MKE
  IDs, stderr, environment, traceback, exception strings, hostname, username, or secret.
- Every task uses TDD, stages exact paths, and creates one local commit after its own GREEN.
- Before implementation, mechanically land this approved plan at
  `docs/superpowers/plans/2026-07-13-m4b-mke-readonly-consumer.md`, review the docs-only
  diff, and merge the M4B spec, ADR 0005, plan, docs index, and approved repository-rule
  adjustment through a PR. Implement and merge the MKE prerequisite separately; only its
  exact merge artifact may unlock Night Voyager Task 1.
- The repository-rule adjustment is one line in `AGENTS.md`: PR titles use concise English
  Conventional Commit wording unless the user explicitly requests otherwise. Preserve the
  existing rule that PR bodies default to Simplified Chinese with English section headings.

---

## File and responsibility map

### Pure product-owned boundary

- `src/night_voyager/evidence/__init__.py`: intentional public exports only.
- `src/night_voyager/evidence/mke_contract.py`: strict consumed MKE v1 response models.
- `src/night_voyager/evidence/mke_models.py`: manifest, query, candidate, trace, no-match,
  and typed failure models.
- `src/night_voyager/evidence/mke_projection.py`: pure fingerprint/tenant/pack/claim/role/
  locator projection and deterministic UUIDv5 identity.
- `src/night_voyager/evidence/ports.py`: read-only async consumer protocol.
- `src/night_voyager/evidence/candidate_lock.py`: strict checked-in lock and upstream receipt
  parsing plus pre-install artifact identity verification.

### Optional process boundary and verifier

- `src/night_voyager/adapters/mke_readonly.py`: official MCP SDK stdio implementation,
  bounded stderr, typed normalization, and cleanup mapping.
- `scripts/verify_mke_consumer.py`: internal subcommands `record-lock`, `doctor`,
  `artifact-check`, and `proof`; owns temporary environment/store and redacted receipt.
- `scripts/run_mke_lane.sh`: isolated `UV_PROJECT_ENVIRONMENT` wrapper for marked tests
  and the real candidate-wheel proof.
- `tests/fixtures/m4b/fake_mke_server.py`: deterministic fake stdio MCP process.

### Checked-in proof inputs

- `fixtures/m4b/candidate-artifact-lock.json`: actual reviewed MKE artifact identity.
- `fixtures/m4b/manifest.json`: one strict Night Voyager source/claim/locator contract.
- `fixtures/m4b/smoke-assertions.json`: test-only positive/no-match queries and expected
  statuses; never loaded by runtime `EvidenceQuery`.
- `fixtures/m4b/sources/australia-program-fit.pdf`: one deterministic repository-authored
  synthetic text-layer PDF.
- `fixtures/m4b/responses/*.json`: minimal consumer-owned v1 response fixtures.
- `scripts/generate_m4b_fixture.py`: deterministic no-dependency PDF generator.

### Tests and documentation

- `tests/architecture/test_m4b_contract.py`
- `tests/contracts/test_mke_v1_contract.py`
- `tests/contracts/test_mke_projection.py`
- `tests/contracts/test_mke_candidate_artifact.py`
- `tests/integration/adapters/test_mke_readonly_smoke.py`
- `tests/integration/adapters/test_mke_candidate_wheel.py`
- affected existing architecture/release tests, Makefile, CI, pyproject, and lockfile.
- `docs/reference/mke-readonly-consumer.md`
- `docs/operations/mke-candidate-proof.md`
- bilingual README, docs index, CONTRIBUTING, ADR implementation status, release verifier.

## Frozen interfaces

### Query and projection types

```python
type LocatorKind = Literal["page", "timestamp_ms"]

class EvidenceQuery(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    source_pack_id: UUID
    source_pack_version: PositiveInt
    claim: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    evidence_role: EvidenceRole
    query: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    allowed_locator_kinds: tuple[LocatorKind, ...]
    limit: Literal[1] = 1

class MkeTraceV1(FrozenModel):
    evidence_id: str
    source_id: str
    publication_id: str
    publication_revision: PositiveInt
    run_id: str

class CandidateEvidence(FrozenModel):
    schema_version: Literal["night_voyager.candidate_evidence.v1"]
    source_pack_id: UUID
    source_pack_version: PositiveInt
    source_entry_id: UUID
    claim: str
    evidence_role: EvidenceRole
    locator: PageLocatorV1 | TimestampLocatorV1
    selected_text: str
    trace: MkeTraceV1
    projection_status: Literal["manifest_mapped"]
    evidence_ref: EvidenceRef

class CandidateStoreNoMatch(FrozenModel):
    schema_version: Literal["night_voyager.candidate_store_no_match.v1"]
    organization_id: UUID
    source_pack_id: UUID
    source_pack_version: PositiveInt
    claim: str
    evidence_role: EvidenceRole
    query_sha256: str
    observation_state: Literal["active"]
    projection_status: Literal["active_store_no_match"]
```

The fixed UUID namespace is
`UUID("bb82fb65-face-585c-90df-ec155d9580f3")`.

### Closed public failure codes

The adapter, pure projector, and proof controller use this closed public code set; stage
detail belongs only to bounded stderr and must not create ad hoc public codes:

```python
type MkeFailureCode = Literal[
    "mke_candidate_inputs_missing",
    "mke_candidate_mismatch",
    "mke_environment_failed",
    "mke_install_failed",
    "mke_store_setup_failed",
    "mke_contract_incompatible",
    "mke_response_invalid",
    "mke_store_empty",
    "mke_no_active_publication",
    "mke_active_store_no_match",
    "mke_manifest_mapping_failed",
    "mke_evidence_role_mismatch",
    "mke_locator_mismatch",
    "mke_source_snapshot_changed",
    "mke_snapshot_pair_mismatch",
    "mke_startup_timeout",
    "mke_tool_timeout",
    "mke_transport_failed",
    "mke_server_exit",
    "mke_output_limit_exceeded",
    "mke_cleanup_failed",
    "mke_consumer_failed",
]
```

`mke_active_store_no_match` is a proof failure only when the positive assertion unexpectedly
finds no result. A general active-store zero result remains the typed success-side
`CandidateStoreNoMatch`; the proof's expected absent-token path remains a successful
`proof_pack_no_match` assertion.

### Consumer port

```python
class EvidenceConsumer(Protocol):
    async def initialize(self) -> ListLibrariesResponseV1: ...
    async def search(self, query: EvidenceQuery) -> SearchLibraryResponseV1: ...
    async def ask(self, query: EvidenceQuery) -> AskLibraryResponseV1: ...
    async def aclose(self) -> None: ...
```

### Projection functions

```python
def project_search_candidate(
    query: EvidenceQuery,
    manifest: M4BManifestV1,
    response: SearchLibrarySuccessV1,
) -> CandidateEvidence | CandidateStoreNoMatch: ...

def project_ask_candidate(
    query: EvidenceQuery,
    manifest: M4BManifestV1,
    response: AskLibrarySuccessV1,
) -> CandidateEvidence | CandidateStoreNoMatch: ...

def require_paired_candidate(
    search: CandidateEvidence,
    ask: CandidateEvidence,
) -> CandidateEvidence: ...
```

## Task 1: Implement strict manifest, query, and MKE v1 response contracts

**Files:**

- Create: `src/night_voyager/evidence/__init__.py`
- Create: `src/night_voyager/evidence/mke_contract.py`
- Create: `src/night_voyager/evidence/mke_models.py`
- Create: `tests/contracts/test_mke_v1_contract.py`
- Create: `fixtures/m4b/responses/list-active.json`
- Create: `fixtures/m4b/responses/search-match.json`
- Create: `fixtures/m4b/responses/search-no-match.json`
- Create: `fixtures/m4b/responses/ask-match.json`
- Create: `fixtures/m4b/responses/ask-no-match.json`
- Create: `fixtures/m4b/manifest.json`

**Interfaces:** Produces the frozen types above plus strict `M4BManifestV1`,
`M4BSourceEntryV1`, candidate failures, MKE locator/Evidence/observation/success/error/root
response types. No file in this task imports `mcp`, FastAPI, SQLAlchemy, asyncpg, or adapters.

- [ ] **Step 1: Write RED strict-contract tests**

Tests must require exact schema literals:

```python
assert ListLibrariesResponseV1.model_validate(payload).root.ok is True
assert SearchLibraryResponseV1.model_validate(search).root.results[0].locator.kind == "page"
assert AskLibraryResponseV1.model_validate(ask).root.answer_status == "evidence_found"
assert EvidenceQuery.model_validate({**query, "limit": 2})  # must raise ValidationError
```

Parametrize unknown/missing/wrong-type fields, invalid ID prefixes, invalid fingerprint,
non-positive revision, invalid page/timestamp intervals, observation/count mismatch,
Search count beyond observation, Ask status/Evidence mismatch, text over 1,000,000 chars,
duplicate source IDs/fingerprints, path traversal, invalid SHA, unsupported media type,
duplicate locator kinds, and query/manifest identity mismatch.

- [ ] **Step 2: Run RED**

```bash
uv run pytest -q tests/contracts/test_mke_v1_contract.py
```

Expected: collection fails because `night_voyager.evidence` does not exist.

- [ ] **Step 3: Implement minimal strict models**

Mirror only consumed public fields from the approved MKE v1 schemas. Use
`ConfigDict(frozen=True, extra="forbid", strict=True)`, discriminated locator/error unions,
and validators equivalent to the source contract. Manifest entries must be relative,
traversal-free, unique, exact-hash, one source only, `application/pdf`, and bind one exact
claim plus `EvidenceRole.PROGRAM_FIT` and page locator range `[1, 1]` for the smoke.

- [ ] **Step 4: Run GREEN and static checks**

```bash
uv run pytest -q tests/contracts/test_mke_v1_contract.py
uv run ruff check src/night_voyager/evidence tests/contracts/test_mke_v1_contract.py
uv run pyright src/night_voyager/evidence tests/contracts/test_mke_v1_contract.py
```

- [ ] **Step 5: Commit**

```bash
git add src/night_voyager/evidence/__init__.py \
  src/night_voyager/evidence/mke_contract.py \
  src/night_voyager/evidence/mke_models.py \
  tests/contracts/test_mke_v1_contract.py \
  fixtures/m4b/manifest.json fixtures/m4b/responses
git commit -m "feat: 冻结 M4B Evidence 消费合同"
```

## Task 2: Implement deterministic source-pack projection

**Files:**

- Create: `src/night_voyager/evidence/mke_projection.py`
- Create: `src/night_voyager/evidence/ports.py`
- Create: `tests/contracts/test_mke_projection.py`

**Interfaces:** Consumes Task 1 models; produces the three frozen projection functions and
`EvidenceConsumer` protocol. Later tasks must not bypass them.

- [ ] **Step 1: Write RED projection tests**

Require:

```python
candidate = project_search_candidate(query, manifest, search)
assert candidate.evidence_ref.authority is EvidenceAuthority.UNTRUSTED_CANDIDATE
expected_identity = {
    "organization_id": str(query.organization_id),
    "source_pack_id": str(query.source_pack_id),
    "source_pack_version": query.source_pack_version,
    "source_entry_id": str(manifest.sources[0].entry_id),
    "source_sha256": manifest.sources[0].sha256,
    "claim": query.claim,
    "evidence_role": query.evidence_role.value,
    "locator": {"kind": "page", "start": 1, "end": 1},
    "selected_text_sha256": hashlib.sha256(
        search.root.results[0].text.encode("utf-8")
    ).hexdigest(),
}
expected_name = json.dumps(
    expected_identity,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
assert candidate.evidence_ref.evidence_id == uuid5(
    UUID("bb82fb65-face-585c-90df-ec155d9580f3"), expected_name
)
assert require_paired_candidate(candidate, ask_candidate) == candidate
```

The test computes the expected UUID independently with stdlib `hashlib`, `json`, and
`uuid5`; it must not call the production identity helper under test. The namespace is
`bb82fb65-face-585c-90df-ec155d9580f3` and the canonical JSON fields are those specified
by ADR 0005.
Add counterfactuals for organization/pack/version/exact-claim/role mismatch, missing or
ambiguous fingerprint, duplicate Evidence, locator kind/range, selected-text hash change,
Search/Ask fingerprint/publication/revision/run/locator/text mismatch, and changed random
MKE IDs. Changed opaque IDs must preserve local UUID; changed claim/locator/text must change it.

Require `empty` and `no_active_publication` to raise typed failures. Only active plus zero
results may produce `CandidateStoreNoMatch`; no runtime function may emit
`proof_pack_no_match`.

- [ ] **Step 2: Run RED**

```bash
uv run pytest -q tests/contracts/test_mke_projection.py
```

- [ ] **Step 3: Implement the pure projector**

Canonical UUID input is exactly:

```python
identity = {
    "organization_id": str(query.organization_id),
    "source_pack_id": str(query.source_pack_id),
    "source_pack_version": query.source_pack_version,
    "source_entry_id": str(source.entry_id),
    "source_sha256": source.sha256,
    "claim": query.claim,
    "evidence_role": query.evidence_role.value,
    "locator": locator.model_dump(mode="json"),
    "selected_text_sha256": hashlib.sha256(evidence.text.encode("utf-8")).hexdigest(),
}
evidence_id = uuid5(M4B_EVIDENCE_NAMESPACE, canonical_json(identity))
```

Use the existing `EvidenceRef` and `EvidenceAuthority`; introduce no second authority enum
and no repository/application service.

- [ ] **Step 4: Run GREEN and commit**

```bash
uv run pytest -q tests/contracts/test_mke_projection.py
uv run ruff check src/night_voyager/evidence tests/contracts/test_mke_projection.py
uv run pyright src/night_voyager/evidence tests/contracts/test_mke_projection.py
git add src/night_voyager/evidence/mke_projection.py \
  src/night_voyager/evidence/ports.py tests/contracts/test_mke_projection.py
git commit -m "feat: 添加确定性 MKE candidate 投影"
```

## Task 3: Add candidate artifact identity and deterministic smoke fixture

**Files:**

- Create: `src/night_voyager/evidence/candidate_lock.py`
- Create: `scripts/generate_m4b_fixture.py`
- Create: `scripts/verify_mke_consumer.py`
- Create: `tests/contracts/test_mke_candidate_artifact.py`
- Create: `fixtures/m4b/candidate-artifact-lock.json`
- Create: `fixtures/m4b/smoke-assertions.json`
- Create: `fixtures/m4b/sources/australia-program-fit.pdf`

**Interfaces:** Produces strict `CandidateArtifactLockV1`,
`CandidateArtifactReceiptV1`, `VerifiedCandidateArtifact`, `verify_candidate_artifact`,
and internal verifier modes `record-lock`, `doctor`, `artifact-check`.

- [ ] **Step 1: Write RED artifact and fixture tests**

Require lock/receipt exact keys, 64-hex hashes, package/repository/schema literals, wheel
filename safety, receipt self-hash, wheel byte/hash/metadata agreement, source commit and
proof-input digest agreement, `operator_supplied` or HTTPS durable locator, and rejection
before installation.

Require `record-lock` to emit deterministic checked-in JSON only when wheel and receipt
already pass. It records actual reviewed values and cannot accept caller overrides for
repository, package, version, source commit, or digests.

Require the PDF generator to produce byte-identical output, one page, exact text
`Synthetic Australia program fit requires advisor evidence review.`, and the manifest's
recorded byte length/SHA. Test-only assertions must contain one positive query and one
absent-token query; they must not appear in `EvidenceQuery` or production manifest types.

- [ ] **Step 2: Run RED**

```bash
uv run pytest -q tests/contracts/test_mke_candidate_artifact.py
```

- [ ] **Step 3: Implement artifact verification and generator**

Use `zipfile.ZipFile` to inspect wheel `METADATA` and `entry_points.txt` without installing.
Require distribution `multimodal-knowledge-engine`, exact receipt version, supported Python
including 3.12, and console entry `mke = mke.cli:console_main`.

The script subcommands are:

```text
verify_mke_consumer.py record-lock --wheel PATH --candidate-receipt PATH \
  --artifact-locator operator_supplied --reviewed-at YYYY-MM-DD --output LOCK
verify_mke_consumer.py doctor --wheel PATH --candidate-receipt PATH
verify_mke_consumer.py artifact-check --wheel PATH --candidate-receipt PATH --json
```

`doctor` also checks current Python 3.12, `uv`, temporary-directory writability, lock file,
and input existence but performs no install, ingest, or server start. Missing inputs map to
`mke_candidate_inputs_missing`; identity mismatch maps to `mke_candidate_mismatch`.

- [ ] **Step 4: Generate actual locked inputs**

Use only the independently reviewed MKE merge artifact:

```bash
uv run python scripts/generate_m4b_fixture.py --output fixtures/m4b/sources/australia-program-fit.pdf
uv run python scripts/verify_mke_consumer.py record-lock \
  --wheel "$MKE_WHEEL" \
  --candidate-receipt "$MKE_RECEIPT" \
  --artifact-locator operator_supplied \
  --reviewed-at "$(date -u +%F)" \
  --output fixtures/m4b/candidate-artifact-lock.json
```

Review the generated JSON and commit actual values; no placeholder is allowed.

- [ ] **Step 5: Run GREEN and commit**

```bash
uv run pytest -q tests/contracts/test_mke_candidate_artifact.py
uv run ruff check src/night_voyager/evidence/candidate_lock.py \
  scripts/generate_m4b_fixture.py scripts/verify_mke_consumer.py \
  tests/contracts/test_mke_candidate_artifact.py
uv run pyright src/night_voyager/evidence/candidate_lock.py \
  scripts/generate_m4b_fixture.py scripts/verify_mke_consumer.py \
  tests/contracts/test_mke_candidate_artifact.py
git add src/night_voyager/evidence/candidate_lock.py \
  scripts/generate_m4b_fixture.py scripts/verify_mke_consumer.py \
  tests/contracts/test_mke_candidate_artifact.py fixtures/m4b
git commit -m "build: 固定 MKE candidate artifact 身份"
```

## Task 4: Add the isolated official MCP SDK adapter

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/night_voyager/adapters/mke_readonly.py`
- Create: `tests/fixtures/m4b/fake_mke_server.py`
- Create: `tests/integration/adapters/test_mke_readonly_smoke.py`
- Create: `scripts/run_mke_lane.sh`

**Interfaces:** Implements Task 2 `EvidenceConsumer`; produces trusted-config-only
`MkeReadOnlyConfig` and typed consumer errors. The adapter imports `mcp`; no default module does.

- [ ] **Step 1: Write RED fake-process tests**

Mark the file `pytestmark = pytest.mark.mke`. Cover exact required-tool discovery,
compatible optional inputs, fixed outbound `limit=1`, List/Search/Ask parse, malformed and
oversized response rejection, startup/tool timeout, bounded stderr overflow, nonzero exit,
normal close, a server that ignores stdin until SDK terminate/kill fallback, cleanup error
precedence, and absence of MKE path/text/IDs in typed public errors.

- [ ] **Step 2: Run RED in a clean isolated optional environment**

```bash
temp="$(mktemp -d)"
trap 'rm -rf -- "$temp"' EXIT
UV_PROJECT_ENVIRONMENT="$temp/venv" \
  uv run --extra mke pytest -q -m mke tests/integration/adapters/test_mke_readonly_smoke.py
```

Expected: FAIL because the optional extra and adapter do not exist.

- [ ] **Step 3: Add the optional dependency and adapter**

Add exactly:

```toml
[project.optional-dependencies]
mke = ["mcp>=1.28.1,<2"]
```

Regenerate `uv.lock` and review that only the expected MCP optional graph changes.

`MkeReadOnlyConfig` contains executable, database, allowed root, cwd, allowlisted child
environment, startup/tool deadlines, parsed-response bound, selected-text bound, and stderr
bound. `EvidenceQuery` cannot modify any config field. Use `mcp.client.stdio.stdio_client`,
`ClientSession`, and `StdioServerParameters`; depend on SDK-owned stdin close -> wait ->
terminate -> kill, and map any context-exit failure to `mke_cleanup_failed`.

The fake server is test-only and accepts scenario names only from its process argv. No
constructor-injected runtime test oracle exists in product models.

- [ ] **Step 4: Add isolated wrapper**

`scripts/run_mke_lane.sh` requires a first argument of `test` or `proof`, creates a fresh
temporary directory, exports `UV_PROJECT_ENVIRONMENT="$temp/venv"`, and runs
`uv sync --locked --extra mke`. `test` shifts the mode argument and executes
`uv run pytest -q -m mke "$@"` (all marked tests when no paths remain); `proof` shifts the
mode argument and executes `uv run python scripts/verify_mke_consumer.py proof "$@"`.
The wrapper removes only its freshly created directory through a trap and never touches the
shared `.venv`.

- [ ] **Step 5: Run GREEN and no-extra proof**

```bash
scripts/run_mke_lane.sh test
uv run pytest -q -m "not database and not mke"
uv run python -c 'import sys; assert "mcp" not in sys.modules; import night_voyager'
uv run ruff check src/night_voyager/adapters/mke_readonly.py \
  tests/fixtures/m4b/fake_mke_server.py \
  tests/integration/adapters/test_mke_readonly_smoke.py scripts/run_mke_lane.sh
uv run pyright src/night_voyager/adapters/mke_readonly.py \
  tests/integration/adapters/test_mke_readonly_smoke.py
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/night_voyager/adapters/mke_readonly.py \
  tests/fixtures/m4b/fake_mke_server.py \
  tests/integration/adapters/test_mke_readonly_smoke.py scripts/run_mke_lane.sh
git commit -m "feat: 添加隔离的 MKE read-only stdio adapter"
```

## Task 5: Implement the exact candidate-wheel proof

**Files:**

- Modify: `scripts/verify_mke_consumer.py`
- Create: `tests/integration/adapters/test_mke_candidate_wheel.py`
- Modify: `fixtures/m4b/smoke-assertions.json` only if real RED proves a fixture defect.

**Interfaces:** Adds internal `proof` mode and deterministic
`night_voyager.m4b_proof.v1` receipt. It consumes the actual wheel/receipt/lock and Tasks
1-4; it produces no domain persistence.

- [ ] **Step 1: Write RED controller tests**

Mark the file `pytestmark = pytest.mark.mke`. Mock only command/process boundaries. Require
stable stage sequence:

```text
artifact_verify, env_create, wheel_install, store_setup, initialize,
discover, search, ask, cleanup
```

Require total deadline, per-stage timeout, exact `uv venv` and `uv pip install` command,
installed `mke --db STORE ingest SOURCE --json`, trusted stdio command, positive and no-match
calls with `limit=1`, one-source active-count receipt, Search/Ask pairing, proof-only
pack-no-match assertion, cleanup on every failure, and cleanup precedence.

Failure stdout is exactly:

```json
{"schema_version":"night_voyager.m4b_proof.v1","status":"failed","code":"<stable_code>"}
```

Stderr uses only `FAILED CHECK`, `stage`, `code`, `expected`, `observed`, `recovery` and
bounded elapsed time. Parametrize all stable codes and forbidden sensitive values.

- [ ] **Step 2: Run RED**

```bash
scripts/run_mke_lane.sh test tests/integration/adapters/test_mke_candidate_wheel.py
```

- [ ] **Step 3: Implement minimal controller**

The verifier creates all state under one `TemporaryDirectory`, installs the exact wheel,
provisions only the committed synthetic PDF, constructs adapter config from owned paths,
uses runtime `EvidenceQuery` without expectations, and loads positive/no-match expectations
only in the proof controller. It closes the consumer before removing environment/store.

The success receipt includes only schema/status, Night Voyager pack/version, MKE package
version/source commit/wheel SHA, required tool/response schema names, bounded counts/states,
booleans for identity/contracts/mapping/pairing/no-match/redaction/cleanup, and canonical
receipt SHA. Exclude timestamps and elapsed time from the hash.

- [ ] **Step 4: Run the real exact-artifact smoke**

```bash
scripts/run_mke_lane.sh proof \
  --wheel "$MKE_WHEEL" \
  --candidate-receipt "$MKE_RECEIPT" \
  --json
```

Expected: one redacted success JSON; installed MKE uses the exact locked wheel; positive
projection yields `UNTRUSTED_CANDIDATE`; proof-scoped no-match remains bounded; all owned
processes and temporary paths are gone.

- [ ] **Step 5: Run GREEN and commit**

```bash
scripts/run_mke_lane.sh test tests/integration/adapters/test_mke_candidate_wheel.py
scripts/run_mke_lane.sh test
uv run ruff check scripts/verify_mke_consumer.py \
  tests/integration/adapters/test_mke_candidate_wheel.py
uv run pyright scripts/verify_mke_consumer.py \
  tests/integration/adapters/test_mke_candidate_wheel.py
git add scripts/verify_mke_consumer.py \
  tests/integration/adapters/test_mke_candidate_wheel.py
git commit -m "test: 证明 exact MKE candidate wheel 消费边界"
```

## Task 6: Integrate Make, pytest, CI, and release contracts

**Files:**

- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify_release.py`
- Modify: `tests/architecture/test_m2_contract.py`
- Create: `tests/architecture/test_m4b_contract.py`
- Modify affected release-verifier tests discovered by `rg`.

**Interfaces:** Adds four canonical Make targets and keeps required contexts/default lanes
artifact-free.

- [ ] **Step 1: Write RED architecture/config tests**

Require:

```python
assert pyproject["tool"]["pytest"]["ini_options"]["addopts"] == '-m "not database and not mke"'
assert set(pyproject["tool"]["pytest"]["ini_options"]["markers"]) == {
    "database: requires disposable PostgreSQL 18 roles",
    "mke: requires the optional MKE/MCP process extra",
}
```

Assert default `make check` and `python` job use `not database and not mke`; the Python job
also runs a separate `UV_PROJECT_ENVIRONMENT` optional fixture/process step but references
no MKE wheel, receipt, network endpoint, checkout, credential, or artifact download.

Assert exact targets `mke-doctor`, `mke-artifact-check`, `mke-check`,
`mke-consumer-proof`; default Make/Compose/Docker proof do not call them. Assert pure files
do not import `mcp`, M4A task/HTTP/worker files do not reference MKE, no migration `0005`,
and public spec/ADR/plan exist.

- [ ] **Step 2: Run RED**

```bash
uv run pytest -q tests/architecture/test_m2_contract.py \
  tests/architecture/test_m4b_contract.py
```

- [ ] **Step 3: Implement config and target wiring**

Make targets call:

```make
mke-doctor:
	@uv run python scripts/verify_mke_consumer.py doctor --wheel "$(MKE_WHEEL)" --candidate-receipt "$(MKE_RECEIPT)"

mke-artifact-check:
	@uv run python scripts/verify_mke_consumer.py artifact-check --wheel "$(MKE_WHEEL)" --candidate-receipt "$(MKE_RECEIPT)" --json

mke-check:
	@scripts/run_mke_lane.sh test

mke-consumer-proof:
	@scripts/run_mke_lane.sh proof --wheel "$(MKE_WHEEL)" --candidate-receipt "$(MKE_RECEIPT)" --json
```

The CI optional step runs only committed fake-process tests. `verify_release.py` checks the
optional range, locked MCP version, unchanged default imports, candidate lock/manifest
presence, no MKE Compose service, no migration, and public-hygiene scanning of new JSON/docs.

- [ ] **Step 4: Run GREEN and commit**

```bash
uv lock --check
uv run pytest -q tests/architecture/test_m2_contract.py tests/architecture/test_m4b_contract.py
uv run pytest -q -m "not database and not mke"
scripts/run_mke_lane.sh test
uv run ruff check .
uv run pyright
uv build --build-constraints build-constraints.txt --require-hashes
git add pyproject.toml uv.lock Makefile .github/workflows/ci.yml \
  scripts/verify_release.py tests/architecture/test_m2_contract.py \
  tests/architecture/test_m4b_contract.py
git commit -m "build: 集成 M4B 可选验证门禁"
```

## Task 7: Complete documentation and fresh verification

**Files:**

- Create: `docs/reference/mke-readonly-consumer.md`
- Create: `docs/operations/mke-candidate-proof.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/README.md`
- Modify: `docs/decisions/0005-mke-readonly-evidence-boundary.md`
- Modify: `docs/superpowers/plans/2026-07-13-m4b-mke-readonly-consumer.md`
- Modify documentation contract tests if required by current patterns.

**Interfaces:** Produces public role-based discovery, quick path, exact contract/runbook,
atomic upgrade/rollback, and implementation-complete plan/ADR status.

- [ ] **Step 1: Write RED documentation contract tests**

Require README wording to be optional/local/synthetic/read-only and link the runbook.
Require docs index routes: evaluator needs no MKE; contributor runs `make mke-check`;
maintainer runs artifact and real proof. Require runbook five-line quick path, all stable
codes with exact recovery command, current/previous candidate procedure, unavailable
artifact stop, and no checkout rebuild. Require bilingual boundary parity.

- [ ] **Step 2: Run RED**

Run the focused documentation tests identified by `rg` plus the new M4B contract test.

- [ ] **Step 3: Update public docs**

Set ADR 0005 `Implementation status: Implemented in M4B` only after behavior exists.
Mark the public implementation plan complete only after all gates below pass. State that
the candidate is operator-supplied unless a durable URL is actually present in the lock.

- [ ] **Step 4: Run all fresh gates**

```bash
make doctor MODE=dev
make mke-doctor MKE_WHEEL="$MKE_WHEEL" MKE_RECEIPT="$MKE_RECEIPT"
make mke-artifact-check MKE_WHEEL="$MKE_WHEEL" MKE_RECEIPT="$MKE_RECEIPT"
make mke-check
make mke-consumer-proof MKE_WHEEL="$MKE_WHEEL" MKE_RECEIPT="$MKE_RECEIPT"
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
make db-check
make check
make proof
make compose-proof
make down
docker compose ps --all
git diff --check
```

Expected: every command passes; final Compose list is empty; default gates do not require
the MKE artifact; no MKE process or owned temp directory remains.

- [ ] **Step 5: Commit docs and completion records**

```bash
git add README.md README_CN.md CONTRIBUTING.md docs/README.md \
  docs/reference/mke-readonly-consumer.md \
  docs/operations/mke-candidate-proof.md \
  docs/decisions/0005-mke-readonly-evidence-boundary.md \
  docs/superpowers/plans/2026-07-13-m4b-mke-readonly-consumer.md
git commit -m "docs: 完成 M4B MKE candidate 消费证明"
```

- [ ] **Step 6: Final branch-diff review and stop**

Compare the implementation base to HEAD. Confirm only approved M4B files changed; no
migration, API, worker, task, SSE, frontend, Compose service, provider credential,
private path, generated cache, M5 artifact, release, or deployment change exists. Report
ordered commits, RED/GREEN evidence, exact wheel/receipt identity, all gates,
documentation impact, risks, and deferred candidate acceptance/M5 work. Keep the local
branch/worktree clean; do not push or create a PR.

## Self-review checklist

- Spec coverage: Tasks 1-7 cover every authority, artifact, model, projection, process,
  no-match, cleanup, isolation, command, documentation, and completion requirement.
- Placeholder scan: the only future values are the actual MKE merge artifact identity;
  Task 3 generates and reviews them before any implementation can proceed. No placeholder
  may enter the checked-in lock.
- Type consistency: the frozen models, consumer port, projection functions, script modes,
  Make variables, marker names, failure schema, and receipt schema are consistent across
  all tasks.
- Cross-project boundary: MKE changes live only in its prerequisite plan; Night Voyager
  consumes only wheel/receipt/public commit evidence.
- YAGNI: no persistence, API, worker, UI, default runtime selection, or duplicate generic
  MKE conformance platform is introduced.
