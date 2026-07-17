# Governed Collaboration and Memory Authority Implementation Plan

> **For agentic workers:** REQUIRED PRIMARY CONTROLLER: use
> `superpowers:dispatching-parallel-agents` when the bounded lanes below can run in
> isolated worktrees; otherwise use `superpowers:executing-plans`. Use exactly one
> primary controller for this PR. Every behavioral, authority, migration, HTTP, and
> proof slice follows test-first RED -> GREEN. Steps use checkbox (`- [ ]`) syntax
> for tracking.

**Implementation status:** Complete. PR A was merged to `main` through PR #30 as an
unreleased post-v0.1.1 backend capability.
PR B, PR C, and live-provider work remain unimplemented and outside this plan.
The checkboxes below retain the approved test-first execution recipe; actual command
evidence belongs to the implementation record.

**Goal:** Add one shared Case collaboration thread in which an assigned student or
parent can propose one typed fact from their own message and an assigned advisor can
atomically confirm or reject it, with confirmation publishing the next Case revision
and complete ConfirmedFact provenance.

**Architecture:** Migration `0007` adds six forced-RLS immutable authority tables,
narrow PostgreSQL mutation/read functions, and a single atomic advisor verification
gate. A focused Python collaboration package owns strict commands, role/fact policy,
application ports, PostgreSQL mapping, and FastAPI routes. The existing whole-revision
writer is removed from API runtime authority and retained only for migrator-owned
bootstrap/test setup.

**Tech Stack:** Python 3.12.13, Pydantic 2.13.4, FastAPI 0.139.0, Starlette
1.3.1, SQLAlchemy 2.0.51 async, asyncpg 0.31.0, PostgreSQL 18.4, Alembic,
pytest 9, Docker Compose, and the existing opaque-session/CSRF/idempotency boundary.

## Global Constraints

- Begin from clean `main` after the approved Governed Collaboration Core design and
  all three approved implementation plans are merged. Record the actual base SHA
  before editing; do not start from the docs worktree if it has not been retained.
- Create a short-lived `codex/` branch and isolated worktree. Migration graph
  ownership, `src/night_voyager/api.py`, `scripts/seed_demo.py`, Make/CI/release
  verification, shared docs, and full Docker/PostgreSQL gates belong only to the
  integration owner.
- PR A adds exactly migration `0007_conversation_and_memory.py`, exactly six tables,
  and accepted ADR `0008`. It does not add Skill tables/pins, frontend/BFF code,
  another queue, external transport, provider call, dependency, or release change.
- One Case has exactly one immutable always-active collaboration thread. All assigned
  advisor/student/parent participants read the same messages; there are no private
  channels, unread state, thread close/archive, attachment, webhook, or message SSE.
- Only the student or parent who authored a message may propose one fact from it.
  Advisor-authored text cannot manufacture a participant proposal.
- Closed fact keys are exactly `student.intended_field`,
  `student.preferred_countries`, `student.intake`, `family.risk_tolerance`,
  `family.japan_risk_accepted`, and `family.budget`.
- `student.preferred_countries` is a non-empty sorted unique subset of
  `australia|japan|malaysia`; intake is a real calendar month in `YYYY-MM`; budget
  reuses the existing strict `BudgetEnvelope` contract.
- Candidate state is derived with exact precedence: terminal `confirmed|rejected`,
  then `stale`, then `expired`, otherwise `pending`. Expiry is seven days by database
  clock. No candidate is rebased or revived.
- Confirmation is allowed only while the Case is `intake|planning`, against the
  exact current revision, and only when no task is `queued|leased|running|waiting_review`.
  It does not advance Case state and never creates a task.
- Confirmation and rejection use one fixed lock order: idempotency advisory lock,
  Case `FOR UPDATE`, candidate, current fact head, current PlanningRun, then writes.
  Confirmation writes verification, fact, cloned revision, complete fact refs, Case
  CAS, PlanningRun currentness, audit, and idempotency response in one transaction.
- Migration `0007` must also align the existing planning-result writer with that
  order: `persist_planning_result(...)` locks the Case before replacing a current
  PlanningRun. Downgrade restores the exact `0006` function definition.
- Every redundant parent reference uses an exact composite foreign key containing
  `organization_id`, `case_id`, and parent identity. Forced RLS alone is not accepted
  as same-tenant cross-Case protection.
- Runtime roles receive no direct table `SELECT|INSERT|UPDATE|DELETE|TRUNCATE` on
  the six PR A tables. Existing least-privilege grants on earlier M2-M6 tables remain
  unchanged. API receives four mutation functions plus narrow read projections;
  worker and `PUBLIC` receive none. All functions are `SECURITY DEFINER` with fixed
  `search_path = pg_catalog, pg_temp` and participant/context checks.
- Revoke API execution of legacy
  `publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)`. Remove the runtime
  `CaseService.publish_revision()` / `CaseRepository.create_revision()` seam.
  Migrator-owned bootstrap/test setup may still call the legacy function explicitly.
- Public problem codes are frozen to:
  `resource_unavailable`, `case_revision_stale`, `memory_candidate_stale`,
  `memory_candidate_expired`, `memory_candidate_terminal`,
  `collaboration_thread_full`,
  `active_task_blocks_revision`, `invalid_collaboration_message`,
  `unsupported_fact_key`, `unsafe_fact_value`, `idempotency_conflict`, and
  `persistence_unavailable`. Unknown database errors become bounded 503 responses.
- SQLSTATE mapping is frozen to existing `NV003` stale, `NV006` invalid contract,
  `NV007` non-enumerating authorization, `NV008` idempotency mismatch, and `NV012`
  terminal/concurrent conflict, plus new `NV013` solely for candidate expiry and
  `NV014` solely for active-task revision blocking. `NV012` is operation-sensitive:
  append capacity maps only to `collaboration_thread_full`, candidate verification
  maps only to `memory_candidate_terminal`, and unexpected uses fail closed. Tests lock
  SQLSTATE-to-public-code mapping; raw SQL messages are never returned.
  The mapping is operation-sensitive without parsing SQL text: `NV003` from proposal
  creation is `case_revision_stale`, while `NV003` from candidate verification is
  `memory_candidate_stale`. Python/HTTP validation selects
  `invalid_collaboration_message`, `unsupported_fact_key`, or `unsafe_fact_value`
  before the database call; database `NV006` is the typed unsafe-contract fallback.
- Message body is inert UTF-8 plain text of 1..4096 bytes, rejects control characters,
  credential/secret material, local paths, any case-insensitive `file://` substring,
  URL credentials, and executable/shell structure, but does not use a broad lexical
  prompt-injection keyword filter.
- New bounded string fact values are 1..160 UTF-8 bytes. Verification reasons are
  1..512 UTF-8 bytes. Candidate expiry is exactly seven days by PostgreSQL clock;
  application or browser time cannot revive or expire a candidate.
- Read pages default to 50 and hard-cap at 100. A thread hard-caps at 1000 events.
  Append locks the thread and assigns gap-free monotonic `sequence_no`.
- Existing `audit_events` and `idempotency_records` are reused with exact PR A
  operation/event discriminators. Audit events are exactly
  `memory_candidate_confirmed|memory_candidate_rejected`; idempotency operations are
  exactly `collaboration_thread_create|collaboration_message_append|memory_candidate_propose|memory_candidate_verify`.
  Unrelated M3B/M4A history must not block downgrade.
- Migrations remain seed-free. Demo fixtures use explicit migrator-role seed paths.
- Required checks stay `python`, `frontend`, and `compose`; do not invent hosted
  check names. Do not change v0.1.1 release docs, tag, Release, or package version.
- Keep source, fixtures, errors, logs, commits, PR body, and docs public-neutral.
  Do not persist or print cookies, CSRF values, credentials, raw SQL, tracebacks,
  local paths, prompt text, provider payloads, or private workflow metadata.

## File Ownership Map

Integration owner exclusively owns:

- `migrations/versions/0007_conversation_and_memory.py`
- `src/night_voyager/api.py`
- `scripts/seed_demo.py`, `scripts/run_db_tests.sh`,
  `scripts/run_collaboration_db_tests.sh`, `scripts/verify_release.py`
- `Makefile`, `.github/workflows/ci.yml`, Compose proof scripts, shared docs/index
- `tests/architecture/test_collaboration_contract.py`
- `tests/integration/collaboration/`

Bounded lane A1 may own pure files only:

- `src/night_voyager/collaboration/{__init__,models,policy,hashing,errors}.py`
- `tests/unit/collaboration/`

Bounded lane A2 may start only after A1 interfaces freeze and may own:

- `src/night_voyager/collaboration/{application,ports}.py`
- `src/night_voyager/interfaces/http/collaboration.py`
- focused unit/HTTP contract tests that do not require PostgreSQL

Bounded lane A3 may start after the migration function signatures freeze and may own:

- `src/night_voyager/collaboration/postgres.py`
- `tests/unit/collaboration/test_postgres.py`

The integration owner performs all cross-lane merges, migration work, API wiring,
seed ordering, database catalog tests, full gates, docs, and final branch review.

---

### Task A1: Freeze strict collaboration contracts and pure policy

**Files:**
- Create: `src/night_voyager/collaboration/__init__.py`
- Create: `src/night_voyager/collaboration/models.py`
- Create: `src/night_voyager/collaboration/policy.py`
- Create: `src/night_voyager/collaboration/hashing.py`
- Create: `src/night_voyager/collaboration/errors.py`
- Create: `tests/unit/collaboration/__init__.py`
- Create: `tests/unit/collaboration/test_models.py`
- Create: `tests/unit/collaboration/test_policy.py`
- Create (integration owner): `tests/architecture/test_collaboration_contract.py`

**Interfaces:**
- Consumes: `ActorRole`, `BudgetEnvelope`, `Country`, and strict Pydantic v2 models.
- Produces: `FactKey`, six discriminated fact proposal models,
  `MemoryCandidateState`, `VerificationDecision`, `AppendMessageCommand`,
  `ProposeMemoryCandidateCommand`, `VerifyMemoryCandidateCommand`,
  `CollaborationThreadV1`, `MessageEventV1`, `MessagePageV1`,
  `MemoryCandidateParticipantV1`, `MemoryCandidateAdvisorV1`,
  `ConfirmedFactParticipantV1`, `ConfirmedFactAdvisorV1`,
  `ConfirmedFactParticipantPageV1`, `ConfirmedFactAdvisorPageV1`,
  `ConfirmedFactHistoryCursorV1`, `CollaborationThreadFullError`,
  `validate_message_body()`, `project_candidate_state()`, and
  `apply_confirmed_fact()`.

- [ ] **Step 1: Write strict RED tests**

  Add model tests for exact fields, `extra="forbid"`, UTF-8 byte bounds, valid month,
  role/fact matrix, non-empty sorted unique countries, budget validation, terminal
  precedence, and structural unsafe-value rejection. Include counterfactuals proving
  ordinary words such as “approve” and “ignore” remain valid preferences. Freeze two
  distinct candidate projections: the advisor model includes candidate/source/
  verification identities, pinned Case revision, and terminal reason, while the participant model includes
  only the caller's own proposal fact key/value/status/timestamps and contains no
  candidate ID, verification ID, reason, history, or internal digest fields.

  ```python
  def test_preferred_countries_are_sorted_unique_and_supported() -> None:
      with pytest.raises(ValidationError):
          PreferredCountriesProposal(
              schema_version=1,
              fact_key="student.preferred_countries",
              value=(Country.JAPAN, Country.AUSTRALIA),
          )
      assert PreferredCountriesProposal(
          schema_version=1,
          fact_key="student.preferred_countries",
          value=(Country.AUSTRALIA, Country.JAPAN),
      ).value == (Country.AUSTRALIA, Country.JAPAN)

  def test_terminal_candidate_state_precedes_stale_and_expired() -> None:
      assert project_candidate_state(
          decision=VerificationDecision.CONFIRM,
          pinned_revision=1,
          current_revision=2,
          expires_at=PAST,
          now=NOW,
      ) is MemoryCandidateState.CONFIRMED
  ```

- [ ] **Step 2: Run focused tests and record RED**

  Run:

  ```bash
  uv run pytest tests/unit/collaboration tests/architecture/test_collaboration_contract.py -q
  ```

  Expected: collection fails because `night_voyager.collaboration` does not exist.

- [ ] **Step 3: Implement frozen models and validators**

  Use one discriminated union so `fact_key` selects the only legal value type.

  ```python
  class FactKey(StrEnum):
      STUDENT_INTENDED_FIELD = "student.intended_field"
      STUDENT_PREFERRED_COUNTRIES = "student.preferred_countries"
      STUDENT_INTAKE = "student.intake"
      FAMILY_RISK_TOLERANCE = "family.risk_tolerance"
      FAMILY_JAPAN_RISK_ACCEPTED = "family.japan_risk_accepted"
      FAMILY_BUDGET = "family.budget"

  class MemoryCandidateState(StrEnum):
      PENDING = "pending"
      STALE = "stale"
      EXPIRED = "expired"
      CONFIRMED = "confirmed"
      REJECTED = "rejected"

  type FactProposal = Annotated[
      IntendedFieldProposal
      | PreferredCountriesProposal
      | IntakeProposal
      | RiskToleranceProposal
      | JapanRiskAcceptedProposal
      | BudgetProposal,
      Field(discriminator="fact_key"),
  ]
  ```

  `apply_confirmed_fact()` must clone `StudentCaseRevision`, replace exactly the
  selected field, increment revision by one, and leave all other fields byte-equal
  after canonical serialization.

- [ ] **Step 4: Run focused GREEN and type checks**

  Run:

  ```bash
  uv run pytest tests/unit/collaboration tests/architecture/test_collaboration_contract.py -q
  uv run ruff check src/night_voyager/collaboration tests/unit/collaboration \
    tests/architecture/test_collaboration_contract.py
  uv run pyright src/night_voyager/collaboration tests/unit/collaboration
  ```

  Expected: all focused tests pass; Ruff and Pyright report zero errors.

- [ ] **Step 5: Commit the pure contract slice**

  ```bash
  git add src/night_voyager/collaboration tests/unit/collaboration \
    tests/architecture/test_collaboration_contract.py
  git commit -m "feat: add governed collaboration contracts"
  ```

### Task A2: Add migration `0007` and close the revision authority seam

**Files:**
- Create: `migrations/versions/0007_conversation_and_memory.py`
- Modify: `src/night_voyager/planning/application.py`
- Modify: `src/night_voyager/planning/ports.py`
- Modify: `src/night_voyager/planning/postgres.py`
- Modify: `tests/unit/planning/test_application.py`
- Modify: `tests/security/test_database_catalog.py`
- Modify: `tests/security/test_dra_mixed_catalog.py`
- Modify: `tests/architecture/test_m4a_contract.py`
- Modify: `tests/architecture/test_m5_contract.py`
- Create: `tests/security/test_collaboration_catalog.py`
- Modify: `tests/architecture/test_m3a_contract.py`
- Modify: `tests/architecture/test_collaboration_contract.py`
- Create: `scripts/run_collaboration_db_tests.sh`
- Modify: `Makefile`

**Interfaces:**
- Consumes: A1 fact-key/value canonical projection and existing
  `student_case_participants`, `audit_events`, `idempotency_records`, Case, revision,
  PlanningRun, and AgentTask authorities.
- Produces: six exact tables; mutation functions
  `create_collaboration_thread`, `append_collaboration_message`,
  `propose_memory_candidate`, `verify_memory_candidate`; read functions
  `read_collaboration_thread`, `read_collaboration_messages`,
  `read_memory_candidates`, `read_confirmed_facts`; migrator-only
  `seed_demo_collaboration`; SQLSTATE/public-code contract; exact downgrade.

- [ ] **Step 1: Write migration/catalog RED tests**

  Freeze exact table names, constraints, policies, ownership, function signatures,
  grants, fixed `search_path`, PUBLIC revocation, API/worker denial, legacy writer
  revocation, and removal of Python runtime seam.

  ```python
  EXPECTED_TABLES = {
      "collaboration_threads",
      "message_events",
      "memory_candidates",
      "memory_candidate_verifications",
      "confirmed_facts",
      "case_revision_confirmed_fact_refs",
  }

  def test_legacy_revision_writer_is_not_an_api_runtime_seam() -> None:
      source = Path("src/night_voyager/planning/postgres.py").read_text()
      assert "publish_case_revision" not in source
      migration = Path("migrations/versions/0007_conversation_and_memory.py").read_text()
      assert "REVOKE EXECUTE ON FUNCTION app.publish_case_revision" in migration
  ```

- [ ] **Step 2: Run focused RED**

  Run:

  ```bash
  uv run pytest tests/security/test_collaboration_catalog.py \
    tests/architecture/test_collaboration_contract.py \
    tests/unit/planning/test_application.py -q
  ```

  Expected: tests fail because migration `0007`, its catalog, and the removed seam do
  not yet exist.

- [ ] **Step 3: Implement exact DDL and immutable constraints**

  The migration must encode, rather than merely document, the parent/Case lineage.

  Freeze the exact parent keys and foreign-key tuples below. Redundant role columns
  are authority columns, not caller input: `created_by_role`, `advisor_role`, and
  `confirming_advisor_role` are constrained to `advisor`; candidate proposer and
  subject roles are constrained equal.

  | Table | Primary/supporting keys | Exact parent references |
  | --- | --- | --- |
  | `collaboration_threads` | `PRIMARY KEY (organization_id,id)`; `UNIQUE (organization_id,case_id)`; `UNIQUE (organization_id,case_id,id)` | `(organization_id,case_id)` -> `student_cases`; `(organization_id,case_id,created_by_actor_id,created_by_role)` -> `student_case_participants` |
  | `message_events` | `PRIMARY KEY (organization_id,id)`; `UNIQUE (organization_id,case_id,id)`; `UNIQUE (organization_id,thread_id,sequence_no)`; `UNIQUE (organization_id,case_id,id,actor_id,actor_role)` | `(organization_id,case_id,thread_id)` -> thread; `(organization_id,case_id,actor_id,actor_role)` -> participant |
  | `memory_candidates` | `PRIMARY KEY (organization_id,id)`; `UNIQUE (organization_id,message_event_id)`; `UNIQUE (organization_id,case_id,id)`; `UNIQUE (organization_id,case_id,id,message_event_id,subject_actor_id,subject_role)` | `(organization_id,case_id,message_event_id,proposing_actor_id,proposing_role)` -> source message actor tuple; subject and proposer tuples each -> participant; `CHECK` proposer identity/role equals subject identity/role |
  | `memory_candidate_verifications` | `PRIMARY KEY (organization_id,id)`; `UNIQUE (organization_id,candidate_id)` | `(organization_id,case_id,candidate_id)` -> candidate; `(organization_id,case_id,advisor_actor_id,advisor_role)` -> advisor participant; confirmation-only result fact and result revision FKs described below |
  | `confirmed_facts` | `PRIMARY KEY (organization_id,id)`; `UNIQUE (organization_id,case_id,id)`; `UNIQUE (organization_id,case_id,fact_key,id)`; `UNIQUE (organization_id,case_id,fact_key,fact_version)`; partial unique successor on non-null `(organization_id,case_id,fact_key,supersedes_fact_id)` | `(organization_id,case_id,source_candidate_id,source_message_event_id,subject_actor_id,subject_role)` -> candidate lineage; subject and confirming-advisor tuples -> participants; `(organization_id,case_id,fact_key,supersedes_fact_id)` -> prior fact tuple |
  | `case_revision_confirmed_fact_refs` | `PRIMARY KEY (organization_id,case_id,case_revision,fact_key)` | `(organization_id,case_id,case_revision)` -> revision; `(organization_id,case_id,fact_key,confirmed_fact_id)` -> fact |

  After all six tables exist, add the verification result references with `ALTER
  TABLE`: `(organization_id,case_id,result_fact_id)` -> confirmed fact and
  `(organization_id,case_id,result_revision)` -> student Case revision. Both are
  `DEFERRABLE INITIALLY DEFERRED`; `confirm` requires both values and `reject`
  requires both null. No other lineage FK is deferrable.

  Add immutable triggers, dual tenant policies, confirmation/rejection result checks,
  source-role/fact constraints, SHA-256 checks, message/candidate bounds, expiry, and
  exact fact-reference uniqueness. Runtime roles must not own tables.

- [ ] **Step 4: Implement narrow functions with fixed idempotency and lock orders**

  Every mutation first validates bounded arguments, then takes an operation-scoped
  advisory lock derived from organization, resolved actor, operation discriminator,
  and `Idempotency-Key`; only then may it read or write the shared idempotency
  ledger. Same key plus the same canonical request returns the stored response. Same
  key plus a different canonical request raises `NV008`.

  Freeze the remaining resource order:

  1. `create_collaboration_thread`: advisory lock -> ledger -> Case `FOR UPDATE` ->
     assignment check -> existing-thread lookup/create. A second key for the same
     body/Case records and returns the single existing thread; concurrent distinct
     keys still create exactly one row.
  2. `append_collaboration_message`: advisory lock -> ledger -> thread `FOR UPDATE`
     -> assignment/cap check -> next sequence -> insert. Concurrent distinct keys
     create gap-free ordered events.
  3. `propose_memory_candidate`: advisory lock -> ledger -> read source identity ->
     Case `FOR SHARE` and current-revision validation -> source message `FOR UPDATE`
     and author revalidation -> existing-candidate lookup/create. A second request
     whose canonical body matches returns the existing candidate; a different body
     for that source message raises `NV008`. The Case share lock serializes against
     advisor confirmation.
  4. `verify_memory_candidate`: advisory lock -> ledger -> Case `FOR UPDATE` ->
     candidate `FOR UPDATE` -> current fact head -> optional current PlanningRun ->
     writes.

  `verify_memory_candidate(...)` must use explicit predicates rather than SQL-text
  omissions. Its executable skeleton is:

  ```sql
  PERFORM pg_advisory_xact_lock(hashtextextended(
    p_organization_id::text || ':' || p_actor_id::text ||
    ':memory_candidate_verify:' || p_key_sha256,
    0
  ));
  SELECT * INTO prior
    FROM app.idempotency_records
   WHERE organization_id = p_organization_id
     AND actor_id = p_actor_id
     AND operation = 'memory_candidate_verify'
     AND key_sha256 = p_key_sha256;
  SELECT * INTO selected_case
    FROM app.student_cases
   WHERE organization_id = p_organization_id AND id = p_case_id
   FOR UPDATE;
  SELECT * INTO candidate
    FROM app.memory_candidates
   WHERE organization_id = p_organization_id
     AND case_id = p_case_id AND id = p_candidate_id
   FOR UPDATE;
  SELECT * INTO prior_fact
    FROM app.confirmed_facts AS fact
   WHERE fact.organization_id = p_organization_id
     AND fact.case_id = p_case_id
     AND fact.fact_key = candidate.fact_key
     AND NOT EXISTS (
       SELECT 1 FROM app.confirmed_facts AS successor
        WHERE successor.organization_id = fact.organization_id
          AND successor.case_id = fact.case_id
          AND successor.fact_key = fact.fact_key
          AND successor.supersedes_fact_id = fact.id
     )
   FOR UPDATE;
  SELECT * INTO current_run
    FROM app.planning_runs
   WHERE organization_id = p_organization_id
     AND case_id = p_case_id AND is_current
   FOR UPDATE;
  ```

  Then validate assignment, candidate precedence, Case state/currentness, absence of
  active task, and typed value. Reject writes only terminal verification, audit, and
  idempotency. Confirm writes the exact transaction described in Global Constraints.
  `intake` with no current PlanningRun is valid and writes no run update. `planning`
  with one current run locks it and makes it non-current. More than one current run
  is a persistence error, not an arbitrary row choice.
  To prevent the worker finalize path from taking the reverse PlanningRun-to-Case
  order, `0007` replaces `persist_planning_result(...)` with an otherwise identical
  body whose Case currentness check uses `FOR UPDATE` before the superseded-run
  update. The downgrade must restore the exact `0006` body.
  Injected-failure test hooks may exist only in test-owned temporary function
  replacement, never as production parameters.

- [ ] **Step 5: Remove the application runtime revision seam**

  Delete `CaseService.publish_revision()`, `CaseRepository.create_revision()`, and
  `PostgresPlanningRepository.create_revision()`. Keep `CaseService.start_planning()`
  and all result/source persistence paths. Update unit fakes so no runtime interface
  can call `publish_case_revision(...)`.

- [ ] **Step 6: Implement exact downgrade**

  `0007 -> 0006` must refuse when any six-table row exists or when exact operations
  `collaboration_thread_create`, `collaboration_message_append`,
  `memory_candidate_propose`, or `memory_candidate_verify` exist in reused ledgers.
  It must ignore unrelated ledger operations. On an empty boundary it drops PR A
  functions/tables and restores the exact `0006` legacy function signature, API
  grant, Python verifier expectation, and migrator bootstrap behavior.

- [ ] **Step 7: Add the disposable focused database runner**

  Add `make collaboration-db-check SUITE=<name>` backed by
  `scripts/run_collaboration_db_tests.sh`. It must create an isolated Compose
  project/volume, upgrade with the migrator, clear configured/default Pytest addopts,
  invoke explicit `-m database`, and always tear down its owned containers, network,
  and volume. Freeze exact suites: `repository` runs the PostgreSQL repository file;
  `http` runs the HTTP file; `authority` runs all collaboration PostgreSQL,
  concurrency, rollback, downgrade, HTTP, and catalog files. Unknown suite names
  fail before Docker starts.

- [ ] **Step 8: Run focused GREEN and commit**

  Run:

  ```bash
  uv run pytest tests/security/test_collaboration_catalog.py \
    tests/security/test_database_catalog.py \
    tests/architecture/test_collaboration_contract.py \
    tests/architecture/test_m3a_contract.py tests/architecture/test_m4a_contract.py \
    tests/architecture/test_m5_contract.py tests/security/test_dra_mixed_catalog.py \
    tests/unit/planning/test_application.py -q
  uv run ruff check migrations/versions/0007_conversation_and_memory.py \
    src/night_voyager/planning tests/security tests/architecture
  uv run pyright src/night_voyager/planning tests/unit/planning
  ```

  Expected: focused tests pass and static checks report zero errors.

  ```bash
  git add migrations/versions/0007_conversation_and_memory.py \
    src/night_voyager/planning tests/security tests/architecture Makefile \
    scripts/run_collaboration_db_tests.sh \
    tests/unit/planning/test_application.py
  git commit -m "feat: add collaboration database authority"
  ```

### Task A3: Add application ports and PostgreSQL adapters

**Files:**
- Create: `src/night_voyager/collaboration/ports.py`
- Create: `src/night_voyager/collaboration/application.py`
- Create: `src/night_voyager/collaboration/postgres.py`
- Create: `tests/unit/collaboration/test_application.py`
- Create: `tests/unit/collaboration/test_postgres.py`
- Create (integration owner): `tests/integration/collaboration/__init__.py`
- Create (integration owner): `tests/integration/collaboration/test_postgres_collaboration.py`

**Interfaces:**
- Consumes: A1 commands/projections and A2 function signatures.
- Produces: `CollaborationRepository`, `CollaborationService`, and
  `PostgresCollaborationRepository` with methods `create_thread`, `get_thread`,
  `list_messages`, `append_message`, `propose_candidate`, `list_candidates`,
  `verify_candidate`, and `list_confirmed_facts`.

- [ ] **Step 1: Write application and adapter RED tests**

  Prove advisor-only thread creation/verification, assigned shared reads, source-author
  proposal, role-safe fact projection, canonical request hashes, replay, typed error
  mapping, and no application-computed actor/Case authority. Real PostgreSQL
  assertions must deserialize the advisor and participant candidate projections into
  different strict models and prove prohibited fields are absent from the participant
  result rather than merely hidden by HTTP code.

  ```python
  async def test_parent_cannot_propose_from_another_participants_message() -> None:
      repository = RecordingRepository(source_actor_id=STUDENT_ID)
      service = CollaborationService(repository)
      with pytest.raises(CollaborationAuthorizationError):
          await service.propose_candidate(PARENT_CONTEXT, parent_proposal(), "key")
  ```

- [ ] **Step 2: Run focused RED**

  Run:

  ```bash
  uv run pytest tests/unit/collaboration/test_application.py \
    tests/unit/collaboration/test_postgres.py -q
  make collaboration-db-check SUITE=repository
  ```

  Expected: collection fails because ports, service, and adapter are absent.

- [ ] **Step 3: Implement the service and strict repository boundary**

  Services generate resource IDs, enforce coarse role eligibility, and delegate all
  assignment/currentness/terminal authority to PostgreSQL. Repository methods return
  typed models, not unbounded `dict[str, object]`. Canonical request hashes cover the
  exact command body but never CSRF/session/idempotency key plaintext.

- [ ] **Step 4: Map SQLSTATE to frozen domain errors**

  The adapter maps `NV003`, `NV006`, `NV007`, `NV008`, `NV012`, `NV013`, and `NV014`
  to separate typed errors. Connection, serialization, permission, unknown SQLSTATE,
  and result-shape failures propagate as persistence failures and are not collapsed
  into stale or authorization responses.

- [ ] **Step 5: Run focused GREEN and commit**

  Run:

  ```bash
  uv run pytest tests/unit/collaboration/test_application.py \
    tests/unit/collaboration/test_postgres.py -q
  make collaboration-db-check SUITE=repository
  uv run ruff check src/night_voyager/collaboration tests/unit/collaboration
  uv run pyright src/night_voyager/collaboration tests/unit/collaboration
  ```

  Expected: focused non-database tests pass; Ruff/Pyright report zero errors.

  ```bash
  git add src/night_voyager/collaboration tests/unit/collaboration \
    tests/integration/collaboration/test_postgres_collaboration.py
  git commit -m "feat: add collaboration application boundary"
  ```

### Task A4: Expose the closed FastAPI collaboration surface

**Files:**
- Create: `src/night_voyager/interfaces/http/collaboration.py`
- Modify: `src/night_voyager/api.py`
- Create: `tests/integration/collaboration/test_http_collaboration.py`
- Modify: `tests/unit/test_api.py`
- Modify: `tests/architecture/test_collaboration_contract.py`

**Interfaces:**
- Consumes: `CollaborationService` and all A1 response models.
- Produces: the exact eight `/api/v1` endpoints from the approved design, strict
  request DTOs, RFC 9457-style bounded problems, `Cache-Control: no-store`, stable
  `after_sequence` pagination, and OpenAPI registration.

  ```text
  POST /api/v1/cases/{case_id}/collaboration-thread
  GET  /api/v1/cases/{case_id}/collaboration-thread
  GET  /api/v1/collaboration-threads/{thread_id}/messages
  POST /api/v1/collaboration-threads/{thread_id}/messages
  POST /api/v1/messages/{message_id}/memory-candidates
  GET  /api/v1/cases/{case_id}/memory-candidates
  POST /api/v1/memory-candidates/{candidate_id}/verification-decisions
  GET  /api/v1/cases/{case_id}/confirmed-facts
  ```

- [ ] **Step 1: Write HTTP/OpenAPI RED tests**

  Cover all eight routes, exact Origin/CSRF/idempotency requirements, body limits,
  `extra="forbid"`, expired session cookie clearing, wrong-role 404, no-store, stable
  pagination, role-safe fact visibility, the append-only `409
  collaboration_thread_full` OpenAPI problem, and error-code mapping.

  Lock the read matrix: every page keeps all current fact heads reachable; advisor
  history uses stable bounded cursor pagination without duplicate or omitted rows.
  The cursor carries the Case revision visible on the first read; successor
  verification revisions at or below that immutable high-water mark freeze history
  membership across later commits.
  Advisor sees current and historical facts, candidate and
  verification identities, source message metadata, confirming advisor, reason, and
  supersession; student/parent see current values, fact version, confirmed-at,
  subject role, and advisor role label, plus only their own proposal status. They do
  not receive historical values, source digest/sequence, internal IDs, reason, or
  supersession. All assigned participants still see the shared message thread.

  ```python
  async def test_verification_requires_origin_csrf_and_idempotency_key(client) -> None:
      response = await client.post(
          f"/api/v1/memory-candidates/{CANDIDATE_ID}/verification-decisions",
          json=confirm_payload(),
      )
      assert response.status_code in {400, 401, 403}
      assert response.headers.get("cache-control") == "no-store"
  ```

- [ ] **Step 2: Run focused RED**

  Run:

  ```bash
  uv run pytest tests/unit/test_api.py \
    tests/architecture/test_collaboration_contract.py -q
  make collaboration-db-check SUITE=http
  ```

  Expected: route/OpenAPI assertions fail because the router is absent.

- [ ] **Step 3: Implement explicit DTOs and route handlers**

  Use explicit Pydantic request models:

  ```python
  class CreateCollaborationThreadRequest(StrictModel):
      schema_version: Literal[1]

  class AppendMessageRequest(StrictModel):
      schema_version: Literal[1]
      body: str

  class ProposeMemoryCandidateRequest(StrictModel):
      schema_version: Literal[1]
      case_revision: PositiveInt
      proposal: FactProposal

  class VerifyMemoryCandidateRequest(StrictModel):
      schema_version: Literal[1]
      expected_case_revision: PositiveInt
      decision: VerificationDecision
      reason: str
  ```

  Reuse the existing identity dependency, Origin guard, cookie names, and problem
  response shape. Never trust actor/role/subject IDs from request JSON. Candidate
  proposal returns the participant projection without candidate/verification IDs;
  the subsequent advisor list projection supplies candidate identity and pinned Case
  revision. Advisor verification returns the resulting fact/revision identities
  needed for authority reload, never an unbounded database row.

- [ ] **Step 4: Run focused GREEN and commit**

  Run:

  ```bash
  uv run pytest tests/unit/test_api.py \
    tests/architecture/test_collaboration_contract.py -q
  make collaboration-db-check SUITE=http
  uv run ruff check src/night_voyager/interfaces/http/collaboration.py \
    src/night_voyager/api.py tests/integration/collaboration
  uv run pyright src/night_voyager/interfaces/http/collaboration.py \
    tests/integration/collaboration/test_http_collaboration.py
  ```

  Expected: all route tests pass and static checks report zero errors.

  ```bash
  git add src/night_voyager/interfaces/http/collaboration.py src/night_voyager/api.py \
    tests/integration/collaboration tests/unit/test_api.py \
    tests/architecture/test_collaboration_contract.py
  git commit -m "feat: expose governed collaboration API"
  ```

### Task A5: Prove runtime authority, concurrency, rollback, seed, and downgrade

**Files:**
- Modify: `src/night_voyager/identity/demo_seed.py`
- Modify: `scripts/seed_demo.py`
- Modify: `scripts/run_db_tests.sh`
- Modify: `scripts/run_collaboration_db_tests.sh`
- Modify: `tests/unit/identity/test_seed_demo.py`
- Modify: `tests/integration/collaboration/test_postgres_collaboration.py`
- Create: `tests/integration/collaboration/test_collaboration_concurrency.py`
- Create: `tests/integration/collaboration/test_collaboration_downgrade.py`
- Create: `tests/integration/collaboration/test_collaboration_rollback.py`
- Modify: `tests/security/test_database_catalog.py`

**Interfaces:**
- Consumes: A2 migration and A3/A4 runtime paths.
- Produces: explicit collaboration demo seed identities, browser-addressable negative
  fixtures for PR C, real PostgreSQL/HTTP authority evidence, and `0007 -> 0006 ->
  0007` proof.

- [ ] **Step 1: Write real PostgreSQL RED tests**

  Cover same/cross-tenant reads/writes, same-tenant cross-Case FKs, source-author
  enforcement, sequence concurrency, candidate cardinality, stale/expired/terminal
  precedence, active-task block, concurrent first confirmation, supersession, exact
  fact refs, role visibility, direct DML/TRUNCATE denial, API/worker/PUBLIC grants,
  size-one pool cleanup, and injected failure after every consequential write.
  Include two-connection races for same/different idempotency keys on thread create,
  message append, and proposal creation. Prove proposal waits behind confirmation's
  Case lock and then fails stale, task creation first blocks confirmation with
  `NV014`, and confirmation first advances the revision so an old-revision task
  request fails stale. Prove `intake` with no current PlanningRun succeeds while
  `planning` with one current run marks that exact run non-current.
  Add bounded worker-finalize races against both confirmation and rejection and fail
  on `40P01` or timeout; both paths must preserve their documented transaction result
  and allow the worker to complete after the verifier releases the Case lock.

- [ ] **Step 2: Add deterministic seed contracts**

  Add fixed IDs for one primary collaboration Case/thread and separate active-task,
  stale-candidate, and expired-candidate Cases. The active-task fixture is exactly a
  `waiting_review` legacy-unpinned task so migration `0008` must preserve it while it
  continues to block confirmation. Seed only through migrator-role
  functions after identity/participant setup. Repeated seed must be idempotent and
  must not mutate the existing default `/demo` Case.

- [ ] **Step 3: Run the database tests and record RED**

  Run:

  ```bash
  make db-check
  ```

  Expected: the new focused tests fail before the migration/runtime/seed boundary is
  complete; existing suites must remain green up to the first new assertion.

- [ ] **Step 4: Complete migration/runtime fixes until exact GREEN**

  Use independent connections for concurrency tests and savepoints for expected
  SQLSTATE paths. Do not replace actual runtime functions with mocks. Injected
  rollback failures temporarily replace only the exact function under test inside a
  disposable database and restore it before the next assertion.

- [ ] **Step 5: Prove downgrade behavior**

  Run separate disposable databases for:

  1. empty PR A boundary: `0007 -> 0006 -> 0007` succeeds;
  2. unrelated M3B/M4A audit/idempotency history only: downgrade succeeds;
  3. any PR A thread/message/candidate/fact/ref/verification: downgrade refuses;
  4. any PR A audit or idempotency discriminator: downgrade refuses.

  Reorder `scripts/run_db_tests.sh` so the seed cannot invalidate the empty-boundary
  proof it is supposed to test:

  ```text
  upgrade to 0007 with an empty PR A boundary
  -> empty 0007 -> 0006 -> 0007
  -> existing 0006 -> 0005 -> 0006 mixed downgrade regression
  -> empty full graph 0007 -> 0001 -> 0007
  -> identity/participant-only seed
  -> upgrade head
  -> full demo seed including collaboration thread
  -> broad DB/HTTP/security suites
  -> with-PR-A-data downgrade refusal
  ```

  Do not run a generic downgrade after the full collaboration seed; refusal there is
  the expected authority contract, not a migration failure.

- [ ] **Step 6: Run GREEN and commit**

  Run:

  ```bash
  make db-check
  make collaboration-db-check SUITE=authority
  ```

  Expected: all database suites and migration round trips pass, repeated seed passes,
  and the disposable volume is removed.

  ```bash
  git add src/night_voyager/identity/demo_seed.py scripts/seed_demo.py \
    scripts/run_db_tests.sh scripts/run_collaboration_db_tests.sh \
    tests/unit/identity/test_seed_demo.py \
    tests/integration/collaboration tests/security/test_database_catalog.py
  git commit -m "test: prove collaboration authority boundaries"
  ```

### Task A6: Integrate proof, accepted ADR, public docs, and local closeout

**Files:**
- Create: `docs/decisions/0008-governed-collaboration-and-memory-authority.md`
- Create: `docs/reference/collaboration-and-confirmed-facts.md`
- Create: `docs/operations/collaboration-authority.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `DESIGN.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/reference/domain-and-source-manifests.md`
- Modify: `docs/operations/database-roles.md`
- Modify: `docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md`
- Modify: `docs/superpowers/plans/2026-07-16-governed-conversation-memory-authority.md`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify_release.py`
- Modify: `scripts/verify_compose.sh`
- Create: `scripts/verify_collaboration_flow.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/architecture/test_collaboration_contract.py`

**Interfaces:**
- Consumes: complete A1-A5 authority.
- Produces: `collaboration-check`, Compose backend proof, accepted ADR 0008,
  implemented-vs-deferred documentation, release/catalog verification, and clean
  local branch handoff.

- [ ] **Step 1: Write proof/documentation RED tests**

  Assert Make/CI routing, migration head `0007`, six-table catalog, API/worker grants,
  legacy seam closure, docs links/status, v0.1.1 immutability, and public-neutral
  claims. Add a Compose script that uses real sessions and HTTP calls to append,
  propose, confirm, reload the fact/revision, and prove wrong-role/stale/expired/
  active-task failures without frontend code.

- [ ] **Step 2: Run focused RED**

  Run:

  ```bash
  uv run pytest tests/unit/test_release_surface.py \
    tests/architecture/test_collaboration_contract.py -q
  ```

  Expected: missing ADR/docs/proof routing assertions fail.

- [ ] **Step 3: Implement proof and documentation**

  Add `collaboration-check` as a deterministic offline Python/architecture lane.
  Keep hosted check names unchanged. ADR 0008 records PostgreSQL ownership,
  MessageEvent/Candidate/Fact separation, atomic confirmation, legacy writer
  revocation, downgrade contract, and explicit non-goals. Mark PR A implemented but
  PR B/PR C and live-provider work unimplemented.

- [ ] **Step 4: Run fresh full verification**

  Run exactly:

  ```bash
  make doctor MODE=dev
  uv lock --check
  make collaboration-check
  make db-check
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  git diff --check "$(git merge-base HEAD origin/main)"..HEAD
  ```

  Expected: every command exits 0; `docker compose ps --all` has no project
  containers; no dependency/lockfile/frontend/release-version change appears.

- [ ] **Step 5: Review the complete branch and commit**

  Inspect the base-to-HEAD diff, migration graph, grants, public output, worktree
  inventory, and secret/private-path scan. Fix only in-scope defects, rerun affected
  focused tests and the full gates, then commit:

  ```bash
  git add README.md README_CN.md CONTRIBUTING.md DESIGN.md Makefile \
    .github/workflows/ci.yml docs scripts src tests migrations
  git commit -m "docs: complete collaboration authority proof"
  ```

- [ ] **Step 6: Stop at local authority-review handoff**

  Report base, branch, worktree, ordered commits, exact diff, RED -> GREEN evidence,
  runtime catalog/grant/concurrency/rollback/downgrade proof, documentation impact,
  worktree inventory, and remaining risks. Worktree must be clean. Do not push,
  create a PR, merge, tag, release, deploy, start PR B, or run live-provider proof.

## PR A Acceptance Checklist

- [ ] Exactly six PR A tables exist, all tenant-keyed, migrator-owned, forced-RLS,
  immutable, and protected by composite tenant+Case lineage constraints.
- [ ] Shared messages are visible to assigned participants; historical verification
  metadata remains advisor-only through PostgreSQL projections.
- [ ] Source participant, role/fact/value, expiry, stale, terminal, active-task,
  idempotency, concurrent, and rollback paths are proven through actual SQL/HTTP.
- [ ] Confirmation creates one terminal verification, one fact/version, one cloned
  revision, complete current fact refs, Case CAS, currentness change, audit, and
  idempotency response atomically; rejection creates no fact or revision.
- [ ] API cannot execute the legacy whole-revision writer, no Python runtime seam
  exposes it, worker has no collaboration authority, and bootstrap remains explicit
  migrator-owned setup.
- [ ] Empty/unrelated-history downgrade succeeds; any exact PR A authority history
  blocks downgrade without data deletion.
- [ ] Existing M1-M5, DRA, synthetic/mixed planning, task/SSE, frontend, Compose, and
  v0.1.1 release contracts remain green and unchanged outside documented effects.
