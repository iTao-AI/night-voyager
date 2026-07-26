# DRA v0.1.6 Live Closure PR B Implementation Plan

**Implementation status:** PR A, PR B, PR C, and the effective-query v2 repair are
implemented provider-free. One bounded live attempt projected 25 Evidence rows, all
`uncited`, and stopped safely before candidate import; governed live acceptance
remains pending.

> **For agentic workers:** REQUIRED PRIMARY CONTROLLER: use
> `superpowers:executing-plans`. Execute serially on top of merged PR A. Do not use
> subagents or parallel write lanes because receipt identity, filesystem lifetime,
> reconciliation, and candidate import share one authority chain.

**Goal:** Add a provider-free-tested Stage 1 live-capture controller that freezes one
attempt, validates one DRA terminal result, requires exact human source selection,
imports one existing untrusted candidate, and emits a content-free recovery bundle.

**Architecture:** A pure controller consumes the PR A transport/projection contracts
through narrow ports. A task-owned receipt store persists only canonical JSON
identities and hashes using atomic writes; canonical artifact bytes exist only in a
private inspection directory and are deleted after candidate import or any stop.
Ambiguous creation and late result handling reconcile only the same frozen intent and
run under explicit stage authorization.

**Tech Stack:** Python 3.12, Pydantic 2, httpx2, existing FastAPI candidate API,
stdlib filesystem/JSON/hash primitives, pytest, uv/Hatch, Docker Compose.

## Global Constraints

- Base PR B only on the exact merged PR A main. Record base SHA and verify migration
  head `0010`.
- PR B owns Stage 1 `capture-live`, frozen intent, stage receipts, recovery bundle,
  exact source selection, and existing candidate-import composition. It does not
  promote, create a planning task, review, decide, call a live provider during
  implementation/CI, or change DRA.
- One scenario has one `attempt_id`, one intent hash, one DRA create key, and at most
  one remote run. No automatic retry and no implicit second run.
- An ambiguous create produces a reconciliation-required receipt and stops.
  Replaying the exact create requires a separate stage authorization and identical
  intent/key. Poll timeout marks the provider attempt consumed and may later poll
  only the same `run_id`.
- Stage 1 selects only one exact cited raw URL. It accepts no source snapshot,
  attestation fields, or promotion instruction.
- Artifact bytes are inspection-only, never printed or persisted in a receipt, and
  are deleted after candidate import, handled failure, interrupt, and cleanup.
- Candidate import uses the existing assigned-advisor HTTP authority and remains
  `UNTRUSTED_CANDIDATE`.
- Required gates are deterministic and use fake transport plus local Night Voyager
  HTTP/database fixtures only. The live command remains absent from required CI.
- Preserve all PR A Docker, Git staging, public-hygiene, and retained-resource rules.

## File Structure

- `src/night_voyager/dra/live_ports.py` — transport, candidate gateway, receipt store,
  clock, sleep, and artifact-inspection protocols.
- `src/night_voyager/dra/live_storage.py` — safe root, atomic content-free receipt
  writes, private artifact file lifecycle, and recovery-bundle verification.
- `src/night_voyager/dra/live_controller.py` — Stage 1 state machine,
  domain-separated idempotency, ambiguous-create stop, polling, source selection,
  candidate import, and cleanup.
- `src/night_voyager/dra/live_fakes.py` — deterministic fake transport/gateway used
  by required tests and rehearsal.
- `scripts/verify_dra_live_closure.py` — public-neutral CLI for `capture-live`,
  `reconcile-capture`, `rehearse-capture`, `inspect`, and `cleanup`.
- `scripts/run_dra_lane.sh` — isolated dependency environment and CLI routing.

---

### Task B1: Freeze Stage 1 intent, receipt, and idempotency semantics

**Files:**
- Modify: `src/night_voyager/dra/live_models.py`
- Create: `src/night_voyager/dra/live_ports.py`
- Create: `tests/unit/dra/test_live_intent.py`
- Modify: `tests/contracts/test_dra_live_models.py`

**Interfaces:**
- `derive_stage_key(intent_sha256, stage, target_identity) -> str`
- `DraCaptureInputV1` contains exact Case/revision, advisor actor/tenant identity,
  bounded request identity, receipt root, and authorization flag; it contains no
  selected URL or reusable session material.
- `DraCaptureReceiptV1` contains producer/intent/run/artifact/selected Evidence and
  candidate identities plus cleanup result, never content.
- `DraReconciliationRequiredReceiptV1` retains the exact create identity and permitted
  next action.

- [ ] **Step 1: Write RED tests**

  Freeze canonical intent JSON, one generated `attempt_id`, domain separation across
  create/import stages, same-input stability, different-target divergence, and
  rejection of whitespace, secret-like, content-bearing, unknown, or missing fields.
  Assert a child receipt cannot validate without its parent intent.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q tests/unit/dra/test_live_intent.py \
    tests/contracts/test_dra_live_models.py
  ```

  Expected: failures because Stage 1 input and key derivation are absent.

- [ ] **Step 3: Implement exact intent and keys**

  Use a domain-separated hash:

  ```python
  def derive_stage_key(intent_sha256: str, stage: str, target: str) -> str:
      payload = f"night-voyager.dra-live.v1\\0{intent_sha256}\\0{stage}\\0{target}"
      return hashlib.sha256(payload.encode("utf-8")).hexdigest()
  ```

  The create key is derived once from intent plus `attempt_id`; candidate import key
  uses the same intent but a distinct stage and Case identity. Never generate a new
  attempt or key during recovery.

- [ ] **Step 4: Run GREEN**

  Run Step 2. Expected: all tests pass with byte-stable intent and receipt hashes.

- [ ] **Step 5: Commit**

  ```bash
  git add src/night_voyager/dra/live_models.py \
    src/night_voyager/dra/live_ports.py \
    tests/unit/dra/test_live_intent.py \
    tests/contracts/test_dra_live_models.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: freeze DRA live capture identity"
  ```

### Task B2: Implement safe receipt and artifact lifecycle storage

**Files:**
- Create: `src/night_voyager/dra/live_storage.py`
- Create: `tests/unit/dra/test_live_storage.py`
- Modify: `tests/security/test_dra_catalog.py`

**Interfaces:**
- `LiveReceiptStore.open(root: Path) -> LiveReceiptStore`
- `write_receipt(name, model) -> ReceiptIdentityV1`
- `read_receipt(name, model_type) -> model`
- `write_artifact_for_inspection(identity, content) -> Path`
- `delete_artifact() -> CleanupResultV1`
- `verify_recovery_bundle() -> RecoveryBundleV1`

- [ ] **Step 1: Write filesystem RED tests**

  Use a real temporary directory to prove:

  ```text
  root must exist, be task-owned, non-symlink, and mode 0700
  receipt names are allowlisted and traversal-free
  atomic temp-write -> fsync -> replace
  receipt files use mode 0600
  duplicate same bytes replay; different bytes conflict
  artifact uses mode 0600 and exact length/hash
  artifact is removed on success, exception, interrupt hook, and cleanup
  recovery bundle contains no content/body/prompt/header/env/private path
  symlink, root escape, partial write, malformed JSON, and forged hash fail closed
  ```

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q tests/unit/dra/test_live_storage.py \
    tests/security/test_dra_catalog.py
  ```

  Expected: collection fails because safe storage does not exist.

- [ ] **Step 3: Implement fail-closed storage**

  Resolve the declared root once with `strict=True`; reject if symlinked or not owned
  by the current process user. Use `os.open` flags that refuse symlink following
  where supported, verify `stat` after open, and always compare resolved child paths
  against the root. Receipt JSON uses canonical UTF-8 bytes. Artifact content is
  exposed only through a context manager:

  ```python
  with store.inspect_artifact(identity, content) as artifact_path:
      operator.inspect(artifact_path)
  # path is absent here even when the body raises
  ```

- [ ] **Step 4: Run GREEN**

  Run Step 2. Expected: all lifecycle and counterfactual tests pass.

- [ ] **Step 5: Commit**

  ```bash
  git add src/night_voyager/dra/live_storage.py \
    tests/unit/dra/test_live_storage.py \
    tests/security/test_dra_catalog.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add DRA live recovery storage"
  ```

### Task B3: Add the provider-free Stage 1 controller

**Files:**
- Create: `src/night_voyager/dra/live_controller.py`
- Create: `src/night_voyager/dra/live_fakes.py`
- Create: `tests/unit/dra/test_live_capture_controller.py`
- Modify: `tests/contracts/test_dra_reconciliation.py`
- Modify: `tests/unit/dra/test_application.py`

**Interfaces:**
- `DraLiveCaptureController.capture(command) -> DraInspectionRequiredReceiptV1`
- `select_and_import(command) -> DraCaptureReceiptV1`
- `reconcile_create(command, prior_failure) -> DraCaptureReceiptV1 | failure`
- `resume_poll(command, prior_failure) -> DraCaptureReceiptV1 | failure`
- The candidate gateway calls the existing
  `POST /api/v1/cases/{case_id}/dra-candidates` contract.

- [ ] **Step 1: Write controller RED tests**

  Cover the happy path and injected stop after each boundary:

  ```text
  preflight -> create -> accepted -> poll -> terminal -> artifact
  -> Evidence ownership -> inspection -> exact URL selection
  -> candidate import -> artifact cleanup -> receipt
  ```

  Also cover ambiguous create with no automatic replay, explicitly authorized exact
  replay, same-key/different-payload conflict, deadline exhaustion, later same-run
  terminal reconciliation, wrong run/segment, malformed terminal state, zero/multiple
  selected URLs, import conflict, wrong actor/tenant, crash after each receipt, and
  no second create call.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/unit/dra/test_live_capture_controller.py \
    tests/contracts/test_dra_reconciliation.py \
    tests/unit/dra/test_application.py
  ```

  Expected: failures because Stage 1 controller and fakes do not exist, and the old
  reconciler still automatically replays ambiguous creation.

- [ ] **Step 3: Implement Stage 1 state machine**

  Make ambiguous create a stable stop:

  ```python
  try:
      acceptance = await transport.create_run(request, create_key)
  except DraAmbiguousOutcome:
      return store.write_failure(
          phase="run_acceptance_ambiguous",
          provider_attempt_consumed=True,
          permitted_next_action="reconcile_exact_create",
      )
  ```

  Reconciliation is a separate method requiring the prior failure receipt and exact
  authorization. Poll timeout stores `run_id`, last state version, deadline, and
  `permitted_next_action=poll_same_run`; it never calls create again.

  After strict projection, write artifact bytes to the inspection context and stop
  with an inspection-required receipt. A separate provider-free
  `select_and_import` resume requires the operator-declared raw URL, revalidates the
  same run/artifact/Evidence identities, calls `select_cited_evidence`, imports
  exactly that row, confirms untrusted authority, and only then deletes artifact
  bytes and finalizes the capture receipt.

- [ ] **Step 4: Run GREEN**

  Run Step 2. Expected: all tests pass; each failure has a closed phase and bounded
  next action; no test observes a second run.

- [ ] **Step 5: Commit**

  ```bash
  git add src/night_voyager/dra/live_controller.py \
    src/night_voyager/dra/live_fakes.py \
    tests/unit/dra/test_live_capture_controller.py \
    tests/contracts/test_dra_reconciliation.py \
    tests/unit/dra/test_application.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add bounded DRA live capture"
  ```

### Task B4: Wire CLI, fake rehearsal, and recovery bundle

**Files:**
- Create: `scripts/verify_dra_live_closure.py`
- Modify: `scripts/run_dra_lane.sh`
- Modify: `scripts/verify_dra_consumer.py`
- Modify: `Makefile`
- Modify: `tests/unit/dra/test_proof_controller.py`
- Create: `tests/integration/dra/test_live_capture_rehearsal.py`
- Modify: `tests/architecture/test_dra_contract.py`

**Interfaces:**
- CLI subcommands:
  `freeze-intent`, `preflight-live`, `rehearse-capture`, `capture-live`,
  `select-and-import`, `reconcile-create`, `resume-poll`, `inspect-recovery`, and
  `cleanup`.
- Required `make dra-check` runs `rehearse-capture` with fake transport.
- `make dra-consumer-proof` remains optional and calls `capture-live`; it is absent
  from CI.

- [ ] **Step 1: Write CLI RED tests**

  Assert exact subcommands, closed arguments, no secret-bearing argument, no default
  live action, `capture-live` requiring both one-attempt acknowledgement and frozen
  intent, fake rehearsal requiring no network/credential, and bounded JSON/stdout.
  Run recovery from a copied receipt directory in a new process to prove no in-memory
  dependency.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/unit/dra/test_proof_controller.py \
    tests/integration/dra/test_live_capture_rehearsal.py \
    tests/architecture/test_dra_contract.py
  ```

  Expected: failures because the staged CLI and rehearsal do not exist.

- [ ] **Step 3: Implement CLI and fake rehearsal**

  Credentials and live sessions remain process-only and are read only by the command
  that needs them. Query content is read from an operator-supplied bounded UTF-8 file
  but never printed or copied into a receipt. The selected raw URL is accepted only
  by `select-and-import` after the inspection-required receipt exists; the final
  receipt stores it because it is public source identity.

  `rehearse-capture` uses the versioned scenario, fake DRA transport, and existing
  Night Voyager candidate API/database fixture. It produces a recovery bundle, then
  verifies and deletes it within the test-owned temp root.

- [ ] **Step 4: Run GREEN**

  Run Step 2 plus:

  ```bash
  make dra-check
  ```

  Expected: provider-free rehearsal passes and required CI still contains no live
  acknowledgement or provider credential.

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/verify_dra_live_closure.py scripts/run_dra_lane.sh \
    scripts/verify_dra_consumer.py Makefile \
    tests/unit/dra/test_proof_controller.py \
    tests/integration/dra/test_live_capture_rehearsal.py \
    tests/architecture/test_dra_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "test: add DRA live capture rehearsal"
  ```

### Task B5: Document recovery and complete PR B gates

**Files:**
- Modify: `docs/operations/dra-consumer-proof.md`
- Modify: `docs/reference/dra-governed-evidence.md`
- Modify: `docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md`
- Modify: `scripts/verify_release.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: approved spec and PR A/PR B plan status banners

- [ ] **Step 1: Write docs/release RED tests**

  Require documented one-attempt semantics, exact recovery commands, ambiguous-create
  stop, same-run late polling, artifact lifetime, URL-only Stage 1 selection,
  candidate-untrusted boundary, no remote cancellation, no provider call during PR B,
  and PR C still unimplemented.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py tests/architecture/test_dra_contract.py
  ```

- [ ] **Step 3: Update docs and verifier**

  Document environment variable names only, never values. State that a Stage 1
  success is not promotion or governed-live closure. Preserve historical release
  documents.

- [ ] **Step 4: Run complete PR B verification**

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

  Record Docker pre/post inventory and scan the full branch for content leakage,
  private paths, secrets, proxy persistence, task metadata, and historical release
  drift. Do not run `capture-live`.

- [ ] **Step 5: Commit**

  Stage only Task B5 files and commit:

  ```bash
  git commit -m "docs: publish DRA live capture recovery"
  ```

## Final Plan-Review Corrections

These corrections are normative and supersede any earlier ambiguous task wording:

1. **Stage 1 is a post-result, two-step inspection boundary.**
   `DraCaptureInputV1` contains Case/revision, advisor actor/tenant identity,
   bounded request identity, receipt root, and one-attempt authorization. It contains
   neither a selected URL nor reusable session material. `capture-live` performs the
   one provider run, validates the terminal result, writes the private canonical
   artifact plus bounded same-run Evidence inventory, then stops with an
   `operator_action_required` / inspection-required receipt before candidate import.
   Only a separate provider-free `select-and-import` command may accept the raw URL.
   It re-verifies the same intent/run/artifact/Evidence identities, imports the exact
   unique cited row, confirms `UNTRUSTED_CANDIDATE`, deletes the artifact, and
   finalizes the capture receipt. A URL supplied before the inspection receipt is
   rejected.
2. **The artifact context spans import.** The content remains available only from
   terminal projection through operator inspection and candidate import/replay.
   Cleanup occurs afterward or on handled failure. Normal exit, handled exception,
   `SIGINT`, and `SIGTERM` are synchronous guarantees. `SIGKILL`, host crash, and
   power loss are non-guarantees: next store open detects allowlisted residue,
   records `cleanup_incomplete`, and blocks downstream stages until explicit safe
   cleanup.
3. **Filesystem operations bind descriptors, not checked pathnames.** Open the
   task-owned mode-`0700` root as a no-follow directory descriptor, verify
   owner/mode/type with `fstat`, and walk every logical component with
   directory-relative no-follow operations. Publish immutable receipts with
   create-once CAS semantics; exact existing bytes are replay and different bytes
   conflict. Fsync both file and parent directory. Add Linux tests for root/parent
   rename, symlink swap, same/same and same/different two-process races. Platforms
   lacking the required primitives fail closed for live commands.
4. **Frozen effective request bytes are checked immediately before provider
   access.** Re-read the bounded single-line UTF-8 base query, reject the reserved
   citation-clause marker, and deterministically compose
   `night-voyager.dra-live-effective-query.v2`. Compare the base/effective lengths
   and SHA-256 identities plus code-owned clause hash with both candidate readiness
   and intent before `health()` or `create_run()`. The clause requires one admitted
   `internet_search` public HTTPS source's exact raw URL in the final canonical
   report and forbids invented, altered, normalized, or guessed URLs. Legacy v1
   readiness/intent, same-path mutation, duplicate/replaced clause, CR/LF,
   empty/oversize/invalid UTF-8, or hash drift fails without consuming the provider
   attempt.
5. **Preflight and operator output are executable contracts.** Add provider-free
   `preflight-live`, producing a hash-bound readiness receipt over exact
   intent/scenario/schema/commit identities, receipt-root safety, candidate freeze,
   environment, and one-shot budget. `capture-live` requires that receipt. Freeze
   five exit classes: success, safe pause/operator action required, recoverable
   incomplete, terminal failure, and cleanup incomplete. Machine output contains a
   bounded problem code, receipt path/hash, safe interpretation, and exact permitted
   next command; raw exceptions are restricted and opt-in.
6. **Recovery is safe for a fresh process.** Durable receipts store actor/role/
   tenant identity hashes only, never session handles, cookie jars, headers, bearer
   material, auth paths, credentials, or environment values. Every recovery command
   re-injects the required live session ephemerally and revalidates it against the
   receipt actor. `inspect-recovery` shows intent/attempt/run, last completed stage,
   provider-attempt consumption, required external inputs, permitted and forbidden
   next actions, and content/session cleanup state.
7. **CLI and cleanup are closed.** The canonical commands are `freeze-intent`,
   `preflight-live`, `capture-live`, `select-and-import`, `reconcile-create`,
   `resume-poll`, `inspect-recovery`, `rehearse-capture`, and `cleanup`. Help labels
   each as provider-consuming/provider-free/read-only/mutating. Cleanup defaults to
   dry-run for one exact root, requires its own acknowledgement to delete, and
   reports removed/absent/retained/failed groups. Identity receipts and evaluation
   reports follow an explicit retention table.

Update B1-B5 interfaces, RED tests, file lists, staging commands, runbook, and
architecture contracts to match this two-step journey. PR B completion requires the
fake fresh-process rehearsal to pass inspection pause/resume without a second
provider call.

## PR B Completion Gate

- Final branch is clean and based on merged PR A.
- Fake Stage 1 reaches existing untrusted candidate import and cleans artifact bytes.
- Recovery works from receipts in a fresh process and never creates a second run.
- Required CI stays offline/provider-free.
- No source snapshot, promotion, planning, review, family decision, live provider,
  release, or deployment occurred.
