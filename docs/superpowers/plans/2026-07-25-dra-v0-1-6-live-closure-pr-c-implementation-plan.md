# DRA v0.1.6 Live Closure PR C Implementation Plan

**Implementation status:** PR A and PR B implemented provider-free; PR C remains approved but not implemented.

> **For agentic workers:** REQUIRED PRIMARY CONTROLLER: use
> `superpowers:executing-plans`. Execute serially on top of merged PR B. Do not
> dispatch parallel agents: Stage 2 attestation, promoted-pack identity, task/Skill
> pin, review, family decision, and evaluator output form one ordered authority chain.

**Goal:** Complete the provider-free governed closure from an existing live-capture
candidate receipt through explicit advisor source attestation, atomic promotion,
governed mixed planning, AdvisorReview, family decision, DecisionReceipt,
TimelinePlan, and matching trajectory/database evaluation.

**Architecture:** The PR B controller gains three resumable provider-free stages.
Stage 2 validates an operator-supplied private snapshot and calls the existing
advisor promotion API; Stage 3 uses existing AgentTask/worker/SSE/PlanningRun and
AdvisorReview authorities; Stage 4 uses existing family decision authority. A
read-only database inspector supplies outcome facts to the pure evaluator. No new
business table, workflow, browser route, queue, or provider call is introduced.

**Tech Stack:** Python 3.12, Pydantic 2, existing FastAPI/HTTP contracts,
PostgreSQL 18, SQLAlchemy/asyncpg, existing AgentTask worker/SSE, pytest, uv/Hatch,
Docker Compose.

## Global Constraints

- Base PR C only on the exact merged PR B main; record base SHA and verify migration
  head `0010`.
- Reuse existing candidate import, `verify_and_promote_dra_candidate`, source pack,
  `generate_governed_mixed_planning_run_v1`, Skill pin, worker lease/fencing, SSE,
  `AdvisorReview`, family decision, `DecisionReceipt`, and `TimelinePlan`.
- Add no new product table, HTTP route, browser demo, queue, worker, provider
  dependency, orchestration framework, or automatic authority.
- Stage 2 requires an existing capture receipt and a newly supplied task-owned source
  snapshot. It does not fetch the source and does not infer attestation metadata from
  DRA, artifact, or Evidence.
- The snapshot must bind exact selected raw URL, logical path, byte length, SHA-256,
  required known gaps, and assigned advisor action. Missing/mismatched/symlinked/
  escaped input fails before promotion with no partial rows.
- Snapshot bytes are deleted on success, handled failure, SIGINT/SIGTERM, and
  cleanup. Hard-termination residue is detected on next open and blocks later
  stages until safe cleanup. Recovery requires re-supplying the same bytes and
  identity.
- Stage 3 and Stage 4 re-read authoritative state before every mutation and use
  domain-separated idempotency keys. A receipt cannot substitute for database
  authority.
- Evaluation observes exact database projections and stage receipts; it never
  promotes, reviews, decides, retries a provider, or writes business state.
- Required CI and implementation remain offline/provider-free. Live acceptance is a
  later separately authorized gate after all PRs merge and candidate freeze.
- Preserve PR A/B Git, Docker, hygiene, and historical-release boundaries.

## File Structure

- `src/night_voyager/dra/live_controller.py` — Stage 2/3/4 orchestration and replay.
- `src/night_voyager/dra/live_ports.py` — promotion, task/SSE, review, decision, and
  read-only outcome-inspector protocols.
- `src/night_voyager/dra/live_storage.py` — re-supplied snapshot validation/lifetime.
- `src/night_voyager/dra/live_http.py` — narrow adapter over existing Night Voyager
  HTTP routes and assigned-advisor/parent sessions.
- `src/night_voyager/dra/live_outcome.py` — framework-free authoritative outcome
  model and inspector protocol.
- `src/night_voyager/dra/live_outcome_postgres.py` — SQLAlchemy/asyncpg read-only
  PostgreSQL projection and correlation adapter.
- `scripts/verify_dra_live_closure.py` — `promote`, `review`, `decide`, `evaluate`,
  provider-free `rehearse-full`, and frozen one-shot controller.
- `scripts/verify_dra_governed_flow.py` — shared deterministic helper only where the
  existing fixture flow and new closure truly use the same HTTP authority.

---

### Task C1: Validate operator-supplied snapshot and Stage 2 authority

**Files:**
- Modify: `src/night_voyager/dra/live_models.py`
- Modify: `src/night_voyager/dra/live_ports.py`
- Modify: `src/night_voyager/dra/live_storage.py`
- Modify: `src/night_voyager/dra/live_controller.py`
- Create: `src/night_voyager/dra/live_http.py`
- Create: `tests/unit/dra/test_live_promotion_controller.py`
- Modify: `tests/unit/dra/test_live_storage.py`
- Modify: `tests/integration/dra/test_http_dra.py`
- Modify: `tests/integration/dra/test_postgres_candidate_promotion.py`

**Interfaces:**
- `DraPromotionInputV1` binds capture receipt, candidate, Evidence ID, selected raw
  URL, expected Case revision, advisor actor, reason, and `SourceAttestationV1`.
- `validate_supplied_snapshot(root, attestation, selected_url) -> SnapshotIdentityV1`
- `DraLiveClosureController.promote(command) -> DraPromotionReceiptV1`
- `NightVoyagerAuthorityGateway.promote_candidate(...)` calls the existing
  verification-decision route.

- [ ] **Step 1: Write Stage 2 RED tests**

  Cover exact success plus missing snapshot, empty file, wrong root, absolute or
  traversal path, file/parent symlink, root escape, wrong URL, case/slash/encoding/
  query/fragment/port substitution, wrong byte length/hash, missing known gaps,
  wrong Evidence/candidate/Case/revision/advisor/tenant, DRA `verified` without
  advisor action, injected failure before/inside/after HTTP mutation, exact replay,
  same-key conflict, and snapshot deletion on every exit.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/unit/dra/test_live_promotion_controller.py \
    tests/unit/dra/test_live_storage.py \
    tests/integration/dra/test_http_dra.py \
    tests/integration/dra/test_postgres_candidate_promotion.py
  ```

  Expected: failures because Stage 2 composition and supplied-snapshot binding do not
  exist.

- [ ] **Step 3: Implement snapshot validation and promotion composition**

  Validation order is:

  ```text
  capture receipt -> current candidate -> assigned advisor -> selected Evidence
  -> exact raw URL -> safe declared root/path -> regular non-symlink file
  -> exact bytes/length/hash -> complete attestation -> atomic promotion
  ```

  Read bytes once from an already-validated descriptor, hash those exact bytes, and
  delete the task-owned copy in `finally`. The gateway sends existing
  `dra_evidence_id`, decision, reason, and source attestation. It must confirm the
  returned promoted pack/entry/Evidence identities before writing the receipt.

- [ ] **Step 4: Run GREEN**

  Run Step 2. Expected: success and replay are exact; every invalid input leaves
  candidate unpromoted and no partial verification/source-pack rows.

- [ ] **Step 5: Commit**

  ```bash
  git add src/night_voyager/dra/live_models.py \
    src/night_voyager/dra/live_ports.py \
    src/night_voyager/dra/live_storage.py \
    src/night_voyager/dra/live_controller.py \
    src/night_voyager/dra/live_http.py \
    tests/unit/dra/test_live_promotion_controller.py \
    tests/unit/dra/test_live_storage.py \
    tests/integration/dra/test_http_dra.py \
    tests/integration/dra/test_postgres_candidate_promotion.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: add explicit DRA source promotion stage"
  ```

### Task C2: Compose mixed planning, AdvisorReview, and family decision

**Files:**
- Modify: `src/night_voyager/dra/live_models.py`
- Modify: `src/night_voyager/dra/live_ports.py`
- Modify: `src/night_voyager/dra/live_controller.py`
- Modify: `src/night_voyager/dra/live_http.py`
- Create: `tests/unit/dra/test_live_review_controller.py`
- Create: `tests/unit/dra/test_live_decision_controller.py`
- Modify: `tests/integration/tasks/test_planning_start_authority.py`
- Modify: `tests/integration/dra/test_governed_closure.py`
- Modify: `tests/integration/decision/test_http_decision.py`

**Interfaces:**
- `review(command) -> DraReviewReceiptV1`
- `decide(command) -> DraDecisionReceiptV1`
- Review receipt binds promoted pack, task, five-field Skill pin, execution, terminal
  event, PlanningRun, and AdvisorReview.
- Decision receipt binds family actor, family decision, DecisionReceipt, and
  TimelinePlan.

- [ ] **Step 1: Write Stage 3/4 RED tests**

  Prove exact ordering and re-read:

  ```text
  promotion receipt -> current promoted mapping -> create mixed AgentTask
  -> observe task/execution/events/SSE/PlanningRun -> assigned advisor review
  -> parent/family decision -> DecisionReceipt + TimelinePlan
  ```

  Cover stale/wrong pack, wrong operation, stale/partial Skill pin, task conflict,
  worker failure, SSE mismatch, wrong PlanningRun, wrong/unassigned advisor,
  cross-tenant actor, review conflict, wrong parent, decision conflict, receipt/
  timeline mismatch, replay after crash, and no duplicate business rows.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/unit/dra/test_live_review_controller.py \
    tests/unit/dra/test_live_decision_controller.py \
    tests/integration/tasks/test_planning_start_authority.py \
    tests/integration/dra/test_governed_closure.py \
    tests/integration/decision/test_http_decision.py
  ```

  Expected: failures because downstream stage methods and receipt bindings do not
  exist.

- [ ] **Step 3: Implement Stage 3 and Stage 4**

  Stage 3 sends only:

  ```json
  {
    "operation": "generate_governed_mixed_planning_run_v1",
    "expected_case_revision": "<current exact revision>",
    "source_pack_id": "<promoted pack>",
    "source_pack_version": "<promoted version>"
  }
  ```

  The server resolves the five-field Skill pin; the controller verifies but never
  supplies it. Observe native SSE cursor/reconnect semantics without creating a
  second stream contract. Submit existing AdvisorReview only after the PlanningRun
  terminal projection matches the task.

  Stage 4 uses the existing family route and verifies exact receipt/timeline
  correlation. Each stage writes its success receipt only after authoritative
  response and re-read agree.

- [ ] **Step 4: Run GREEN**

  Run Step 2. Expected: full provider-free downstream authority path passes and all
  conflict/rollback cases remain fail closed.

- [ ] **Step 5: Commit**

  ```bash
  git add src/night_voyager/dra/live_models.py \
    src/night_voyager/dra/live_ports.py \
    src/night_voyager/dra/live_controller.py \
    src/night_voyager/dra/live_http.py \
    tests/unit/dra/test_live_review_controller.py \
    tests/unit/dra/test_live_decision_controller.py \
    tests/integration/tasks/test_planning_start_authority.py \
    tests/integration/dra/test_governed_closure.py \
    tests/integration/decision/test_http_decision.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: compose governed DRA decision closure"
  ```

### Task C3: Add authoritative outcome inspection and final evaluation

**Files:**
- Create: `src/night_voyager/dra/live_outcome.py`
- Create: `src/night_voyager/dra/live_outcome_postgres.py`
- Modify: `src/night_voyager/dra/live_evaluation.py`
- Create: `tests/unit/dra/test_live_outcome_evaluation.py`
- Create: `tests/integration/dra/test_live_outcome_projection.py`
- Modify: `tests/security/test_dra_catalog.py`

**Interfaces:**
- `LiveOutcomeInspector.inspect(context, intent) -> DraLiveOutcomeProjectionV1`
- `evaluate_full_closure(scenario, receipts, outcome) -> DraLiveEvaluationReportV1`
- Outcome projection is read-only and contains exact counts/identities for candidate,
  verification, promoted mapping, external Evidence, task/execution/events/Skill pin,
  PlanningRun, AdvisorReview, family decision, DecisionReceipt, and TimelinePlan.

- [ ] **Step 1: Write evaluator/database RED tests**

  Assert:

  ```text
  exactly one candidate and terminal approval
  claim australia_program_fit
  evidence role program_fit
  authority externally_verified
  exact promoted pack mapping
  one governed mixed task and expected terminal run
  one advisor review, family decision, receipt, timeline
  same tenant and correlated IDs
  trajectory assertions and DB assertions agree
  ```

  Inject missing, duplicate, cross-tenant, mismatched, partial, reordered, forged,
  and unknown rows. Ensure evaluation failure performs no writes.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/unit/dra/test_live_outcome_evaluation.py \
    tests/integration/dra/test_live_outcome_projection.py \
    tests/security/test_dra_catalog.py
  ```

- [ ] **Step 3: Implement read-only projection and report**

  Reuse runtime-equivalent actor context and RLS. Use bounded explicit selects; do not
  grant new DML or expose raw SQL. Keep Pydantic outcome models and the inspector
  protocol independent of SQLAlchemy; only `live_outcome_postgres.py` imports the
  database stack. The final report contains both trajectory and outcome assertion
  arrays and derives success only when every required assertion passes. A failure
  receipt can be evaluated as safe-stop evidence but never yields capability success.

- [ ] **Step 4: Run GREEN**

  Run Step 2. Expected: deterministic JSON and readable report agree across repeated
  runs; injected inconsistencies fail closed with bounded public codes.

- [ ] **Step 5: Commit**

  ```bash
  git add src/night_voyager/dra/live_outcome.py \
    src/night_voyager/dra/live_outcome_postgres.py \
    src/night_voyager/dra/live_evaluation.py \
    tests/unit/dra/test_live_outcome_evaluation.py \
    tests/integration/dra/test_live_outcome_projection.py \
    tests/security/test_dra_catalog.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "feat: evaluate governed DRA live outcomes"
  ```

### Task C4: Prove a full offline closure and recovery matrix

**Files:**
- Modify: `scripts/verify_dra_live_closure.py`
- Modify: `scripts/verify_dra_governed_flow.py`
- Modify: `scripts/verify_compose.sh`
- Modify: `scripts/seed_dra_proof.py`
- Create: `tests/integration/dra/test_live_closure_recovery.py`
- Modify: `tests/integration/dra/test_governed_closure.py`
- Modify: `tests/architecture/test_compose_contract.py`
- Modify: `Makefile`

**Interfaces:**
- CLI subcommands add `promote`, `review`, `decide`, `evaluate`, and
  `rehearse-full`.
- `make dra-check` runs the pure/provider-free recovery matrix.
- `make compose-proof` runs one deterministic full closure against real PostgreSQL,
  FastAPI, worker, SSE, and database inspector using fake DRA transport.

- [ ] **Step 1: Write recovery and Compose RED tests**

  Require fresh-process resume after every stage, forged/missing receipt rejection,
  re-supplied snapshot identity, no artifact/source bytes in bundle, no second
  provider run, exact task/Skill pin/SSE/run correlations, rollback injection, and
  task-owned teardown. Bind exact Compose coverage markers.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/integration/dra/test_live_closure_recovery.py \
    tests/integration/dra/test_governed_closure.py \
    tests/architecture/test_compose_contract.py
  ```

- [ ] **Step 3: Implement the full offline rehearsal**

  The fake DRA transport emits the real `v0.1.6` status/result shapes from the
  versioned scenario. The source snapshot is copied into a task-owned private root
  only for Stage 2 and removed by the stage trap. Reuse existing seeded synthetic
  actors/Case and public HTTP routes. `scripts/verify_compose.sh` builds once and
  reuses unchanged images; it tears down only the unique proof project.

- [ ] **Step 4: Run focused and full Compose GREEN**

  ```bash
  make dra-check
  make doctor MODE=dev
  make compose-proof
  make down
  docker compose ps --all
  ```

  Expected: one full deterministic closure, exact evaluator success, zero task-owned
  containers/networks/ephemeral volumes/images after teardown, retained resources
  unchanged.

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/verify_dra_live_closure.py \
    scripts/verify_dra_governed_flow.py \
    scripts/verify_compose.sh scripts/seed_dra_proof.py Makefile \
    tests/integration/dra/test_live_closure_recovery.py \
    tests/integration/dra/test_governed_closure.py \
    tests/architecture/test_compose_contract.py
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "test: prove governed DRA live closure offline"
  ```

### Task C5: Freeze live acceptance, docs, and complete repository gates

**Files:**
- Modify: `docs/operations/dra-consumer-proof.md`
- Modify: `docs/reference/dra-governed-evidence.md`
- Modify: `docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: approved spec and PR A/B/C plan status banners
- Modify: `scripts/verify_release.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `tests/architecture/test_dra_contract.py`

- [ ] **Step 1: Write candidate-freeze/docs RED tests**

  Require the exact ten freeze prerequisites from the approved spec, the one-attempt
  acknowledgement, separate Stage 2 snapshot-supply procedure, provider-free
  recovery bundle, second-substantive-failure stop rule, Docker ownership, cleanup,
  success-versus-safe-failure claim boundary, and explicit non-claims. Assert the
  live command remains outside required CI.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/architecture/test_documentation_governance.py \
    tests/architecture/test_dra_contract.py \
    tests/unit/test_release_surface.py
  ```

- [ ] **Step 3: Update runbook, reference, ADR, verifier, and status**

  Document the canonical resumable operator transcript and exact receipt
  dependencies; do not describe the larger command set as only four commands. The
  candidate-freeze checklist must state that all three PRs, hosted checks, authority
  review, recovery bundle, Docker preflight, source-inspection/snapshot procedure,
  and explicit user authorization precede one live attempt.

  A retained failure receipt is documented only as safe-stop evidence; capability
  status remains incomplete/blocked. Public claims do not change until a separately
  authorized frozen full closure succeeds and any evidence-only change is reviewed.

- [ ] **Step 4: Run final PR C verification**

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

  Run public-hygiene, private-path, secret, content-bearing receipt, proxy
  persistence, and historical-release scans. Record Docker pre/post inventory. Do
  not run the provider or claim live success.

- [ ] **Step 5: Commit**

  Stage only Task C5 files and commit:

  ```bash
  git commit -m "docs: freeze governed DRA live acceptance"
  ```

## Final Plan-Review Corrections

These corrections are normative and supersede any earlier ambiguous task wording:

1. **Stage 2 snapshot I/O inherits the descriptor-bound store.** Open the declared
   root and each path component through fixed no-follow directory descriptors; never
   validate with `resolve()` and later reopen by pathname. Hash the exact bytes read
   once from the validated descriptor. Unsupported safe primitives fail closed.
   Synchronous deletion claims cover normal exit, handled exception, `SIGINT`, and
   `SIGTERM`; hard-termination residue is detected on next open and blocks progress
   until explicit cleanup.
2. **Every Night Voyager mutation has lost-ack reconciliation.** Promotion, planning
   task creation, advisor review, and family decision use domain-separated keys and
   bounded `mutation_outcome_ambiguous` receipts. Recovery always re-reads authority
   first: synthesize success when the exact committed result exists; replay the
   identical request/key only when no result exists; fail closed on partial or
   conflicting state. Tests must simulate server commit followed by client timeout.
   “No mutation” expectations apply only to pre-validation failures and transactional
   rollback, not a committed lost acknowledgement.
3. **Outcome inspection uses migration `0010` authority.** The PostgreSQL adapter
   consumes the closed RLS-preserving projection installed in PR A. It must not gain
   table `SELECT`, a privileged connection, generic SQL, DML, cross-tenant access, or
   a new role. PR C verifies runtime-equivalent actor context, grants, forced RLS,
   downgrade parity, bounded cardinality, and cross-tenant denial.
4. **Sessions remain ephemeral.** Each fresh-process `promote`, `review`, or `decide`
   command re-injects the appropriate assigned-advisor or parent session and verifies
   actor/tenant identity against its parent receipt. No receipt, recovery bundle,
   log, or cleanup report may contain session identifiers, cookies, tokens, headers,
   auth-file paths, or credential material.
5. **Each stage requires a distinct acknowledgement.** Before mutation, print the
   bounded actor/tenant/Case/target/action preview. `promote`, `review`, and `decide`
   each require their own exact acknowledgement; no global `--yes` or prior-stage
   acknowledgement authorizes a later stage.
6. **Decision and capability completion are separate.** `decide` produces
   `decision_recorded`. Only a successful provider-free `evaluate` over the
   authoritative database projection produces `closure_passed`. If evaluation fails
   after the family decision committed, the state is recoverable incomplete; do not
   roll back or repeat the decision.
7. **Freeze one canonical operator transcript.** The runbook must number preflight,
   provider capture, post-capture inspection/selection, promotion, review, decision,
   evaluation, and cleanup. For every command list receipt dependency, ephemeral
   authority/session input, provider-consumption and mutation class, expected
   bounded output/exit class, and exact recovery command. Keep auxiliary commands in
   a separate reference.
8. **Candidate freeze is executable, not prose-only.** Produce a provider-free
   readiness receipt binding exact merged-main SHA, spec/plan hashes, producer pin,
   intent/scenario/receipt/CLI schema hashes, required hosted checks, recovery-matrix
   result, Docker preflight/inventory, cleanup state, and explicit authorization
   placeholder. A successful implementation/merge leaves capability
   `INCOMPLETE_PENDING_LIVE_ACCEPTANCE`; only one separately authorized frozen full
   closure may change that claim.

Expand C1-C5 RED tests, file lists, exact staging commands, documentation and
Compose coverage markers to enforce these contracts.

## PR C Completion and Candidate-Freeze Gate

- Final branch is clean and based on merged PR B.
- Deterministic full closure and recovery matrix pass through real Night Voyager
  PostgreSQL/HTTP/worker/SSE authority with fake DRA transport.
- Trajectory and database outcome reports agree.
- All source/artifact content is absent from durable receipts and cleaned from
  task-owned temporary roots.
- Required CI remains offline/provider-free.
- After independent authority review, hosted CI, merge, and exact merged-main verification, freeze
  the candidate. Only then may the user separately authorize one live attempt.
- A successful implementation PR is not a successful live acceptance, release, or
  deployment.
