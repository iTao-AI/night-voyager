# Customer revision and recovery acceptance

Date: 2026-10-02. Status: local native/UI acceptance verified; final branch review and
owner acceptance pending. This controlled synthetic pilot is not a published
release, deployment, real-family outcome or live-provider proof.

The reviewed implementation input is `5d2ec2ca3ea4e0966b67e90868f8060eda657056`
on `codex/customer-revision-recovery`. Tasks 1–3 are independently reviewed.
Acceptance follows the [approved design](../superpowers/specs/2026-10-01-customer-revision-recovery.md)
and [active plan](../superpowers/plans/2026-10-01-customer-revision-recovery.md).
See the [runnable walkthrough](../operations/customer-revision-recovery.md).

## Current verified boundaries

- Runtime PostgreSQL uses migration, API and worker roles with forced RLS.
  Migration `0016` is current in this branch; historical lanes explicitly retain
  their `0009`–`0015` targets and exact downgrade/catalog semantics.
- The dedicated recovery lane uses actual classifier and claim/start/fail or
  lease exhaustion, then fresh TaskWorker result and advisor review. A direct
  terminal row edit supplies only named negative controls.
- Source task/events/executions remain immutable, concurrency and exact replay
  create one successor, and fresh task authority cannot reuse old approval.
- The connected browser is synthetic-only. Native mixed HTTP recovery retains
  the promoted pack and operation without expanding the UI's evidence shapes.

## Verification record

All gates below ran sequentially in task-owned environments with the existing
locks; counts describe their separate lanes and are not unique-test totals.

| Gate | Actual result |
| --- | --- |
| `sh scripts/run_db_tests.sh` | Exit 0, including historical migrations/downgrades, exact current catalog, 27 terminal recovery tests, original country-helper phases and fresh-volume budget absent/authority/empty-downgrade/restoration phases, main 248 passed / 6 skipped, governed closure 1, decision DB 9 and decision HTTP 1 |
| `sh scripts/run_db_tests.sh planning-revision all` | Exit 0: authority 108 passed / 5 skipped, worker 32, historical mixed downgrade 1, projection 30 |
| `sh scripts/run_db_tests.sh planning-revision journey` | Exit 0: 41 passed |
| `SUITE=authority sh scripts/run_collaboration_db_tests.sh` | Exit 0: catalog 51, native 46, revision/historical and five downgrade scenarios |
| Required backend `-m "not database and not mke"` | 1505 passed / 386 deselected |
| `uv lock --check`, Ruff, Pyright with isolated interpreter | Exit 0; Pyright 0 errors/warnings |
| Web lint, TypeScript, Vitest, default Next.js build | Exit 0; 46 files / 555 tests; Next.js 16.3.6 Turbopack build |
| DRA fixture/rehearsal, synthetic fixture validation | Exit 0, provider-free |
| Existing hermetic MKE smoke | 10 passed; separate from unavailable external artifact proof |
| Hash-constrained `uv build` and actual archive inspection | Exit 0; sdist has no task scratch/venv/node_modules/Next build; wheel resources equal both authoritative fixtures |
| `Dockerfile.proof` target `proof`, task-owned tag | Exit 0; isolated installed-wheel import and API app factory |
| `sh scripts/verify_compose.sh planning-revision` | Exit 0: base health/native flows, API/worker restart, SSE, real lock/lease reclaim; zh-CN/en country revision, fresh review, receipt and blocked counterfactual |
| Bilingual parent-budget/native recovery supplement | Exit 0: zh-CN 28.8s / en 34.7s; real parent 503/reload, changed budget, native timeout, explicit retry 202/new task/SSE, fresh review, receipt 300000–360000, hard/controlled-unknown negatives and exact source-diagnostic equality |

The default native main explicitly imports from installed `site-packages` with
`uv run --no-editable python -m pytest`, without a source `PYTHONPATH`. Host
source-import tests resolve through an ignored per-file overlay to the current
worktree source; this is distinct from the native wheel proof.

## Runtime and artifact identity

Runtime Python source and fixture trees match the reviewed input above. Source tree: `d3fdcbafcd980d69262a842b7bf2f3b058669d5d`;
fixture tree: `878f179bb67ff51a56de7c305592a9bfe447ca89`.

| Material | SHA-256 |
| --- | --- |
| `src/night_voyager/tasks/application.py` | `9d7557349f893fc47262db0bb4b65293278a94dc8235e3599bca4c69c0f73829` |
| Packaged runtime Skill manifest | `6e7a8dc12cc2a71f417ff9bbed998a732645122d3bb1f720af3a546172dda716` |
| Packaged evaluation Skill manifest | `fb60c25be720afdbd0c4885057412957c68f4d48f0d09c615a439ac73bd527cb` |
| Host wheel `night_voyager-0.1.6-py3-none-any.whl` (258,502 bytes) | `68f9e3b944564cc2d7035a762d41a3c0fa089a37b5dda1b5f78bc3cd629b010f` |

The native UI API image was
`sha256:664f019232e30c66ab81bb95f42f15bdf83b486e3770be3cea1b08add0e97f30`;
web image `sha256:317f77da4b84258c4797afa984efc6389112aadd60f7e051f39d96ca0841ce2d`.
Their installed package/resource bytes were checked before disposable cleanup.
Migration `0016` hash is
`818652d2f639608613273041b6479719581a14646a4168bcb76361f1ef300d64`;
seed script hash is
`f47c89e08dd371bb41507bb552085c9457a368db48798f6da579e2a361dead8e`.
Final source-archive and task proof-image identities are emitted by the local
verification commands and retained with the task report; source archives include
this document, so an archive hash is not embedded in itself. Wheel app/resource
bytes and runtime image identities bind the executable behavior independently.
Neither `make check` nor the fixed-tag `make proof` command was invoked: their
relevant constituent paths were executed separately to preserve unrelated tags.

## Acceptance harness corrections

The historical empty `0015` identity roundtrip now explicitly upgrades to
`0015`, rather than interpreting the newer `head` as that historical revision.
Its catalog test checks exact `0015` in the isolated historical phase and exact
`0016` at current head. The current main suite uses `python -m pytest` so the
existing `tests` package is resolvable with a noneditable installed wheel.

Recovery security fixtures create random Cases and intentionally isolate dispatch.
They remain in the complete dedicated fresh-volume recovery lane; the older main
lane keeps its fixed Case/dispatch baseline. This is suite isolation, not a waiver
of recovery authority or RLS testing. Initial failures are retained in local logs;
final successful runs use separate files.

The first Compose browser run timed out before the task/SSE sentinel while
confirmation replay was still reconnecting. The replay returned the same
verification identity with `replayed=true`, and authoritative status became
revision 2 / `replan_required`. The verifier now waits explicitly for the real
create-task button before clicking; the unchanged 120-second SSE and native
reclaim gates passed in both locales. The first complete raw browser trace was
not retained after its disposable container ended. Sanitized observations and
later task-owned persisted trace directories are distinct from that missing
artifact; none is published as a raw session transcript.

The packaging RED exposed task scratch in the sdist; `/.superpowers` is now
excluded. The generated Next.js standalone output was reversibly retained inside
that excluded task environment before the successful actual archive probe.
The host Next.js build temporarily used the same locked dependency directory
inside the web root, then restored its original task location. These are bounded
artifact/environment corrections, with no dependency, loader or product changes.

## Native acceptance findings and corrections

The initial native browser gate exposed a disabled parent handoff. The explicit
`Edit budget as parent` transition and session/draft recovery repair were reviewed
at `b3da31c80c9d384408e302d6519a74480656e073`. The next native browser run passed a real
parent session mint, a controlled first confirmed-facts read returning 503, and a
same-tab reload using the persisted parent credentials without a second mint or
business mutation. The authoritative read then returned only the shared country
fact: the canonical synthetic fixture had no initial `family.budget` confirmed
fact. The earlier explanation that student reads hide budgets was incorrect:
all verified participants share safe current facts; parent-only budget mutation
remains enforced. Formal seed completion was scoped-reviewed at
`5d2ec2ca3ea4e0966b67e90868f8060eda657056`; native gates were refreshed on fresh
task volumes. The default/planning/journey/collaboration and bilingual
country/budget browser gates passed. Its baseline budget is 340000 / 400000 CNY `program_total`, with
elasticity 1000 bps. Old-installed `0016` and old country-only/evolved Cases receive
no automatic helper installation or backfill; existing volumes are preserved. API/session
hydration or SQL completion is not accepted for the main budget/recovery success
path. The RED is retained separately from final GREEN. Final browser proof used actual
parent credentials and authority before the 300000 / 390000 proposal, then a real
classifier/worker-lease timeout producer and explicit retry. Both locales persisted
300000 / 360000 with separate `budget_elasticity` acknowledgment and final parent
consent. `invalid_schema` is a real native failure; only the named `provider_unknown`
negative uses a controlled exact-one-row terminal-code change. Neither negative
shows retry authority, and both POSTs return 409. The old happy source Task,
events and execution snapshot remains exactly equal after the final receipt.

The first successful retry attempt exposed a harness issue: `compose start worker`
restarted completed seed dependencies, correctly failing closed on evolved Cases.
The bounded runner now starts only the existing worker with
`up --no-deps --no-build -d worker`; both complete locale flows passed. Its prior
RED and partial browser trace remain retained, without substituting SQL success.
A later image readback missed disposable cleanup and produced no valid binding;
final identities were recorded before running the browser with `--pull=never`.

Real Chromium captures retain editor, candidate, retry consent, comparison/fresh
review, family consent, receipt, hard and unknown panels plus full-page context
at 1440 and 390 pixels. The budget proof records 36 bounded panel geometry files;
text-entry/action controls are at least 44 pixels high, with no horizontal overflow.
Fresh country proof also passes its 1440/768/390/320 overflow/restart/reclaim gates.
No generated public screenshot was replaced. UI review evidence does not replace
native functional authority.

## Remaining boundaries

Nine optional MKE retained-artifact tests require the separately retained native
operator environment and receipts. That external proof is unavailable and not
passed; it is not fabricated or copied from another checkout. Required backend
CI excludes `mke`; hermetic provider-free contracts are separate evidence.
Reassessment successor automation, new dependencies, paid providers, hosted CI,
push/PR/merge/tag/release/deploy and remote cleanup are outside authorization.
The final whole-branch review and owner acceptance are still pending.
