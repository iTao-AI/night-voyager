# Controlled intake revision acceptance

Verified on `2026-10-06` against implementation commit
`816ced9bd32af2977d5a269344575c7881b149ab`.
The [curated database summary](controlled-intake-revision.json) contains the actual
old/new run identities, output hashes, new pack, direct parent receipt and timeline.
The scenario is hypothetical, local synthetic and provider-free, with source/FX
as-of `2026-07-01`. This is bounded runtime-role database and unit evidence;
the later authorized native/browser acceptance below also passed; hosted delivery remains pending.

## Persisted behavior

The fixed Case advances from revision 1 / `2027-02` to revision 2 / `2028-02`
through assigned advisor request-review, actual student proposal, explicit advisor
confirmation and explicit Task creation. The existing deterministic worker reads
the stored new intake and independently frozen source
`50000000-0000-0000-0000-000000000017/v1`. It stores CNY minor `32,640,000` cost,
new-source Evidence references and a new output hash.

Fresh advisor review precedes a direct parent decision accepting CNY minor
`32,000,000`–`36,000,000` and `budget_elasticity`. The immutable receipt retains
the parent as both decision maker and recorder. The persisted timeline dates are
`2027-09-01`, `2027-10-15`, `2027-12-15`, `2028-01-20`. This range includes the new
cost and excludes the old `30,550,000` estimate.

The predecessor run, route/dimension/cost/ranking rows, Evidence and old request
review remain byte-equal across the success path, apart from the intended old
run `is_current` retirement. The baseline Task is a copied `legacy_unpinned` seed;
the successor is an actual worker Task with active packaged Skill pins.

The same real-role tests demonstrate finalized intake denial, unsupported
`2028-09` refusal without business writes, explicit candidate rejection/replacement,
later non-intake inheritance of the new pack, and exclusion of that pack from
otherwise qualified terminal timeout recovery. A tampered source-metadata snapshot
cannot pass the readback verifier. Empty downgrade restores the exact five prior
function bodies, OIDs and grants; persisted fixture/lineage refuses downgrade.
If the controlled source disappears after intake confirmation and before explicit
Task creation, the actual API role returns `409 intake_evidence_unavailable`.
The refused request leaves Case, revisions, runs, Tasks, dispatch and Task-create
idempotency records unchanged. Other missing source packs retain their existing
`NV003` behavior.

## Verification

An installed, constrained project wheel and existing retained PostgreSQL image
were used with separate empty task databases. No source overlay, new application
image build/pull, browser run, real provider or remote mutation formed this proof.

| Check | Actual result |
| --- | --- |
| `tests/integration/connected_demo/test_intake_revision_flow.py` with `-m database` | 4 passed |
| Read-only API-role `scripts/verify_controlled_intake_revision.py` | Passed |
| Separate empty `test_intake_revision_migration.py` lane, including missing-source HTTP regression | 4 passed |
| Related planning/revision/read-model/collaboration runtime-role regressions | 80 passed with current-head seed; 1 legacy seed assertion passed in its original initialization context |
| Legacy Task-create authority and actual HTTP contracts | 15 passed |
| Default Python suite (`not database and not mke`) | 1,570 passed; 421 deselected |
| Frontend `npm --prefix web test` | 49 files / 614 passed |
| Full project Pyright, affected Ruff, frontend typecheck/lint | Passed |
| Repository documentation/link governance | 32 passed |

The legacy collaboration seed assertion requires the existing `0007` seed without
Skills followed by an upgrade and default seeding. It failed against a freshly
pinned current-head seed, then passed in a new database using that original
initialization path. The 80 already-green runtime-role cases were reused. The
default Python suite initially exposed eight stale migration inventory, seed-helper
and CLI-mock expectations; these now assert the exact `0017` head, the closed seed
helper choice and the unchanged opt-in default. The full default suite passed
afterward. Raw logs and environment state remain ignored task artifacts. The
targeted documentation audit used repository checks and manual coverage review.

The whole branch was independently reviewed at `d91085b`; no Critical issue was
found. Its one Important bounded-error finding was reproduced RED at the actual
HTTP/API-role boundary and fixed in `816ced9`, with the migration, persisted-flow,
default Python and relevant runtime-role suites green. This was one fix pass
verified by tests, with no second review.

One Minor documentation finding was deferred at the initial review gate: the
walkthrough said the opt-in seed included an initial budget fact lineage. An
authorized documentation follow-up on `2026-10-06` corrected that description:
the seed supplies an intake ConfirmedFact chain, while its initial budget values
are revision preferences. The original review finding remains in the JSON record
as history; no deferred minor remains. Documentation checks were run for this
follow-up; unchanged runtime verification was reused.
This record does not establish default-branch availability, full local runtime
READY, a new release or deployment.

## First two native attempts: retained failure history

The separately authorized image/browser follow-up on `2026-10-06` built the
application, web and PostgreSQL init images from `6154bfd` and verified all 134
installed Python source files, embedded intake fixture/Skill manifests, copied
migrations/scripts and locked browser assets against the archived input. No
source bind mount or base-image pull was used. Actual API/worker roles connected
to a new isolated `night_voyager` cluster at migration `0017`. Image IDs and the
cluster identity are retained in the JSON record. Startup and the capacity/port
gates passed; build-only cache was released before runtime startup.

The first focused browser attempt failed on an incorrect test assumption about
the ordinary `/demo` Case; the actual Case is `400…002`, in `plan_ready`. No
controlled business mutation occurred. The test fix passed typecheck/lint and
one-test discovery. Only the browser image was rebuilt from `2542195`; unchanged
application/web/PostgreSQL images were reused.

The second attempt proved that an active journey was preserved, the controlled
Case was explicitly started, `request_revision` was submitted through the real
BFF/API and the student handoff succeeded. It timed out at the exact label
selector for the fact dropdown. The failure screenshot/accessibility snapshot
shows the intake combobox. Its wrapping label also contains the option text;
the locked Playwright label matcher reads that full text. An existing local DOM
check reproduced `要修改的事实入学月份`, which does not equal the test's exact
`要修改的事实`. The later low-cost repair below implements the exact role/name
selector; no new browser run has verified it. This was not a missing student
handoff or intake control.

At that checkpoint the native/browser phase was **DEFERRED and frozen after two
substantive failures**. Neither failed attempt established actual browser submission of
`2028-02`, successor-worker processing, the new cost, fresh approval or parent
receipt/timeline. The earlier bounded database acceptance above remains valid
within its original scope. Post-failure API-role readback confirmed revision 1,
unchanged predecessor output/evidence and frozen request-review bytes, with no
new candidate, confirmed fact, Task, run, brief, family decision or timeline.

Both attempts' containers, networks and PostgreSQL/artifact volumes, temporary
builders/cache volumes and task caffeinate were released. Five candidate image
IDs, source, screenshots, traces, raw logs and checkpoints remain retained as
task evidence. Hosted delivery is separately gated; no remote branch or PR exists.

## Low-cost test repair and remaining-step audit

The separately authorized low-cost follow-up is implemented at
`34acfa87b38e7813bcd29f2915c36d4015f4b0ac`, tree
`63a597c7fc92ff31bdb1b1a4ced24ceb4bc19eff`. It uses the existing locked local
environment and changes only focused tests/configuration and current documentation.
No Docker runtime, image build/pull, browser business run, provider or hosted
action occurred during that repair. At its checkpoint the native failure count
stayed **2** and the runtime stage stayed frozen.

The selector regression renders the actual `RevisionFactEditor` and runs the
installed Playwright `1.58.2` selector engine inside JSDOM. Exact label matches
zero controls; exact `combobox` role/name matches one. The old E2E helper produced
a real RED failure, then the repaired helper passed both tests. This local DOM
check establishes selector behavior without claiming real-browser acceptance.

The participant proposal DTO contains six projection fields and no `candidate_id`.
The previous replay assertion compared two undefined IDs. Its regression observed
two RED failures for an altered/missing projection; the repair compares the exact
parsed participant projection and requires one matching advisor candidate after
the explicit handoff. Six readback regression tests pass. Confirmation is bound
to that persisted candidate's actual UUID and result revision.

The [focused E2E](../../web/e2e/controlled-intake-revision.spec.ts) was audited
against actual components/copy, BFF/HTTP contracts, existing E2E and the earlier
successful PostgreSQL records. The following are source/readback findings, not
new browser passes:

| Remaining step | Evidence-backed finding and test treatment |
| --- | --- |
| Student fact control | Actual wrapping label includes option text; use exact accessible `combobox` name `要修改的事实`. The `新入学月份` input label is already correct. |
| Proposal and replay | `POST /api/demo/messages/{messageId}/memory-candidates` returns the participant projection. Compare all six fields, then require one matching entry in the advisor **array** DTO. |
| Pending reload and handoff | Saved intent contains `expectedCaseRevision`, `factKey`, `value`; the existing recovery regression retains both original mutation keys. Preserve explicit advisor handoff. |
| Confirmation reason | `AdvisorLedger` renders textarea label `确认理由`; the actual UTF-8 reason is within the existing 1–512-byte boundary. Bind `/verification-decisions` to the unique candidate UUID and assert revision `2`. |
| Canonical Task | Existing ledger supplies operation `generate_planning_run_v1`, policy `m3a-policy-v1`, revision `2`, pack `500…017/v1`. Assert exact canonical inputs, actual case-scoped POST and returned Task UUID. |
| Worker and comparison | Keep the 60-second durable phase wait. Require that same Task, new pack, `2028-02`, CNY minor `32640000`, fixed FX date, changed-fact leaf and frozen old request-review. Comparison leaf has no extra schema field. |
| Cost and fresh approval | The actual cost panel is filtered by `326,400`; the Chinese/English approval names are correct. Bind fresh approval to the successor run and its actual Australia eligible route. |
| Parent choice | The brief pins the Australia route. Existing family validation and successful E2E support the two budget labels, `budget_elasticity` checkbox and separate parent acknowledgement. Use the actual Brief ID/version/route; retain both disabled-button checks. |
| Receipt, timeline and reload | Earlier API-role proof joins the fresh approval/Brief to direct parent receipt and four February dates. Assert Australia, intake, exact dates and unchanged receipt **and timeline** after reload. |

Action and screenshot waits are 10 seconds, navigation 20 seconds, POST response
waits 15 seconds and API read/replay requests 10 seconds. The justified database
observer acknowledgement remains 45 seconds and the worker phase remains 60
seconds inside the 240-second whole-test bound. There is one worker and no retry.
New stage diagnostics contain fixed stage names, paths/status and synthetic DTOs;
idempotency keys are hashed. Session equality reports a boolean and reload checks
only the safe intent projection. Request failures omit raw headers. Focused traces
are disabled to prevent saving credentials; earlier traces remain ignored history.

Actual follow-up checks: **7 files / 96 unit tests passed**, frontend typecheck and
lint passed, and discovery found exactly one focused E2E. The unchanged 1,570/614
full suites and earlier PostgreSQL acceptance were reused within their original
scope. No second whole-branch review or production behavior change was introduced.
The maintainer subsequently accepted this repair/audit and explicitly authorized
[one controlled third attempt](../superpowers/plans/2026-10-06-controlled-intake-revision.md#authorized-third-native-acceptance-one-attempt).
The two prior failures remain. The actual third-attempt results follow.

## Authorized third attempt: local native/browser passed

The maintainer accepted the low-cost repair/audit and explicitly allowed one
third attempt of the same goal. Browser input is `34acfa87b38e7813bcd29f2915c36d4015f4b0ac` /
tree `63a597c7fc92ff31bdb1b1a4ced24ceb4bc19eff`; unchanged application input is
`6154bfd1b4a56e79527b0c03109fefc75f8a1193` /
tree `37291ccb39d1fdb2032aa1163643ad95ac1a99a9`. Only the browser image was
derived by copying the four frozen spec/helper/config files from the retained
browser candidate. No application/Web/PostgreSQL rebuild, install, browser
download, base pull or source bind occurred.

The new browser image is
`sha256:8a1d65defcd9632e0554faf0525068594eabb3621c14d66a091d1e4cf56ddbc3`.
The retained API/worker/migrator/seed, Web and PostgreSQL-init image IDs in the
JSON record were reused. Their installed sources/fixture/Skill/migration assets
and the four new browser file hashes were verified. Both capacity checks exceeded
8 GiB, all task ports were free before startup, and the build-only builder/cache
was released before the second check.

One worker and zero retries executed the single real BFF/API/worker journey.
The browser process passed with exit `0` in `18.854` seconds. Its exact participant
replay, actual advisor candidate UUID, confirmation result revision `2`, canonical
pack `500…017/v1` Task and successor worker were all verified. Six observed
business POSTs used the real UI; the captured proposal was replayed with its
original key. Final API-role readback found exactly one matching intake candidate.
Actual V3 month/cost, Chinese and English comparison, renewed approval and the
Brief-bound parent decision passed. The receipt stores CNY minor
`32000000`–`36000000`, `budget_elasticity`, parent maker/recorder and `direct`
source. The four dates and unchanged receipt/timeline after reload passed.

The independent read-only API-role checkpoint and final verifier establish
byte-equal predecessor output, child rows/Evidence, frozen request-review and old
revision, apart from the intended old run retirement. The new cluster used
`night_voyager_api` / `night_voyager_worker`, database `night_voyager`, migration
`0017` and the opt-in seed. Current curated run/receipt IDs come from this actual
attempt; the prior bounded readback and both failed attempts remain history.

All 12 screenshots at viewport widths `1440` and `390` were inspected; all 12
panel geometry checks and page overflow checks passed. The captured intake,
actual cost, bilingual comparison, explicit parent choices, receipt and four-date
timeline are present. The comparison table still wraps country/change columns
tightly, and English history/authority captions sit adjacent to their labels;
this acceptance makes no broader visual-polish claim. No new trace archive or
plaintext session/CSRF/idempotency-key field was saved in the new logs/artifacts.

Artifacts were copied before cleanup. Exact a3 containers/network/PG and artifact
volumes, the exited profiled browser one-off, builder/cache and caffeinate were
released. Other Docker inventories are unchanged. Six candidate images, all
source/bindings, raw logs and screenshots remain retained in ignored task evidence.
The two prior substantive failures stay recorded; no fourth run occurred.
Local native/browser acceptance is complete. Hosted PR/check/merge acceptance is
tracked separately; this local record establishes no release or deployment.

See the [walkthrough](../operations/controlled-intake-revision.md),
[approved plan](../superpowers/plans/2026-10-06-controlled-intake-revision.md)
and [ADR 0016](../decisions/0016-controlled-intake-revision-source-pins.md).
