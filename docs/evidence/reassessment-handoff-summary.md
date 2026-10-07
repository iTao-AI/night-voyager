# Saved reassessment handoff acceptance

Status: local implementation and progressive-disclosure repair verified.
The first hosted proof attempt failed on the preceding head; the repaired
candidate has not been pushed or revalidated on hosted CI. Publication is separate.

Verification date: 2026-10-07. Base:
`0017d364995ca59e9b71cad48433d9e485fb6c3a`. Application implementation:
`911a732c6b3e5ec37d4ab85739ce87bb8a2d7db3`.

## Scope

This is a read-only bilingual consumer of an already saved reassessment. It
adds specific facts, source disclosure and user-initiated text copy with a
selectable fallback. It preserves the Stop and `pending_future_authorization`.
There is no backend, migration, lockfile, worker, receipt, consent, successor,
recovery or replanning-authority change.

## Current local checks

- `npm --prefix web test`: 54 files and 668 tests passed. The 32 projection/UI
  tests cover the saved checkpoint, blocked/deadline facts, mismatched reference,
  checkpoint/execution, absent detail, context anchors, export privacy, clipboard
  failure/unavailability and invalidation across state, role and locale changes.
  Four live-hook regressions cover Happy/Blocked source changes in both
  directions and delayed clipboard success/failure. They failed before the
  source-binding fix and passed afterward; a different requested source cannot
  copy the retained Case before a fresh validated read.
  The same whole-main raw-data regex used by the native journey failed against
  the old closed disclosure's DOM text, then passed after rendering technical
  contents only on explicit expansion. Closing removes identities and the
  projection explanation from the DOM; context changes remove open old content.
- `npm --prefix web run lint`: passed.
- `npm --prefix web run typecheck`: passed.
- `NEXT_TELEMETRY_DISABLED=1 npm --prefix web run build`: passed.
- `web/e2e/reassessment-handoff.spec.ts`: 17 actual Chrome browser tests passed
  against a task-owned built Next.js server. Chinese and English, 1440/390,
  accepted blocked/deadline fixtures, native clipboard read/write, fault-injected
  clipboard denial, source disclosure and context/session invalidation passed.
  Exported text matched the displayed rows and excluded synthetic actor IDs.
  The repaired tests also check the unchanged whole-main pattern before
  disclosure and after close, native Enter/Space interaction, exact disclosed
  IDs, and no request triggered by open/close. Copy retains its complete
  whitelist while the source disclosure is closed.
  Browser geometry checked page/section overflow. Raw screenshots, logs and
  reports remain ignored task artifacts, not public product evidence assets.

Node 24.18.0, locked Next.js 16.3.6/Vitest 4.1.11/Playwright 1.58.2 and the
existing Chrome 154 browser were used. Dependency synchronization used the
existing package lock and a task-owned cache; no new dependency was added.

## Evidence classes and source mapping

| Evidence | What it establishes | Limit |
| --- | --- | --- |
| Current Vitest and static/build checks | Projection, render/copy boundaries and frontend compatibility | No new business mutation or database run |
| Current routed-fixture browser | Real browser parser/UI/clipboard behavior and responsive reading | Demo sessions and HTTP reads are synthetic routes; no native persistence or recovery assertion |
| Existing `0014` read projection and typed DTOs | Saved reassessment IDs, acceptance date/digest, predecessor anchors and current observed date already exist | Inspected/reused; not newly executed in this slice |
| Existing runtime-role database tests and receipt/GET browser proof | Established execution/reassessment projection authority and stop boundary | Historical acceptance; this change does not relabel it as a new native run |

The SQL projection is `app.read_timeline_execution` in
`migrations/versions/0014_timeline_execution_authority.py`. It independently
selects latest attestations and returns saved reassessment fields and
`observed_date`. The DTO is `TimelineReassessmentRequestV1` in
`src/night_voyager/timeline_execution/models.py`; repository decoding and HTTP
serialization retain those fields. Existing
`tests/integration/timeline_execution/test_authority.py`, `test_repository.py`,
`test_http.py` and `web/e2e/plan-execution.spec.ts` cover the runtime-role authority
and receipt/fresh-read seam. This slice inspects those sources rather than
restarting the native/Compose recovery chain.

The consumer selects the saved checkpoint by ID and references a blocker reason
only for a matching attestation ID/execution/checkpoint and blocked kind/status.
It uses saved acceptance and view dates directly and exports the projection
digest as a reference with an explicit non-verification note.

## Documentation audit and limits

The targeted `document-release` audit covers the reference contract, existing
walkthrough, docs entry/index and this acceptance classification. Existing
explanation and walkthrough coverage is sufficient; no new architecture ADR or
duplicate tutorial is needed. Historical release notes/guides remain untouched.

A fresh read-only whole-branch review at
`0b7bf1a5c20b7cd34fa3de7dd332563d269ed2af` found one Important issue: a retained
seeded controller could copy the old Case after its requested scenario changed.
The fix records the source of each validated read in client metadata and gates
copy on that source matching the current request. It changes no HTTP/DB or
business authority. The delivery owner reviewed the targeted repair and reran
the full frontend/static/build and 17-test browser acceptance on the repaired
implementation. No Critical or Minor findings remain from that review; no
second independent review is claimed.

## Hosted failure and local disclosure repair

[Draft PR #133](https://github.com/iTao-AI/night-voyager/pull/133) published the
previous head `e51764a0587c01a16df3f00313efed2f7594a7b9`.
[CI run 37614480946](https://github.com/iTao-AI/night-voyager/actions/runs/37614480946)
failed `make compose-proof`: `expectPublicSurface` in
`web/e2e/fact-to-plan.spec.ts` read UUIDs from the closed handoff disclosure
through its whole-main text assertion. Visual closure did not remove DOM text.
The original failure log and local review captures remain retained; hosted
failure count is 1, with no retry or relabeling as a flaky failure. The job log
lists a failure screenshot/trace, but its diagnostic upload was skipped and
the run has no downloadable artifact; those runner files are not claimed as
locally retained images.

The repair follows progressive disclosure: source identities and their saved
projection explanation are rendered only while the user has opened the native
details element and are removed on close. Read facts, copy/fallback and business
authority remain unchanged. The native journey's regex, whole-main assertion,
timeout and gate are unchanged; no shared-frame relocation was made.

Focused DOM regressions were RED before this repair and GREEN afterward. The
local full suite, static/build checks and 17 actual fixture/browser cases passed
on the repaired implementation. This is a cheap consumer guard proof; it does
not prove a successful subsequent native or hosted run. The repaired commit is
local only and requires separate acceptance and a concrete hosted route before
the draft PR can satisfy merge gates.

Clipboard copy is initiated by the user. Already initiated operating-system
clipboard writes cannot be recalled after navigation; delayed completion cannot
attach stale feedback or fallback to a new summary. No external message is sent.
Native recovery, hosted checks, merge, release and deployment are not newly
verified by this local frontend slice.
