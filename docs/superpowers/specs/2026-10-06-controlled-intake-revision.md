# Controlled February intake revision

Status: Approved for local implementation; implementation in progress, runtime acceptance pending.
Date: 2026-10-06.
Git starting point: `68de260b1e207f83153d51801501c7775b4f4374`, the merged PR #128 main baseline.
Delivery owner: the maintainer-directed delivery owner retains design, integration and acceptance.
Companion: [implementation plan](../plans/2026-10-06-controlled-intake-revision.md).

## Purpose and fixed scenario

A student postpones one existing synthetic Case from `2027-02` to `2028-02`
before any family decision or TimelinePlan exists. The assigned advisor confirms
the proposal, an explicit action creates a new PlanningRun, a fresh advisor
review authorizes its brief, and the parent submits an explicit decision that
produces a new receipt and the February 2028 timeline. The predecessor run and
its request-revision review remain inspectable history.

The success fixture is one dedicated Case, `49000000-0000-0000-0000-000000000003`,
initial revision `1`, with the existing synthetic organization and assigned
advisor/student/parent actors. It starts with confirmed intake `2027-02`, the
existing three preferred countries, budget `34,000,000` / `40,000,000` CNY minor,
elasticity `1,000` bps, and the existing Japan-risk preference. Its initial run
uses the unchanged M3A source pack and is awaiting advisor review. There is no
pre-existing family consent, receipt or timeline to revoke or replace.

All fixture source snapshots and FX dates use fixed `2026-07-01`. Future-intake
amounts are expressly hypothetical synthetic test values, not real prices,
forecasts or institution coverage. The scenario retains the existing local,
provider-free product boundary.

## Current executable boundaries

| Surface | Current behavior | Required design change |
| --- | --- | --- |
| `collaboration/models.py` and `policy.py` | Student-authored `student.intake` proposals exist; generic confirmation can project the value into a Case revision | Reuse this fact and role vocabulary; reject invalid calendar years consistently |
| Migration `0012`, `verify_memory_candidate` | Planning revisions allow only countries/budget; require exact request-revision review; reject finalized Cases | Add intake under the same fences and verify supported source availability before publication |
| Migration `0012`, `read_connected_journey_fact_pending` | Boolean counts only countries/budget; API-only execution | Include intake without exposing candidates or adding table grants |
| `planning/revision.py`, connected repository | Closed two-fact comparison; any other changed student field is rejected | Version the projection and recognize exactly one of three changed facts |
| `planning/synthetic.py`, worker snapshot SQL | Only the exact baseline pack/version and raw/canonical manifest hashes are supported | Add one independently pinned fixture; select by persisted pack identity |
| `connected_demo/fixtures.py` and repository | One global canonical baseline is used for task inputs and validation | Resolve the V3 source from the current persisted revision before creation, and from stored task/run pins afterward |
| `planning/policy.py` | Australia cost must match intake exactly; its selected cost is the first Australia row | Keep one Australia cost per pack; never combine the two months in that list |
| `decision/policy.py` and `application.py` | February-only dates derive from brief intake and source snapshot date | Reuse the existing calculation with `2028-02`; do not change the timeline rule |

The governing lineage is [ADR 0012](../../decisions/0012-versioned-planning-revision-authority.md).
The BFF and recovery boundaries remain [ADR 0006](../../decisions/0006-connected-demo-bff-authority.md)
and [ADR 0015](../../decisions/0015-guarded-terminal-task-recovery.md).

## Approach selection

Recommended: a two-entry synthetic source allowlist, one additive migration and
an explicitly negotiated comparison/ledger version. Existing source-pack tables,
fact confirmation, task pins, worker leases and decision services remain the
authority path. No source publishing service or source lifecycle is introduced.

Two alternatives were considered. Expanding the existing comparison V1 union
in place would break clients whose closed discriminator admits two facts.
Building an arbitrary-month catalog, non-February timeline or post-consent
revision workflow would add new authority and data lifecycle requirements beyond
this scenario. Neither alternative is part of this draft.

## Authority and unsupported intake

Only the assigned student authors the intake candidate. Only an assigned advisor
with the exact current-revision `request_revision` review confirms it. Existing
Case locks, active-task checks, revision fences, candidate expiry/terminal checks,
idempotency and organization/participant isolation remain in force. Confirmation
publishes exactly one adjacent revision; it does not start planning or approve a
route. The family still makes its own explicit decision after fresh review.

Intake is an ASCII calendar month in `YYYY-MM`, year `0001` through `9999`.
Malformed months, year `0000`, unchanged values and non-student authors are
rejected. No whitespace or alternate encoding is coerced into a stored month.

For a planning intake revision, confirmation also requires the exact registered
synthetic source for that intake. `2028-09`, an unregistered February year, a
missing pack or a drifted pack returns bounded `409 intake_evidence_unavailable`
before publication. Proposed SQLSTATE `NV027` maps only to this domain error;
unauthorized callers still fail before the source check. The candidate may be
explicitly rejected and replaced through existing actions.

This refusal point is deliberate: publishing an unsupported revision without a
successor would leave no current run from which the existing request-review
authority could resume. Refusal retains the old revision/run and review
authority. It produces no successor, accepted cost, family brief, receipt or
timeline, and never substitutes `2027-02` costs or dates. Existing initial
planning and governed mixed-provider semantics are outside this new gate.

Cases with any FamilyDecision or TimelinePlan remain finalized and reject
revision. No receipt editing, consent revocation or post-consent replan is added.

## Independent synthetic source and persistence

Create `fixtures/intake-delay-v1/manifest.json` and manifest-owned source files.
Use source pack `50000000-0000-0000-0000-000000000017`, version `1`, and distinct
entry/Evidence identities. All evidence is `accepted_synthetic_demo`. The new
Australia source explicitly declares `2028-02`, hypothetical tuition `4,200,000`
AUD minor, living cost `2,600,000` AUD minor, FX `4.80` and the fixed as-of date.
The expected total is `(4,200,000 + 2,600,000) * 4.80 = 32,640,000` CNY minor.
Non-intake Japan/Malaysia disclosures preserve existing synthetic policy facts
in separately declared entries; no new countries or program recommendations are
introduced. Each pack contains exactly one Australia cost row.
The new manifest's example Case describes target revision `2`; materialization
always replaces it with the exact persisted Case, while the initial seed uses
the unchanged baseline facts at revision `1`.

The new fixture uses the existing manifest/path/hash/PlanningInput validation
shape. Compute and freeze its raw manifest SHA-256 and canonical source-pack
SHA-256 from the reviewed fixture bytes during implementation. Those exact
values must agree between loader constants, the migration seed helper and
stored source-pack rows; they are not derived from a runtime intake request.
Existing `fixtures/m3a`, all `BASELINE_*` constants, DRA baseline identities and
tagged Release records remain byte-for-byte unchanged.

The new fixture is also included as package data under
`night_voyager/planning/data/intake-delay-v1`; its loader resolves installed
resources independently of checkout cwd. The API builder copies the new
fixture into its build context, and the final runtime retains the existing
`/home/app/fixtures` layout. Wheel/archive inventory and exact resource digests
are checked without calling a source overlay an installed-image proof. A new
Docker image acceptance run remains a separately authorized gate.

An opt-in `scripts/seed_demo.py --with-intake-revision` setup registers the new
pack, entries, Evidence and dedicated initial Case through a new migrator-only
seed helper. The initial confirmed-intake fixture includes student message,
candidate, advisor verification and revision fact references. It is visibly
synthetic bootstrap data. Exact replay is a no-op; identity, bytes or row-shape
drift refuses atomically. Existing seeded Cases are never overwritten or backfilled.
Default seed behavior remains unchanged.

The API does not create or promote sources. Before confirmation and task
creation, PostgreSQL checks the allowlisted pack/version, canonical hash,
manifest-owned entries and accepted synthetic references. Task creation locks
the exact Case revision and verifies the requested source pin against its
persisted intake; a client cannot substitute the old pack for the new intake.
The resulting task, successor run and evidence uses retain that immutable pin.
The worker snapshot validates the persisted identity and the loader chooses the
fixture by that identity, never by changing fixture cost dates to match input.
Persisted budget/countries/intake reach the adapter unchanged.

Source selection is bounded by persisted lineage: initial planning and existing
baseline country/budget revisions retain the baseline. An authorized intake
delta selects the exact registered target; later non-intake revisions retain
that predecessor's pin. A request for the new pack without this lineage, or for
the baseline on the successful `2028-02` intake delta, is rejected. This does not
globally change source choice for arbitrary initial Case intake values.

## Additive migration and permissions

Proposed migration `0017_controlled_intake_revision.py` follows `0016` and replaces
only the affected function bodies. It must not edit historical migrations.

- `validate_collaboration_fact`: retain all existing fact branches and add the calendar-year guard to intake.
- `verify_memory_candidate`: add intake to the planning whitelist; perform the source-availability check inside the existing transaction before publication; retain finalized and request-review fences.
- `read_connected_journey_fact_pending`: include intake in the exact boolean filter, with unchanged API-only grant.
- `create_agent_task`: validate the new synthetic pack/intake binding under the existing Case lock, revision fence and task/Skill pin rules.
- `load_persisted_synthetic_planning_snapshot`: accept the second exact registered pin and enforce its persisted intake/manifest identity; retain the worker-only grant and strict snapshot DTO.
- A closed source assertion and synthetic seed helper are migrator-owned, `SECURITY DEFINER`, with `search_path = pg_catalog, pg_temp`; no direct API/worker/PUBLIC execution or candidate-table privileges are added.

Other task finalization, predecessor uniqueness, RLS, runtime Skill manifests,
governed mixed-source verification and terminal recovery remain unchanged. The
existing `0016` retry whitelist does not authorize the new pack; a failed new-pack
task must not advertise retry eligibility. Downgrade refuses before mutation if
the new fixture has been persisted or intake revision/new-pack task lineage
exists; otherwise it restores exact `0016` bodies and grants.

Current-source Alembic verification, role/seed revision sets, DB lane current-head
checks and package/source inventory must explicitly recognize `0017` and the
new fixture/helper. Historical downgrade and initial-budget phase checks at
`0016` stay explicit. This is a targeted current-source update, not a replacement
of every `0016` literal or a change to tagged Release verification history.

## DTO, HTTP and comparison compatibility

Keep comparison V1 and existing default/V2 HTTP reads unchanged for the old
country/budget scenarios. Add `IntakeFactDeltaV1` with strict changed calendar
months and `PlanningRevisionComparisonV2` with schema
`night-voyager.planning-revision-comparison.v2`. Its closed `changed_fact` union
admits countries, budget or intake. The existing common lineage, output hashes,
country outcomes and approval-eligibility rules remain required.

V2 comparison also carries `previous_request_review` with only review ID,
review version, predecessor run ID, Case revision and `request_revision` action.
It is reconstructed from the revision's frozen review reference under the same
organization/Case joins. This provides a bounded view of the old review without
adding a generic history endpoint or exposing notes. Output is audit context,
not a caller-supplied approval or mutation token.

Exactly `contract_version=3` on `advisor-ledger` selects `AdvisorLedgerV3`:
`schema_version=3`, actual `case_intake`, the V2 comparison when revised, and
route cost projections that explicitly include their stored `intake`. Before
creation, canonical inputs select the registered source for the current
persisted intake. Existing task/run pins become the source of truth afterward.
Unknown, empty, repeated or malformed negotiation values continue to fail closed.
Legacy V1/V2 reads of the new intake/new-pack scenario return the existing safe
`demo_contract_unavailable` response rather than misrepresenting a two-fact
comparison. Their old scenarios retain their exact prior response shapes.

`current-decision-brief` remains V2: its family-safe intake, revision context,
pinned cost requirements, actual receipt and timeline already express the
result. Task creation, proposal, confirmation, advisor review and family
decision request shapes stay unchanged, apart from the explicit bounded error
for unavailable intake evidence. The new BFF ledger route requests V3; its brief
route continues requesting V2. No browser-computed source hash or authority is
accepted.

## UI and decision consumption

The controlled entry is `/demo?scenario=intake-delay`, mapped to the single
allowlisted synthetic Case after the opt-in seed. An explicit start action is
required. Existing active journey metadata is retained and presents an explicit
journey conflict rather than silently switching Cases or replacing replay data.
Bare `/demo` retains its current initial Case.

The existing revision editor offers intake only from an exact current confirmed
intake fact. Student preparation, `YYYY-MM` input, saved intention, submitted
message/candidate value, advisor matcher and reload recovery use the actual
value. Missing/stale facts, no change and invalid months disable submission;
the supported alternate is clearly labelled hypothetical `2028-02`. Parent
proposals remain forbidden. The new comparison shows both intake values, old
run/review history and current cost intake. Unchanged country eligibility may
still be labelled unchanged even though intake and source/cost changed.

Fresh review and parent consent are separate explicit actions. The success
decision accepts `32,000,000` to `36,000,000` CNY minor and required
`budget_elasticity`, which contains the new `32,640,000` cost and excludes the
old `30,550,000` cost. Existing decision policy and receipt persistence validate
and retain these actual inputs. The source-pinned brief intake drives milestones
`2027-09-01`, `2027-10-15`, `2027-12-15`, `2028-01-20` through the unchanged
February timeline calculation.

## Observable acceptance and gates

1. On the fixed initial Case, student proposal and assigned-advisor confirmation produce revision `2` with actual intake `2028-02`; other preferences remain equal and no task starts automatically.
2. Explicit new planning freezes the new pack/version/hash, predecessor and Skill pin. Persisted cost/Evidence rows, adapter input, comparison, fresh review, brief, direct parent decision, receipt and timeline form one exact same-Case/revision chain.
3. Required negative controls cover illegal month/year, non-student author, unassigned advisor, missing request review, unchanged value, stale revision/candidate, expiry, same-key replay and changed-payload conflict, missing/drifted sources, wrong old/new pack and unsupported month. Refused confirmation has an identical before/after business snapshot.
4. Already finalized Cases remain rejected; no existing family decision, receipt or timeline is modified. Old run output/hash/routes/costs/Evidence and old review payload remain byte-identical. The predecessor's existing `is_current` flag intentionally becomes false at successful publication; whole-row byte equality is not claimed for that flag.
5. V1/V2 old-contract regressions, strict V3 negotiation, exact one-of-three deltas, malformed extra fields, role handoff, saved old intents and new intake recovery remain covered. API/worker grants and RLS are tested with runtime roles.
6. Inspect database facts and persisted identities for final acceptance. UI success, mocked repositories or fake facades alone are insufficient. Assert exact new-source references, distinct cost, receipt interval, decision actor and the four dated milestones.

Local fixture, migration, public-contract, UI and documentation implementation
is approved, including existing locked isolated dependencies and the bounded
real PostgreSQL/runtime-role lane in the plan. Full native/browser/image rebuild,
pull and hosted delivery require concrete separate verification authorization.
No such full runtime acceptance is claimed here.
The deferred native recovery CI stage remains separate and frozen. No new
dependencies, lock changes, arbitrary-month rules, batch replans, N3 work, remote
publication, tag, Release or deployment belongs to this design preparation.

Implementation includes an ADR for these source-pin/read-contract decisions
and update the affected reference/how-to documentation. The intended minimum
sequence and evidence ownership are in the companion plan. The targeted engineering
review used executable source; the GStack plugin is unavailable in this environment
and has not been invoked. Repository document checks cover the affected entry,
reference and how-to surfaces; any concrete gap is recorded explicitly.
