# Customer revision and terminal recovery

This walkthrough uses the controlled local synthetic pilot and deterministic
adapter. The current branch implements migration `0016`; the published v0.1.6
record remains historical migration `0015`. No release or deployment is implied.
See the [acceptance evidence](../evidence/customer-revision-recovery.md),
[HTTP reference](../reference/http-api-v1.md),
[task contract](../reference/agent-tasks-and-events.md) and
[ADR 0015](../decisions/0015-guarded-terminal-task-recovery.md).

## Revise one confirmed fact

Use a fresh, separately named synthetic pilot volume for this unreleased branch.
Initial migration `0016` now seeds complete country and budget lineage for the two
canonical revision Cases. An already-installed earlier `0016` does not gain the
new closed seed helper from `alembic upgrade head`; country-only or evolved Cases
fail exact seed replay checks. No backfill is provided. Preserve existing user
volumes and start a new unused Compose project, then run `make demo`.
Open `/demo/collaboration` for the full intake or `/demo` for the task-owning flow.
The canonical revision proof never operates on real records. Its initial CNY
`program_total` budget is 340000 preferred / 400000 ceiling, elasticity 1000 bps.
Verified participants share safe current facts; only the parent may propose a
budget change. Reading a budget as the student does not grant write authority.

1. The assigned advisor requests revision of the current plan.
2. Choose one editable confirmed fact in the editor. Choices come from the current
   server projection: budget-only starts on budget and still requires explicit
   parent preparation; country-only offers countries; both retain both paths.
   Missing country confirmation is explained and cannot be supplied by reloading.
   Missing, stale or wrong-Case projections offer no edit or role-preparation action.
   A saved submission remains identified, and an unavailable/stale saved fact is
   retained rather than silently changed into another proposal. For countries,
   select a materially different,
   nonempty subset of Australia/Japan/Malaysia and continue as the student.
   For budget, choose **Edit budget as parent** to complete the real session
   handoff and load authoritative current facts before entering preferred and
   maximum CNY amounts. Submit the budget proposal as the parent.
   The current and proposed values remain visible. Invalid, unchanged or stale
   facts cannot authorize a revision.
3. Click the explicit next-role action; revoke/mint runs after that action,
   not merely because the waiting panel appeared. Continue as advisor. Inspect the
   actual pending candidate and enter a
   confirmation reason. Confirmation publishes the next CaseRevision; a draft
   or participant proposal alone cannot change confirmed facts.
4. Create the revised planning task explicitly. Wait for its authorized SSE
   result, inspect the retained predecessor and old/new comparison, and perform
   fresh advisor approval. Previous approval remains historical.
5. Continue as parent. Enter the accepted budget minimum and maximum, acknowledge
   each required trade-off separately, and give final consent. The interval must
   contain the pinned cost and remain within the current hard ceiling. The
   receipt renders the actual accepted values and parent authority.

Only one supported fact changes per revision. Route eligibility, currency,
minor-unit conversion, required trade-offs and current Brief version remain
server-owned. A changed Brief resets stale choices. Lost mutation responses
retain the exact submitted body/key for same-tab reload and explicit replay;
edited intentions cannot reuse an earlier submitted body.

## Recover a qualified failed task

An assigned advisor may see a consent checkbox and **Create a fresh planning
task** only for the server-qualified latest current-revision terminal source.
The exact allowed state/code pairs are `failed` with `transient_unavailable`,
`transport_interrupted` or exhausted `lease_expired`, and `timed_out` with
`deadline_exceeded`.

Select the checkbox and submit once. The new Task preserves source operation,
source-pack and policy, validates the active packaged Skill, follows a fresh SSE
stream and requires fresh advisor review. It does not rewrite the old Task,
events or executions, and cannot inherit an approval. Hard or unknown failures,
cancellation, outdated/result-bearing sources and sources with a successor have
no unchanged-input recovery action. Correcting facts/configuration is a separate
workflow.

Retry sends only `schema_version=1`, `expected_row_version` and
`expected_case_revision` to `POST /api/v1/tasks/{task_id}/retry`. Browser pins
never grant authority. Exact replay returns one successor while current role and
revision still apply; a changed body or another key cannot create a duplicate.
The connected UI remains synthetic-only; governed mixed recovery preserves the
promoted pack through the Task API.

## Reproduce local acceptance

Use an unused, task-owned Compose project and serialize heavy builds. These
commands use fresh disposable volumes and remove only their own project:

```bash
export COMPOSE_PROJECT_NAME=night-voyager-customer-review
sh scripts/run_db_tests.sh
sh scripts/run_db_tests.sh planning-revision all
sh scripts/run_db_tests.sh planning-revision journey
SUITE=authority sh scripts/run_collaboration_db_tests.sh
UPDATE_PLANNING_REVISION_SCREENSHOT=0 sh scripts/verify_compose.sh planning-revision
```

The planning lane builds once and covers health/native flows, API/worker restart,
real predecessor-lock/lease reclaim, bilingual country revision, comparison,
renewed review, explicit family choices and a blocked budget counterfactual.
It retains screenshots under `tmp/planning-revision-review` by default.

For the bounded parent-budget/recovery supplement, build the existing images and
then run the no-build runner:

```bash
docker compose --profile browser-proof build
sh scripts/verify_customer_revision_recovery.sh
```

It uses the canonical synthetic revision Cases in a fresh stack for each locale.
After **Edit budget as parent**, it injects one controlled confirmed-facts read503,
then uses a real same-tab reload to prove parent credentials recover without a
second mint or business writes before the authoritative facts load. Session mint,
revoke, bootstrap, role checks and successful mutations remain real.
The worker is stopped while the bounded acceptance producer invokes the actual
classifier and runtime worker `claim/start/fail` authority. A native timeout
reaches the rendered consent checkbox, real retry POST, new task/SSE, fresh
comparison/review and persisted parent receipt. A real `invalid_schema` producer
and an explicitly controlled unknown-code negative prove no action and POST
denial. Direct terminal row mutation never supplies the success proof.
Review artifacts and source-diagnostic checks remain under
`tmp/customer-revision-recovery-review`; temporary control files contain no
session cookies or CSRF tokens. The runner tears down its own containers, images
and volumes. Starting the worker uses `up --no-deps --no-build -d worker`:
`compose start worker` would restart completed seed dependencies and correctly
fail closed on the now-evolved canonical Case. Screenshots supplement functional assertions and require inspection.

## Environment notes

Verified on 2026-10-02 with the existing locked Python and web dependencies.

A task-owned BuildKit builder can be selected only for these commands with
`BUILDX_BUILDER`; avoid changing the global builder or pruning unrelated cache.
If an installed Docker credential helper stalls even for public images, a
separate task `DOCKER_CONFIG` containing empty `auths` and installed CLI-plugin
paths was verified with a task builder. Do not copy credential configuration,
login or alter global Docker settings to work around it.

Host source-import tests need packaged Skill resource files. An ignored per-file
source overlay may link current source and the authoritative fixture manifests;
verify resolved source paths and hashes. Do not add a product loader fallback or
copy package data into `src`. The real Docker wheel must independently prove
installed resource packaging. On macOS arm64, an existing-lock greenlet platform
marker supplement may be necessary for SQLAlchemy; use the exact locked wheel
hash in an isolated environment, without changing dependency declarations.

The sdist excludes task scratch under `/.superpowers`. Before `uv build`, move
task-generated `web/.next` into that ignored task environment: a generated
standalone tree is a build artifact, not source. Inspect the actual sdist for
scratch, virtual environments, `node_modules` and `.next`, and compare both wheel
Skill manifests byte-for-byte with their authoritative fixtures. This does not
change runtime resource loading or the wheel's declared `force-include` files.

The default Next.js Turbopack host build cannot follow a `node_modules` symlink
outside the web filesystem root. For a task-owned locked dependency directory,
record its link target, temporarily move that same directory to `web/node_modules`,
run `npm --prefix web run build`, and restore the original directory/link with an
exit trap. Do not overwrite an existing directory or change Next.js configuration.
The Docker web build remains an independent check.

Optional external MKE artifact proof requires its separately retained reviewed
candidate/environment; a missing artifact is not a passing test. The required
backend lane is `-m "not database and not mke"`. Reassessment successor automation,
paid providers, real household data and hosted delivery remain outside this work.
