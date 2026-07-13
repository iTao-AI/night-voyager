# M4B MKE Read-Only Consumer Design

## Goal

M4B proves one bounded compatibility boundary: Night Voyager consumes an exact,
reviewed Multimodal Knowledge Engine candidate wheel through the public v1 stdio MCP
tools and maps locator-bearing results to a Night Voyager-owned source manifest.

The output remains an untrusted candidate. M4B does not accept Evidence, create a
PlanningRun, change a Case, or connect MKE to the durable M4A worker.

```text
reviewed candidate lock + exact wheel + upstream receipt
  -> isolated Python 3.12 environment
  -> MKE stdio list/search/ask v1 tools
  -> Night Voyager-owned strict response models
  -> exact source fingerprint + tenant/pack/claim/locator projection
  -> CandidateEvidence(UNTRUSTED_CANDIDATE) | CandidateStoreNoMatch | typed failure
```

## Scope

M4B adds:

- a checked-in candidate artifact lock that pins MKE repository identity, source
  commit, package version, wheel SHA-256, upstream receipt SHA-256, artifact locator,
  and review date;
- strict Night Voyager-owned models for the consumed v1 List, Search, Ask,
  observation, and Evidence reference fields;
- a pure source-pack projector and deterministic local Evidence identity;
- a read-only consumer port plus official MCP SDK stdio adapter;
- one repository-authored synthetic text-layer PDF for the real smoke;
- fixture contracts, fake-process tests, exact-artifact verification, and one real
  installed-wheel smoke;
- isolated optional-dependency commands, safe diagnostics, cleanup proof, upgrade and
  rollback guidance;
- public-neutral reference, operations, ADR, and bilingual entry-point updates during
  implementation.

M4B does not add or change:

- `PlanningAdapter`, `AgentTask`, `AgentExecution`, worker lease/retry/fencing, SSE, or
  the deterministic M4A adapter;
- migrations, PostgreSQL roles, API routes, source-pack acceptance, planning policy,
  advisor/family authority, Case state, UI/BFF, or `/demo` wiring;
- OCR, DRA, OpenClaw, provider credentials, remote hosted services, deployment,
  release, production claims, or real study-abroad facts;
- any default evaluator, `make demo`, Compose, or required-CI dependency on MKE.

## Authority boundary

MKE owns its v1 producer contract, generic stdio lifecycle/conformance proof, source
Publication and Run references, content fingerprint, locator, and selected text.

Night Voyager owns organization, source-pack ID/version, stable source-entry ID,
publisher, snapshot date, freshness, exact claim, `EvidenceRole`, locator allowance,
tenant binding, candidate authority, acceptance, planning, human review, and decision
semantics.

MKE opaque IDs are store-local trace data and never become Night Voyager source or
Evidence identity. MKE text cannot select a tenant, claim, role, authority, executable,
state transition, or command.

The only M4B authority value is the existing
`EvidenceAuthority.UNTRUSTED_CANDIDATE`. No M4B result can construct
`accepted_synthetic_demo` or `externally_verified`, persist domain Evidence, or become
eligible for planning.

## Dependency direction

```text
proof controller -> concrete MKE adapter -> read-only EvidenceConsumer port
                                             |
                                             v
                               strict contract + pure projector

existing M4A worker -> existing PlanningAdapter -> deterministic adapter
```

The MKE consumer does not implement `PlanningAdapter` and cannot be selected from a
public task request.

Proposed modules are:

```text
src/night_voyager/evidence/
  candidate_lock.py
  mke_contract.py
  mke_models.py
  mke_projection.py
  ports.py

src/night_voyager/adapters/
  mke_readonly.py

scripts/
  verify_mke_consumer.py

fixtures/m4b/
  candidate-artifact-lock.json
  manifest.json
  responses/*.json
```

## Candidate artifact trust

M4B never builds from a moving or active MKE checkout. The checked-in candidate lock
pins:

```text
repository = iTao-AI/multimodal-knowledge-engine
source_commit = <reviewed immutable commit>
package_version = <reviewed candidate version>
wheel_sha256 = <reviewed wheel digest>
upstream_receipt_sha256 = <reviewed receipt digest>
contract = mke.*_response.v1 / mke.evidence_ref.v1
proof_mode = immutable_candidate_wheel
artifact_locator = <durable public URL | operator_supplied>
reviewed_at = <UTC review date>
```

The upstream authority must produce `mke.candidate_artifact_receipt.v1`, binding a
clean source commit, package name/version, wheel filename/byte length/SHA-256,
supported Python range, upstream consumer-proof result, the exact wheel digest consumed
by that proof, and canonical receipt digest.

Night Voyager trusts only the reviewed checked-in lock. A caller-supplied wheel and
receipt cannot establish or override trust. Before installation, the verifier checks
local input presence, receipt digest, wheel digest and length, package metadata,
supported Python range, and the upstream proof-input digest.

`artifact_locator` is either a durable public artifact URL or explicit
`operator_supplied`. If the exact artifact is unavailable, the real proof is unavailable
and stops. Contributors must not rebuild substitute bytes from a checkout.

Parallel MKE work, including OCR, is independent unless it changes the selected
candidate bytes or consumed v1 contract/runtime semantics. Candidate selection must
re-query those consumed files before implementation.

## Optional dependency isolation

The official MCP SDK is an optional extra, pinned by the Night Voyager lockfile:

```toml
[project.optional-dependencies]
mke = ["mcp>=1.28.1,<2"]
```

Default imports, API, worker, Compose, `make demo`, `make check`, and installed-wheel
proof must not install or import `mcp`. Manifest, response, identity, and projector tests
stay in the default suite.

Process tests use an `mke` marker. The default pytest selection becomes
`not database and not mke`. `make mke-check` uses a dedicated temporary
`UV_PROJECT_ENVIRONMENT`, so the optional graph does not pollute a contributor's shared
environment. A fresh no-extra installed-wheel proof runs after the optional lane.

Required GitHub contexts remain `python`, `frontend`, and `compose`. M4B adds no
cross-repository, network, expiring-artifact, or provider-credential requirement to the
ruleset.

## Query and result contracts

`EvidenceQuery` contains only caller intent and policy-owned constraints:

- organization ID;
- source-pack ID/version;
- exact claim and `EvidenceRole`;
- query text;
- allowed locator kinds;
- v1 result limit fixed to the literal value `1`.

It contains no expected source, text, match count, answer status, or other test oracle.

`CandidateEvidence` contains the local schema version, pack/source/claim projection,
validated locator, bounded selected text for the immediate caller, MKE opaque trace
references, projection status `manifest_mapped`, and an existing Night Voyager
`EvidenceRef` fixed to `UNTRUSTED_CANDIDATE`.

`CandidateStoreNoMatch` contains only the local schema version, pack/query/claim
projection, active store observation, zero Evidence, and projection status
`active_store_no_match`.

The general consumer cannot claim pack-level no-match because the MKE observation does
not enumerate active source fingerprints. The proof controller may assert
`proof_pack_no_match` only after it creates a fresh empty store, ingests exactly the one
locked manifest source, verifies active counts of one, and binds an internal setup
receipt to the manifest and candidate wheel hashes. This assertion is not a runtime
result and never means a real-world fact does not exist.

## Strict response and projection rules

Consumed response models are frozen, strict, and `extra="forbid"`. They require exact
v1 response identities, valid opaque IDs, positive revisions, fingerprint syntax,
locator and observation invariants, answer/evidence consistency, bounded counts and
text, and the public error union.

The consumer requires the three exact v1 tool names and compatible required input
fields. Additional tools or optional input fields are allowed. Missing or renamed tools,
incompatible required inputs, or changed response identities fail closed.

For every candidate, the projector:

1. strips `sha256:` and maps the fingerprint to exactly one manifest source;
2. requires query organization and pack identity to equal the manifest;
3. requires that source to allow both the exact claim and `EvidenceRole`;
4. validates locator kind and range against source and query allowances;
5. rejects duplicates, ambiguous mapping, invalid revisions, and inconsistent counts;
6. never uses MKE `source_id` or `evidence_id` as local identity.

The local `EvidenceRef.evidence_id` is UUIDv5 over canonical JSON containing the
Night Voyager organization, pack ID/version, source-entry ID, source SHA-256, exact
claim, `EvidenceRole`, locator kind/range, and selected-text SHA-256. MKE opaque IDs,
Publication revision, and Run identity are excluded so the local ID is stable across
fresh MKE stores; they remain trace fields only.

Search and Ask are separate reads without a shared snapshot token. M4B therefore uses a
disposable no-writer proof store. With `limit=1`, the proof pairs the two unique results
only when fingerprint, Publication identity/revision, Run identity, locator, and selected
text agree. M4B makes no concurrent-production snapshot claim.

## Process, diagnostics, and cleanup

Request data cannot choose executable, working directory, environment, store path,
upstream ref, timeout, or cleanup scope.

Fixed bounds are:

- startup deadline: 60 seconds;
- per-tool deadline: 60 seconds;
- total proof deadline: 5 minutes;
- request limit: `1`, with at most one Evidence result per call;
- parsed response: at most 1 MiB per call;
- selected Evidence text: at most 64 KiB per result and 1 MiB total;
- captured MKE stderr: at most 64 KiB;
- controller stdout/stderr: hard bounded.

The verifier emits safe stderr progress for
`artifact_verify -> env_create -> wheel_install -> store_setup -> initialize -> discover
-> search -> ask -> cleanup`. Each stage reports `started`, `passed`, or `failed` with
bounded elapsed time. Timing is excluded from deterministic receipt hashing. There is no
verbose payload dump.

The verifier owns only its temporary environment, fresh MKE store, setup files, and
consumer invocation. The consumer owns only its SDK session and child stdio transport.
Neither may read, change, or clean an operator's existing MKE store, cache, repository,
or worktree.

On every exit path, the consumer closes its session and applies bounded
terminate/wait/kill fallback to the owned child. The verifier removes only owned state.
`mke_cleanup_failed` overrides an earlier public failure because cleanup is the terminal
safety result.

Failure stdout is exactly:

```json
{"schema_version":"night_voyager.m4b_proof.v1","status":"failed","code":"<stable_code>"}
```

Stderr may contain `FAILED CHECK`, `stage`, `code`, `expected`, `observed`, and a
concrete recovery command. It must not contain absolute paths, Evidence text,
environment values, traceback, exception strings, credentials, or MKE opaque IDs.

Stable failures distinguish missing artifact inputs, candidate mismatch, contract or
response incompatibility, empty/no-active/active-no-match observations, manifest
mapping/role/locator mismatch, source snapshot change, startup/tool timeout, transport,
server exit, output bound, cleanup failure, and unknown consumer failure. M4B is not
connected to AgentTask retry policy and performs no automatic retry.

## Canonical commands and developer journey

The public entrypoints are:

```bash
make mke-doctor MKE_WHEEL=/path/to/candidate.whl MKE_RECEIPT=/path/to/receipt.json
make mke-artifact-check MKE_WHEEL=/path/to/candidate.whl MKE_RECEIPT=/path/to/receipt.json
make mke-check
make mke-consumer-proof MKE_WHEEL=/path/to/candidate.whl MKE_RECEIPT=/path/to/receipt.json
```

`mke-doctor` validates Python 3.12, `uv`, artifact identity, supported Python metadata,
setup/server entrypoints, and temporary-directory writability without ingest or process
startup. `mke-artifact-check` validates identity only. `mke-check` runs fake-process
contracts in an isolated optional environment. `mke-consumer-proof` runs the exact
candidate smoke.

Targets are: first actionable doctor result within 5 seconds when local files exist,
artifact identity within 30 seconds, contract hello world within 3 minutes, and the real
proof within its 5-minute controller deadline. No cold-start reproducibility time is
claimed while the artifact is operator-supplied.

The maintainer runbook records current and previous reviewed candidates plus review
date. Upgrade changes wheel, receipt, lock, and fixtures atomically, reviews consumed v1
diffs, then reruns artifact, contract, real, and no-extra gates. Rollback restores the
previous reviewed lock and exact artifact without changing any operator store. If that
artifact is unavailable, the real proof is marked unavailable and stops.

## Required evidence

Tests must cover:

- strict lock/manifest/receipt/hash/path/bounds contracts and public hygiene;
- golden and malformed List/Search/Ask response unions;
- tenant/pack/exact-claim/role/fingerprint/locator projection failures;
- stable UUIDv5 identity across changed MKE opaque IDs;
- store-level no-match versus empty/no-active, plus proof-only pack no-match;
- fixed `limit=1`, required-tool discovery, malformed/oversized responses;
- default no-extra import/worker behavior and isolated optional dependency use;
- normal cleanup, timeout cleanup, terminate/wait/kill fallback, and cleanup precedence;
- redacted stdout receipt and actionable but non-sensitive stderr;
- exact candidate wheel/receipt/lock agreement and same-wheel upstream proof identity;
- one positive page-located Search/Ask projection and one proof-scoped no-match in the
  owned one-source store;
- unchanged non-database, Ruff, Pyright, build, frontend, PostgreSQL, proof, Compose, and
  hosted required checks.

## Documentation and public claims

Implementation updates the bilingual READMEs, docs index,
`docs/reference/mke-readonly-consumer.md`,
`docs/operations/mke-candidate-proof.md`, this spec, and ADR 0005.

The supported public statement is limited to an exact-artifact, local, synthetic,
read-only compatibility proof. It shows that MKE locator Evidence can map to a
Night Voyager-owned manifest by source-byte hash while remaining untrusted. It does not
prove automatic Evidence acceptance, MKE-backed planning, production integration, real
study-abroad accuracy, official-source freshness, real users, adoption, SLA, or business
impact.

## Completion gate

M4B is complete only when the exact candidate lock, upstream receipt, delivered wheel,
and same-wheel upstream proof agree; the installed-wheel stdio smoke passes; positive
and proof-scoped no-match projections obey the frozen authority and identity contracts;
all failure, bound, redaction, diagnostic, timeout, and cleanup paths are proven; the
default deterministic profile and required CI remain independent and green; public docs
state the limitations; and the reviewed branch diff is clean before PR creation.

M4B then stops for a continue/kill decision. A later gate may design explicit candidate
acceptance or visible M5 integration. If the compatibility slice proves no unique
Night Voyager boundary value, the optional adapter should be removed instead of expanded.
