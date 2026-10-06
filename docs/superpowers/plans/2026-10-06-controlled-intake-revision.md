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
- Written design/plan approval is complete. The bounded PostgreSQL/runtime-role lane and the focused native/browser/image follow-up below are approved. Hosted delivery remains separate. The deferred native recovery CI proof is not a dependency or acceptance substitute.

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
are in scope. The frozen local candidate and its bounded evidence were accepted;
the focused native/browser/image phase below is now authorized. Remote actions
remain a separate gate.

## Authorized focused native follow-up

This phase was approved on `2026-10-06`. Reuse the design and direct execution;
do not dispatch a second whole-branch reviewer. Do not run the frozen terminal
recovery proof or real providers. No base-image pull, new dependency/tool,
shared-cache or permanent host setting change, or hosted mutation is authorized.

### Task 6: Correct the seed description and freeze the documentation follow-up

- [x] Distinguish the initial intake ConfirmedFact chain from budget values held
  in revision preferences. Update current status while retaining the original
  review finding as history.
- [x] Run documentation governance only: `32 passed`; reuse unchanged runtime
  checks. Index the 18 `tmp/intake-n2-20261006/final-review-*.txt` raw logs by
  relative path, SHA-256 and observed exit result, including the failed/superseded
  runs, in the ignored approval checkpoint.
- [x] Semantic commit `4456217e37f574da4c209e7dbd022a8ab95885ef`, tree
  `9823138750ddab2f439182c499ea98a9a185832a`. No deferred minor remains.

### Task 7: Prove the controlled intake through actual images and browser

**Create:** `web/e2e/controlled-intake-revision.spec.ts` and
`web/playwright.intake.compose.config.ts`. Use the existing Playwright framework,
real BFF requests, actual API/worker and empty PostgreSQL. A task-only runner and
Compose configuration remain ignored diagnostic/environment artifacts; this is
one focused acceptance lane, not a general proof platform.

**Frozen source:** application/E2E input HEAD
`6154bfd1b4a56e79527b0c03109fefc75f8a1193`, tree
`37291ccb39d1fdb2032aa1163643ad95ac1a99a9`. The focused spec/config passed
typecheck, lint and discovery (one test). The task's ignored `native-a1/source.tar`
is a `git archive` of that commit, SHA-256
`7ee8866818b03b101c3a181381b83420e1eaf7a950d435a34f69829191253876`.
Later documentation-only commits do not change the archived input or
cause a rebuild. Any changed runtime/E2E input requires new binding and affected
verification.

**Images:** locally available Python
`sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36`,
Node Alpine `sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd`,
PostgreSQL `sha256:9a8afca54e7861fd90fab5fdf4c42477a6b1cb7d293595148e674e0a3181de15`
and retained Chromium/locked browser dependencies
`sha256:c46303754e0a27744be8d839c5a298bf031855a49f7244cda43158880757ce07`.
The browser image's package-lock SHA equals the current web lock. Use a dedicated
builder from retained BuildKit
`sha256:cec9f139f45e93c5c69c60f8b07cfad9f43f4ef6b6a6cd917527fea5ff2e3dea`
with task-only Docker client configuration and cache volume. Start it with
`docker run --pull never` and connect Buildx's `remote` driver over the existing
Docker container connection helper; the managed container driver would attempt
a registry pull. No builder port or Docker socket is mounted. Export existing
bases to local OCI contexts rather than resolving registry images; Buildx
[supports local OCI contexts](https://docs.docker.com/reference/cli/docker/buildx/build/#additional-build-contexts---build-context).
Apply only base aliases/task cache IDs to copies of the existing Dockerfiles;
retain their package/wheel/build operations. Record the derived Dockerfile hashes,
all resulting image IDs, frozen source and lock hashes. Copy PostgreSQL init assets
and focused E2E assets into their task images; no source bind mounts.

**Resources:** Compose project `night-voyager-intake-native-n2-20261006-a1`;
database `night_voyager` on a new project-owned cluster/volume; host web/API/PG
ports `52130`/`52131`/`52132`; public/browser origin
`http://127.0.0.1:52130`. The browser's existing socat bridges that origin to the
actual web service. Only named task PostgreSQL/browser-artifact volumes are
mounted. Labels and inventory must prove ownership. Hold only a task caffeinate
process. Recheck the established 8 GiB Docker VM capacity gate before costly work
and before runtime startup; do not bypass it or prune unrelated resources.

**Actual commands:** the ignored runner executes these explicit phases with
arguments/assets recorded in its checkpoint (all from this worktree):

```bash
N2ROOT="$PWD/tmp/intake-n2-20261006/native-a1"
# Capture the already configured local endpoint before selecting task client config.
N2_DOCKER_ENDPOINT=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
export DOCKER_HOST="$N2_DOCKER_ENDPOINT" DOCKER_CONFIG="$N2ROOT/docker-client"
MODE=dev NIGHT_VOYAGER_DOCTOR_PORTS='52130 52131 52132' \
  NIGHT_VOYAGER_DOCTOR_PROBE_IMAGE=sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 make doctor
git archive 6154bfd1b4a56e79527b0c03109fefc75f8a1193 -o "$N2ROOT/source.tar"
tar -xf "$N2ROOT/source.tar" -C "$N2ROOT/source"
.venv/bin/python "$N2ROOT/prepare.py"
.venv/bin/python "$N2ROOT/build.py" # records exact argv without executing builds
N2_EXECUTE_BUILD=1 .venv/bin/python "$N2ROOT/build.py"
docker compose -p night-voyager-intake-native-n2-20261006-a1 -f "$N2ROOT/compose-bound.json" \
  up -d --no-build --pull never --wait --wait-timeout 120 api worker web
docker compose -p night-voyager-intake-native-n2-20261006-a1 -f "$N2ROOT/compose-bound.json" \
  run --no-deps --name night-voyager-intake-native-n2-20261006-a1-browser browser-proof \
  ./node_modules/.bin/playwright test --config playwright.intake.compose.config.ts
docker compose -p night-voyager-intake-native-n2-20261006-a1 -f "$N2ROOT/compose-bound.json" \
  down --volumes
```

The pre-execution checkpoint binds `preparation.json`, `build-commands.json`,
the task client config (existing bundled CLI plugin directory only), and the
derived Dockerfiles. Their SHA-256 values are:

| Artifact | SHA-256 |
| --- | --- |
| `api.Dockerfile` | `f48424b64b8f9e75efbc0af73bdc64c81420c194d358b7a4d8ccee0e0b7317ca` |
| `web.Dockerfile` | `c4915510aa1b1230ece8b47503d01731801a741b9517d02bafb738faa56d16ca` |
| `postgres.Dockerfile` | `4f5d129197cd011a5373dc1f5cd8cee2518c98b2822af7fb6ad8ed7ec1981a4f` |
| `browser.Dockerfile` | `91a3d099d9d4aaf772eeb1b5f0b64476343006a5f58f2ad158efd1d960f00e4e` |
| Proposed Compose with unique task tags | `059e12c1582be45be2a86f63c58d87974233b4c1eca158de89d8fa1d583a16a3` |

The resulting image IDs replace only those tags in `compose-bound.json` before
startup; record its final hash and image-to-service binding. The builder is
`nv-intake-n2-native-20261006-a1`, container with suffix `-buildkit`, state volume
with suffix `-state`. Release that cache/container after builds and before the
second capacity check, retaining the four candidate images. PostgreSQL and
browser volumes are the project name plus `_postgres-data`/`_browser-artifacts`.

Each image build is bounded to 600 seconds, startup to 120 seconds and the focused
browser test to 240 seconds, with no Playwright retry and one worker. The browser
pauses at its actual request-review response for at most 45 seconds while an
observer captures a read-only API-role snapshot and acknowledges the stage in
the task artifact volume; this does not alter business state or control the worker.
Preserve
diagnostics after the first failure and identify its cause before another run.
The second substantive failure of this same costly goal stops the lane for a
route decision, even if its harness changed. Do not rebuild for documentation or
verification-record changes. Capture browser results/screenshots, pre/post API-role
database snapshots, installed image assets and role/cluster identity. Clean up
only this stage's containers, networks, temporary builder/cache volumes and
caffeinate; retain candidate images, source and diagnostics.

- [x] Prepare the focused spec/config and validate their discovery/type/lint.
  Acceptance tests verify existing behavior; do not invent a RED result when they
  already pass. Ordinary product fixes found here require proportional TDD.
- [ ] Freeze input HEAD/tree and archived input hashes; prepare local base contexts,
  task builder/config and image bindings, then build the task application images.
- [ ] Start the empty seeded cluster with `--with-intake-revision`; prove actual
  API/worker roles, installed package/fixture/Skill/migration assets and no source
  overlays. Save the initial same-Case/history snapshot before browser mutation.
- [ ] In Chinese, explicitly start an existing default journey, demonstrate the
  controlled entry cannot overwrite it, explicitly end it and start Case3. Request
  revision, submit actual student `2028-02`, reload pending state, hand off to advisor,
  confirm and explicitly create the new task. Replay one captured mutation with its
  original idempotency key and assert one persisted business result.
- [ ] Verify V3 actual intake/new pack/cost `32640000`, fresh review, then direct
  parent `32000000`–`36000000` with `budget_elasticity`, receipt and four dates.
  Reload the completed view; compare old output/review bytes with only the intended
  old run `is_current` change. Capture desktop/mobile rendered screens and inspect
  them. Choose other-language coverage only for the actual changed surfaces.
- [ ] Collect exact input/final HEAD/tree, image/artifact/DB/browser evidence and
  raw log hashes/exit results; update current public evidence and scope status.
  Verify task resource release and unaffected worktrees, then return once. Hosted
  delivery remains separately gated.
