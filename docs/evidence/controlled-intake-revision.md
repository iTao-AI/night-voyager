# Controlled intake revision acceptance

Verified on `2026-10-06` against implementation commit
`5e4d5be8f42f0d4a3b37544272f0dd8f8bb1f044`.
The [curated database summary](controlled-intake-revision.json) contains the actual
old/new run identities, output hashes, new pack, direct parent receipt and timeline.
The scenario is hypothetical, local synthetic and provider-free, with source/FX
as-of `2026-07-01`. This is bounded runtime-role database and unit evidence;
full native/application-image/browser acceptance and hosted delivery are pending.

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

## Verification

An installed, constrained project wheel and existing retained PostgreSQL image
were used with separate empty task databases. No source overlay, new application
image build/pull, browser run, real provider or remote mutation formed this proof.

| Check | Actual result |
| --- | --- |
| `tests/integration/connected_demo/test_intake_revision_flow.py` with `-m database` | 4 passed |
| Read-only API-role `scripts/verify_controlled_intake_revision.py` | Passed |
| Separate empty `test_intake_revision_migration.py` lane | 3 passed |
| Related planning/revision/read-model/collaboration runtime-role regressions | 106 unique passed; 3 skipped |
| Focused backend Task/decision/planning/read-model units and documentation | 282 passed |
| Frontend `npm --prefix web test` | 49 files / 614 passed |
| Full project Pyright, affected Ruff, frontend typecheck/lint | Passed |
| Repository documentation/link governance | 32 passed |

The broader database run initially omitted the established `DEMO_SEED_READY=1`
runner flag; the one affected real HTTP-role test passed after verifying actual
seed success and providing that flag. Its 105 already-green companions were reused.
No failed substantive check is treated as success. Raw logs and environment state
remain ignored task artifacts. GStack was unavailable and was not invoked; the
targeted documentation audit used repository checks and manual coverage review.

The final whole-branch review is pending. This record does not establish default-
branch availability, full local runtime READY, a new release or deployment.
See the [walkthrough](../operations/controlled-intake-revision.md),
[approved plan](../superpowers/plans/2026-10-06-controlled-intake-revision.md)
and [ADR 0016](../decisions/0016-controlled-intake-revision-source-pins.md).
