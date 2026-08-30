# Connected same-Case plan execution continuation v1 implementation plan

Status: Approved
Implementation: Merged on the current default branch in PR #103; local synthetic and provider-free; not included in stable v0.1.5; not deployed
Delivery: One pull request

## Constraints

Implement test-first in one isolated worktree. Preserve PostgreSQL, ActorContext, RLS, current timeline execution mutations, current domain transitions, independent scenarios, and synthetic/local boundaries.

Do not add a migration, database function, permission change, dependency, provider, second state machine, automatic successor, Release, deploy, or unrelated refactor.

## Task 0: Land the approved records

Create this spec and plan, add the smallest docs/README.md status entry, run focused documentation checks, create one semantic local commit, and stop for authority landing review before product implementation.

## Task 1: Add the case-scoped read contract

Modify only the owning timeline execution model, port, service, PostgreSQL repository, HTTP router, and owning tests.

Write RED tests first for:

- exact current Case/revision/decision/receipt/timeline with no execution;
- the same projection with an existing execution;
- strict schema and extra-field rejection;
- non-participant, wrong role, stale/noncurrent revision, foreign timeline, zero rows, multiple rows, and identity contradiction;
- bounded non-enumerating problem responses.

Implement the smallest GREEN read projection with existing RLS and SELECT grants. Do not change mutation SQL or add database DDL.

Expected owning surfaces:

- src/night_voyager/timeline_execution/models.py
- src/night_voyager/timeline_execution/ports.py
- src/night_voyager/timeline_execution/application.py
- src/night_voyager/timeline_execution/postgres.py
- src/night_voyager/interfaces/http/timeline_execution.py
- tests/unit/timeline_execution/
- tests/integration/timeline_execution/

## Task 2: Add the strict BFF and authority adapter

Write RED tests first for canonical case UUID handling, strict response parsing, connected/seeded route exclusivity, active-role identity, cross-Case drift, session loss, stale authority, and recovery metadata source mismatch.

Add the case-scoped BFF. Model the plan execution context as a strict seeded-or-connected union with common execution anchors. Parameterize the existing API/controller at the context/session authority seam; keep one reducer and one mutation/reconciliation implementation.

Extend recovery metadata to bind the authority kind and exact case or scenario. Preserve existing valid seeded behavior or fail old metadata safely; never reinterpret its identity.

Expected owning surfaces:

- web/lib/connected-demo/api.ts
- web/lib/plan-execution/api.ts
- web/lib/plan-execution/contracts.ts
- web/lib/plan-execution/scenario.ts
- web/lib/plan-execution/session-storage.ts
- web/lib/plan-execution/use-plan-execution.ts
- web/app/api/demo/cases/[caseId]/plan-execution-context/route.ts
- web/app/demo/plan/page.tsx
- owning web/tests/unit/ files

## Task 3: Continue the connected presentation without a second workflow

Write presentation and routing RED tests. At plan_ready, replace the independent-scenario handoff as the primary action with same-Case continuation while retaining a clearly secondary independent evaluation/recovery entry.

Reuse PlanExecutionWorkspace and existing execution presentation components. Do not redesign shared visual language or create a new execution state machine.

Expected owning surfaces:

- web/components/connected-demo/ConnectedDemo.tsx
- web/components/plan-execution/PlanExecutionWorkspace.tsx
- current presentation copy catalogs
- web/tests/unit/connected-demo-*.test.*
- web/tests/unit/plan-execution-*.test.*
- relevant Playwright journeys

## Task 4: Prove the exact same-Case journey

Use real PostgreSQL roles/RLS in a disposable task-owned Compose lane when the daemon is available, and always require the hosted Compose gate before merge.

The end-to-end proof must cover:

fact revision -> confirmed fact -> replan -> renewed advisor review -> family decision -> exact DecisionReceipt/TimelinePlan -> case-scoped context -> family execution start -> lost-ack replay -> reload -> role handoff -> checkpoint blocked -> advisor reassessment -> pending_future_authorization.

Assert exact identity equality and fail-closed counterfactuals. Do not use a frontend-only fixture as database proof. Do not read, modify, or rebuild a retired holdout.

Retain regressions for the independent happy and blocked scenarios.

## Task 5: Update current public truth and deterministic evidence

Update only affected current entry docs, reference/API docs, runbooks, route/storyboard descriptions, navigation, and deterministic screenshot/manifests.

Keep synthetic/local/non-production boundaries. Explain the difference between same-Case continuation and independent seeded recovery scenarios.

Do not rewrite historical Release records or unrelated screenshots. Freeze the source tree/input fingerprint before capture, inspect resulting images, and run public/private marker, raw UUID, credential, and private-path scans.

## Verification

Run fresh evidence on the final clean tree:

- focused timeline execution and connected demo Python tests;
- uv run pytest -q -m "not database and not mke";
- make dra-check;
- make collaboration-check;
- make skills-check;
- the existing MKE read-only smoke lane;
- uv run ruff check .;
- uv run pyright;
- uv build --build-constraints build-constraints.txt --require-hashes;
- uv run python scripts/verify_release.py --tree-mode release;
- npm --prefix web ci;
- npm --prefix web run lint;
- npm --prefix web run typecheck;
- npm --prefix web run test;
- npm --prefix web run build;
- full and omit-dev npm audit;
- docker compose config --quiet;
- task-owned database/Compose/browser same-Case proof when local Docker is available;
- PR-head hosted Python, frontend, database, Compose, browser, and aggregate gates;
- git diff --check, exact changed-path review, public/private marker scan, and affected evidence provenance/readback.

If local Docker is unavailable, do not start or reconfigure it. Record the local omission and require hosted Compose/database/browser success before merge.

## Review and delivery

After implementation and complete local verification, create a clean semantic commit and return READY for independent authority diff review. Do not push before that review.

Resolve only verified same-scope findings, rerun targeted and affected broad verification, and return the amended exact HEAD for targeted re-review.

After authority acceptance, the designated remote owner performs exact reviewed HEAD push, one public-neutral PR, persisted body readback, hosted checks, same-scope repair if needed, conditional squash merge, exact merge-SHA default-branch checks, primary fast-forward when safe, and task-owned cleanup.

## Stop conditions

Stop and return to authority if safe completion requires any migration or database function, RLS/permission relaxation, mutation schema/domain transition change, new dependency/tool, second workflow authority, automatic successor, provider/model call, real data, host/Docker global change, broad cleanup, Release, deploy, package publication, or access to protected owner-unknown state.
