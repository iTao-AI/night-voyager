# Controlled intake revision

This opt-in local synthetic scenario defers the same unfinalized Case from
`2027-02` to `2028-02`. It uses an independent hypothetical source pack and the
existing deterministic worker. It is not included in the current default-branch
runtime or published v0.1.6. Bounded database and unit proof is recorded in the
[acceptance evidence](../evidence/controlled-intake-revision.md); complete
application-image/browser acceptance and hosted delivery remain separate gates.

## Prepare the independent Case

Use a fresh, task-owned development database with the existing migrator/API/worker
roles and locked project environment from [database operations](database-roles.md).
Configure the existing `NIGHT_VOYAGER_*_DATABASE_URL` variables for that database,
`NIGHT_VOYAGER_ENVIRONMENT=development` and `NIGHT_VOYAGER_DEMO_MODE=true`.
From the current source checkout and its installed project environment, run:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed_demo.py --with-intake-revision
```

Default seeding does not add this Case. The flag adds fixed Case
`49000000-0000-0000-0000-000000000003`, its full initial intake ConfirmedFact
lineage and a baseline plan awaiting advisor review. Initial budget values remain
in the Case revision's family preferences; this seed does not create a budget
ConfirmedFact chain. It creates no family decision,
receipt or timeline. Exact initial replay is a no-op; a drifted or progressed Case
refuses atomically. Preserve existing volumes and history; reseeding is not a reset.
The baseline Task is a copied `legacy_unpinned` fixture; the successor below must
be an actual runtime-pinned worker result. Wheel resources and image asset layout
are defined, but the new application image has not yet been built for acceptance.

## Revise and explicitly decide

1. With the API, web and deterministic worker available, open
   `/demo?scenario=intake-delay` and explicitly begin. An active different Case
   or collaboration journey shows a conflict. Return to it or explicitly end its
   session before starting this scenario; entry never overwrites journey metadata.
   Bare `/demo` can resume this Case through its saved envelope.
2. As assigned advisor, request revision of the current `2027-02` plan. Inspect its
   current month, cost and review state. The initial budget is CNY minor
   `34,000,000` preferred / `40,000,000` ceiling, elasticity `1000` bps.
3. Choose the confirmed student intake and explicitly continue as student. Enter
   `2028-02`, submit the actual month and continue as advisor. The value remains
   pinned to this Case revision; reloading retains the exact submitted intent/key.
4. Inspect and confirm the displayed candidate with a reason. Valid input is
   strict ASCII `YYYY-MM`, years `0001`–`9999`, without trimming or coercion.
   Only the registered alternate has evidence in this scenario. `2028-09`, an
   unregistered February or missing/drifted source returns
   `409 intake_evidence_unavailable` before publication. The old revision and
   current plan remain usable. Explicitly reject the pending intake candidate
   before asking the student for a replacement; no automatic retry or promotion
   supplies evidence.
5. Create the new planning Task explicitly. Its source is
   `50000000-0000-0000-0000-000000000017/v1`, selected from frozen lineage.
   The actual worker input, stored cost and Evidence references must use `2028-02`.
   The new estimate is ¥326,400: AUD minor `4,200,000` tuition + `2,600,000` living,
   FX `4.80`, source/FX as-of `2026-07-01`. Country eligibility may stay unchanged
   while month, source and cost change. The old request-review is displayed as
   historical context and cannot authorize the new run.
6. Give fresh advisor approval, then explicitly continue as parent. Accept
   ¥320,000–360,000, acknowledge `budget_elasticity` and give final consent.
   This interval contains the new cost and excludes the old ¥305,500 estimate.
   The direct parent receipt preserves those actual choices. Existing February
   policy yields `2027-09-01`, `2027-10-15`, `2027-12-15`, `2028-01-20`.

Ledger clients request exact `contract_version=3` (AdvisorLedger V3, Comparison V2);
Brief clients keep exact `contract_version=2`. Existing V1/V2 country/budget reads
retain their shapes. Legacy ledger requests for this controlled intake Case return
bounded `503 demo_contract_unavailable`, preventing misleading month/cost display.
Browser hashes, locale and URL metadata grant no authority.

## Verify persisted results

After the full decision, use the configured runtime API role:

```bash
.venv/bin/python scripts/verify_controlled_intake_revision.py
```

The verifier opens a read-only transaction on the fixed Case. It checks two
revisions/runs/Tasks/reviews, one Brief/direct decision/receipt/timeline, source and
cost provenance, current fact history, frozen joins and actual timeline dates.
It uses the existing controlled collaboration reads; it grants no table access
and mutates no business state. The issued Brief is consumed (`is_current=false`)
after final consent, with its immutable decision link retained. Output is a safe
database summary, not browser, screenshot or image proof.

Finalized intake revisions refuse without changing facts, revisions, decisions or
history. On a separate unfinalized Case, a later country/budget change inherits
the predecessor's new source and month; a retired historical Task blocks only
when its frozen retirement lineage is absent. New-source terminal Tasks remain
ineligible for the `0016` retry allowlist, even for an otherwise qualified timeout.

See [ADR 0016](../decisions/0016-controlled-intake-revision-source-pins.md),
[HTTP contracts](../reference/http-api-v1.md),
[source contracts](../reference/domain-and-source-manifests.md) and the
[approved plan](../superpowers/plans/2026-10-06-controlled-intake-revision.md).
