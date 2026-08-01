# Advisor-Governed Multimodal Evidence Composition Implementation Plan

> **For the execution window:** Use the approved design and this plan as the public-neutral
> authority. Execute task by task with TDD. A passed local gate does not unlock the next slice; only
> the exact merged stage receipt does.

**Status:** Slice 0 ended in local `evaluation_invalid` safe stop; retired holdout retained; no later stage unlocked; merged PR/hosted CI/publication pending
**Goal:** Prove bounded complementary MKE Evidence value, then govern accepted input through
Night Voyager's existing advisor, PostgreSQL, planning, family-decision, timeline, execution, and
recovery authorities.
**Architecture:** Night Voyager is the only consumer and system of record. MKE and DRA remain
independent read-only evidence paths. Slice 0 is file-based and mutation-free during its sealed
evaluation window. Slice 1 adds an MKE-specific candidate and advisor decision. Slice 2 adds one
atomic Night Voyager composition operation. A generic provider framework and runtime multi-agent
system are prohibited.
**Default delivery:** six ordered PRs: A, B1, B2, C1, C2, D.

## 1. Global identity, ownership, and stop rules

### 1.1 Exact starting identities

Before landing any public document, verify:

```bash
git status --short --branch
git rev-parse HEAD main origin/main
git diff --check
uv run alembic heads
```

The reviewed planning baseline is:

- Night Voyager v0.1.5 commit `3a82721a86f65353b849e9ee93050912d0cb079a`;
- tree `bbe32e5629b2758421d80598dbca1c795934fcb5`;
- annotated tag object `44000702c75fa3002e12245b8d7f762b564db944`;
- migration head `0015`.

Producer locks:

- MKE v0.1.5 annotated tag object
  `1ca0a0b348638369e8407270ca5f363b0e551a9e`, peeled commit
  `d258c10dc40bd9eccd67c858b56f4e4cf5fe4610`;
- DRA v0.1.8 annotated tag object
  `f828606741f636bca7ddbb66244ca60019eaa3c8`, peeled commit
  `cb1f4660ee4ac7d81b04ffea014362e933487e61`.

At implementation preflight, re-read tagged archives and compute wheel, source archive, MCP schema,
tool schema, strict-profile artifact, and fixture hashes. If `main` or a tagged archive differs,
stop for architecture authority review. Never silently substitute a newer release or moving
checkout.

### 1.2 Public documents

PR A mechanically lands:

- `docs/superpowers/specs/2026-07-31-advisor-governed-multimodal-evidence-composition-design.md`;
- `docs/superpowers/plans/2026-07-31-advisor-governed-multimodal-evidence-composition-implementation.md`;
- `docs/decisions/0014-advisor-governed-multimodal-evidence-composition.md`;
- one exact index row in `docs/superpowers/README.md`.

ADR 0014 extends ADR 0005 without weakening M4B v1 compatibility, optional dependency isolation,
producer non-authority, moving-checkout prohibition, or cleanup ownership.

### 1.3 Roles

- **Architecture authority:** approves public spec/plan, reviews actual branch diff, owns stage disposition,
  and decides whether a merged receipt unlocks the next slice.
- **Execution owner:** implements one unlocked PR in an isolated worktree/branch, runs RED/GREEN and
  terminal gates, and preserves exact evidence.
- **Dataset author** (`dataset_author_id=independent-dataset-author-v3`): authors public-safe source
  material and development cases, and finalizes holdout payload plus evaluator-independent oracle
  before A4.
- **Evaluator implementer**
  (`evaluator_implementer_id=night-voyager-slice0-evaluator-v1`): sees development cases and only
  opaque, separate payload/oracle commitments until final freeze.
- **Holdout custodian/reviewer**
  (`holdout_custodian_id=independent-holdout-custodian-v3`): independently verifies and seals the
  pre-authored payload/oracle bytes in a non-mounted custody workspace, and reveals only after the
  complete evaluator and harness freeze.
- **Publication owner:** owns Draft PR lifecycle, exact-head CI binding, conditional merge, and
  task-owned cleanup after architecture review.

The evaluator implementer may not also author or custody the holdout answers used for that receipt.
Other mechanical roles may overlap only when committed receipts preserve ordering and no holdout
content was visible before evaluator freeze. The implementation report must state the actual role
mapping and `nv.slice0.one-way-reveal.v1` procedure.

The admitted package is `author_revision=3`; revisions 1 and 2 are permanently
`rejected_pre_admission`. Their author packages, sources, custody seals, and reveal inputs are
never read, copied, admitted, or reused. The DRA baseline nature is
`deterministic_public_safe_synthetic_governed_fixture`, which is a contract fixture rather than a
production or historical-user receipt claim.

The producer-native PDF proof precedes final evaluator freeze. A3 binds every admitted PDF to the
exact MKE v0.1.5 descriptor and complete Search/Read result before A4 issues
`PreRegistrationReceiptV2`.

### 1.4 Shared hard stops

Stop without scope expansion when:

- any exact producer, corpus, schema, tool, artifact, baseline, evaluator, or holdout identity
  differs;
- DRA typed baseline provenance cannot be exported without parsing Markdown;
- a required MKE query is `capped`, incomplete, non-active, or not restartable under the same frozen
  policy;
- holdout bytes were visible before evaluator freeze;
- a revealed holdout would be reused after an evaluator/threshold/mapping/source change;
- any retrieved content affects a tool call, approval, or mutation;
- any producer or browser is asked to select a Case or supply business authority;
- a stage receipt is missing, unmerged, or bound to a different commit;
- a PR would expose a route that creates an operation not yet executable in the same deployable PR;
- exact-head hosted `python`, `frontend`, or required `compose` is not terminal SUCCESS;
- cleanup cannot prove ownership.

Slice 0 outcomes `no_incremental_value`, `inconclusive`, and `evaluation_invalid` all cancel B1–D
for this direction. They do not authorize threshold relaxation, corpus replacement, or a new
holdout under the same receipt.

### 1.5 Shared PR lifecycle

Every unlocked PR follows:

```text
ordinary non-force push
-> Draft PR create/update
-> persisted title/body/head/base readback
-> exact reviewed HEAD + required checks/platform review binding
-> mark Ready only after all merge gates pass
-> conditional non-admin squash merge
-> exact merge-SHA/tree/readback
-> safe task-owned cleanup
```

The PR body uses the project's required six Simplified-Chinese headings and public-neutral
non-claims. A repair creates a new reviewed HEAD on the same Draft PR and refreshes all readbacks.
Worktree ownership is not a publication blocker. A PR never starts Ready.

For every PR, the publication owner runs a mechanical, dynamically discovered checklist rather
than hard-coding today's ruleset:

```bash
REVIEWED_HEAD="$(git rev-parse HEAD)"
REVIEWED_TREE="$(git rev-parse HEAD^{tree})"
git ls-remote origin refs/heads/main
gh api repos/iTao-AI/night-voyager/rules/branches/main
gh pr view "$PR" --json \
  title,body,state,isDraft,baseRefName,baseRefOid,headRefName,headRefOid,mergeable,mergeStateStatus
gh pr checks "$PR" --required --json name,state,bucket,link
```

Require persisted title/body format, Draft state, exact head/base, all dynamically required checks
bound to `REVIEWED_HEAD`, no unresolved platform review, clean mergeability, and the
`StageReadinessCandidateV1` body block before `gh pr ready "$PR"`. Merge only with:

```bash
gh pr merge "$PR" --squash --match-head-commit "$REVIEWED_HEAD"
```

Never use `--admin`. After merge, read back PR state/merge SHA/time/body, fetch/prune, compare
`REVIEWED_TREE` to the merge tree, require zero diff, verify exact-merge required checks, sync main
ff-only, confirm the open PR/check queue is empty, and then remove only task-owned remote/local
branch, worktree, runtime, and execution-task state. Any changed head or required context restarts
the Draft exact-head review; it does not inherit prior approval.

### 1.6 Contributor quick path

All commands run from the Night Voyager repository root. The operator supplies exact tagged source
archives; the scripts never fetch a moving checkout. The source-only MKE v0.1.5 archive is built
locally into a wheel inside `work_root`; it is not described as a release wheel asset.

```bash
umask 077
: "${MKE_SOURCE_ARCHIVE:?set the exact MKE v0.1.5 tagged source archive}"
: "${DRA_SOURCE_ARCHIVE:?set the exact DRA v0.1.8 tagged source archive}"
EVIDENCE_LOOP_RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nv-evidence-loop.XXXXXX")"
export EVIDENCE_LOOP_RUN_ROOT
chmod 700 "$EVIDENCE_LOOP_RUN_ROOT"
```

The execution owner supplies the canonical A3 MKE source-tree archive
`mke-v0.1.5.tar` (14,643,200 bytes, SHA-256
`12e0dc785723bd35e4f1ba40d3935fd4d906ae360b1e99fcecb43d24a009aa5a`) and the
exact DRA release source archive `dra-v0.1.8-source.tar.gz` (SHA-256
`ab9deaf7678571b2dda6e8275fcfe2ff69d6baab04f3ab66f84c6abdcb2a6e7f`). The
script exclusively creates the fresh `input`, `work`, `store`, and `receipts`
children and prepares and seals the exact producer/store boundary:

```bash
uv run python scripts/prepare_evidence_loop_store.py \
  --mke-source-archive "$MKE_SOURCE_ARCHIVE" \
  --mke-tag-object 1ca0a0b348638369e8407270ca5f363b0e551a9e \
  --mke-commit d258c10dc40bd9eccd67c858b56f4e4cf5fe4610 \
  --dra-source-archive "$DRA_SOURCE_ARCHIVE" \
  --dra-tag-object f828606741f636bca7ddbb66244ca60019eaa3c8 \
  --dra-commit cb1f4660ee4ac7d81b04ffea014362e933487e61 \
  --source-manifest tests/fixtures/evidence_loop/source-manifest-v1.json \
  --run-root "$EVIDENCE_LOOP_RUN_ROOT" \
  --json
```

Success prints one JSON object whose `code` is `evidence_loop_store_sealed`. It verifies source
archive/tree identity, builds the MKE wheel in `work_root`, ingests only allowlisted bytes, closes
write capability, materializes the exact read-only WAL peers while the preparation root is `0700`,
then seals `store.sqlite`, `store.sqlite-shm`, and `store.sqlite-wal` as one immutable authority
image with all files `0400` and `store_root` `0500`. Three fresh exact tagged Search/Read plus
rejected-write processes must preserve its bytes, modes, tree digest, and active-set identity. The
receipt records WAL materialization as task-owned preparation mutation plus the task-owned archive
basenames/digests and wheel/store/active-set identities. It never records the caller's external
archive path.

The evaluator implementer first completes and tests the evaluator, reveal validator, tagged-wheel
lane, frozen-suite harness, terminal verifier, and runner using development or mock structural
fixtures without access to holdout payload/oracle bytes. Development-only evaluation does not
consume a final pre-registration receipt:

```bash
uv run python scripts/evaluate_evidence_loop.py \
  --development-dataset tests/fixtures/evidence_loop/development-dataset-v1.json \
  --store-receipt "$EVIDENCE_LOOP_RUN_ROOT/receipts/sealed-mke-store-v1.json" \
  --output "$EVIDENCE_LOOP_RUN_ROOT/receipts/development-evaluation-v2.json" \
  --json
```

Only after the complete implementation is tested on a clean candidate does the evaluator
implementer issue `PreRegistrationReceiptV2`:

```bash
uv run python scripts/freeze_evidence_loop.py \
  --store-receipt "$EVIDENCE_LOOP_RUN_ROOT/receipts/sealed-mke-store-v1.json" \
  --source-manifest tests/fixtures/evidence_loop/source-manifest-v1.json \
  --development-dataset tests/fixtures/evidence_loop/development-dataset-v1.json \
  --holdout-manifest tests/fixtures/evidence_loop/holdout-manifest-v1.json \
  --dra-baseline tests/fixtures/evidence_loop/dra-governed-baseline-v1.json \
  --output "$EVIDENCE_LOOP_RUN_ROOT/receipts/pre-registration-v2.json" \
  --json
```

The success codes are `evidence_loop_development_evaluated` and
`evidence_loop_preregistered`. Only after both succeed does the independent custodian run:

```bash
: "${EVIDENCE_LOOP_CUSTODY_ROOT:?set the unmounted custodian-owned holdout root}"
uv run python scripts/reveal_evidence_loop_holdouts.py \
  --pre-registration "$EVIDENCE_LOOP_RUN_ROOT/receipts/pre-registration-v2.json" \
  --expected-pre-registration-sha256 "$CAREER_REVIEWED_PREREGISTRATION_SHA256" \
  --holdout-manifest tests/fixtures/evidence_loop/holdout-manifest-v1.json \
  --store-root "$EVIDENCE_LOOP_RUN_ROOT/store" \
  --custody-root "$EVIDENCE_LOOP_CUSTODY_ROOT" \
  --destination tests/fixtures/evidence_loop/holdout-dataset-v1.json \
  --json
```

The reveal command is the only command allowed to receive `custody_root`; it runs outside the
evaluator process, requires the frozen evaluator/tree hashes, validates the exact sealed store and
retained native runtime before custody access and again before publication, verifies the measured
custody mode plus every committed byte/hash, and copies once atomically. Global mount/index state
remains an independent custodian attestation rather than an evaluator claim. Success code:
`evidence_loop_holdouts_revealed`.

The execution owner then runs the exact tagged native evaluation and terminal verifier:

```bash
uv run python scripts/evaluate_evidence_loop.py \
  --pre-registration "$EVIDENCE_LOOP_RUN_ROOT/receipts/pre-registration-v2.json" \
  --store-root "$EVIDENCE_LOOP_RUN_ROOT/store" \
  --dataset tests/fixtures/evidence_loop/holdout-dataset-v1.json \
  --capture-output tests/fixtures/evidence_loop/mke-capture-v2.json \
  --output tests/fixtures/evidence_loop/slice0-receipt-v2.json \
  --json

uv run python scripts/verify_evidence_loop.py \
  --pre-registration "$EVIDENCE_LOOP_RUN_ROOT/receipts/pre-registration-v2.json" \
  --dataset tests/fixtures/evidence_loop/holdout-dataset-v1.json \
  --capture tests/fixtures/evidence_loop/mke-capture-v2.json \
  --receipt tests/fixtures/evidence_loop/slice0-receipt-v2.json \
  --json
```

Success codes are `evidence_loop_evaluated` with one terminal disposition and
`evidence_loop_receipt_verified`. All new CLIs implement:

| Exit | Meaning |
| ---: | --- |
| 0 | exact success |
| 2 | invalid CLI or unreadable input |
| 10 | producer/artifact identity mismatch |
| 11 | custody, mode, measured reachability, or reveal-order violation |
| 12 | capped/incomplete/budget-exhausted evaluation |
| 13 | evaluator, holdout, receipt, or canonicalization invalid |
| 14 | prohibited store/domain mutation or tool use |

Every failure emits one bounded JSON diagnostic with
`stage/code/problem/cause/recovery`; stderr begins with `recovery:`. `--json` never includes raw
Evidence, query, cursor, physical root, key, cookie, CSRF value, credential, or unbounded output.
Unit/CLI contract tests freeze help text, required arguments, sentinel, exit code, and redaction.

### 1.7 Mechanical cross-PR readiness

PR A adds `StageReadinessContractV1`, `StageReadinessCandidateV1`,
`StageReadinessReceiptV1`, and
`scripts/verify_stage_readiness.py`. Canonical stage contracts live at:

```text
tests/fixtures/evidence_loop/stage-contracts/slice0-v1.json
tests/fixtures/evidence_loop/stage-contracts/candidate-authority-v1.json
tests/fixtures/evidence_loop/stage-contracts/candidate-journey-v1.json
tests/fixtures/evidence_loop/stage-contracts/composition-authority-v1.json
tests/fixtures/evidence_loop/stage-contracts/composition-journey-v1.json
```

Each contract freezes stage name, canonical committed proof artifact path, allowed terminal
disposition, required hosted check names discovered from the active main ruleset, next-stage
unlock, and non-claims. Each implementation PR commits its own byte-stable proof artifact:

```text
tests/fixtures/evidence_loop/slice0-receipt-v2.json
tests/fixtures/evidence_loop/b1-candidate-authority-proof-v1.json
tests/fixtures/evidence_loop/b2-candidate-journey-proof-v1.json
tests/fixtures/evidence_loop/c1-composition-authority-proof-v1.json
tests/fixtures/evidence_loop/c2-composition-journey-proof-v1.json
```

The readiness artifacts are not self-referential repository files. After exact-head checks pass,
the publication owner first generates and persists `StageReadinessCandidateV1` in the Draft PR
body. It binds stage, reviewed HEAD/tree, committed proof path/digest, terminal disposition,
actual required hosted contexts and URLs, next-stage unlock, and non-claims. That exact candidate
is a Ready/merge precondition.

After squash merge and exact-merge checks, one terminal body reconciliation replaces the candidate
with `StageReadinessReceiptV1`, adding merge SHA/tree/time, reviewed-tree equality, post-merge
required contexts, main-sync identity, and cleanup state. The final persisted readback must contain
the receipt and no candidate/pending wording. A later execution trusts only this terminal receipt.

Before the next branch is created, run:

```bash
: "${PRIOR_STAGE_MERGE_SHA:?set the exact prior stage squash merge}"
: "${PRIOR_STAGE:?set slice0, candidate-authority, candidate-journey, composition-authority, or composition-journey}"
uv run python scripts/verify_stage_readiness.py \
  --stage "$PRIOR_STAGE" \
  --merge-commit "$PRIOR_STAGE_MERGE_SHA" \
  --expected-main "$(git rev-parse origin/main)" \
  --json
```

The verifier reads the committed stage contract/proof, resolves the unique merged PR for that
merge commit through authenticated read-only GitHub API, validates persisted receipt bytes,
reviewed/merge tree equality, required checks, disposition, and exact current main ancestry, then
prints `stage_readiness_verified`. Exit 10 means identity mismatch, 12 means required check or
disposition did not unlock, 13 means malformed/contradictory receipt, and 20 means external
readback unavailable. No local or unmerged receipt unlocks work.

## 2. PR A — Slice 0 frozen-suite falsification gate

### Task A1 — Land design, plan, ADR, and governance contracts

**Files**

- the four public document paths in §1.2;
- `tests/architecture/test_multisource_evidence_contract.py` (new);
- `tests/architecture/test_documentation_governance.py`;
- `scripts/verify_release.py` only if current documentation inventory requires it.

**RED**

Add architecture assertions for:

- exact producer locks;
- no runtime multi-agent claim;
- DRA Markdown parsing prohibition;
- disposable MKE store preparation/seal;
- separate `evaluation_canonical_source_id` and `source_entry_canonical_id_v1`;
- eight cases and four sealed holdouts;
- mechanism/target/guardrail metrics;
- `capped -> inconclusive`;
- reveal invalidates holdout secrecy;
- four terminal dispositions;
- six-PR sequence;
- Draft-first lifecycle;
- zero product tables/routes in Slice 0.

Run:

```bash
uv run pytest -q \
  tests/architecture/test_multisource_evidence_contract.py \
  tests/architecture/test_documentation_governance.py
```

Expected RED: missing documents/markers.

**GREEN**

Mechanically land approved bytes, compare source/target with `cmp`, record SHA-256, and rerun the
focused tests.

**Commit:** `docs: design advisor-governed evidence composition`

### Task A2 — Add closed producer and baseline contracts

**Files**

- `src/night_voyager/evidence_loop/__init__.py` (new);
- `src/night_voyager/evidence_loop/models.py` (new);
- `src/night_voyager/evidence_loop/provider_locks.py` (new);
- `src/night_voyager/evidence_loop/mke_v2.py` (new);
- `src/night_voyager/evidence_loop/dra_baseline.py` (new);
- `src/night_voyager/evidence_loop/errors.py` (new);
- `tests/unit/evidence_loop/test_provider_locks.py` (new);
- `tests/unit/evidence_loop/test_mke_v2.py` (new);
- `tests/unit/evidence_loop/test_dra_baseline.py` (new);
- `scripts/verify_stage_readiness.py` (new);
- `tests/unit/evidence_loop/test_stage_readiness.py` (new);
- `tests/fixtures/evidence_loop/stage-contracts/` (five closed contracts, new).
- `tests/fixtures/evidence_loop/provider-locks-v1.json` (new);

`ProviderLockV1` binds exact Night Voyager/MKE/DRA release identities and computed archive/schema
digests.

`MkeObservationV1` models only the public v2 Search/Read contract. It distinguishes:

- MCP query text at most 512 UTF-8 bytes;
- Night Voyager display/domain query text at most 4096 UTF-8 bytes;
- MCP canonical success body at most 32,768 bytes;
- installed SDK proof envelope below the separately documented 96 KiB harness cap.

The 96 KiB harness cap is not described as a producer protocol limit.

`GovernedDraBaselineExportV1` binds:

- Case/revision and decision dimension;
- typed Night Voyager row identity;
- original producer/profile/run/Evidence identity;
- assigned-advisor verification receipt;
- export and row digests.

It accepts no Markdown-to-fact transformation. A current DRA v0.1.8 compatibility artifact has a
separate schema and never replaces historical provenance.

**RED/GREEN**

- wrong tag/wheel/schema/profile;
- moving checkout;
- unknown tool/schema field;
- query/body cap confusion;
- invalid cursor/expired cursor;
- `capped` treated as complete;
- missing historical DRA provenance;
- Markdown-derived claim;
- current compatibility artifact substituted as row origin;
- unknown terminal state.

**Commit:** `feat: close complementary evidence contracts`

### Task A3 — Build the frozen public-safe corpus and seal receipt

**Files**

- `tests/fixtures/evidence_loop/source-manifest-v1.json` (new);
- `tests/fixtures/evidence_loop/source-manifest-fragment-v1.json` (exact public commitment, new);
- `tests/fixtures/evidence_loop/development-dataset-v1.json` (new; four cases);
- `tests/fixtures/evidence_loop/holdout-manifest-v1.json` (new; four hashes/identities, no content);
- `tests/fixtures/evidence_loop/holdout-case-schema-v1.json` (exact public schema, new);
- `tests/fixtures/evidence_loop/holdout-dataset-schema-v1.json` (exact public schema, new);
- `tests/fixtures/evidence_loop/dra-governed-baseline-v1.json` (new);
- `tests/fixtures/evidence_loop/mke-corpus/` (new; public-safe synthetic material);
- `scripts/prepare_evidence_loop_store.py` (new);
- `scripts/freeze_evidence_loop.py` (new);
- `scripts/teardown_evidence_loop.sh` (new);
- `Makefile` (`evidence-loop-down`, task-owned only);
- `tests/unit/evidence_loop/test_freeze.py` (new);
- `tests/unit/evidence_loop/test_cli_contracts.py` (new);
- `tests/integration/adapters/test_mke_store_seal.py` (new).

The source manifest defines Night Voyager-owned `evaluation_canonical_source_id` from admitted URL
or source bytes, publication revision, and normalized full-content digest; it excludes the locator.
A separate `evaluation_canonical_evidence_id` binds that source ID to locator/range, selected-byte
digest, and terminal text digest. Product persistence separately computes
`source_entry_canonical_id_v1` over the exact existing `SourcePackEntryV1` business projection, so
locked legacy rows never need fabricated publication metadata. MKE opaque IDs remain observation
trace.

`prepare_evidence_loop_store.py`:

1. verifies the exact MKE v0.1.5 archive/wheel;
2. creates a task-owned disposable store;
3. ingests only manifest-listed sources;
4. records library/ingest receipts and active-set fingerprint;
5. closes ingestion and, while `store_root` is still `0700`, uses one exact tagged native read to
   materialize zero-byte `store.sqlite-wal` and regular 32768-byte `store.sqlite-shm`;
6. seals the exact ordered `store.sqlite`, `store.sqlite-shm`, and `store.sqlite-wal` inventory as
   one immutable SQLite authority image with all files `0400` and `store_root` `0500`;
7. proves three fresh exact tagged Search/Read plus rejected-write processes preserve the complete
   store tree and active-set identity;
8. records a RECORD-driven identity of the complete installed runtime distribution closure actually
   available to the retained MKE venv, including exact distribution name/version inventory, each
   RECORD identity, hashed regular non-linked runtime files, aggregate file trees, Python/platform,
   SQLite source identity, exact wheel, and entrypoint bytes; task-owned `*.pyc` and `__pycache__`
   entries are deleted before the runtime seal, any remaining or reappearing bytecode fails closed,
   and every later native Python/MCP child uses the frozen no-bytecode, no-user-site, safe-path policy;
   it also binds the exact relative `pyvenv.cfg` file byte identity/mode and closed
   `include-system-site-packages=false` semantics, with a native probe proving `sys.prefix` selects
   only the frozen venv site-packages root and no external/base site-packages are active;
9. writes the read-only sealed-store receipt and closes mutation capability before evaluation.

The setup receipt records ingestion and WAL-peer materialization as bounded store preparation
mutations. The later zero-mutation claim applies only after the exact three-file seal and setup
receipt begin the sealed evaluation window.

`freeze_evidence_loop.py` implements the closed final-freeze validator and canonical receipt
builder, but A3 does not issue `PreRegistrationReceiptV2`. A3 tests that the future receipt binds
all identities, cases, source access, metrics, thresholds, evaluator/harness inputs, three distinct
logical roles, separate payload/oracle commitments, pre-reveal scan, one-way reveal procedure, and
post-reveal generated-file allowlist.

Holdout content and answer keys live outside the evaluator checkout in a custodian-owned source
whose mount/index state is independently attested. Before freeze, scan the evaluator worktree and
command environment for the holdout byte digests and answer-key markers; only opaque
identity/dimension plus separate
`payload_byte_length`, `payload_sha256`, `oracle_byte_length`, and `oracle_sha256` may be present.
The future receipt binds that scan, the three role identities, and
`nv.slice0.one-way-reveal.v1`.

**RED/GREEN**

- unlisted/private source;
- source bytes or URL drift;
- duplicate `evaluation_canonical_source_id`;
- store artifact drift;
- missing, extra, linked, writable, or tampered SQLite WAL authority peer;
- store-root mode drift from sealed `0500`;
- ingest after seal;
- active-set mismatch;
- receipt created after observation;
- holdout content present before freeze;
- baseline export missing verification;
- wrong role/reveal ordering.
- custody-bearing environment input, a post-reveal path, or committed holdout bytes observed in
  the named evaluator checkout/task run roots.

**Commit:** `test: freeze the complementary evidence suite`

### Task A4 — Implement evaluator and complete the pre-reveal freeze boundary

**Files**

- `src/night_voyager/evidence_loop/canonicalization.py` (new);
- `src/night_voyager/evidence_loop/evaluator.py` (new);
- `src/night_voyager/evidence_loop/receipt.py` (new);
- `scripts/evaluate_evidence_loop.py` (new);
- `scripts/reveal_evidence_loop_holdouts.py` (new; validator implemented without custody content);
- `scripts/verify_evidence_loop.py` (new);
- `scripts/run_mke_lane.sh`;
- `tests/unit/evidence_loop/test_canonicalization.py` (new);
- `tests/unit/evidence_loop/test_evaluator.py` (new);
- `tests/unit/evidence_loop/test_receipt.py` (new).
- `tests/integration/adapters/test_mke_v2_tagged_wheel.py` (new; development/mock structural lane);
- `tests/integration/evidence_loop/test_frozen_suite.py` (new; development/mock structural harness);
- `tests/architecture/test_m4b_contract.py`;
- `tests/architecture/test_skills_contract.py` only if runner inventory requires it.

Implement:

- four arms: control, governed DRA baseline, MKE, combined;
- exact duplicate and provenance-path retention;
- explicit conflict relations;
- separate `source_access_gain` and `extraction_gain`;
- mechanism, target, and guardrail metrics;
- terminal dispositions;
- byte-stable canonical JSON output.

MKE acquisition runs once per Case/query and its exact artifact is reused by the `mke` and
`combined` arms. Freeze these ceilings in the receipt and CLI:

- one exact query per Case;
- at most four Search pages with `limit=20`;
- at most 32 Evidence reads per Case;
- 10 seconds per MCP call and 120 seconds per Case;
- 1 MiB combined stdout/stderr;
- no unregistered tool name or fallback.

Budget exhaustion, process-output overflow, extra tool use, or required non-`complete` selection is
`inconclusive`.

Guardrails are vetoes. The evaluator never averages them into a quality score.

**RED/GREEN**

- removed positive evidence removes gap closure;
- forged duplicate creates zero novelty;
- identical source through two paths retains two provenance paths but one canonical source;
- conflict cannot collapse into one value;
- prompt injection stays inert;
- DRA Markdown cannot create a fact;
- required `capped` cannot produce pass/no-value;
- empty exhaustive active result can produce no-match;
- filesystem/database mutation is rejected;
- three fresh processes produce identical bytes.

Do not mount or read holdout payload/oracle content during A4. A4 completes the reveal validator,
tagged-wheel lane, frozen-suite harness, terminal verifier, and runner before final
pre-registration. All paths are fully tested with development or mock structural fixtures. The
final pre-registration binds exact clean HEAD/tree, evaluator and harness path digests,
environment/dependencies, corpus/source identities, thresholds/mappings, separate holdout
payload/oracle digests, three roles, the pre-reveal scan, `nv.slice0.one-way-reveal.v1`, and this
exact post-reveal generated-file allowlist:

```text
tests/fixtures/evidence_loop/holdout-dataset-v1.json
tests/fixtures/evidence_loop/mke-capture-v2.json
tests/fixtures/evidence_loop/slice0-receipt-v2.json
```

**Commit:** `feat: evaluate bounded complementary evidence`

### Task A5 — One-shot reveal and execution

**Files**

- `tests/fixtures/evidence_loop/holdout-dataset-v1.json` (new; exact pre-authored bytes);
- `tests/fixtures/evidence_loop/mke-capture-v2.json` (new generated canonical artifact);
- `tests/fixtures/evidence_loop/slice0-receipt-v2.json` (new generated terminal receipt);

Holdouts:

- one positive-increment `program_requirements` case;
- one positive-increment `application_timeline` case;
- one zero-novelty decoy;
- one explicit conflict-retention case.

The custodian verifies the pre-freeze hashes before copying the bytes once into the evaluator
worktree. A5 is one-shot reveal and execution only. No code, test, evaluator, oracle, threshold,
mapping, or eligible-source change is permitted after reveal; only the three preregistered
generated files may be added. Apart from the preregistered three fresh-process determinism runs,
there is no retry or repair with revealed holdouts. Any drift returns `evaluation_invalid` and ends
the direction; “restart with the same holdouts” is prohibited.

Run the actual archive/wheel through:

```text
sealed disposable store
-> local stdio MCP server
-> search_library_v2
-> complete pagination
-> read_evidence_v1 chunks
-> terminal text digest
-> MkeCaptureArtifactV2
-> frozen evaluator
```

No v1 fallback, editable source, moving checkout, HTTP service, provider call, or private corpus.

Artifact generation collapses an exact `evaluation_canonical_evidence_id` to one candidate item
with bounded provenance paths. It emits one `CandidateSourceEntryProjectionV1` per
`source_entry_canonical_id_v1`, exact candidate storage claims in that source's sorted `coverage`,
and distinct items/claims for same-dimension different-value conflicts. Tests round-trip every
projection through the checked-in Python canonicalizer; no browser or producer field can supply
the product source-entry identity.

Pass requires:

- all mechanism gates;
- exhaustive `complete` for required queries;
- both positive holdouts close one gap each across two dimensions;
- decoy novelty zero;
- conflict explicit;
- all guardrails;
- three byte-identical fresh-process receipts.

An exhaustive active miss is `no_incremental_value`; bounded incomplete or unavailable retrieval
is `inconclusive`; custody, hash, order, freeze, mutation, or identity drift is
`evaluation_invalid`. Every non-confirming outcome ends the direction. Only the exact confirmed
receipt can unlock B1.

`MkeCaptureArtifactV2` is a frozen provider-free reference artifact. It does not imply arbitrary
advisor corpus intake.

**Commit:** `test: prove the frozen complementary evidence gate`

### Task A6 — PR A terminal disposition

Run once on the final clean candidate:

```bash
uv lock --check
uv run ruff check .
uv run pyright
uv run pytest -q tests/unit/evidence_loop tests/integration/evidence_loop \
  tests/integration/adapters/test_mke_v2_tagged_wheel.py
uv run pytest -q tests/architecture
uv run python scripts/verify_evidence_loop.py \
  --pre-registration "$EVIDENCE_LOOP_RUN_ROOT/receipts/pre-registration-v2.json" \
  --dataset tests/fixtures/evidence_loop/holdout-dataset-v1.json \
  --capture tests/fixtures/evidence_loop/mke-capture-v2.json \
  --receipt tests/fixtures/evidence_loop/slice0-receipt-v2.json
make check
uv run python scripts/verify_release.py --tree-mode development
git diff --check
```

The focused evaluator commands provide fast failure localization. `make check` is the one full
final-candidate gate and already invokes the project proof target; do not immediately repeat
`make proof` on the same tree.

PR A has no new product DB/API/Web behavior and therefore no new local product Compose lane.
Hosted exact-head project checks remain mandatory.

Persist exactly one disposition:

- `incremental_value_confirmed`;
- `no_incremental_value`;
- `inconclusive`;
- `evaluation_invalid`.

Only a merged `incremental_value_confirmed` receipt unlocks B1. Otherwise close the phase, clean
task-owned resources, document the safe-stop result, and do not create v0.1.6 for this direction.

#### Actual local A6 disposition (2026-08-01)

The executed Slice 0 ended with terminal status `evaluation_invalid`. The one-way reveal
succeeded once, but the frozen evaluator rejected a noncanonical input path before MKE capture
because the temporary run-root assignment was not available to that command's argument
expansion. No `MkeCaptureArtifactV2`, Slice 0 terminal receipt, or information-gain result
exists. The revealed holdout suite is retained as retired evidence and cannot be reused.

This is a fail-closed operator/evaluation-protocol safe stop, not evidence of
`no_incremental_value` and not evidence about MKE or DRA quality. No candidate or product
persistence, Slice 1/2 work, v0.1.6 release, provider action, production claim, or
incremental-value claim follows. The verifier was not run because its required capture and
terminal receipt do not exist; no evaluator, verifier, or reveal retry is permitted. Local
safe-stop closeout is separate from the pending merged PR, hosted CI, and publication cleanup.

## 3. PR B1 — Slice 1 candidate database and API authority

### Entry receipt

Before branch creation, verify the exact merged PR A commit and receipt. Recompute all artifact and
producer locks. Any mismatch blocks B1.

### Task B1.1 — Migration `0016`

**Files**

- `migrations/versions/0016_mke_candidate_decision.py` (new);
- `tests/integration/mke_candidates/test_migration.py` (new);
- `tests/integration/mke_candidates/test_downgrade.py` (new);
- `tests/security/test_mke_candidate_catalog.py` (new);
- `scripts/run_db_tests.sh`;
- current-head architecture/release inventories required by migration `0016`.

Tables:

- `app.mke_evidence_candidates`;
- `app.mke_candidate_sources`;
- `app.mke_candidate_items`;
- `app.mke_candidate_decisions`.

Use migrator-owned tables, forced RLS, closed states, immutable triggers, exact unique constraints,
and composite tenant/Case/revision/candidate/item/decision keys. Candidate and items are immutable.
One assigned advisor can create one terminal decision.

Freeze the exact DDL in migration and architecture tests:

- candidate primary key `(organization_id,id)` and unique
  `(organization_id,case_id,case_revision,id)`;
- source primary key `(organization_id,candidate_id,id)`, unique
  `(organization_id,candidate_id,source_entry_canonical_id_v1)`, exact canonical projection/hash,
  and composite candidate foreign key;
- item primary key `(organization_id,candidate_id,id)`, unique
  `(organization_id,candidate_id,item_ordinal)`, unique
  `evaluation_canonical_evidence_id`, unique storage claim, and composite candidate/source foreign
  keys;
- decision primary key `(organization_id,id)`, unique `(organization_id,candidate_id)`, and
  composite candidate/Case/revision/actor foreign keys;
- foreign keys to organization, Case revision, and assigned participant actor;
- immutable 64-hex Slice 0 receipt/artifact columns, checked against the committed import allowlist
  by the function rather than falsely modeled as foreign keys;
- each candidate source stores the complete server-owned
  `CandidateSourceEntryProjectionV1`: an exact materializable `SourcePackEntryV1` subprojection
  (deterministic source-entry ID, `source_entry_canonical_id_v1`, traversal-safe declared path,
  source SHA-256, canonical URL, publisher, institution, snapshot date, freshness,
  redistribution/evidence classes, coverage, and known gaps), plus a retained provenance extension
  (MKE Source/Publication identity, publication date, source byte length,
  `evaluation_canonical_source_id`, and manifest identity) and canonical projection hash;
- each candidate item stores
  `evaluation_canonical_evidence_id`, closed route country/decision dimension, normalized-value
  SHA-256,
  `mke.<route_country>_<decision_dimension>.<evaluation_canonical_evidence_id>` storage claim,
  locator/range/digests, relation/conflict group, and bounded provenance paths; exact duplicate
  observations are one item with multiple paths, while same-dimension conflicting values remain
  distinct items and claims;
- the exact v0.1.6 decision dimensions are
  `program_requirements | application_timeline`, scoped by one existing supported route country;
  no artifact-defined arbitrary dimension is accepted;
- source-entry IDs are derived by the checked-in SHA-256 namespace helper from candidate ID and
  `source_entry_canonical_id_v1`; two items for one source reference one candidate-source row,
  while distinct Evidence locators/ranges remain item-specific; this is a proposed entry ID, and
  canonical comparison excludes all tenant/pack/version/entry identity fields;
- source coverage is the sorted unique set of its candidate storage claims, and checks freeze the
  claim regex, 64-hex hashes, positive versions, closed
  dimensions/candidate/decision/reason/conflict states, conflict-group consistency, and every
  payload/count limit;
- immutable update/delete triggers, forced-RLS tenant policies, bounded list/detail indexes, and
  current-action lookup index;
- migrator-owned `SECURITY DEFINER` functions with closed `search_path`; API has only exact
  `EXECUTE`, worker has no candidate functions, neither role has direct table DML or `BYPASSRLS`.

Bounds:

- domain query 4096 UTF-8 bytes;
- 16 items and observations;
- 16 KiB selected text per item;
- 256 KiB candidate payload;
- 16 duplicate/conflict relations;
- list page 20;
- candidate detail at most 16 item summaries and below 32 KiB;
- one-item detail at most 16 KiB selected text and below 32 KiB total;
- public problem 32 KiB.

Migration/catalog tests freeze these new callable signatures and exact return projections:

```text
app.import_mke_candidate(uuid,uuid,uuid,integer,uuid,jsonb,text,text)
app.decide_mke_candidate(uuid,uuid,uuid,uuid,integer,text,text,uuid,text,text)
app.read_mke_candidates(uuid,uuid,text,uuid,text,integer)
app.read_mke_candidate(uuid,uuid,text,uuid,uuid)
app.read_mke_candidate_item(uuid,uuid,text,uuid,uuid,uuid)
```

Import accepts organization, actor, Case, expected revision, server-generated candidate ID, the
server-resolved closed artifact projection, key hash, and request hash. Decision accepts
organization, actor, Case, candidate, expected version, decision, reason, server-generated decision
ID, key hash, and request hash. The API never passes the opaque `candidate_ref` into PostgreSQL;
the application resolves and verifies the committed artifact first.

**RED/GREEN**

- cross-tenant/Case/revision;
- forged Slice 0 receipt;
- wrong producer/corpus/artifact/source/Evidence identity;
- forged source-entry ID/path/projection, same source-entry identity with disagreeing source bytes,
  claim absent from source coverage, duplicate claim/evidence identity, conflicting values
  collapsed into one item, and
  two locators for one source with non-identical source-level metadata;
- wrong assigned advisor;
- concurrent terminal decisions;
- mutation after terminal;
- downgrade with candidate/history;
- migration parity and ownership.

**Commit:** `feat: add MKE candidate authority`

### Task B1.2 — Domain, repository, and authenticated API

**Files**

- `src/night_voyager/mke_candidates/__init__.py` (new);
- `src/night_voyager/mke_candidates/models.py` (new);
- `src/night_voyager/mke_candidates/errors.py` (new);
- `src/night_voyager/mke_candidates/ports.py` (new);
- `src/night_voyager/mke_candidates/application.py` (new);
- `src/night_voyager/mke_candidates/postgres.py` (new);
- `src/night_voyager/interfaces/http/mke_candidates.py` (new);
- `src/night_voyager/api.py`;
- affected API/reference documentation for the closed routes and recovery semantics;
- `tests/unit/mke_candidates/` (new);
- `tests/integration/mke_candidates/test_repository.py` (new);
- `tests/integration/mke_candidates/test_authority.py` (new);
- `tests/integration/mke_candidates/test_http.py` (new);
- `tests/integration/mke_candidates/test_query_plans.py` (new);
- `scripts/verify_mke_candidate_flow.py` (new; authority mode first);
- `tests/architecture/test_mke_candidate_contract.py` (new);

Routes:

```text
POST /api/v1/cases/{case_id}/mke-candidates
GET  /api/v1/cases/{case_id}/mke-candidates
GET  /api/v1/cases/{case_id}/mke-candidates/{candidate_id}
GET  /api/v1/cases/{case_id}/mke-candidates/{candidate_id}/items/{item_id}
POST /api/v1/cases/{case_id}/mke-candidates/{candidate_id}/decisions
```

Import body is only:

```json
{"candidate_ref":"opaque","expected_case_revision":2}
```

Decision body is only:

```json
{
  "decision":"accepted_for_planning",
  "reason_code":"source_bound_gap_relevant",
  "expected_candidate_version":1
}
```

Server resolves the committed artifact and revalidates all identities. Mutations require
`Idempotency-Key` and return immutable receipt plus authoritative projection.

Import and decision both lock the stable Case row first, then inspect the prior actor/operation/key
idempotency record. Same-key/same-body committed results replay before later stale-state checks;
same-key/different-body conflicts. A new mutation requires Case state `advisor_review`, current
revision, current PlanningRun `review_required`, the same assigned advisor, and no finalized
FamilyDecision or TimelinePlan.

The candidate list is a bounded summary projection: identity, state, decision dimension, conflict
count, terminal decision summary, row version, and timestamps only. Full selected text and
provenance appear only on the one-item detail route; candidate detail contains at most 16 bounded
item summaries. All three reads have deterministic identity/sort rules, explicit response-size
caps, and real PostgreSQL query-plan/index tests.

Before a receipt is accepted, recovery may replay only the exact same POST/body/key. After receipt
acceptance, recovery retries only the candidate-detail GET. Import recovery never guesses from the
list: replay of the original POST returns the original candidate identity. No operation-status
endpoint, background retry, or automatically minted key is added.

**RED/GREEN**

- same key/same body replay;
- same key/different body conflict;
- stale Case/revision/candidate;
- wrong role/advisor;
- foreign candidate/item/source;
- artifact/hash mismatch;
- terminal decision concurrency;
- concurrent same-key/same-body first requests create one row and one receipt;
- 401/transport/receipt-loss/cross-actor recovery;
- Case-state, current-run, FamilyDecision, and TimelinePlan ineligibility;
- bounded list/detail response and indexed query plan;
- acceptance creates zero source pack/revision/task/run/family/timeline/execution;
- direct API/worker DML denial, exact grants, non-`BYPASSRLS`, and closed `search_path`;
- closed public problem mapping.

**Commit:** `feat: govern MKE candidate decisions`

### Task B1.3 — Backend terminal gate

Run:

```bash
uv run pytest -q tests/unit/mke_candidates
COMPOSE_PROJECT_NAME=<task> scripts/run_db_tests.sh mke-candidates migration
COMPOSE_PROJECT_NAME=<task> scripts/run_db_tests.sh mke-candidates authority
COMPOSE_PROJECT_NAME=<task> scripts/run_db_tests.sh mke-candidates http
make check
uv run python scripts/verify_mke_candidate_flow.py \
  --mode authority \
  --write-proof tests/fixtures/evidence_loop/b1-candidate-authority-proof-v1.json \
  --json
uv run python scripts/verify_release.py --tree-mode development
```

There is no default product import and no browser proof in B1. The merged B1 receipt proves only
candidate/API authority and zero promotion. `make check` is the one full final-candidate gate and
already includes the default database and proof targets; the focused commands above exist to
localize failures, not to repeat the full matrix.

## 4. PR B2 — Slice 1 advisor UI, recovery, and candidate proof

### Task B2.1 — BFF and controller

**Files**

- `src/night_voyager/connected_demo/models.py`;
- `src/night_voyager/connected_demo/application.py`;
- `src/night_voyager/connected_demo/postgres.py`;
- `src/night_voyager/interfaces/http/connected_demo.py`;
- `web/lib/mke-candidates/contracts.ts` (new);
- `web/lib/mke-candidates/api.ts` (new);
- `web/lib/mke-candidates/idempotency.ts` (new);
- `web/lib/connected-demo/contracts.ts`;
- `web/lib/connected-demo/api.ts`;
- `web/lib/connected-demo/reducer.ts`;
- `web/lib/connected-demo/use-connected-demo.ts`;
- BFF routes under
  `web/app/api/demo/cases/[caseId]/mke-candidates/` (new);
- `web/tests/unit/mke-candidate-api.test.ts` (new);
- `web/tests/unit/mke-candidate-recovery.test.tsx` (new);
- focused connected-demo reducer/recovery tests.

Extend the server read model to exact `AdvisorLedgerV3` with one closed `current_action`. Candidate
availability, identity, and opaque server-owned `candidate_ref` come only from this read model.

The only product route is `/demo`. `ConnectedDemo` and `useConnectedDemo` remain the single
page/controller owners. MKE helpers may decode responses and hold immutable operation-slot data, but
a second candidate hook/reducer must not independently own a primary action, recovery state, focus,
or live region.

Closed candidate actions include `review_mke_candidate`, `decide_mke_candidate`, and the existing
governed-planning action after rejection or when no candidate exists. Selecting “审阅补充证据”
submits only the ledger-projected opaque reference, then installs the authoritative candidate. This
is a retained reference workflow, not arbitrary advisor corpus intake.

Use exact runtime decoders, public response cap, one stable operation slot, receipt-then-GET,
generation-guarded finalization, and zero automatic mutation. Retrieved text is inert and cannot
affect request construction.

**RED/GREEN**

- malformed/oversized response;
- untrusted HTML/instruction content;
- same-body/key lost response;
- receipt/view/context contradiction;
- session/role/Case/revision/candidate change;
- stale tab and concurrent decision;
- transport uncertainty;
- cross-candidate envelope;
- candidate and existing ledger offering competing primary actions;
- accepted/rejected terminal reload;
- zero promotion.

### Task B2.2 — Advisor presentation

**Files**

- `web/components/mke-candidates/MkeCandidateReview.tsx` (new);
- `web/components/mke-candidates/MkeCandidateProvenance.tsx` (new);
- `web/components/mke-candidates/MkeCandidateRecoveryNotice.tsx` (new);
- `web/components/connected-demo/ConnectedDemo.tsx`;
- `web/components/connected-demo/AdvisorLedger.tsx`;
- `web/components/connected-demo/EvidenceDisclosure.tsx`;
- `web/lib/presentation/catalog.ts`;
- `web/tests/unit/mke-candidate-ui.test.tsx` (new).

The exact page hierarchy is:

```text
Case/revision/role/synthetic boundary
-> one server-owned current action
-> evidence summary and conflict
-> decision fieldset and explicit confirmation
-> result summary
-> technical details
-> existing governed journey
```

`AdvisorLedger` does not derive a competing action when V3 supplies `current_action`.

UI must show:

- untrusted warning;
- decision dimension and excerpt before technical identity;
- source/publication/locator in progressive disclosure;
- selected excerpt;
- decision dimension;
- duplicate/conflict relations;
- one current action across ledger/candidate/composition;
- “accepted as planning input” wording;
- user-facing operation record before technical receipt identity.

It must not say “verified true,” “approved route,” “trusted source,” or “DRA/MKE agreement proves
truth.”

Terminal decision UI uses a labelled accept/reject fieldset, one closed reason choice, consequence
summary, and separate confirmation. Frozen primary copy:

- warning: `这段外部证据可能不完整或有误。它不会自动修改 Case 或计划。`;
- accept: `用于下一版规划`;
- reject: `本次规划不采用`;
- accepted: `已标记为规划输入；Case 和计划尚未改变。`;
- conflict: `存在未解决分歧；新版本仍需顾问审阅。`;
- receipt label: `操作记录`;
- disclosure: `技术详情`.

Source URLs/locators are non-executing text with copy affordance. v0.1.6 does not navigate to
retrieved links.

Accessibility:

- bilingual zh-CN/en;
- fieldset/legend, associated errors, and keyboard decision/details flow;
- deterministic focus and one polite live region;
- 44 px touch targets, non-color status, and AA contrast;
- 200% zoom, 320 px layout, reduced motion;
- escaped text and safe link presentation.

Unit/rendered tests cover loading, no candidate, unavailable, wrong role/session/Case, pending,
0/1/16 items, duplicate, conflict, long/malicious content, missing reason, submitting, accepted,
rejected, concurrent terminal decision, transport uncertainty, receipt found/absent, stale identity,
projection contradiction, locale switch, focus, and live announcements.

### Task B2.3 — Provider-free browser/database proof

**Files**

- `web/e2e/mke-candidate-review.spec.ts` (new);
- `scripts/verify_mke_candidate_flow.py` (extend with journey mode);
- `scripts/verify_compose.sh`;
- `web/playwright.compose.config.ts`;
- `tests/architecture/test_compose_contract.py`;
- `scripts/seed_demo.py`;
- `src/night_voyager/identity/demo_seed.py`;
- focused seed/idempotency tests.

The fixture references the exact committed capture. Seed creates no candidate before the
server-owned review action/import.

Proof both terminal paths:

- review action/import -> advisor accepts -> reload/recovery -> exact candidate/decision receipt ->
  zero promotion;
- review action/import -> advisor rejects -> terminal reload -> zero promotion.

Counterfactuals:

- role/session change during request;
- lost response;
- stale version;
- cross-Case/candidate envelope;
- instruction content;
- same key/different body.

On the clean final candidate run focused Web/architecture tests during development, then one
authoritative `make check`, the development release verifier, and one normal task-scoped Compose
proof with task-owned teardown and before/after inventory. `make check` already contains the
default DB and proof targets. Then write
`tests/fixtures/evidence_loop/b2-candidate-journey-proof-v1.json` through
`scripts/verify_mke_candidate_flow.py --mode journey --write-proof ... --json`; the proof binds
both terminal paths, zero promotion, browser/database identities, recovery, and exact candidate
authority.

**Commits**

- `feat: present MKE candidate review`
- `test: prove governed MKE candidate recovery`

The exact merged accepted-candidate receipt unlocks C1. A rejected-only result proves the path but
does not unlock composition.

## 5. PR C1 — Slice 2 deployable headless composition authority

### Task C1.1 — Migration `0017`

**Files**

- `migrations/versions/0017_mke_evidence_composition.py` (new);
- `tests/integration/evidence_composition/test_migration.py` (new);
- `tests/integration/evidence_composition/test_downgrade.py` (new);
- `tests/security/test_evidence_composition_catalog.py` (new);
- `scripts/run_db_tests.sh`;
- current-head migration/release inventories.

Tables:

- `app.evidence_composition_receipts`;
- `app.evidence_composition_sources`;
- `app.evidence_composition_items`;
- `app.evidence_composition_dimensions`;
- `app.evidence_composition_dimension_evidence_refs`;
- `app.evidence_composition_results`;
- `app.evidence_composition_recoveries`.

Freeze the DDL and grants in architecture/catalog tests:

- receipt primary key `(organization_id,id)`, unique actor/operation/idempotency-key identity, unique
  accepted-decision composition, and composite old/staged Case/revision/source-pack/task identity;
- source primary key `(organization_id,receipt_id,id)`, exact generated source-entry identity,
  complete `SourcePackEntryV1` canonical projection/hash, and retained-entry/candidate-source
  origins with at least one present; both origins are legal only after an exact canonical match;
- item primary key `(organization_id,receipt_id,id)`, mutually exclusive
  `predecessor_evidence_ref_id`/`candidate_item_id`, unique generated Evidence and storage claim,
  unique retained old-to-new Evidence mapping, and composite
  receipt/candidate/source/item/composition-source/Evidence foreign keys;
- dimension primary key `(organization_id,receipt_id,id)`, unique generated
  PlanningRun/route-country/role identity, and closed supplementary role/outcome/reason;
- dimension-Evidence primary key `(organization_id,receipt_id,dimension_id,evidence_ref_id)`,
  exact composition-item/source/Evidence membership, and no legacy planning-table fallback;
- result primary key and unique receipt identity `(organization_id,receipt_id)`, composite
  receipt/task/execution/generation/generated-PlanningRun identity, exact composed output
  contract/schema hash/wrapper hash, and independently recomputed base v1 hash;
- recovery primary key `(organization_id,id)`, unique receipt and actor/operation/idempotency-key
  identities, and composite receipt/terminal-task/generation/prior-current-run/actor foreign keys;
- exact foreign keys to organization, Case old/new revisions, same source-pack ID old/new versions,
  candidate/decision, assigned advisor, `request_revision` review, predecessor PlanningRun, queued
  task, source entry, generated Evidence, terminal task generation, and recovery actor;
- exact source-entry coverage: every retained and candidate branch binds a persisted canonical
  source projection, every generated Evidence binds one same-version entry, candidate storage
  claims occur in the source coverage, and every successor entry participates in the recomputed
  canonical manifest;
- checks for retained/candidate XOR, closed operation/result kinds, positive versions, 64-hex
  request/body/artifact hashes, next revision/version, and bounded item count;
- closed task operation `generate_composed_evidence_planning_run_v1`, execution adapter
  `composed_evidence_planning@v1`, and claim-time operation-to-adapter mapping; all existing task
  operations retain their exact mapping;
- exact `evidence_refs.authority='advisor_accepted_planning_input'` extension; it is distinct from
  `externally_verified` and is legal only with the matching composition receipt;
- leave `comparison_dimension_evidence_refs`, its role CHECK, shared v1 `EvidenceRole`,
  `PlanningResult`, and `app.guard_link_provenance()` unchanged; the new composition tables own
  exactly `program_requirements` and `application_timeline` through
  `ComposedEvidenceRoleV1`;
- add `app.guard_composed_evidence_link_provenance()` on the composition-owned link table; a
  supplementary role requires an `advisor_accepted_planning_input` Evidence whose route
  country/claim, composition receipt/source/item, staged revision/source pack, and generated
  PlanningRun all agree;
- immutable receipt/source/item/dimension/dimension-link/result/recovery update-delete triggers,
  forced-RLS policies,
  current-action/receipt/task indexes, and the existing unique effective-task rule;
- migrator-owned `SECURITY DEFINER` functions with closed `search_path`; API receives only exact
  compose/read/abandon `EXECUTE`; worker receives its unchanged claim/failure grants plus exact
  operation-specific start **and** finalize `EXECUTE`; PUBLIC/API are revoked from both worker
  functions and neither role has direct table DML or `BYPASSRLS`.

Freeze exact callable signatures and return projections in migration/catalog tests:

```text
app.compose_mke_candidate(
  uuid,uuid,uuid,integer,uuid,integer,uuid,uuid,uuid,uuid,integer,
  uuid,uuid,jsonb,text,text
)
app.read_evidence_composition(uuid,uuid,text,uuid,uuid)
app.abandon_evidence_composition(
  uuid,uuid,uuid,uuid,uuid,bigint,uuid,text,text
)
app.start_composed_evidence_agent_task(uuid,uuid,text,bigint,text)
app.finalize_composed_evidence_planning_result(
  uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid
)
app.cancel_agent_task(uuid,uuid,uuid,integer,text,text)
app.source_entry_canonical_identity_v1(jsonb)
app.canonical_source_pack_manifest_v1(uuid,uuid,integer)
```

The first signature binds organization, actor, Case, expected current revision, candidate and
version, terminal decision, expected current PlanningRun, exact request-revision review, current
pack and version, server-generated receipt/task IDs, a closed item projection, key hash, and
request hash. Abandon binds the terminal task and exact final generation. Its result is the
recovery receipt plus unchanged prior current revision/run and `replayed`. Operation-specific start
accepts the same worker arguments as `app.start_agent_task` but validates the
receipt-bound prior-current/staged split. It is required because ordinary start correctly rejects a
task whose revision is not yet current. Migration `0017` also uses `CREATE OR REPLACE` for the
existing exact cancel signature: after the normal context/task lock,
`generate_composed_evidence_planning_run_v1` raises SQLSTATE `NV037`, mapped only to HTTP 409
`composition_not_cancellable`; every prior operation preserves its existing behavior.
The two canonical helpers are migrator-owned, revoked from API/worker/PUBLIC, and callable only
inside approved `SECURITY DEFINER` functions. Python/SQL parity tests freeze their canonical UTF-8
projection and SHA-256 output. The source helper maps SQL `declared_path` to public model key
`path`, uses persisted canonical URL text without a second normalizer, sorts `coverage` and
`known_gaps` by UTF-8 byte order, excludes tenant/pack/version/entry IDs, and uses compact
non-ASCII-escaped JSON with sorted object keys. Retained and candidate fixtures must produce
byte-identical Python/SQL projections, not merely equal hashes.

Catalog tests invoke operation-specific start and finalize as the worker role and assert both
succeed only with their exact signatures. The same tests inspect role grants and prove that
PUBLIC/API cannot execute either function; naming `start_composed_evidence_agent_task` without the
worker grant is an explicit RED.

Architecture tests also call the exact existing participating signatures:

```text
app.review_planning_run(
  uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text
)
app.decide_family_brief(
  uuid,uuid,text,uuid,integer,uuid,uuid,uuid,bigint,bigint,text,jsonb,
  uuid,text,uuid,jsonb,text,text
)
```

These are runtime catalog checks plus real concurrency counterexamples, not string-only assertions.
Migration `0017` uses `CREATE OR REPLACE` for the exact review signature without changing other
review semantics: after existing Case/run/advisor validation, `request_revision` against the
unchanged predecessor of an abandoned composition raises `NV038`, mapped only to public
`composition_branch_closed`; `approve_for_consultation`, `reject`, and reviews without that
lineage behave exactly as before. The abandoned-branch reject regression freezes the existing
non-approval transition to `planning`, zero task/composition creation, and a terminal safe-stop UI
for this reference journey.

Every Case-changing PostgreSQL function participating in this journey must take the stable Case
`FOR UPDATE` lock first. The composition function then locks in this exact order:

1. Case;
2. prior actor/operation/idempotency-key record;
3. current revision;
4. current `review_required` PlanningRun and assigned-advisor `request_revision` review;
5. current source-pack version;
6. accepted candidate and terminal decision;
7. prior immutable composition/recovery rows for the accepted decision.

Resolve the source-pack ID/version only from the locked current PlanningRun. Reject a standalone
browser-supplied pack that does not exactly match; never select by maximum version or timestamp.

The Case lock closes first-request concurrency when the idempotency row does not yet exist. After
the lock, same-key/same-body committed work replays before stale-state checks; same key/different
body conflicts. A new request atomically:

1. creates the next version of the same source-pack ID and copies every retained source entry with
   the same entry ID and byte-identical business columns;
2. derives `source_entry_canonical_id_v1` and the complete projection for every locked retained
   entry and stores one composition-source mapping for each copied entry;
3. groups candidate sources by `source_entry_canonical_id_v1`; reuses a copied entry only when
   exactly one retained projection is byte-equal, rejects ambiguous/disagreeing matches, and
   otherwise inserts exactly one new same-version entry from the frozen candidate source
   projection's proposed entry ID; the composition-source row records proposed and resolved IDs;
4. creates new Evidence IDs for every retained Evidence row with byte-identical
   claim/authority/source hash and records a complete unique
   old-Evidence-to-new-Evidence map;
5. appends immutable MKE-derived Evidence using the resolved same-version source entry, the exact
   frozen `mke.<route_country>_<decision_dimension>.<evaluation_canonical_evidence_id>` storage
   claim,
   `advisor_accepted_planning_input`, item-specific locator/range, normalized-value hash, and
   retained relation/conflict group;
6. recomputes the successor source-pack manifest from the complete inserted entry set using the
   frozen canonical JSON algorithm (schema version, organization, pack ID, successor version, and
   entries sorted by lowercase UUID; UTF-8, sorted object keys, no insignificant whitespace) and
   requires exact internally expected/stored/recomputed equality;
7. creates a staged next `student_case_revisions` row with predecessor run and request-review
   lineage, without changing `student_cases.current_revision`;
8. keeps the Case in `planning` and the predecessor PlanningRun current;
9. creates the immutable composition receipt/source/item/Evidence mappings;
10. creates one exact-pinned `generate_composed_evidence_planning_run_v1` queued task, dispatch row,
   and queued event against the staged revision/source pack;
11. writes the composition idempotency result;
12. commits all or none.

It creates neither `AgentExecution` nor successor `PlanningRun`.

**RED/GREEN**

- cross-tenant/Case/revision/source-pack/candidate/item;
- advisor change;
- rejected/stale candidate;
- current planning/family/timeline/execution conflict;
- conflict relation dropped;
- partial failure after each insert;
- concurrent same-key same-body composition creates one receipt/task;
- concurrent different-key composition and composition versus every other Case mutation serialize
  under the common Case lock;
- same key/different request;
- missing request-revision review;
- novel candidate source creates one new same-version entry; an already represented source reuses
  its copied entry only after an exact unique canonical match; two items for one source create one
  entry; the same source with different Evidence locators creates distinct Evidence on one entry;
- exact duplicate observation paths create one candidate item/Evidence with multiple provenance
  paths; same-dimension different-value conflict creates distinct unique claims/Evidence and
  remains policy-blocking; claim collision, missing source coverage, or collapsed conflict fails;
- forged candidate source projection/entry ID, source-level disagreement, wrong retained entry,
  incomplete successor entry set, manifest mismatch, or failure between source entry/Evidence/
  manifest/receipt inserts rolls back all rows;
- incorrect next source-pack version, changed retained entry bytes, missing/duplicate/cross-pack
  Evidence remap, old-version Evidence reference in new PlanningRun output, or orphan mapping;
- premature Case revision advance or predecessor retirement;
- duplicate composition after an abandoned receipt;
- direct API/worker DML, grant, `search_path`, or `BYPASSRLS` drift;
- downgrade with history;
- function ownership/grants/search path.

### Task C1.2 — Domain, public operation, pinned task, and worker finalization

**Files**

- `src/night_voyager/evidence_composition/__init__.py` (new);
- `src/night_voyager/evidence_composition/models.py` (new);
- `src/night_voyager/evidence_composition/errors.py` (new);
- `src/night_voyager/evidence_composition/ports.py` (new);
- `src/night_voyager/evidence_composition/application.py` (new);
- `src/night_voyager/evidence_composition/postgres.py` (new);
- `src/night_voyager/evidence_composition/planning_postgres.py` (new);
- `scripts/verify_mke_evidence_composition.py` (new; authority mode first);
- `src/night_voyager/interfaces/http/mke_candidates.py`;
- `src/night_voyager/api.py`;
- `src/night_voyager/adapters/evidence_composition_planning.py` (new);
- `src/night_voyager/adapters/protocols.py`;
- `src/night_voyager/adapters/router.py`;
- `src/night_voyager/tasks/models.py`;
- `src/night_voyager/tasks/policy.py`;
- `src/night_voyager/tasks/postgres.py`;
- `src/night_voyager/tasks/worker.py`;
- `src/night_voyager/worker.py`;
- `src/night_voyager/identity/demo_seed.py`;
- `scripts/seed_demo.py`;
- exact Skill paths required to pin `generate_composed_evidence_planning_run_v1`:
  `src/night_voyager/skills/models.py`, `ports.py`, `registry.py`, `evaluation.py`,
  `application.py`, and `postgres.py`; `fixtures/skills/runtime-manifest-v1.json`;
  `fixtures/skills/eval-manifest-v1.json`; new immutable
  `fixtures/skills/runtime-manifest-v2.json` and `fixtures/skills/eval-manifest-v2.json`; and
  `pyproject.toml` force-include mappings that package all four files as
  `night_voyager/skills/data/*.json`. No source `src/night_voyager/skills/data` directory is
  created;
- affected API/reference documentation for the route, response, replay, and worker lifecycle;
- `tests/unit/evidence_composition/` (new);
- `tests/unit/planning/test_policy.py`;
- `tests/unit/tasks/test_policy.py`;
- `tests/integration/evidence_composition/test_repository.py` (new);
- `tests/integration/evidence_composition/test_atomicity.py` (new);
- `tests/integration/evidence_composition/test_concurrency.py` (new);
- `tests/integration/evidence_composition/test_http.py` (new);
- `tests/integration/evidence_composition/test_query_plans.py` (new);
- `tests/integration/tasks/test_evidence_composition_worker.py` (new);
- `tests/integration/skills/test_evidence_composition_pins.py` (new);
- `tests/unit/identity/test_seed_demo.py`;
- `tests/integration/skills/test_postgres_skills.py`;
- `tests/integration/skills/test_skill_migration_parity.py`;
- `tests/architecture/test_evidence_composition_contract.py` (new).

Expose the closed operation in the same deployable PR:

```text
POST /api/v1/cases/{case_id}/mke-candidates/{candidate_id}/compose
GET  /api/v1/cases/{case_id}/evidence-compositions/{receipt_id}
POST /api/v1/cases/{case_id}/evidence-compositions/{receipt_id}/abandon
```

The public call and complete executable operation land together. Body:

```json
{
  "expected_case_revision":2,
  "expected_candidate_version":2,
  "expected_candidate_decision_id":"uuid",
  "expected_planning_run_id":"uuid",
  "expected_request_revision_review_id":"uuid",
  "expected_source_pack_id":"uuid",
  "expected_source_pack_version":2
}
```

The operation is closed and version-pinned. Its synchronous response contains the immutable
composition receipt, exact queued task identity, authoritative prior current Case/revision/run,
staged revision/source-pack projection, and `replayed`; it never claims an execution or successor
PlanningRun exists yet. The composition receipt/task summary is capped at 16 KiB; composition
detail and public problem responses are capped at 32 KiB to fit the existing BFF
`maxJsonBytes=32*1024`. Candidate pagination retains the B1 cap of 20 summaries.

`EvidenceCompositionPlanningAdapter` reuses the deterministic planning policy but loads only the
new revision, source-pack version, composition receipt/items, and retained predecessor/conflicts
from PostgreSQL. It accepts `advisor_accepted_planning_input` Evidence only when every row binds the
same immutable composition receipt and candidate decision. There is no MKE or DRA call at runtime.

The adapter emits `ComposedEvidencePlanningInputV1`; it does not add optional fields to
`PlanningInput` or masquerade as `GovernedMixedPlanningInput`.
`evidence_composition/models.py` owns `ComposedPlanningEvidenceRefV1` with exact receipt, decision,
composition-source/item, storage claim, route country, semantic decision dimension,
`evaluation_canonical_evidence_id`, normalized-value hash, relation/conflict group, source-entry
and authority bindings. The input also binds predecessor PlanningRun, request-revision review,
staged Case revision/source pack, costs, rankings, and narrative. Shared planning v1 input models
remain byte/schema/hash unchanged.

`tasks/policy.validate_adapter_payload` uses an exact three-way dispatch and no catch-all:

```text
generate_planning_run_v1
  -> PlanningInput
generate_governed_mixed_planning_run_v1
  -> GovernedMixedPlanningInput
generate_composed_evidence_planning_run_v1
  -> ComposedEvidencePlanningInputV1
unknown
  -> invalid_schema
```

The shared `EvidenceAuthority`, `EvidenceRef`, `TrustedEvidenceRef`, `EvidenceRole`, `EvidenceUse`,
and `PlanningResult` v1 types remain unchanged. `evidence_composition/models.py` adds a separate
closed `ComposedEvidenceAuthorityV1` and admits
`advisor_accepted_planning_input` only in `ComposedPlanningEvidenceRefV1`.
`evidence_composition/planning_postgres.py` reconstructs and validates the exact supported
predecessor v1 input kind, runs the existing v1 planning policy unchanged to obtain a base
`PlanningResult`, and then builds the supplementary composition projection:

- ordinary v1 input still permits only `accepted_synthetic_demo`;
- DRA mixed v1 input still permits its exact existing `externally_verified` baseline;
- composed refs permit `advisor_accepted_planning_input` only when every ref is backed by the same
  receipt/decision and exact PostgreSQL composition source/item mapping; retained copied refs
  preserve their prior authority and mapping;
- `UNTRUSTED_CANDIDATE`, a composed authority presented to any v1 model/operation, or an unknown
  operation always fails before task execution.

For composed input, storage `claim` exists only for row uniqueness/provenance. Policy groups by the
closed `(route_country,decision_dimension)` after exact receipt validation. The only v0.1.6
dimensions are `program_requirements | application_timeline`. One unconflicted value adds a
`conditional` comparison dimension with reason `advisor_accepted_untrusted_input`; different
normalized-value hashes in a conflict group preserve every Evidence ref and add a `blocked`
dimension with reason `accepted_input_conflict`. Neither changes route outcome automatically.
MKE-derived items create no `cost_evidence` or `ranking_evidence` in this release; predecessor
governed rows are copied. Raw candidate text and producer metadata are never interpreted as policy
instructions.

Add `ComposedEvidenceRoleV1.PROGRAM_REQUIREMENTS` and
`ComposedEvidenceRoleV1.APPLICATION_TIMELINE`, `ComposedEvidenceUseV1`,
`ComposedComparisonDimensionV1`, and `ComposedEvidencePlanningResultV1` in
`evidence_composition/models.py`. The new result contains the unchanged v1 `PlanningResult` base
projection plus composition dimensions using only those separate roles.

The operation-specific finalizer validates the wrapper, persists only the unchanged base
`PlanningResult` and legacy Evidence links through existing planning tables, and persists
supplementary dimensions through `evidence_composition_dimensions` and
`evidence_composition_dimension_evidence_refs`. Existing PlanningRun `output_sha256` remains the
base v1 result hash. The synchronous composition receipt remains immutable and contains no future
output. Generation-current finalize atomically inserts one immutable
`evidence_composition_results` row containing receipt/task/execution/generation/generated-run
identity, the new contract ID/schema hash/wrapper hash, and the independently recomputed base hash.
No new role or authority enters `comparison_dimension_evidence_refs`.

For `app.finalize_composed_evidence_planning_result`, `p_output_hash` is frozen as the canonical
complete-wrapper hash. The function validates the exact Skill/contract/schema pins, recomputes that
hash from the wrapper, recomputes the nested base v1 hash, stores the wrapper hash on the execution
result and composition-result row, and stores the base hash on the PlanningRun. Composition GET
returns `result=null` before success and left-joins the one immutable result after success.
`guard_composed_evidence_link_provenance()` joins route country, planning run/source pack,
generated Evidence, composition item/source/receipt, storage claim, and authority before allowing
the supplementary link. RED/GREEN freezes every old role/claim pair and old v1 projection,
the two valid new roles, wrong new role, wrong route-country prefix, old claim/new role, new
claim/old role, foreign receipt/item, and correct claim with wrong authority.

Contract regression tests must freeze
`night-voyager.planning-result.v1` at schema SHA-256
`2e8f5dbdfd1f213ef4ca085f16b59162ec9f9ef8d58898bdc98487ddf3956135`, keep its existing
producer and `family-decision-brief` consumer pins unchanged, prove every v1 manifest byte/hash is
unchanged, prove the new composed output accepts exactly the two new roles, and prove either new
role fails parsing in every v1 contract. A completed C1 worker-finalize regression must then call
the existing connected-demo status, planning comparison, and Evidence disclosure readers: they
must reconstruct byte-equivalent v1 projections without seeing a new role/authority, while the
composition GET returns the complete supplementary projection and wrapper identity.

Result-persistence RED/GREEN covers pre-finalize `result=null`, one successful atomic
result/dimension/link/PlanningRun insert, old-generation finalize, same-generation replay, wrong
contract/schema/wrapper hash, wrong nested base hash, partial failure after each result child,
lost-response GET recovery, and update/delete denial. Every failure leaves no result,
supplementary dimension, generated PlanningRun, or partial Case advance.

Add one immutable Skill bundle instead of editing an existing version:

```text
skill_key: evidence-composition-planning
version: 1.0.0
operation: generate_composed_evidence_planning_run_v1
adapter: composed_evidence_planning@v1
input: night-voyager.composed-evidence-planning-input.v1
output: night-voyager.composed-evidence-planning-result.v1
evaluation_dataset: night-voyager.evidence-composition-planning.eval@1.0.0
approval_policy: advisor_review_required
```

Migration `0017` extends the closed Skill-key, task-operation, execution-adapter, runtime-manifest,
evaluation-manifest, claim mapping, and pin guards together. It inserts the definition, version,
passing deterministic evaluation, and activation event with exact hashes. Existing Skill versions
and operation bindings remain immutable and row/byte identical.

Manifest evolution is append-only rather than an in-place global-hash replacement:

- preserve the exact v1 manifest files, version `1.0.0`, and hashes;
- add v2 files with `schema_version=2`, `manifest_version=2.0.0`, the complete supported catalog,
  and the new Skill/evaluation entry;
- add exact `SkillRuntimeManifestV2`/`SkillEvaluationManifestV2` models and replace the
  single-manifest loader with a closed installed-wheel catalog that indexes both generations by
  exact manifest ID/version/SHA-256 and exposes v2 only as `current` for new registration;
- extend `SkillKey`, leaf binding, adapter request/result, and router contracts with only the exact
  new operation/adapter pair; v1 study-destination entries retain their exact two-operation map and
  the v2 composition entry owns only its one operation;
- make worker pin validation select the exact persisted manifest generation before validating the
  Skill entry and operation binding;
- replace the `skill_versions` single-pair CHECK with a closed v1/v2 pair allowlist and store v2
  only on the new Skill row;
- leave all old Skill rows, activations, and task pins untouched;
- retain `SkillSeedEnvelopeV1` with its top-level manifest tuple and byte-equivalent migration-0008
  behavior;
- add `SkillSeedEnvelopeV2`, whose every entry carries its own exact runtime/evaluation
  manifest-ID/version/SHA-256 binding; historical entries carry v1 and only the composition entry
  carries v2;
- use `CREATE OR REPLACE app.seed_demo_skill_registry(uuid,uuid,jsonb)` without changing the
  signature; dispatch only on envelope schema 1 or 2, require per-entry bindings for v2, and reject
  unknown/missing/mixed pairs before any catalog write;
- make fresh head demo seed emit v2 and replay compare each persisted row to its own binding; no
  seed rebuild rewrites old rows to the current manifest.

RED/GREEN proves an old v1 queued/reclaimed task still runs after upgrade, a new composition task
uses v2, unknown/cross-generation/partial pins fail closed, current registration selects v2, both
manifests load from an installed wheel, downgrade refuses when v2 Skill/composition history exists,
and the release verifier freezes all four bytes/hashes. Seed-specific RED/GREEN proves legacy v1
envelope parity, fresh v2 head seed, exact replay, existing historical-row equality, missing
per-entry binding, v1/v2 cross-pair, wrong entry generation, partial-write rollback, and historical
head runners that still invoke their historical seed contract.

Add typed-policy RED/GREEN for operation fall-through, a composed payload parsed as governed mixed,
new authority on ordinary/DRA paths, DRA authority substituted on the composed branch, missing or
foreign receipt/decision/source/item, mismatched storage claim/semantic dimension, unresolved
same-dimension conflict, and a valid retained-plus-candidate composed input.

Worker lifecycle is exact:

- composition commit creates queued task/dispatch/event only;
- claim creates the `AgentExecution` attempt and generation;
- operation-specific start validates the operation, adapter, skill pin, request hash, staged
  revision/pack, prior current revision/run, predecessor, and composition receipt, then moves the
  execution created at claim from leased to running; ordinary `app.start_agent_task` remains
  unchanged for other operations;
- generation-current finalize takes the Case lock, revalidates the still-current prior
  revision/run and staged receipt, creates the successor PlanningRun, binds
  `supersedes_run_id=predecessor_planning_run_id`, attaches task/execution result IDs, marks the
  predecessor non-current, advances the Case to the staged revision, makes the successor current,
  and returns the Case to `advisor_review`, all in one transaction;
- crash/reclaim uses the existing automatic attempt ceiling; failure/timeout/reclaim leaves no
  fabricated PlanningRun and leaves the prior revision/run current;
- generic task cancel is rejected by the unchanged-signature database function with
  `NV037 -> HTTP 409 composition_not_cancellable`;
- after the final automatic attempt is terminal, only assigned-advisor `abandon_composition` is
  legal. It appends one immutable recovery row and moves the Case from `planning` to
  `advisor_review` while leaving the prior current revision/run unchanged;
- abandon is same-body/key idempotent, never requeues, and permanently closes this accepted
  decision from a second composition in v0.1.6;
- after abandon, the exact review actions for the unchanged prior run are
  `approve_for_consultation` or `reject`; the ledger and PostgreSQL function reject
  `request_revision` for that abandoned Case/predecessor branch;
- an old generation, terminal/abandoned task, or task made stale by Case/run change cannot finalize.

Structured diagnostics record bounded duration, terminal code, task/execution IDs,
attempt/reclaim count, and hashed idempotency identity only. Raw Evidence, candidate payload,
request body, key, cookie, CSRF value, and credentials are prohibited.

**RED/GREEN**

- route exists without executable operation (must fail architecture);
- stale Case/revision/run/source pack;
- absent/wrong request-revision review;
- task/request/skill pin mismatch;
- operation/adapter/manifest mismatch;
- old v1 task after v2 installation, unknown manifest generation, global-hash/entry cross-pair,
  missing packaged v1/v2 resource, and current-registration generation drift;
- existing operation claim mapping changed, new Skill inactive, or
  manifest/evaluation/runtime-binding hash mismatch;
- worker restart/reclaim;
- crash before claim, after claim, after start, and before/after finalize commit;
- old-generation finalize and revision change before finalize;
- terminal exhaustion preserves the prior current run and exposes only abandon;
- non-advisor/early/double abandon, lost abandon response, and same-key changed-body abandon;
- generic cancel rejection and cancel/finalize/abandon races;
- successful abandon restores the prior AdvisorReview, emits no PlanningRun, permits no second
  composition or request-revision branch, exposes only approve/reject for the prior run, and blocks
  every late generation;
- exact `review_planning_run` regression: `NV038` only for abandoned-branch `request_revision`,
  while approve/reject and all non-abandon review fixtures remain byte-equivalent;
- predecessor/successor run lineage;
- conflict retention;
- current-only transition to fresh AdvisorReview;
- same-key lost-response replay returns one receipt/task and no execution;
- after receipt acceptance only GET is retried;
- 401, transport, body mismatch, and cross-Case/actor recovery;
- no automatic family decision or timeline execution.

**Commits**

- `feat: add atomic MKE evidence composition authority`
- `feat: execute composed evidence planning`

### Task C1.3 — Headless terminal gate

Run focused migration/catalog/repository/atomicity/HTTP/task/worker/skill tests, one authoritative
`make check`, development verifier, and diff/hygiene. Write
`tests/fixtures/evidence_loop/c1-composition-authority-proof-v1.json` with
`scripts/verify_mke_evidence_composition.py --mode authority --write-proof ... --json`.
`make check` already includes default DB and proof targets; do not repeat them on the same tree.
Add no BFF/UI/browser journey and no product Compose lane. C1 is independently
deployable and testable through authenticated HTTP plus real PostgreSQL/worker tests; there is no
dormant schema, orphan task, or incomplete public operation.

## 6. PR C2 — Slice 2 product journey

### Task C2.1 — Read model, BFF, controller, and presentation

**Files**

- `src/night_voyager/connected_demo/models.py`;
- `src/night_voyager/connected_demo/application.py`;
- `src/night_voyager/connected_demo/postgres.py`;
- `src/night_voyager/interfaces/http/connected_demo.py`;
- `tests/integration/connected_demo/test_evidence_composition_query_plans.py` (new);
- `web/lib/evidence-composition/contracts.ts` (new);
- `web/lib/evidence-composition/api.ts` (new);
- `web/lib/connected-demo/contracts.ts`;
- `web/lib/connected-demo/api.ts`;
- `web/lib/connected-demo/reducer.ts`;
- `web/lib/connected-demo/use-connected-demo.ts`;
- BFF composition route under the existing candidate Case path (new);
- `web/components/mke-candidates/MkeEvidenceComposition.tsx` (new);
- `web/components/connected-demo/ConnectedDemo.tsx`;
- `web/components/connected-demo/AdvisorLedger.tsx`;
- `web/components/connected-demo/PlanningRevisionComparison.tsx`;
- `web/components/connected-demo/EvidenceDisclosure.tsx`;
- `web/lib/presentation/catalog.ts`;
- focused Web unit tests.

After candidate acceptance, `AdvisorLedgerV3.current_action` retains the existing advisor
`request_revision` action. Only after that immutable review moves the Case to `planning` may it
project `compose_mke_evidence`; after worker completion it returns to the existing
fresh-AdvisorReview action. `ConnectedDemo` remains the only controller. A separate composition
hook cannot own a primary action, operation lifecycle, recovery, focus, or live region.

The public projection binds:

- candidate and decision;
- old/new revision and source pack;
- composition receipt/items;
- predecessor/current PlanningRun;
- staged successor identity before completion or immutable abandon recovery after terminal failure;
- queued/running task and execution only when one exists;
- duplicate/conflict relations;
- current advisor/family/timeline phase.

Before confirmation, UI shows an impact preview: a new revision/source pack and planning task will
be created; family decision, timeline, and execution will not start; conflicts remain unresolved.

UI shows accepted input, the existing request-revision decision, explicit
`创建包含该证据的新规划版本` action, user-facing operation record, old/new summary, retained
conflicts, fresh AdvisorReview, and the existing family/timeline journey.
`PlanningRevisionComparison` presents “发生了什么” and “仍未解决什么” before the detailed table.
Technical receipt/hash data stays in progressive disclosure.

Before receipt acceptance, recovery uses exact same-body/key POST replay only under transport
uncertainty. After receipt acceptance it uses the exact composition-receipt GET only. Every install
revalidates Case/prior-current revision/run/staged revision/source-pack/candidate/decision/receipt/
task, execution when present, terminal recovery when present, role, and cursor.

Visible recovery distinguishes:

- receipt found and authoritative result installed;
- receipt absent and exact same-body/key retry proven safe;
- identity changed or projection contradiction, safely stopped with no retry.

Automatic attempts are bounded by the existing task policy and generic cancel is not exposed.
After terminal exhaustion, `AdvisorLedgerV3.current_action` exposes only assigned-advisor
`abandon_composition`. Its one stable operation slot uses same-body/key replay before receipt and
the composition GET after receipt. Success shows the unchanged prior current plan and permanently
closed composition. It then exposes only `approve_for_consultation` or `reject` for that prior run;
it cannot render an ordinary retry, `request_revision`, or a second composition.

Tests bind every busy, running, restart/reclaim, success, terminal exhaustion, cancel rejection,
abandon pending/success/conflict, outdated, no-delta, delta, conflict, fresh-review, and
session-change state to exact heading, allowed action, retained content, focus target, and live
announcement.

The C2 read-model regression in
`tests/integration/connected_demo/test_evidence_composition_query_plans.py` seeds at least 512
historical receipts plus one current composition and uses
`EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)` after one untimed warm-up. Hard assertions require the exact
current-action/receipt/item index names, reject sequential scans of candidate/composition tables
and unbounded join/sort nodes, cap total examined rows at 256/512 and shared-hit blocks at 128/192,
and retain the 16/32 KiB response caps. Execution time is recorded only as a local observation and
is not an SLA or pass/fail threshold.

### Task C2.2 — Full bilingual browser-to-database proof

**Files**

- `web/e2e/mke-evidence-composition.spec.ts` (new);
- `scripts/verify_mke_evidence_composition.py` (extend with journey mode);
- `scripts/verify_compose.sh`;
- `web/playwright.compose.config.ts`;
- `tests/architecture/test_compose_contract.py`;
- exact seed/fixture paths required by the current demo.

Proof in zh-CN and en:

1. inspect untrusted MKE candidate and provenance;
2. accept as planning input;
3. explicitly request revision through the existing advisor review;
4. compose explicitly;
5. recover one lost response by exact body/key;
6. restart/reclaim worker;
7. observe successor source pack/revision/PlanningRun;
8. inspect old/new comparison and unresolved conflict;
9. complete fresh AdvisorReview;
10. preserve current-only FamilyDecision;
11. continue existing timeline/execution journey.

A separate provider-free failure lane exhausts the fixed automatic attempt budget, proves the old
revision/run stayed current, performs assigned-advisor abandon with one lost-response replay, and
proves the Case returned to prior AdvisorReview with no new PlanningRun and no second composition.

Counterfactual:

- stale second tab;
- role/session change;
- cross-Case envelope;
- candidate accepted under prior revision;
- foreign source/conflict item;
- receipt/result contradiction;
- failed worker before/after durable checkpoints;
- generic cancel, non-advisor/early abandon, late old-generation finalize, and second composition
  after abandon;
- retrieved instruction text.

DB verifier closes every candidate, decision, composition, Evidence, source-pack/revision,
PlanningRun, task/execution, family, timeline, and idempotency identity.

### Task C2.3 — C2 terminal gates

Run:

```bash
make check
uv run python scripts/verify_release.py --tree-mode development
COMPOSE_PROJECT_NAME=<unique> make compose-proof
COMPOSE_PROJECT_NAME=<same> \
  EVIDENCE_LOOP_RUN_ROOT="${EVIDENCE_LOOP_RUN_ROOT:-}" \
  make evidence-loop-down
uv run python scripts/verify_mke_evidence_composition.py \
  --mode journey \
  --write-proof tests/fixtures/evidence_loop/c2-composition-journey-proof-v1.json \
  --json
git diff --check
```

`make check` is the one full non-Compose final-candidate gate and includes lock, Python, Web,
database, and proof checks. Development uses the focused commands from C2.1/C2.2. Record
host/VM/Docker inventories and exact browser/database evidence.

**Commits**

- `feat: compose accepted evidence into governed planning`
- `test: prove advisor-governed evidence composition`
- `docs: document governed multimodal evidence composition`

## 7. PR D — v0.1.6 release preparation

### Task D1 — Documentation truth audit

Evaluate and update only affected current documents:

- `README.md`;
- `README_CN.md`;
- `DESIGN.md`;
- `SECURITY.md`;
- `docs/README.md`;
- advisor/mixed-planning/timeline operation guides;
- `docs/reference/mke-readonly-consumer.md`;
- new composition operation/reference guide;
- ADR/spec/plan status and index.

Run `document-release` once because this is a public architecture and workflow change. Do not create
duplicative generated docs.

Required public truth:

- frozen provider-free reference workflow, not arbitrary-corpus intake;
- MKE/DRA read-only non-authority;
- existing governed DRA baseline, not DRA Markdown parsing;
- retrieved content is untrusted;
- advisor accepts planning input, not source truth;
- one PostgreSQL composition authority;
- frozen-suite result and its limits;
- no runtime multi-agent, production, provider-backed, real-user, outcome, or audit-zero claim.

### Task D2 — Release identity

Update:

- Python/Web/package-lock/API release identity to `0.1.6`;
- `uv.lock` only for the mechanical project-version change;
- `docs/releases/v0.1.6.md` (new);
- `docs/how-to/verify-v0.1.6-release.md` (new);
- `scripts/verify_release.py`;
- release surface/architecture contracts.

Freeze v0.1.0–v0.1.5 notes and guides bytewise. Migration head becomes `0017`. Dependency resolution
must remain unchanged unless a separate dependency authority exists.

### Task D3 — Release-prep gates

Run the full project release-prep suite, one normal task-scoped Compose proof, explicit down,
clean-tree release verifier with isolated wheel import, diff/history/hygiene scans, and exact
documentation audit.

PR D does not tag or publish. Hosted exact-head and post-merge exact-SHA checks are mandatory.

After merge:

1. merged-main Gate C;
2. Git-free prepublication Gate D;
3. separate annotated `v0.1.6` tag and GitHub Release authority;
4. public GitHub-generated archive Gate E;
5. terminal PR body reconciliation and cleanup.

## 8. Docker and Compose contract

### 8.1 Preflight

Record:

```bash
df -k /
docker system df
docker buildx du
docker compose ls --format json
docker ps -a
docker image ls
docker volume ls
docker network ls
```

Also record Docker VM filesystem availability through the project's documented doctor/preflight.
Both host and VM must meet the enforced minimum. Do not infer one from the other.

### 8.2 Ownership and reuse

- unique task-owned `COMPOSE_PROJECT_NAME`;
- exact project containers, networks, ephemeral volumes, and local images;
- build once per frozen source candidate;
- reuse only project-native no-build paths;
- preserve `night-voyager_postgres-data`;
- preserve shared base/proof images and BuildKit cache;
- no broad prune, daemon/proxy/source change, or disk resize.

Slice 0's disposable MKE store is task-owned and separate from Night Voyager business data. Its
preparation mutation and sealed evaluation window are independently inventoried.

All real PostgreSQL lanes use task-owned ephemeral volumes. They must not use
`night-voyager_postgres-data` as test authority; that retained volume is read-only inventory for
cleanup purposes. A task may reuse exact project-native build output for one frozen source
candidate, but may not substitute a moving image or stale worktree.

### 8.3 Teardown

Do not change the existing retention-oriented `make down`. Every evidence-loop/Compose lane installs
one trap that calls the task-specific teardown and then calls it explicitly on ordinary success:

```bash
COMPOSE_PROJECT_NAME=<same> \
  EVIDENCE_LOOP_RUN_ROOT="${EVIDENCE_LOOP_RUN_ROOT:-}" \
  make evidence-loop-down
```

`evidence-loop-down` delegates to `scripts/teardown_evidence_loop.sh`, requires a non-empty
task-owned Compose project name, runs exact-project
`docker compose down --volumes --remove-orphans --rmi local`, and removes a run root only when its
ownership receipt matches the current task. Signal, failure, and ordinary exit invoke the same
idempotent function once.

Read back zero task-owned projects, containers, networks, ephemeral volumes, local images, process
groups, temporary files, open ports, and disposable MKE-store paths. Also assert that
`night-voyager-postgres-data`, shared base/proof images, and BuildKit cache still exist. Retained
shared resources remain; no volume/image/cache outside the exact task inventory is removed. A
failed proof does not broaden cleanup authority.

## 9. Failure and recovery matrix

| Boundary | Required result | Counterexamples |
| --- | --- | --- |
| Producer locks | exact archives/wheels/schemas | moving checkout, hash drift, tool drift |
| MKE store | sealed public-safe active set | post-seal ingest, private source, store drift |
| Baseline | governed typed export with original provenance | Markdown parsing, missing verification, retroactive pin |
| Evaluation | eight cases, four arms, frozen holdouts | reveal leakage, decoy novelty, lost conflict, `capped` pass |
| Trust | retrieved content remains inert | prompt injection, HTML, link/tool argument mutation |
| Candidate | immutable and assigned-advisor terminal | foreign Case, stale revision, concurrent terminal decision |
| Composition | all-or-nothing current authority | partial write, stale pack/run, rejected candidate, wrong advisor |
| Runtime | complete operation ships with route | orphan queued task, pin drift, restart/reclaim |
| Terminal composition recovery | prior current plan preserved, assigned-advisor abandon only | premature current advance, generic cancel, second compose, late finalize |
| Recovery | receipt plus fresh authoritative read | cross-Case envelope, session change, changed replay body |
| Release | exact version/head/history | stale migration, changed old notes, wrong tag/Release body |

### 9.1 Rollback and forward-recovery contract

- **PR A:** revert evaluator/docs/contracts and end the direction. No product schema or business row
  exists. A revealed holdout remains retired even after code rollback.
- **PR B1:** migration `0016` may downgrade only when its lossless no-candidate/history predicate
  passes. Once history exists, do not delete it to force rollback; block new imports with a reviewed
  forward compatibility change and retain read/decision evidence.
- **PR B2:** presentation/BFF changes may revert independently while B1's authenticated backend and
  immutable rows remain readable. A pending request is resolved by receipt/GET before rollback.
- **PR C1:** migration `0017` may downgrade only when there is no v2 Skill, composition, task,
  execution, result, or recovery history. With history, rollback is forward-only: first disable new
  compose POSTs in a bounded compatibility patch, retain GET and assigned-advisor abandon, allow
  current tasks to finalize or reach terminal abandon, and keep the schema/catalog pins. Never
  deploy an old worker that cannot validate a persisted v2 task.
- **PR C2:** Web/read-model presentation may revert independently to the deployable C1 headless
  API. Resolve any accepted receipt through authoritative GET before switching clients.
- **PR D/publication:** before tag/Release, revert the release-prep commit if necessary. After an
  annotated release is published, do not move/delete the tag or rewrite the Release to simulate
  rollback; ship a new corrective version.

Every rollback records exact main/schema/task/history identity before action and repeats
connected-demo/read compatibility, migration catalog, worker pin, and task-owned cleanup checks
after action. A failed lossless predicate is a stop, not authorization to truncate immutable rows.

## 10. Stage receipts

| Persisted readiness receipt | Committed proof artifact | Unlocks | Invalidated by / stop code |
| --- | --- | --- | --- |
| `StageReadinessReceiptV1(stage=slice0)` in merged PR A body | `slice0-receipt-v2.json` | B1 only when `incremental_value_confirmed` | identity/evaluator/store/holdout drift or non-confirmation -> exit 10/12 |
| `StageReadinessReceiptV1(stage=candidate-authority)` in merged PR B1 body | `b1-candidate-authority-proof-v1.json` | B2 | missing RLS/API/zero-promotion proof -> exit 12 |
| `StageReadinessReceiptV1(stage=candidate-journey)` in merged PR B2 body | `b2-candidate-journey-proof-v1.json` | C1 only with exact accepted decision | Case/revision/candidate/decision/browser recovery drift -> exit 10/12 |
| `StageReadinessReceiptV1(stage=composition-authority)` in merged PR C1 body | `c1-composition-authority-proof-v1.json` | C2 | atomicity/runtime/v1 compatibility/abandon mismatch -> exit 10/12 |
| `StageReadinessReceiptV1(stage=composition-journey)` in merged PR C2 body | `c2-composition-journey-proof-v1.json` | PR D | missing bilingual DB/recovery/continuation evidence -> exit 12 |

`PreRegistrationReceiptV2`, `SealedMkeStoreReceiptV1`,
`MkeCandidateDecisionReceiptV1`, and `EvidenceCompositionReceiptV1` remain domain/evaluation
artifacts referenced by the corresponding committed proof. They do not by themselves authorize a
new branch. Every next branch first runs `verify_stage_readiness.py`; no local, unmerged, malformed,
or failed-readback receipt unlocks anything.

## 11. Verification matrix

| PR | Focused gates | Full non-Compose | Normal Compose | Hosted |
| --- | --- | --- | --- | --- |
| A | contracts, store seal, evaluator, native tagged wheel | one `make check` + verifier | no new product lane | exact-head required checks |
| B1 | migration, RLS, repository, HTTP | one `make check` + verifier | none | exact-head required checks |
| B2 | Web/recovery, candidate browser/DB | one `make check` + verifier | one task-scoped run | exact-head required checks |
| C1 | migration, atomicity, HTTP/task/worker/skill | one `make check` + verifier | none; headless operation | exact-head required checks |
| C2 | read model/BFF/Web/recovery | one `make check` + verifier | one task-scoped run | exact-head required checks |
| D | docs/release/current version | full release-prep | one task-scoped run | exact-head and post-merge |

## 12. Completion and safe termination

Full completion requires:

- [ ] merged PR A with exact `incremental_value_confirmed`;
- [ ] merged B1/B2 with immutable candidate, assigned-advisor terminal decision, recovery, and zero
      promotion before composition;
- [ ] merged C1/C2 with staged atomic composition, success-only activation, bounded terminal
      abandon, complete runtime operation, retained conflict, successor lineage, and bilingual
      browser-to-database proof;
- [ ] merged PR D with v0.1.6 identity and frozen v0.1.0–v0.1.5 history;
- [ ] merged-main Gate C, Git-free Gate D, annotated Release, and public archive Gate E;
- [ ] exact task-owned Git/Docker/temp/execution-window cleanup.

Safe early local closeout for this run requires:

- [x] `evaluation_invalid` recorded after the one-way reveal and pre-capture evaluator stop;
- [x] no candidate, product persistence, Slice 1/2, v0.1.6, provider, or publication work;
- [x] truthful safe-stop documentation in the ADR, index, spec, and plan;
- [x] the exact revealed holdout retained as retired evidence, with capture and terminal receipt
      absent;
- [ ] merged PR A, hosted CI, and publication cleanup reviewed and completed.

## 13. Implementation mandate summary

One implementation mandate may authorize this bounded phase after renewed architecture approval:

- mechanically land the exact approved design/plan/ADR/index;
- execute PR A and stop on its merged disposition;
- if and only if unlocked, execute B1, B2, C1, C2, and D in order;
- perform TDD, local commits, authority review repairs, targeted re-review, Draft PR lifecycle,
  exact-head hosted monitoring, conditional non-admin squash merge, post-merge readback, and
  task-owned cleanup;
- perform v0.1.6 Gate C/D/E and publication only if the authorization package explicitly includes
  annotated tag/Release creation and every earlier gate passes.

The mandate does not authorize producer changes, a new corpus, threshold/holdout substitution,
scope-changing architecture repair, real provider/credential use, broad Docker cleanup, deploy, or
any claim beyond the frozen-suite/product evidence.

## GSTACK REVIEW REPORT

Fresh sequential AutoPlan review is complete on this revision:

- CEO: all four P0 findings closed; the staged falsification direction remains the smallest
  coherent product.
- Design: initial 6.3/10; final interaction, authority, bilingual copy, accessibility, and
  no-new-dashboard findings incorporated.
- Engineering: final 99/100, `READY = YES`, P0 = 0, P1 = 0.
- Developer Experience: final 9.4/10, `READY = YES`, P0 = 0, P1 = 0, P2 = 0 after the final
  ownership/custody wording correction.

The review did not reopen the approved direction. Option A remains the mandatory Slice 0
falsification gate, Option B remains conditional on its merged confirmation receipt, and generic
Option C remains deferred/rejected. No substantive user choice remains. The design, plan, review
record, and mandate are ready for one implementation mandate.
