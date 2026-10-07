# Saved reassessment handoff acceptance

Status: local application implementation and frontend checks passed; final
branch review pending. Hosted delivery and publication are separate.

Verification date: 2026-10-07. Base:
`0017d364995ca59e9b71cad48433d9e485fb6c3a`. Application implementation:
`8134d94ff29a05f94e78288a2a0c56c0a57b072e`.

## Scope

This is a read-only bilingual consumer of an already saved reassessment. It
adds specific facts, source disclosure and user-initiated text copy with a
selectable fallback. It preserves the Stop and `pending_future_authorization`.
There is no backend, migration, lockfile, worker, receipt, consent, successor,
recovery or replanning-authority change.

## Current local checks

- `npm --prefix web test`: 54 files and 663 tests passed. The new projection/UI
  tests cover the saved checkpoint, blocked/deadline facts, mismatched reference,
  checkpoint/execution, absent detail, context anchors, export privacy, clipboard
  failure/unavailability and invalidation across state, role and locale changes.
- `npm --prefix web run lint`: passed.
- `npm --prefix web run typecheck`: passed.
- `NEXT_TELEMETRY_DISABLED=1 npm --prefix web run build`: passed.
- `web/e2e/reassessment-handoff.spec.ts`: 17 actual Chrome browser tests passed
  against a task-owned built Next.js server. Chinese and English, 1440/390,
  accepted blocked/deadline fixtures, native clipboard read/write, fault-injected
  clipboard denial, source disclosure and context/session invalidation passed.
  Exported text matched the displayed rows and excluded synthetic actor IDs.
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

Clipboard copy is initiated by the user. Already initiated operating-system
clipboard writes cannot be recalled after navigation; delayed completion cannot
attach stale feedback or fallback to a new summary. No external message is sent.
Native recovery, hosted checks, merge, release and deployment are not newly
verified by this local frontend slice.
