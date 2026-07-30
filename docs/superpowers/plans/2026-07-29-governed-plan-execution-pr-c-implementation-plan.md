# Governed Plan Execution PR C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close recorded P1/P2 presentation and developer-experience findings, prove the professional bilingual execution workspace across required viewports and accessibility modes, and prepare the merged feature for a separately authorized `v0.1.5` release.

**Architecture:** Preserve the merged PR A/B domain, PostgreSQL, HTTP, BFF, reducer, recovery, and browser-to-database authority. Begin with a read-only rendered baseline, record concrete findings, and change only routes/components implicated by those findings. Shared presentation primitives and documentation may be refined, but no visual preference may silently change business semantics or authorize a broad redesign.

**Tech Stack:** Next.js 16, React 19, TypeScript, existing CSS and presentation catalog, Vitest/Testing Library, Playwright 1.58, existing provider-free Compose proof, pytest documentation/release contracts.

**Plan status:** Implementation complete and locally verified. Publication and
v0.1.5 release remain pending.

## Global Constraints

- Base is the reviewed and merged PR B at migration head `0015`.
- No backend source, FastAPI/BFF route semantics, migration, database function, fixture authority, dependency, lockfile, Dockerfile, Compose policy, version bump, release note, tag, Release, deploy, provider, credential, or DRA live-status change.
- Preserve the two intentional identities: root `Virtual Night Voyage` portfolio shell and warm-paper governed demo workspace.
- Existing routes may change only when the rendered baseline records a P1/P2 hierarchy, accessibility, responsive, or cross-route consistency finding.
- A route with no recorded finding is not rewritten.
- Preserve exact user actions, strict parsers, recovery state, idempotency, current-action meaning, role authority, receipt-then-GET flow, and browser/database assertions.
- Required widths are 1440, 768, 390, and 320 CSS pixels; 200% zoom must not create horizontal page scrolling.
- Required accessibility includes keyboard completion, visible focus, deterministic focus after mutation/recovery, deduplicated live regions, semantic headings/landmarks, `aria-describedby` error association, reduced motion, WCAG 2.2 AA text contrast, minimum 24×24 targets, and 44×44 preferred primary mobile actions.
- Exact `zh-CN` and `en` copy remain closed and equally complete.
- Pixel screenshots are review evidence, not authority. Semantic assertions remain the contract.
- No UI framework, icon library, animation dependency, analytics, remote font, image CDN, telemetry, hosted playground, public SDK, new CLI, or community service.
- No production, real-user, school-coverage, admissions, time-savings, business-impact, HA/SLA, or audit-zero claim.
- Final rendered review must have zero unresolved P1. Every P2 is fixed or receives a reviewed evidence-based disposition in the PR body.

## File Map and Ownership

Always-authorized review/evidence paths:

- `tests/architecture/test_portfolio_presentation_contract.py`
- `web/tests/unit/plan-execution-presentation.test.ts`
- `web/tests/unit/plan-execution-ui.test.tsx`
- `web/e2e/presentation.spec.ts`
- `web/e2e/plan-execution.spec.ts`
- current design, storyboard, operations, README, docs-index, and release-verifier surfaces listed in Task 5.

Finding-gated implementation paths:

- `web/app/styles.css`
- `web/app/layout.tsx`
- `web/app/page.tsx`
- `web/app/demo/plan/page.tsx`
- route pages under `web/app/demo/**`
- `web/components/presentation/**`
- presentational JSX/class structure under `web/components/plan-execution/**`
- presentational JSX/class structure under `web/components/collaboration-demo/**`, `web/components/connected-demo/**`, `web/components/demo-session/**`, and `web/components/skill-inspector/**`
- `web/lib/presentation/**`
- related presentation/accessibility/catalog tests and existing E2E selectors.

No file under `src/night_voyager/**`, `migrations/**`, backend fixture modules, dependency manifests, lockfiles, Dockerfiles, or Compose files is authorized. A need to change one is a substantive stop.

## Execution Preflight and Commit Protocol

```bash
git status --short --branch
test -z "$(git status --porcelain)"
: "${EXPECTED_BASE_SHA:?reviewed PR B merge SHA required}"
test "$(git rev-parse HEAD)" = "$EXPECTED_BASE_SHA"
make doctor MODE=dev
uv sync --locked
npm --prefix web ci
test "$(uv run alembic heads | awk '{print $1}')" = "0015"
```

Record `BASE_SHA`. Create a mode-0700 task evidence root outside the repository for baseline screenshots, review notes, and timing logs. Do not commit private paths or raw review metadata. Each implementation task requires a recorded finding ID, valid RED, minimal GREEN, exact diff review, semantic commit, and clean worktree.

---

### Task 1: Capture the rendered baseline and freeze the finding ledger

**Files:**

- Create: `web/e2e/presentation.spec.ts`
- Modify: `tests/architecture/test_portfolio_presentation_contract.py`
- Modify: `web/tests/unit/plan-execution-presentation.test.ts`
- Modify: `web/tests/unit/plan-execution-ui.test.tsx`

**Baseline matrix:**

```text
routes: /, /demo/collaboration, /demo, /demo/plan
locales: zh-CN, en
widths: 1440, 768, 390, 320 CSS px
zoom: default and 200%
states: default/current action, awaiting advisor, blocked/reassessment, recovery, completed where available
input modes: keyboard and pointer
motion: normal and prefers-reduced-motion
```

The private finding ledger has exact fields:

```text
finding_id
severity: P1|P2
route
locale
viewport_or_mode
observable_problem
semantic_or_accessibility_impact
minimal_authorized_paths
acceptance_assertion
status: open|fixed|dispositioned
```

Severity:

- P1: blocks primary action, keyboard completion, readable authority, role/stop understanding, or required reflow/contrast.
- P2: material hierarchy, consistency, target-size, long-copy, or technical-noise problem that does not block the journey.

- [x] **Step 1: Add a RED for the missing presentation-audit harness and matrix coverage**

The architecture RED requires a committed provider-free audit harness that
enumerates every approved route, both locales, 1440/768/390/320 widths, 200%
zoom, keyboard/focus, reduced motion, contrast, overflow, long-copy wrapping,
and latest-64 disclosure. Implement the harness without asserting that current
product presentation already passes every finding. Product-specific REDs are
added only after the rendered finding ledger is frozen in Tasks 2 and 3.

- [x] **Step 2: Run the baseline against one normal task-owned stack**

Use existing provider-free fixture authority and make no source changes during observation. Capture sanitized screenshots and accessibility/overflow data under the private evidence root.

- [x] **Step 3: Run a targeted rendered presentation review and record P1/P2 findings**

The review is read-only. If no P1/P2 exists for an existing route, mark that route `no_change` and remove it from later authorized implementation paths.

- [x] **Step 4: Commit only the baseline contract**

```bash
uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
npm --prefix web run test -- --run \
  web/tests/unit/plan-execution-presentation.test.ts \
  web/tests/unit/plan-execution-ui.test.tsx
npm --prefix web run lint
npm --prefix web run typecheck
git add web/e2e/presentation.spec.ts \
  tests/architecture/test_portfolio_presentation_contract.py \
  web/tests/unit/plan-execution-presentation.test.ts \
  web/tests/unit/plan-execution-ui.test.tsx
git commit -m "test: add governed presentation audit harness"
```

### Task 2: Close plan-execution hierarchy, responsive, and accessibility findings

**Files:**

- Modify only when named by the finding ledger: `web/app/styles.css`
- Modify only when named: `web/app/demo/plan/page.tsx`
- Modify only when named: `web/components/plan-execution/**`
- Modify only when named: `web/components/presentation/**`
- Modify: `web/tests/unit/plan-execution-presentation.test.ts`
- Modify: `web/tests/unit/plan-execution-ui.test.tsx`
- Modify: `web/e2e/plan-execution.spec.ts`
- Modify: `web/e2e/presentation.spec.ts`

**Required hierarchy:**

1. current checkpoint, state, accountable role, and due date;
2. exactly one primary current action or an explicit waiting explanation;
3. next human handoff and risk summary;
4. immutable approved plan context;
5. activity and optional technical details.

`Overview`, `Plan`, and `Activity` are landmarks, anchors, or disclosures, not competing route-level tabs. On narrow screens and at 200% zoom, current action remains first in DOM and visual order. Raw hashes, row versions, SQL, task/lease terminology, and database rows are not default content.

- [x] **Step 1: For each plan-route finding, write one failing semantic/browser assertion**

The assertion names the finding ID and observable failure. Do not create a generic pixel snapshot.

- [x] **Step 2: Run RED**

```bash
npm --prefix web run test -- --run \
  web/tests/unit/plan-execution-presentation.test.ts \
  web/tests/unit/plan-execution-ui.test.tsx
```

- [x] **Step 3: Implement the smallest presentational fix**

Do not edit `web/lib/plan-execution/**`, API calls, reducer states, action labels, or mutation order.

- [x] **Step 4: Run GREEN and commit**

```bash
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
# Print and compare the exact changed-path set with the fixed finding ledger.
git diff --name-only -- web/app/styles.css web/app/demo/plan \
  web/components/plan-execution web/components/presentation \
  web/tests/unit web/e2e
# After the comparison is exact, stage only tracked files in these closed roots.
git diff --name-only -z --diff-filter=ACMRT -- \
  web/app/styles.css web/app/demo/plan \
  web/components/plan-execution web/components/presentation \
  web/tests/unit web/e2e \
  | git add --pathspec-from-file=- --pathspec-file-nul
git diff --cached --name-only
git commit -m "feat: refine the governed execution workspace"
```

If the finding ledger has no plan-route P1/P2, skip source modification and record a no-change evidence task; do not create an empty commit.

### Task 3: Close only recorded cross-route consistency findings

**Files:**

- Modify only when named: `web/app/page.tsx`
- Modify only when named: route pages under `web/app/demo/**`
- Modify only when named: `web/components/presentation/**`
- Modify only when named: presentational structure under collaboration/connected/session/skill components.
- Modify only when named: `web/lib/presentation/catalog.ts`
- Modify: exact unit/E2E tests attached to the recorded findings.

Permitted changes are presentation-only:

- shared navigation/current-route indication;
- page-title and section hierarchy;
- primary versus secondary action prominence;
- consistent status/owner/handoff vocabulary;
- recovery placement;
- spacing, surfaces, target sizes, focus, contrast, long-copy wrapping, and reduced motion.

Existing accessible action names stay unchanged unless the finding explicitly proves an ambiguity and the same closed catalog change is applied to semantic tests and browser selectors.

- [x] **Step 1: Write one RED per cross-route finding**

- [x] **Step 2: Implement only finding-backed presentational changes**

- [x] **Step 3: Run full web regression**

```bash
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
npm --prefix web exec playwright test -- --list
```

- [x] **Step 4: Commit**

```bash
# First print the exact changed-path set and compare every path with the fixed
# finding ledger. Abort if any path is not named by a recorded P1/P2.
git diff --name-only -- web/app web/components web/lib/presentation \
  web/tests/unit web/e2e
# After exact ledger comparison, stage only tracked files in the closed roots;
# do not use a directory-wide git add.
git diff --name-only -z --diff-filter=ACMRT -- \
  web/app web/components web/lib/presentation web/tests/unit web/e2e \
  | git add --pathspec-from-file=- --pathspec-file-nul
git diff --cached --name-only
git commit -m "feat: align governed product presentation"
```

If no existing route has a recorded P1/P2, do not modify it and do not create an empty commit.

### Task 4: Prove the final presentation matrix and publish representative evidence

**Files:**

- Modify: `web/e2e/presentation.spec.ts`
- Modify: `web/e2e/plan-execution.spec.ts`
- Modify only when assertions require it: existing journey E2E specs.
- Modify: `tests/architecture/test_portfolio_presentation_contract.py`
- Create: `docs/assets/plan-execution-current-action.png`
- Create: `docs/assets/plan-execution-advisor-review.png`
- Create: `docs/assets/plan-execution-reassessment-mobile.png`
- Create: `docs/assets/plan-execution-recovery-mobile.png`

The four committed images use synthetic data, contain no session/CSRF/idempotency/private path, and represent:

1. desktop current action;
2. advisor verification/waiting handoff;
3. mobile reassessment stop;
4. mobile recovery.

They are documentation evidence only. Semantic Playwright assertions remain the pass/fail authority.

- [x] **Step 1: Run the complete matrix on one normal task-owned stack**

Assert no overflow, no clipped action/status, one H1, valid landmarks/headings, keyboard completion, visible focus, deterministic post-mutation focus, reduced-motion behavior, contrast evidence, target sizes, and exact bilingual state semantics.

- [x] **Step 2: Re-run targeted rendered review**

Require zero P1. Fix remaining P2 or record an evidence-based PR-body disposition. A disposition cannot waive a blocked action, accessibility failure, hidden authority, or overflow.

- [x] **Step 3: Capture and sanitize the four representative images**

Verify image dimensions, visible synthetic labels, and absence of forbidden text before staging.

- [x] **Step 4: Commit**

```bash
uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
git add web/e2e tests/architecture/test_portfolio_presentation_contract.py \
  docs/assets/plan-execution-*.png
git commit -m "test: prove professional governed presentation"
```

### Task 5: Close evaluator-first documentation and contributor DX

**Files:**

- Modify: `DESIGN.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `docs/operations/plan-execution-walkthrough.md`
- Modify: `docs/operations/timeline-execution.md`
- Modify: `docs/reference/timeline-execution-contract.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `CONTRIBUTING.md`
- Create: `.github/ISSUE_TEMPLATE/proof-failure.yml`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/README.md`
- Modify: governed-plan-execution spec and PR A/B/C plan statuses.
- Modify: `scripts/verify_release.py`
- Modify only after RED: documentation/release/presentation tests.

**DX contract:**

Documentation distinguishes:

- `make proof`: quick provider-free contract proof;
- manual walkthrough: human-readable functional demo;
- `make compose-proof`: full browser-to-database proof.

Each path lists prerequisites, stable success markers, expected phases, proof boundary, safe recovery, exact teardown, and observed duration/cache context. Reuse exact retained timings from PR A/B/C gate logs; if a required cold/warm observation is absent, run one bounded measurement and label actual shared-cache/task-image state rather than claiming a synthetic cold start.

The contributor matrix maps:

```text
domain/model -> unit + type
migration/SQL -> isolated DB + catalog/RLS/downgrade
FastAPI/BFF -> HTTP + strict transport
web state/recovery -> unit + browser
presentation -> semantic + rendered matrix
docs/release surface -> governance + verifier
```

The proof-failure issue template accepts only:

```text
command
public phase marker
public problem code
expected stable marker
observed stable marker
host and Docker VM available-space counts
task-scoped Compose project name
task-resource teardown result
```

It explicitly forbids credentials, cookies, CSRF, raw `.env`, database URLs, private paths, raw database rows, content-bearing Evidence, and uploaded logs containing those values.

- [x] **Step 1: Add documentation/DX RED**

Require all three proof paths, error catalog anchors, migration runbook, contributor matrix, issue-template fields/prohibitions, screenshot references, current statuses, non-claims, and immutable prior releases.

- [x] **Step 2: Update docs, audit documentation coverage, and run a live developer-experience walkthrough**

The live DX review executes documented public commands and records only public output/phase evidence. It does not change product scope.

- [x] **Step 3: Run focused GREEN**

```bash
uv run pytest -q \
  tests/architecture/test_documentation_governance.py \
  tests/architecture/test_portfolio_presentation_contract.py \
  tests/unit/test_release_surface.py
uv run python scripts/verify_release.py --tree-mode development
```

- [x] **Step 4: Commit**

```bash
git add .github/ISSUE_TEMPLATE/proof-failure.yml \
  DESIGN.md CONTRIBUTING.md docs README.md README_CN.md \
  scripts/verify_release.py
# Add only individually reviewed RED-proven compatibility paths.
git commit -m "docs: close governed execution DX"
```

### Task 6: Run exact-head final gates and freeze release readiness

- [x] **Step 1: Run non-container gates**

```bash
uv lock --check
uv run ruff check .
uv run pyright
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
make db-check
make check
make proof
uv run python scripts/verify_release.py --tree-mode development
```

- [x] **Step 2: Run one normal task-scoped full Compose proof**

```bash
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-c-final-$$" \
  make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-execution-pr-c-final-$$" \
  make down
```

Require all existing collaboration, DRA, planning revision, and exact `zh-CN`/`en` governed execution Happy/Blocked lanes, plus presentation matrix evidence. Confirm task/default Compose projects and containers are empty; retain shared volume/images/cache.

- [x] **Step 3: Run final scope and hygiene review**

```bash
git diff --check
git diff "$BASE_SHA"..HEAD --check
git status --short
```

Confirm:

- zero backend, migration, dependency, lockfile, Dockerfile, Compose, version, or release-artifact diff;
- every existing-route source change has a finding ID;
- zero unresolved P1 and every P2 fixed/dispositioned;
- four sanitized screenshot assets only;
- no private path, coordination ID, credential-like value, session/CSRF/idempotency value, or raw sensitive payload;
- published `v0.1.0`–`v0.1.4` notes/how-to remain byte-identical.

- [x] **Step 4: Freeze PR C exit evidence**

Return exact commit list, changed files/stat, finding ledger summary, RED→GREEN evidence, viewports/locales/accessibility proof, DX command observations, normal Compose proof, Docker inventories, documentation impact, rollback boundary, and non-claims. Worktree/staging/untracked must be clean.

**Rollback:** Revert PR C presentation, test, screenshot, and documentation commits. PR A/B execution authority and complete functional/recovery journey remain independently usable and verifiable.

**Exit evidence:** Governed plan execution has zero unresolved P1 presentation/DX findings, all P2 findings are fixed or dispositioned, all functional/database proofs remain GREEN, and the project is ready for a separately authorized `v0.1.5` release-preparation workflow. No version bump, release, provider execution, deploy, or successor workflow is claimed.
