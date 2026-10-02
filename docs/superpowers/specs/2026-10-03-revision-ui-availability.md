# Revision UI availability and explicit role handoff

Status: Implemented and locally verified on 2026-10-03; hosted delivery is separately gated.
Delivery: maintainer-directed local repair, based on `05672d86667a483d7f5da2b809f5d1a6988cb602`. Local changes, verification and semantic commits only; hosted delivery is separately gated.

## Approved scope

- Derive revision choices from the current Case's current server confirmed-fact projection. Budget-only defaults to budget but retains explicit parent preparation; country-only offers countries; both retain country/role selection. Missing, stale, wrong-Case or non-editable projections fail closed with distinct guidance. Missing country confirmation is not repaired by reload.
- Preserve submitted intention and its exact replay data across recovery. A stale or unavailable submitted fact must remain visible and cannot silently become a different mutation. Explicit opposite-fact preparation can preserve the original replay while opening the current participant's editor.
- Waiting role panels ask for the explicit next action before describing revoke/mint as complete. Actual role authority, revocation, minting, consent and write guards remain unchanged. The revision workspace identifies the actual participant.
- Separate receipt milestone labels from the existing localized dates without changing dates, arithmetic or layout.

## Non-scope

No backend validation, API/DB contract, preference promotion, first-country capture/confirmation flow, dependency addition, provider, release or deployment change.

## Observable acceptance

Budget-only, country-only, both, no editable facts, missing/stale/wrong-Case projection, refused budget and restored intention regressions. Explicit role preparation creates no proposal; existing same-tab failure/recovery, exact replay and identity/version guards remain covered. English receipt label/date separation is rendered. Focused and full frontend tests, lint/typecheck/build and the affected normal-entry plus bilingual browser/native proof pass. Original QA evidence and unrelated resources remain intact.

## Local verification

The full frontend suite passed 47 files / 574 tests, plus lint, typecheck and
production build. The normal intake path exercised a budget-only confirmed
projection through parent revision, fresh advisor review and a direct family
receipt. Chinese and English native recovery proofs passed at 1440 and 390 pixels,
including zero session writes before role consent, real revoke/mint after consent,
same-tab 503 recovery, qualified terminal retry, SSE, fresh review and receipt.
No first-country confirmation flow or hosted delivery is implied.
