# Controlled February Intake Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task only after written spec/plan approval. Steps use checkbox syntax for tracking.

**Status:** Local implementation, bounded runtime-role verification, final review fix pass and documentation minor correction complete. The separately authorized native/browser/image phase is pending; hosted delivery remains separate.
**Goal:** Prove a pre-consent same-Case `2027-02` to `2028-02` revision with separately pinned synthetic costs, fresh review and an explicit family receipt/timeline.
**Architecture:** Extend existing fact/revision/task authority with one additive migration and a two-entry synthetic source allowlist. Negotiate new comparison/ledger read contracts; retain existing decision and February timeline policies.
**Tech Stack:** Existing PostgreSQL/Alembic, Python/Pydantic/FastAPI and Next.js/TypeScript/Vitest; no new dependencies.
**Spec:** [Controlled February intake revision](../specs/2026-10-06-controlled-intake-revision.md).
**Git starting point:** `68de260b1e207f83153d51801501c7775b4f4374` on an isolated `codex/` branch.

## Global constraints

- Fixed synthetic Case `49000000-0000-0000-0000-000000000003`, revision `1`, `2027-02` to `2028-02`; no existing family decision or timeline.
- Fixed source/FX as-of `2026-07-01`; hypothetical tuition `4,200,000`, living `2,600,000` AUD minor and FX `4.80`; expected `32,640,000` CNY minor.
- New source pack `50000000-0000-0000-0000-000000000017`, version `1`; old M3A files, baseline hashes, DRA pins and historical Release records remain byte-identical.
- ASCII `YYYY-MM`, year `0001` through `9999`; unsupported source refuses confirmation before publishing a revision.
- Preserve role/RLS, exact request-review, active-task, stale, idempotency, predecessor/successor, finalized-Case and fresh-consent gates.
- Keep old V1/V2 country/budget response shapes; new ledger uses exact `contract_version=3`, comparison V2 and stored cost intake; brief stays V2.
- Do not widen the existing terminal recovery source whitelist or change runtime Skill manifests, dependency locks or February date rules.
- Written design/plan approval is complete. The bounded PostgreSQL/runtime-role lane below is approved; full native/browser/image and remote verification require separate approval. The deferred native recovery CI proof is not a dependency or acceptance substitute.

## Authorized bounded PostgreSQL lane

Use only retained PostgreSQL image
`postgres:18.4-alpine3.24@sha256:9a8afca54e7861fd90fab5fdf4c42477a6b1cb7d293595148e674e0a3181de15`
(Docker Engine `29.7.2` readback at preparation). No application image rebuild or
pull is needed for this lane. A task-only Compose file in the ignored plan
workspace starts PostgreSQL under project `night-voyager-intake-n2-20261006-db`,
binding `127.0.0.1:52139` after a free-port check. Its named volume and network
carry only this project's labels and begin empty. Preserve all other projects,
volumes, images and worktrees. Retained API/worker/browser images are not mutated.

Commands use the task-local `.venv/bin/python`, `.venv/bin/alembic` and runtime
role URLs generated for this disposable database; no private `.env` is read:

```sh
docker compose -p night-voyager-intake-n2-20261006-db -f "$N2_PG_COMPOSE" up -d --pull never postgres
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed_demo.py --with-intake-revision
.venv/bin/python scripts/verify_release.py --check-db-roles
.venv/bin/python -m pytest -o addopts='' -q -m database tests/integration/planning/test_intake_revision_migration.py tests/integration/planning/test_intake_revision_authority.py tests/integration/planning/test_intake_revision_source_pins.py
docker compose -p night-voyager-intake-n2-20261006-db -f "$N2_PG_COMPOSE" down --volumes
```

Migration/downgrade cases use separate task-owned disposable databases on that
server; old-contract and runtime-role flow tests use the fresh seeded lane.
Record actual commands/results in the ignored ledger. Reuse the running PG
server for focused cases without starting unrelated services. Hold temporary
`caffeinate` only for this task and release its recorded process at closeout.
Cleanup is limited to this project's containers/network/volume, test databases
and task-owned temporary processes; existing retained images stay retained.

The new fixture must ship in wheel data and the existing final image resource
layout. Target `pyproject.toml` package-data includes and `Dockerfile.api` builder
COPY only as needed; test installed-wheel resource/digest from a different cwd.
Extend current-source `scripts/verify_release.py` Alembic/role/seed/inventory
checks and applicable `scripts/run_db_tests.sh` current-head checks to `0017`.
Keep explicit historical `0016` downgrade/seed-phase checks and tagged records.

## Review focus

- Unsupported confirmation must leave a still-current predecessor; test rollback before publication in Task 2.
- A valid new intake with an old/missing/drifted pack must not queue a usable task; test actual pins and rejected writes in Tasks 1–2.
- Saved budget/country intents and legacy V1/V2 readers must remain exact; test both contracts and intent replay in Tasks 3–4.
- An unchanged country outcome must not hide changed intake/source/cost; test the explicit projections and new receipt chain in Tasks 3–5.
- Seed replay/downgrade and finalized-Case refusal must preserve prior facts and history; test with migrator/API/worker roles in Tasks 2 and 5.

## File and interface map

| Unit | Files | Responsibility |
| --- | --- | --- |
| Exact fixture pins | New `fixtures/intake-delay-v1/` and `src/night_voyager/planning/intake_fixture.py`; existing `planning/synthetic.py`, adapter tests | Validate one independent version; resolve by persisted pack identity; never relabel costs |
| DB authority/seed | New `migrations/versions/0017_controlled_intake_revision.py`; `scripts/seed_demo.py`, `identity/demo_seed.py` | Closed source assertions, guarded intake confirmation, pending boolean, task/snapshot pin checks and opt-in exact seed |
| Safe failure | `collaboration/models.py`, `errors.py`, `postgres.py`, `interfaces/http/collaboration.py` | Calendar guard and `NV027` to bounded `409 intake_evidence_unavailable` |
| Versioned reads | `planning/revision.py`; `connected_demo/models.py`, `fixtures.py`, `ports.py`, `application.py`, `postgres.py`; `interfaces/http/connected_demo.py` | Exact third delta, frozen old review context, V3 current intake/cost projection and strict negotiation |
| UI | Connected-demo contracts/API/revision/storage/hook; revision/comparison components; demo page and ledger BFF route; presentation messages | Explicit controlled start, actual student intake, handoff/replay, new ledger decoding and source/cost/month disclosure |
| Acceptance/docs | New intake-specific unit/integration tests; affected existing regression suites; proposed ADR `0016-controlled-intake-revision-source-pins.md` and affected references/runbook | Persisted same-Case truth, compatibility, authority, documentation and truthful pending runtime gates |

### Task 1: Define and verify the independent source fixture

**Create:** `fixtures/intake-delay-v1/manifest.json`, manifest-owned sources, `src/night_voyager/planning/intake_fixture.py`, `tests/unit/planning/test_intake_revision_fixture.py`, `tests/unit/adapters/test_intake_planning.py`.
**Modify:** `src/night_voyager/planning/synthetic.py`, `pyproject.toml`, `Dockerfile.api`, release/source inventory checks; `tests/unit/planning/test_synthetic.py` and installed-wheel asset regressions.
**Interfaces:** Produce `load_exact_intake_delay_fixture() -> PlanningInput` and a closed `(source_pack_id, source_pack_version, policy_version)` to exact fixture descriptor. Each descriptor fixes intake, path and raw/canonical hashes. `materialize_persisted_synthetic_input(snapshot)` continues consuming the persisted Case and tuple, with unchanged baseline defaults and no mutable current-source lookup.

- [x] Write failing assertions for distinct identity/cost, `2028-02`, accepted synthetic source references, one Australia cost row, baseline byte preservation and manifest/source/path/hash drift refusal.
- [x] Run the new focused tests and record RED for the missing second identity, not an import-only or environment error.
- [x] Add the independently declared fixture, compute its two frozen hashes and implement exact two-entry selection. Preserve persisted intake/budget/countries and existing policy/input/output schemas.
- [x] Run new fixture and existing synthetic/adapter tests; assert `32,640,000` and rejection of wrong/mixed pins. Review the frozen descriptor values for the next task.
- [x] Build/install the project wheel in a task-only environment and verify packaged manifest/source digests from a different cwd. Verify final-image COPY/resource declarations; leave actual new-image proof pending separate authorization.
- [x] Commit exact paths as one source-fixture outcome.

### Task 2: Add intake revision authority, source checks and exact seed

**Create tests:** `tests/integration/planning/test_intake_revision_migration.py`, `test_intake_revision_authority.py`, `test_intake_revision_source_pins.py`; add calendar/error-map unit coverage to existing collaboration tests.
**Create/modify:** New migration `0017_controlled_intake_revision.py`; the seed and collaboration files in the map; current-source `scripts/verify_release.py` and `scripts/run_db_tests.sh` gates and their focused regressions.
**Interfaces:** Consume Task 1's exact descriptor. Replace the five existing function bodies named in the spec without changing signatures. Add a migrator-only `app.assert_controlled_intake_source` and `app.seed_demo_intake_revision`; map SQLSTATE `NV027` through `IntakeEvidenceUnavailableError` to the exact public error. Add opt-in `--with-intake-revision` to the existing seed CLI. Before creation, choose the target from the exact intake delta or retain a non-intake predecessor pin; initial baseline planning remains unchanged.

- [x] Write database regressions with API/worker roles: student authorship, assigned advisor/request-review gate, adjacent publication, pending boolean, no auto-task, illegal year/month, unchanged/stale/expired/replay/conflict, source absence/drift, wrong old/new pack and finalized refusal. Snapshot refused confirmation before/after.
- [x] Use the approved isolated database lane above to demonstrate the intake whitelist/source-pinning failure. Unit/fake SQL checks cannot satisfy this task's acceptance.
- [x] Implement the additive replacements and source checks in the existing transaction order. Keep every inherited finalized/active-task/lineage fence, grants and RLS. The seed persists the independent pack and a confirmed-intake initial Case with exact message/candidate/verification/fact references, without updating other Cases.
- [x] Test exact seed replay, drift rollback, PUBLIC/API/worker privilege denial, stable old function signatures, and downgrade refusal after new fixture/lineage exists. Without new data, compare restored bodies/grants to the `0016` state.
- [x] Test exact current Alembic head `0017`, role/seed helper inventory and current-source DB lane checks; retain historical `0016` phases and old Release bytes.
- [x] Run the affected collaboration, planning-revision and planning-start database regressions within the approved bounded lane; confirm old baseline, mixed-provider and terminal-recovery source boundaries are retained. Commit exact authority paths with the proposed ADR.

Runtime-role authority and source tests are complete. The actual post-receipt finalized denial and later non-intake inheritance assertions remain owned by Task 5's persisted flow, as recorded in the execution ledger.

### Task 3: Version the comparison and advisor ledger

**Modify:** Versioned read files in the map, `tests/unit/planning/test_revision.py`, unit connected-demo tests, and existing HTTP/read-model integration tests.
**Interfaces:** Produce strict `IntakeFactDeltaV1`, `PlanningRevisionComparisonV2`, bounded `PreviousRequestReviewV1`, `CostProjectionV2` with stored intake, and `AdvisorLedgerV3` with `case_intake`. Add repository/service V3 read methods; exactly one `contract_version=3` selects the ledger. Current-decision-brief stays V2.

- [x] Write failing tests for exactly one of three deltas, actual persisted intake, frozen old review joins, source selection before task creation, stored pins after creation, matching cost intake and output-hash validation. Cover extra/malformed values and simultaneous changes.
- [x] Record focused RED, then build V3 from verified persisted Case/task/run/source/review data. Keep V1 builders/models and V2 old-scenario responses unchanged; new-scenario legacy reads return the existing bounded unavailable response.
- [x] Test absent/default, exact V2/V3, empty/repeated/unknown negotiation, participant isolation and safe errors. Use persisted database rows for identity/authority assertions after Task 2's runtime gate is authorized.
- [x] Run affected unit/API contracts and legacy country/budget regressions; commit the versioned read outcome.

### Task 4: Carry the actual intake through the existing UI

**Modify:** `web/app/demo/page.tsx`; `web/lib/connected-demo/use-connected-demo.ts`, `api.ts`, `contracts.ts`, `revision.ts`, `session-storage.ts`; `web/components/connected-demo/ConnectedDemo.tsx`, `RevisionFactEditor.tsx`, `PlanningRevisionComparison.tsx`, `AdvisorLedger.tsx`, `DecisionReceiptTimeline.tsx`; `web/app/api/demo/cases/[caseId]/advisor-ledger/route.ts`; `web/lib/presentation/catalog.ts`.
**Tests:** Existing revision/editor/contract/API/recovery/UI suites plus intake-specific cases.
**Interfaces:** Add the `student.intake` `RevisionIntent` branch, strict month validation and exact candidate/message bodies. The allowlisted `intake-delay` entry supplies the fixed initial Case only for an explicit fresh start; resumed metadata remains bound to its existing Case. The ledger BFF requests V3 and brief BFF continues V2.

- [x] Write failing tests for intake-only/current/missing/stale facts, parent rejection, no change/invalid month, actual proposal value, explicit student/advisor handoff, restored intake intention and retained old intent replay. URL entry must not overwrite an active journey.
- [x] Observe RED, then connect the third editor branch, matcher, saved intent and controlled entry using existing handoff/CSRF/idempotency rules. Display the hypothetical supported alternate and the actual current cost intake. Show old request-review context as history.
- [x] Decode V3 exactly; retain tests for V1/V2 old contracts rather than accepting unknown discriminators. Assert unchanged country eligibility and changed intake can coexist in the comparison.
- [x] Run focused Vitest and frontend lint/typecheck, using an authorized locked isolated environment if needed. Browser/build/pull/native proof remains a separately authorized gate; no scripted facade success proves runtime completion. Commit exact UI paths.

### Task 5: Verify the persisted end-to-end chain and finish documentation

**Create:** `tests/integration/connected_demo/test_intake_revision_flow.py` and `scripts/verify_controlled_intake_revision.py`, a bounded database readback verifier for the fixed Case. Its `verify_persisted_intake_revision(snapshot)` checks persisted identities/counts/values and emits only a safe acceptance summary; it neither mutates business state nor runs a browser.
**Modify:** Existing February timeline/decision regressions, `docs/reference/collaboration-and-confirmed-facts.md`, `http-api-v1.md`, `agent-tasks-and-events.md`, `domain-and-source-manifests.md`, and the customer revision walkthrough; update the two draft status indexes after real acceptance.
**Interfaces:** Consume the exact fixture descriptor, guarded confirmation/task creation and V3 projection. Produce an as-of-bound acceptance record with the final SHA, actual commands, old/new identities and immutable history snapshots.

- [x] Write a real-role flow that starts on the fixed initial Case, records `request_revision`, submits student `2028-02`, confirms as assigned advisor, explicitly creates the successor Task and processes it with the existing deterministic worker. Assert the actual adapter input and PostgreSQL source/cost/evidence pins.
- [x] Add fresh advisor approval and direct parent decision accepting `32,000,000`–`36,000,000` CNY minor with `budget_elasticity`; read the receipt, actor, brief/revision/run/source joins and timeline from PostgreSQL. Assert `2027-09-01`, `2027-10-15`, `2027-12-15`, `2028-01-20` and unchanged policy.
- [x] Exercise finalized denial and unsupported `2028-09` confirmation on separate controlled negative fixtures. Compare all refused business writes; compare predecessor output/routes/cost/evidence and review bytes across success, allowing only the existing intentional `is_current` change.
- [x] Run the approved bounded real database flow and relevant checks, then perform targeted review. GStack is unavailable and is not invoked; use existing repository document/link checks for the affected reference/how-to/entry. Actual new-image/browser gates remain pending until separately approved, not full local READY.
- [x] Document opt-in setup, both read-contract versions, unavailable-source refusal, fixed synthetic values/as-of and the limited pre-consent path. Inspect diff/links/privacy and semantic commits. Report exact HEAD, actual checks, docs impact and remaining gates; no push/PR/merge/release/deploy without separate authorization.

## Plan self-review and handoff

Every spec requirement maps to the owning task: fixture identity (1), database
authority/negative controls (2), third-delta and read compatibility (3), actual
UI value/role/replay (4), persisted receipt/timeline/history truth (5). The five
Review Focus cases have explicit assertions in those tasks. New types and
method names above are proposed interfaces for review, not existing functions.

Written spec/plan and the named migration/read-contract/source refusal choices
are approved. Execute directly using the selected controller; bounded PG tests
are in scope, while complete native/browser/image proof and remote actions are
separate gates. Return a frozen local candidate with actual low-cost and
runtime-role evidence before requesting those broader gates.
