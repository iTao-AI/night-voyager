# Planning Revision Journey PR 3 Implementation Plan

**Goal:** Deliver a bilingual connected journey in which an advisor requests revision, the student changes preferred countries, a new plan is explicitly created and compared with its retained predecessor, and only a fresh advisor approval can reach the current family decision and timeline.

**Architecture:** Evolve the existing connected-demo ledger, client contracts, session recovery, and role rotation instead of creating another business workflow. Reuse the existing collaboration, fact verification, task, SSE, advisor-review, and family-decision APIs. Add a deterministic comparison presentation and one isolated browser-to-database proof lane for both `zh-CN` and `en`.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, Playwright, Python 3.12, FastAPI, PostgreSQL 18, Docker Compose, existing Night Voyager BFF and proof scripts.

**Plan status:** Proposed; implementation has not started.

## Global Constraints

- Base must contain merged PR 2 and migration head `0012`.
- Happy-path fact is exactly `student.preferred_countries`.
- Happy-path value changes from `[australia,japan,malaysia]` to `[australia,japan]`.
- Budget decrease is a blocked negative proof, not the primary public journey.
- Reuse existing HTTP business mutations; do not create a second candidate, task, review, or decision API.
- Browser/session state is recovery metadata only; server and PostgreSQL projections remain authority.
- Old PlanningRun and AdvisorReview remain visible only as bounded audit/comparison history.
- Only the current revision, run, review, and brief may reach family decision.
- All public copy is localized in `zh-CN` and `en`; no raw UUID, SQL state, debug JSON, private path, or internal receipt is shown.
- One EventSource at a time; exact monotonic cursor; old-task events cannot advance the new revision.
- Required CI remains offline and provider-free.
- No provider, credential, DRA live acceptance, dependency, lockfile, Dockerfile, or Compose image-policy change.
- Published `v0.1.0` through `v0.1.3` artifacts remain immutable.
- Every task uses RED before implementation, targeted GREEN after implementation, and a semantic local commit.
- If implementation needs a file outside the exact task lists or changes an approved contract, stop for authority review instead of silently expanding scope.

## Execution Preflight and Commit Protocol

Before Task 1, bind the authority-supplied merged PR 2 base and fail closed:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
: "${EXPECTED_BASE_SHA:?authority-approved merged PR 2 SHA required}"
test "$(git rev-parse HEAD)" = "$EXPECTED_BASE_SHA"
make doctor MODE=dev
uv sync --locked
npm --prefix web ci
test "$(uv run alembic heads | awk '{print $1}')" = "0012"
```

Record `EXPECTED_BASE_SHA` as `BASE_SHA`. Any dirty tree, base drift,
migration-head mismatch, or dependency-install failure stops before RED.

Before every task commit, run `git diff --check`, review the exact task paths,
stage only the listed paths, then run `git diff --cached --name-only`,
`git diff --cached --check`, and `git diff --cached`. After the final commit,
review `BASE_SHA..HEAD` and require a clean worktree. A RED run is valid only
when the intended assertion fails after successful collection; zero selection,
collection errors, and environment failures are stop conditions.

Before and after every Docker-backed gate, run the default
`make doctor MODE=dev` and record:

```bash
docker compose ls --all --format json
docker ps -a --no-trunc --format json
docker image ls --digests --no-trunc --format json
docker buildx du --format json
docker network ls --no-trunc --format json
docker volume ls --format json
```

Use one inline `COMPOSE_PROJECT_NAME` on every project-scoped command; do not
export it. Teardown with
`docker compose down --volumes --remove-orphans --rmi local`, verify the exact
project has no container, network, volume, or local image residue, then
separately verify the default Compose inventory. Preserve
`night-voyager_postgres-data`, shared images, and shared BuildKit cache.

---

### Task 1: Freeze the revision proof seed and database verifier

**Files:**
- Modify: `scripts/seed_demo.py`
- Modify: `scripts/run_db_tests.sh`
- Create: `scripts/verify_planning_revision_flow.py`
- Modify: `tests/integration/connected_demo/test_postgres_read_models.py`
- Modify: `tests/integration/connected_demo/test_http_read_models.py`
- Create: `tests/integration/connected_demo/test_planning_revision_flow.py`
- Modify: `tests/architecture/test_m5_contract.py`

**Interfaces:**
- Consumes: `AdvisorLedgerV2`, `DemoPhaseV2`, and
  `PlanningRevisionComparisonV1` from PR 2.
- Verifies: every closed revision phase required by the web client.
- Produces: deterministic seed identities and a read-only database verifier.
- Consumes: explicit `contract_version=2` backend reads while the existing
  route defaults remain V1.

- [ ] **Step 1: Add RED phase and projection tests**

Consume the exact `DemoPhaseV2` union from PR 2 and add journey-level
PostgreSQL/HTTP tests for every value. Do not redefine or alias the phase
contract in PR 3.

Add tests that reject:

- comparison missing from successor phases;
- comparison present before a successor exists;
- review inputs present for `revision_blocked`;
- old task selected for current revision;
- old brief projected as current;
- student role reading advisor-only risk inputs.

Extend the existing closed database command with one exact PR 3 suite:

```text
scripts/run_db_tests.sh planning-revision journey
```

The inside suite must use
`PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database`
for exactly
`tests/integration/connected_demo/test_postgres_read_models.py`,
`tests/integration/connected_demo/test_http_read_models.py`, and
`tests/integration/connected_demo/test_planning_revision_flow.py`. Unknown or
missing submodes continue to exit `2` before Docker mutation; the command must
not fall through to the full database suite.

- [ ] **Step 2: Run backend projection RED**

Run:

```bash
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-backend-red-$$" \
  scripts/run_db_tests.sh planning-revision journey
```

Expected: successful collection followed by missing seed, verifier, or
journey-level projection assertion failures. Zero selected tests, collection
errors, and Docker/environment failures are not valid RED evidence.

- [ ] **Step 3: Add deterministic seed and database verifier**

Extend `seed_demo.py` with stable actors and session identities for:

- advisor;
- student;
- parent;
- one preferred-country happy-path Case with revision 1 and initial facts;
- one isolated budget-counterfactual Case with revision 1 and initial facts;
- one collaboration thread per Case;
- no pre-created revision request, successor task, review, or family decision.

`verify_planning_revision_flow.py` must read the browser proof file and assert:

```python
assert case.current_revision == 2
assert revision_2.superseded_planning_run_id == run_1.id
assert task_2.predecessor_planning_run_id == run_1.id
assert run_2.supersedes_run_id == run_1.id
assert run_1.is_current is False
assert run_2.is_current is True
assert count_new_reviews == 2
assert count_family_decisions == 1
assert count_decision_receipts == 1
assert count_timeline_plans == 1
```

It must also compare the browser-recorded bounded identities with the database
rows and reject duplicates. For the budget Case it must prove one
request-revision review, two retained PlanningRuns, a blocked current successor,
one exact predecessor/successor chain, zero approval review, and zero
DecisionBrief, FamilyDecision, DecisionReceipt, and TimelinePlan rows.

- [ ] **Step 4: Run backend GREEN**

Run:

```bash
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-backend-green-$$" \
  scripts/run_db_tests.sh planning-revision journey
uv run pytest -q tests/architecture/test_m5_contract.py
```

Expected: all initial, revision, blocked, family, and plan-ready projections pass.

- [ ] **Step 5: Commit the proof seed and verifier**

```bash
git add \
  scripts/seed_demo.py \
  scripts/run_db_tests.sh \
  scripts/verify_planning_revision_flow.py \
  tests/integration/connected_demo/test_postgres_read_models.py \
  tests/integration/connected_demo/test_http_read_models.py \
  tests/integration/connected_demo/test_planning_revision_flow.py \
  tests/architecture/test_m5_contract.py
git commit -m "test: seed the planning revision journey"
```

### Task 2: Version the web contracts, recovery envelope, and reducer

**Files:**
- Modify: `web/app/api/demo/cases/[caseId]/advisor-ledger/route.ts`
- Modify: `web/app/api/demo/cases/[caseId]/current-decision-brief/route.ts`
- Create: `web/app/api/demo/cases/[caseId]/journey-status/route.ts`
- Modify: `web/lib/connected-demo/contracts.ts`
- Modify: `web/lib/connected-demo/api.ts`
- Modify: `web/lib/connected-demo/reducer.ts`
- Modify: `web/lib/connected-demo/session-storage.ts`
- Modify: `web/lib/connected-demo/use-connected-demo.ts`
- Modify: `web/lib/collaboration-demo/api.ts`
- Create: `web/lib/connected-demo/revision.ts`
- Modify: `web/tests/unit/connected-demo-api.test.ts`
- Modify: `web/tests/unit/connected-demo-reducer.test.ts`
- Modify: `web/tests/unit/connected-demo-recovery.test.tsx`
- Modify: `web/tests/unit/connected-demo-test-data.ts`
- Modify: `web/tests/unit/collaboration-api.test.ts`

**Interfaces:**
- Consumes: backend `AdvisorLedgerV2`, versioned current brief, and
  `ConnectedJourneyStatusV1`.
- Produces: strict TypeScript `PlanningRevisionComparison` with preferred-country
  and family-budget fact-delta variants.
- Produces: `AdvisorFamilyJourneyEnvelopeV3`.
- Produces: revision-aware reducer events and hook actions.
- Reuses: existing collaboration proposal/verification and connected review/task/decision APIs.
- Preserves: browser storage as a hint only; durable journey status selects the
  role-safe detail read after load, mutation, or lost acknowledgement.

- [ ] **Step 1: Add TypeScript contract RED tests**

Add exact parser counterfactuals:

```typescript
it.each([
  ["missing comparison", () => {
    const value = ledger("revision_review_required");
    delete (value as Record<string, unknown>).comparison;
    return value;
  }],
  ["unknown country delta", () => ({
    ...ledger("revision_review_required"),
    comparison: {
      ...comparison(),
      countries: [{ ...comparison().countries[0], delta: "invented" }],
    },
  })],
  ["blocked with review inputs", () => ({
    ...ledger("revision_blocked"),
    review_inputs: reviewInputs(),
  })],
])("rejects %s", (_name, make) => {
  expect(() => parseLedger(make())).toThrow("invalid response");
});
```

Add recovery tests for malformed v2/v3 envelopes and stale task/cursor
identities. Require the BFF advisor-ledger and current-brief routes to request
exact upstream `contract_version=2`; require the new journey-status BFF to
forward only the closed read route. Unknown or missing V2 schemas fail closed.

- [ ] **Step 2: Run frontend RED**

Run:

```bash
npm --prefix web run test -- \
  connected-demo-api.test.ts \
  connected-demo-reducer.test.ts \
  connected-demo-recovery.test.tsx
```

Expected: failures for missing v2 ledger, revision contracts, and v3 recovery.

- [ ] **Step 3: Implement strict web comparison parsing**

Define:

```typescript
export interface PlanningRevisionCountryComparison {
  country: Country;
  delta: "added" | "removed" | "changed" | "unchanged";
  previous_outcome: RouteOutcome | null;
  previous_reason_code: string | null;
  current_outcome: RouteOutcome | null;
  current_reason_code: string | null;
}

export interface PlanningRevisionComparison {
  schema: "night-voyager.planning-revision-comparison.v1";
  case_id: string;
  previous_revision: number;
  current_revision: number;
  previous_planning_run_id: string;
  current_planning_run_id: string;
  changed_fact:
    | {
        fact_key: "student.preferred_countries";
        previous_value: Country[];
        current_value: Country[];
      }
    | {
        fact_key: "family.budget";
        previous_value: BudgetValue;
        current_value: BudgetValue;
      };
  countries: PlanningRevisionCountryComparison[];
  current_run_state: "review_required" | "blocked";
  approval_eligible: boolean;
}
```

Use exact-key parsing for every nested object.

Version `AdvisorReviewBody` as a closed discriminated union:

- `request_revision` requires empty eligibility/risk arrays and allows only
  bounded reviewer notes;
- `approve_for_consultation` retains the existing eligible-route and risk
  contract.

Extend the session parser and `ConnectedDemoApi.mint` to the existing identity
role union `advisor | student | parent`. Extend collaboration read overloads so
student receives the same participant-safe candidate/fact projection as parent.

- [ ] **Step 4: Add recovery schema v3**

`AdvisorFamilyJourneyEnvelopeV3` includes:

- `schema_version: 3`;
- role `advisor | student | parent`;
- exact case ID;
- current revision;
- current task ID or null;
- predecessor run ID or null;
- current run ID or null;
- cursor;
- one exact snake-case `DemoPhaseV2` value from the backend contract;
- mutation records for request revision, fact proposal, fact confirmation,
  create task, new review, and family decision.

Older unsupported envelopes are removed fail closed. Do not perform a lossy
upgrade from v2.

- [ ] **Step 5: Extend reducer and hook actions**

Add explicit actions:

```typescript
requestRevision(): Promise<void>
rotateToStudent(caseId: string): Promise<void>
submitPreferredCountries(): Promise<void>
rotateToAdvisor(caseId: string): Promise<void>
confirmPreferredCountries(): Promise<void>
createRevisionTask(): Promise<void>
approveRevision(): Promise<void>
rotateToParent(caseId: string): Promise<void>
decide(): Promise<void>
```

The action composition is exact:

1. `requestRevision` calls the existing advisor-review endpoint with
   `action="request_revision"` and no eligibility/risk grant.
2. `rotateToStudent` revokes the advisor session, mints the assigned-student
   session, reads `ConnectedJourneyStatusV1`, and reloads the participant-safe
   collaboration thread.
3. `submitPreferredCountries` appends one bounded student message and proposes
   the exact `student.preferred_countries=["australia","japan"]` candidate from
   that message.
4. `rotateToAdvisor` revokes the student session and mints the assigned advisor.
5. `confirmPreferredCountries` loads the exact pending candidate and confirms it
   against the current Case revision.
6. `createRevisionTask` and `approveRevision` use the existing task and
   advisor-review endpoints.
7. `rotateToParent` revokes the advisor session, mints the assigned-parent
   session, reads `ConnectedJourneyStatusV1`, and reloads the family-safe
   current brief.
8. The existing family-decision endpoint completes `decide`.

The hook must read `ConnectedJourneyStatusV1` after every role rotation,
mutation, reload, and lost acknowledgement, then load only the matching
role-safe detail projection. Session storage may select an initial recovery
attempt but cannot decide phase, active role, revision, or authority. The hook
must never calculate comparison, candidate identity, predecessor, current
revision, or renewed authorization locally. A status/detail mismatch fails
closed.

Freeze this exact visible-state contract in reducer/hook tests:

| Phase | Role | Visible authoritative view | Actions |
| --- | --- | --- | --- |
| `review_required` | advisor | initial reviewable plan | Primary approve; secondary request revision with an inline consequence summary. |
| `revision_requested` | student | server-projected current preference and closed target | Primary submit change proposal. |
| `revision_fact_pending` | advisor | read-only current/proposed fact delta | Primary confirm proposal. |
| `replan_required` | advisor | confirmed change and retained predecessor notice | Primary create revised task. |
| `revision_task_active` | advisor | retained ledger and task progress | No mutation action. |
| `revision_review_required` | advisor | changed fact and old/new comparison | Primary approve revised plan; no second revision request. |
| `revision_blocked` | advisor | changed fact, comparison, and deterministic reason | No approval or family-decision action. |
| `family_review` | parent | current brief, current revision, and renewed-review context | Primary confirm current family decision. |
| `plan_ready` | parent | current receipt and timeline | No mutation action. |
| `terminal_task_failure` | advisor | retained ledger and bounded failure | No business mutation action. |

The request-revision action remains secondary while the initial approval is
primary. Before the request is submitted, show that the prior plan remains
retained, no fact changes yet, and replanning plus renewed advisor approval will
be required. Student-facing copy says “submit change proposal”; it never says
the student confirms a fact.

- [ ] **Step 6: Run contract/recovery GREEN**

Run:

```bash
npm --prefix web run test -- \
  connected-demo-api.test.ts \
  connected-demo-reducer.test.ts \
  connected-demo-recovery.test.tsx \
  collaboration-api.test.ts
npm --prefix web run typecheck
```

Expected: all parsers, state transitions, recovery, and types pass.

- [ ] **Step 7: Commit web authority contracts**

```bash
git add -- \
  'web/app/api/demo/cases/[caseId]/advisor-ledger/route.ts' \
  'web/app/api/demo/cases/[caseId]/current-decision-brief/route.ts' \
  'web/app/api/demo/cases/[caseId]/journey-status/route.ts' \
  web/lib/connected-demo/contracts.ts \
  web/lib/connected-demo/api.ts \
  web/lib/connected-demo/reducer.ts \
  web/lib/connected-demo/session-storage.ts \
  web/lib/connected-demo/use-connected-demo.ts \
  web/lib/collaboration-demo/api.ts \
  web/lib/connected-demo/revision.ts \
  web/tests/unit/connected-demo-api.test.ts \
  web/tests/unit/connected-demo-reducer.test.ts \
  web/tests/unit/connected-demo-recovery.test.tsx \
  web/tests/unit/connected-demo-test-data.ts \
  web/tests/unit/collaboration-api.test.ts
git commit -m "feat: add revision-aware demo recovery"
```

### Task 3: Build the bilingual revision comparison experience

**Files:**
- Modify: `web/components/connected-demo/ConnectedDemo.tsx`
- Modify: `web/components/connected-demo/AdvisorLedger.tsx`
- Modify: `web/components/connected-demo/FamilyDecisionBrief.tsx`
- Create: `web/components/connected-demo/PlanningRevisionComparison.tsx`
- Create: `web/components/connected-demo/RevisionFactEditor.tsx`
- Modify: `web/components/connected-demo/RecoveryNotice.tsx`
- Modify: `web/lib/presentation/catalog.ts`
- Modify: `web/lib/presentation/codes.ts`
- Modify: `web/app/styles.css`
- Modify: `web/tests/unit/connected-demo-ui.test.tsx`
- Modify: `web/tests/unit/connected-demo-presentation.test.ts`
- Modify: `web/tests/unit/presentation-catalog.test.ts`
- Modify: `web/tests/unit/presentation-codes.test.ts`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`

**Interfaces:**
- Consumes: hook actions and `PlanningRevisionComparison`.
- Produces: accessible bilingual advisor/student/family journey.
- Does not produce business facts or derive comparison fields.

- [ ] **Step 1: Add UI RED tests**

Require Chinese and English copy for:

- request revision;
- student preference edit;
- retained previous plan;
- current revised plan;
- removed route;
- renewed advisor approval;
- blocked revision;
- continue to family decision.
- the family-safe current revision and renewed advisor authorization.

Add accessibility assertions:

```typescript
expect(screen.getByRole("heading", { name: copy("revisionComparisonTitle") })).toBeVisible();
expect(screen.getByRole("button", { name: copy("requestRevisionAction") })).toBeEnabled();
expect(screen.queryByText(UUID_PATTERN)).not.toBeInTheDocument();
```

Require removed Malaysia to be visually subordinate but readable.
Require every phase/role/action row from Task 2, including the absence of
approval/family actions for blocked and terminal phases. Require Chinese output
to contain no hard-coded English overline, role, authority, revision, or
history/current labels; require English output to contain no Chinese fallback
for the same keys or any raw phase/code.

- [ ] **Step 2: Run UI RED**

Run:

```bash
npm --prefix web run test -- \
  connected-demo-ui.test.tsx \
  connected-demo-presentation.test.ts \
  presentation-catalog.test.ts \
  presentation-codes.test.ts \
  presentation-accessibility.test.tsx
```

Expected: missing components, copy, and states fail.

- [ ] **Step 3: Implement `PlanningRevisionComparison`**

Render:

- one changed-fact summary;
- a localized preferred-country delta or family-budget delta, selected only by
  the closed server `fact_key`;
- previous/current revision labels;
- one row per canonical country;
- localized delta and outcome/reason;
- no route UUID;
- no generated prose.

Freeze the page order as:

1. active role and authority;
2. changed-fact summary;
3. old/new comparison;
4. current-plan approval action;
5. Evidence and bounded technical history.

At 1440px, render a semantic table with
`country | previous result | current result | change`. At 390px, present the
same data as one country-keyed `<dl>` at a time with a
`fieldset`/`legend` switcher; retain a visually hidden semantic table for
assistive technology and do not introduce horizontal scrolling. The current
result is primary and the predecessor is marked “history, for comparison
only”. `removed` uses localized “removed from the revised plan” in the current
column; `added` uses “not present in the previous plan” in the previous column.
These valid nulls must not display the unavailable fallback.

Use the current warm-paper visual system. Keep the comparison readable at
320px, 390px, 768px, and 1440px. Delta meaning must be visible in text and not
color alone.

- [ ] **Step 4: Implement the controlled fact editor and actions**

`RevisionFactEditor` reads the current value from the role-safe confirmed-fact
projection and presents only the approved synthetic target:

```typescript
const REVISED: Country[] = ["australia", "japan"];
```

The component is a `fieldset` with a descriptive `legend`. The student submits
a visible change proposal; the student does not confirm a fact. Submission is
disabled with a localized fail-closed reason when the current projection is
missing, malformed, unsorted, duplicated, at the wrong Case revision, or not
the expected synthetic baseline. No free-form country JSON or arbitrary fact
key is accepted.

The budget counterfactual has no primary editor or hidden production control.
Its browser proof uses the real BFF/session/collaboration APIs against the
dedicated synthetic Case, then verifies the same comparison component and
blocked-state presentation.

`ConnectedDemo` implements the Task 2 phase/role/action table. Every actionable
phase has exactly one primary action; `review_required` additionally has the
one secondary revision request. Busy and recovery states disable mutation
without hiding the authoritative ledger. `revision_review_required` has no
second revision request. `revision_blocked` and `terminal_task_failure` hide or
disable all business mutation actions while retaining comparison or ledger
context and a non-business recovery/navigation exit.

`FamilyDecisionBrief` renders only the server-owned current Case revision and
the exact family-safe advisor-authorization marker. It must not infer “revised”
or “re-reviewed” from browser storage, reload success, or comparison presence.

- [ ] **Step 5: Add localized copy and visual states**

Add exact keys to both catalogs and closed code maps. Use descriptive human copy,
not internal state names. Ensure:

- high-contrast primary action;
- no decorative black boxes around route copy;
- reduced-motion support;
- focus moves to the next phase heading only after a user-triggered full-phase
  transition;
- SSE, reconnect, reload, and stale-event notices use `aria-live="polite"` and
  never move focus;
- only blocking errors use `role="alert"`;
- all interactive targets are at least 44 by 44 CSS pixels;
- removed Malaysia remains legible but muted;
- current plan receives the strongest hierarchy.

All overlines, roles, authority explanations, revision labels,
history/current labels, phases, busy copy, disabled reasons, and recovery text
must come from the bilingual catalog or closed code maps.

Add a closed asynchronous presentation table to unit tests:

| State | Retained view | Mutations | Announcement/recovery |
| --- | --- | --- | --- |
| Initial load | skeleton only | disabled | polite loading status |
| Mutation pending | last authoritative ledger | all disabled | polite busy status |
| SSE connected/reconnecting | current ledger | phase-derived | polite, no focus move |
| Reload recovered | new authoritative ledger | phase-derived | polite, no focus move |
| Lost-ack reconciliation | last ledger | disabled | polite reconciliation |
| Stale task event ignored | current ledger unchanged | unchanged | no phase/focus change |
| `revision_blocked` | changed fact and comparison | no business action | reason plus navigation exit |
| `terminal_task_failure` | ledger and failure | no business action | recovery/navigation exit |
| Blocking `recoverable_error` | bounded safe context | disabled | alert plus exact reconnect |

- [ ] **Step 6: Run UI GREEN and production build**

Run:

```bash
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
```

Expected: lint, types, all unit tests, accessibility contracts, and production build pass.

- [ ] **Step 7: Commit the presentation**

```bash
git add \
  web/components/connected-demo/ConnectedDemo.tsx \
  web/components/connected-demo/AdvisorLedger.tsx \
  web/components/connected-demo/FamilyDecisionBrief.tsx \
  web/components/connected-demo/PlanningRevisionComparison.tsx \
  web/components/connected-demo/RevisionFactEditor.tsx \
  web/components/connected-demo/RecoveryNotice.tsx \
  web/lib/presentation/catalog.ts \
  web/lib/presentation/codes.ts \
  web/app/styles.css \
  web/tests/unit/connected-demo-ui.test.tsx \
  web/tests/unit/connected-demo-presentation.test.ts \
  web/tests/unit/presentation-catalog.test.ts \
  web/tests/unit/presentation-codes.test.ts \
  web/tests/unit/presentation-accessibility.test.tsx
git commit -m "feat: present the planning revision journey"
```

### Task 4: Prove the happy path, blocked path, reload, SSE, and restart

**Files:**
- Create: `web/e2e/planning-revision.spec.ts`
- Modify: `web/playwright.compose.config.ts`
- Modify: `scripts/verify_compose.sh`
- Modify: `scripts/verify_planning_revision_flow.py`
- Modify: `tests/architecture/test_compose_contract.py`
- Modify: `tests/architecture/test_fact_to_plan_contract.py`
- Modify: `tests/integration/connected_demo/test_planning_revision_flow.py`
- Create: `docs/assets/night-voyager-planning-revision.png`

**Interfaces:**
- Consumes: real BFF, FastAPI, PostgreSQL, worker, SSE, and browser UI.
- Produces: one bounded proof file per locale and a database verifier result.
- Produces: current synthetic screenshot evidence.

- [ ] **Step 1: Add Compose orchestration RED tests**

Require:

- exact task-owned proof and worker-ready files;
- host pre-creation and `0666` only for those files;
- stale-symlink reset;
- exact sentinel;
- a dedicated `UPDATE_PLANNING_REVISION_SCREENSHOT=1` variable consumed only
  by `planning-revision.spec.ts`;
- `UPDATE_PORTFOLIO_SCREENSHOTS` cannot update the revision asset and the new
  variable cannot update the three existing public proof PNGs;
- one `zh-CN` and one `en` lane;
- one exact task project with fresh seed and isolated volume reset per locale;
- database verifier after browser success;
- trap cleanup;
- no proxy or source override.
- default full-proof mode plus one closed `planning-revision` focused mode;
- `planning-revision.spec.ts` in `playwright.compose.config.ts`.

Run:

```bash
uv run pytest -q \
  tests/architecture/test_compose_contract.py \
  tests/architecture/test_fact_to_plan_contract.py \
  -k "planning_revision"
```

Expected: failures because the revision lane and files do not exist.

- [ ] **Step 2: Write the Playwright happy path**

The browser test must:

1. connect as advisor;
2. record revision 1/run 1;
3. request revision through a committed-response-lost interception:
   server commit succeeds, the browser response is aborted, and retry reuses
   the same idempotency key before authoritative status reload;
4. rotate to student;
5. submit Australia/Japan;
6. rotate to advisor;
7. confirm the fact through the same committed-response-lost pattern and
   reconcile one exact revision;
8. explicitly create the revised task through the same pattern and reconcile
   one exact task;
9. wait for initial SSE request and write the exact worker-ready sentinel;
10. reload during active execution;
11. verify any reconnect uses the stored cursor;
12. wait for the Compose controller to restart the worker after the durable
    revised-task sentinel;
13. recover the same task after lease reclaim and wait for revision comparison;
14. approve the new run;
15. rotate to parent;
16. make the family decision;
17. verify receipt and timeline;
18. write bounded proof JSON.

At each boundary, assert the exact Task 2 phase/role/action row. In particular:

- initial approval remains primary while request revision is secondary;
- the student sees “submit change proposal”, never fact-confirmation authority;
- the advisor sees the read-only proposal before confirmation;
- active planning has no mutation action;
- revised review has one approval action and no second revision request;
- the parent sees the server-owned current revision and renewed-review context.

Reload/SSE checks also prove that user-triggered phase changes may move focus,
while reconnect, reload hydration, and stale-event rejection do not.
Each lost-ack boundary must prove one idempotency key, one authority row, and
one server-owned status transition; no browser-generated phase is accepted.

Assert:

```typescript
expect(comparison.changed_fact.previous_value).toEqual([
  "australia", "japan", "malaysia",
]);
expect(comparison.changed_fact.current_value).toEqual([
  "australia", "japan",
]);
expect(country("malaysia").delta).toBe("removed");
```

- [ ] **Step 3: Add the blocked budget browser counterfactual**

The same Playwright file uses the dedicated second Case. Through real
same-origin BFF calls and role-scoped cookies, not a hidden UI control, it:

- valid request revision;
- rotates to parent;
- appends a bounded message and proposes the closed lower family budget;
- rotates to advisor and confirms that exact candidate;
- exact lineage and successor task;
- deterministic blocked successor;
- renders the localized budget delta and blocked comparison in the real UI;
- proves the approval action is absent and a direct approval request is rejected;
- proves family decision/receipt/timeline counts are zero in the database verifier.

It does not share idempotency keys or rows with the public happy path.

- [ ] **Step 4: Add the isolated Compose lane**

Extend `verify_compose.sh` with one function that:

- reuses the one exported task project and resets its volume before each locale;
- seeds a fresh database;
- starts API, Web, and worker;
- pauses worker before browser start;
- runs `planning-revision.spec.ts`;
- unpauses only after exact SSE sentinel;
- after the revised task reaches its durable worker-ready sentinel, restarts
  the worker container and requires lease-expiry/reclaim of the same task;
- runs `verify_planning_revision_flow.py`;
- executes `make down` under trap;
- deletes only task-owned ephemeral files and images.
- pre-creates the exact ephemeral review-capture files under the ignored
  `tmp/planning-revision-review/` root and mounts only that task-owned directory
  into the browser container;
- forwards `UPDATE_PORTFOLIO_SCREENSHOTS`,
  `UPDATE_PLANNING_REVISION_SCREENSHOT`, and the closed review-capture root
  through explicit `docker compose run -e` values; the script maps the
  host-relative root to `/workspace/tmp/planning-revision-review` in the
  browser container, and no screenshot flag is inferred from the host
  environment.

Add a closed positional mode:

```text
scripts/verify_compose.sh planning-revision
```

It performs the common build/health setup plus only the two revision locales.
No argument retains the current complete proof and includes the same revision
function. Unknown arguments exit non-zero before Docker mutation.
The operations documentation must expose this focused mode, the two screenshot
flags, and the ignored review-capture root.

- [ ] **Step 5: Run focused browser GREEN**

Run:

```bash
UPDATE_PORTFOLIO_SCREENSHOTS=0 \
UPDATE_PLANNING_REVISION_SCREENSHOT=0 \
PLANNING_REVISION_REVIEW_DIR=tmp/planning-revision-review \
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-focused-$$" \
  scripts/verify_compose.sh planning-revision
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-focused-$$" \
  docker compose --profile browser-proof \
  down --volumes --remove-orphans --rmi local
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-focused-$$" \
  docker compose ps --all
docker compose ps --all
```

Expected: both locales, happy/blocked browser assertions, and the database
verifier pass with exact lineage. The exact task project and default Compose
inventories are empty after teardown.
The verifier must assert exact counts for request reviews, fact revisions,
tasks, executions, predecessor/successor runs, events, renewed review, brief,
decision, receipt, and timeline after lost acknowledgements and worker restart.

- [ ] **Step 6: Generate and inspect the screenshot**

Generate the committed Chinese 1440px screenshot from the real Compose page in
this task only:

```bash
UPDATE_PORTFOLIO_SCREENSHOTS=0 \
UPDATE_PLANNING_REVISION_SCREENSHOT=1 \
PLANNING_REVISION_REVIEW_DIR=tmp/planning-revision-review \
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-screenshot-$$" \
  scripts/verify_compose.sh planning-revision
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-screenshot-$$" \
  docker compose --profile browser-proof \
  down --volumes --remove-orphans --rmi local
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-screenshot-$$" \
  docker compose ps --all
```

Also generate ephemeral review captures for English 1440px and both languages
at 390px under `tmp/planning-revision-review/`, using closed filenames that
include locale, viewport, and `happy` or `blocked` state. Preserve those
Playwright artifacts only for the review handoff; record each file's dimensions,
bytes, and SHA-256. Only the approved Chinese 1440px asset is committed.

Inspect every capture for:

- text clarity;
- previous/current hierarchy;
- Malaysia removed state;
- no clipping or horizontal overflow;
- exact primary/secondary action hierarchy;
- visible text labels for every delta;
- visible focus and at least 44px action targets;
- long English copy and 320/768px regression coverage;
- no UUID, debug JSON, private path, browser chrome, or error;
- no regression to the hero and family decision sections.

Before and after generation, verify the existing
`night-voyager-portfolio-entry.png`, `m5-advisor-ledger.png`, and
`m5-family-receipt-timeline.png` SHA-256 values are byte-identical. The
architecture regression must reject either screenshot environment variable
changing the other lane's assets.

- [ ] **Step 7: Commit proof and screenshot**

```bash
git add \
  web/e2e/planning-revision.spec.ts \
  web/playwright.compose.config.ts \
  scripts/verify_compose.sh \
  scripts/verify_planning_revision_flow.py \
  tests/architecture/test_compose_contract.py \
  tests/architecture/test_fact_to_plan_contract.py \
  tests/integration/connected_demo/test_planning_revision_flow.py \
  docs/assets/night-voyager-planning-revision.png
git commit -m "test: prove the planning revision journey"
```

### Task 5: Publish current documentation and run final stage gates

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DESIGN.md`
- Modify: `docs/README.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/projection-matrix.md`
- Modify: `docs/design/route-map.md`
- Modify: `docs/design/state-and-interaction-matrix.md`
- Modify: `docs/operations/collaboration-authority.md`
- Modify: `docs/operations/collaboration-walkthrough.md`
- Modify: `docs/operations/connected-demo.md`
- Modify: `docs/operations/worker-and-sse.md`
- Modify: `docs/reference/agent-tasks-and-events.md`
- Modify: `docs/reference/collaboration-and-confirmed-facts.md`
- Modify: `docs/reference/http-api-v1.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md`
- Modify: `docs/superpowers/plans/2026-07-27-planning-revision-journey-pr-3-implementation-plan.md`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `scripts/verify_release.py`

**Interfaces:**
- Consumes: completed three-PR provider-free stage.
- Produces: current public documentation and release-candidate evidence.
- Does not authorize version bump, tag, GitHub Release, deploy, or provider run.

- [ ] **Step 1: Add documentation RED assertions**

Require current docs to describe:

```text
request revision
student preferred-country change
retained predecessor
successor PlanningRun
deterministic old/new comparison
fresh advisor authorization
only current family decision
blocked budget counterfactual
provider-free DRA strict commit pin
live acceptance still incomplete
```

- [ ] **Step 2: Run documentation RED**

Run:

```bash
uv run pytest -q tests/architecture/test_documentation_governance.py
```

Expected: missing current product and verification text fails.

- [ ] **Step 3: Update current documentation**

Synchronize root discovery, architecture, state/projection matrices, operations,
reference, screenshot links, spec, plans, and status index.

State accurately:

- PR 1/2/3 implemented provider-free;
- DRA live acceptance incomplete;
- no third provider attempt;
- the prior 25- and 83-Evidence live attempts remain unchanged historical
  failures with zero cited rows;
- the revision journey is controlled/provider-free evidence, not strict live
  acceptance;
- post-v0.1.3 unreleased;
- expected separate release decision, not automatic publication.

Add release-verifier assertions for each statement above so a future release
cannot silently upgrade the claim.
Before the final documentation commit, run one targeted `document-release`
audit over README/docs-index discoverability, reference, operations/how-to,
design explanation, tutorial need, screenshot links, exact commands, and
release/non-claim boundaries. Record the result in the PR
`Documentation impact`. Include the focused `planning-revision` Compose mode,
both screenshot flags, and the review-capture ownership/cleanup contract.

- [ ] **Step 4: Run all non-Compose gates**

The task-level commands above are focused diagnostics. This block is the
authoritative final non-Compose evidence for PR 3:

```bash
uv lock --check
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
uv run ruff check .
uv run pyright
make db-check
make collaboration-db-check SUITE=authority
make dra-check
make check
make proof
uv run python scripts/verify_release.py --tree-mode development
git diff --check "$(git merge-base HEAD origin/main)"..HEAD
```

Expected: all commands exit zero.

- [ ] **Step 5: Run one normal full Compose proof**

After formal host and Docker VM preflight:

```bash
UPDATE_PORTFOLIO_SCREENSHOTS=0 \
UPDATE_PLANNING_REVISION_SCREENSHOT=0 \
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-$$" \
  make compose-proof
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-$$" \
  docker compose --profile browser-proof \
  down --volumes --remove-orphans --rmi local
COMPOSE_PROJECT_NAME="night-voyager-revision-pr-3-$$" docker compose ps --all
docker compose ps --all
git diff --exit-code -- \
  docs/assets/night-voyager-planning-revision.png \
  docs/assets/night-voyager-portfolio-entry.png \
  docs/assets/m5-advisor-ledger.png \
  docs/assets/m5-family-receipt-timeline.png
```

Expected:

- existing reconnect, collaboration, DRA, fact-to-plan, and bilingual flows pass;
- new bilingual revision journey passes;
- browser-to-database lineage verifier passes;
- no screenshot asset changes during this final verification; Task 4 already
  committed `docs/assets/night-voyager-planning-revision.png`, and the three
  existing public proof PNGs remain byte-identical;
- exact project resources are removed;
- retained shared volume/images/cache remain.

Record host and Docker VM availability plus projects, containers, images,
BuildKit cache, networks, and volumes before and after. Confirm the default
Compose inventory is empty separately; do not use host free space as a
substitute for Docker VM evidence.

- [ ] **Step 6: Run final hygiene and immutable-history checks**

Verify:

- exact changed-file scope;
- `git diff --check`;
- no private paths, coordination labels, credentials, debug content, or real user data;
- v0.1.0-v0.1.3 release and verification files unchanged;
- migrations `0001`-`0011` unchanged;
- dependency and lockfile surfaces unchanged;
- no provider, tag, release, or deploy action.

- [ ] **Step 7: Commit documentation and stage closure**

```bash
git add \
  README.md README_CN.md DESIGN.md docs/README.md \
  docs/design/demo-storyboard.md \
  docs/design/projection-matrix.md \
  docs/design/route-map.md \
  docs/design/state-and-interaction-matrix.md \
  docs/operations/collaboration-authority.md \
  docs/operations/collaboration-walkthrough.md \
  docs/operations/connected-demo.md \
  docs/operations/worker-and-sse.md \
  docs/reference/agent-tasks-and-events.md \
  docs/reference/collaboration-and-confirmed-facts.md \
  docs/reference/http-api-v1.md \
  docs/superpowers/README.md \
  docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md \
  docs/superpowers/plans/2026-07-27-planning-revision-journey-pr-3-implementation-plan.md \
  tests/architecture/test_documentation_governance.py \
  scripts/verify_release.py
git commit -m "docs: publish the planning revision journey"
```

## PR 3 Completion Gate

Stop for authority review with:

- exact merged PR 2 base and migration head;
- exact final HEAD and ordered commits;
- exact changed-file list and diff stat;
- RED/GREEN evidence for backend, web, browser, and blocked scenario, including
  selected/passed/failed counts;
- two Case revisions and exact predecessor/successor database evidence;
- old/new comparison canonical JSON;
- fresh advisor review and current family receipt/timeline;
- reload, SSE, restart, and lost-ack evidence;
- bilingual screenshot and visual inspection;
- complete local gates with selected/passed/failed counts and Docker
  before/after inventory; elapsed time is diagnostic only;
- explicit non-claims for provider, live acceptance, release, and deploy.

Do not push or create a pull request until separate publication authorization.

## Post-PR 3 Release Gate

After PR 3 is reviewed, merged, and exact merge-SHA hosted checks are GREEN:

1. re-read clean local/origin/live main;
2. verify all three PR trees and documentation status;
3. decide separately whether to prepare expected `v0.1.4`;
4. use a dedicated release-prep branch and pull request;
5. run merged-main release, Git-free archive rehearsal, annotated tag, GitHub
   Release, and public archive smoke only under separate authorization.

The release-prep review must keep machine-checked non-claims that:

- there was no third provider attempt;
- strict-profile live acceptance remains incomplete;
- the prior 25/83-uncited attempts remain failed history;
- the revision proof is controlled and provider-free.

Do not create `v0.2.0` from this stage.
