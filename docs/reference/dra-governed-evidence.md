# Governed DRA evidence reference

Candidate import, atomic human verification/promotion, and governed mixed
PlanningRun generation are implemented as a deterministic local proof. The
existing `generate_planning_run_v1` path remains all-synthetic, and `/demo` is
unchanged. Live provider proof was not run and remains separately authorized.

## Pinned consumer contract

| Field | Exact value |
| --- | --- |
| DRA release | `v0.1.3` |
| DRA commit | `87b2a8e335385eb865086f7a69fe2b190567cfa2` |
| Contract schema | `dra.downstream-consumer.v1` |
| Copied fixture SHA-256 | `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157` |
| Baseline source pack | `50000000-0000-0000-0000-000000000001`, version `1` |
| Canonical manifest SHA-256 | `84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28` |
| Raw manifest SHA-256 | `5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25` |

The import DTO is strict and frozen. It accepts the exact producer pins,
bounded request/run identities, canonical `research-report.md`, and ordered
six-field Evidence projections. Artifact content exists only at the import
boundary; persistence retains its byte length and SHA-256, never Markdown.
Exactly one ordered Evidence item must be promotable through a public HTTPS
source. Candidate authority is fixed to `untrusted_candidate`.

## Authority surface

Migration `0005` adds exactly two forced-RLS tables:

- `app.dra_research_candidates`, an immutable candidate ledger;
- `app.external_evidence_verifications`, an immutable terminal decision/audit ledger.

Only `night_voyager_api` may execute
`app.import_dra_research_candidate(...)` and
`app.verify_and_promote_dra_candidate(...)`. Runtime roles have no direct DML;
`night_voyager_worker` has no execute grant. Import is candidate-only. Approval
atomically creates one derived source-pack revision and exactly one
`australia_program_fit -> program_fit -> externally_verified` Evidence while
copying the other accepted synthetic facts. Rejection creates no pack or
Evidence. There is no later promotion command or table.
Any approve or reject decision makes the whole candidate terminal. A rejected
source therefore requires a newly imported candidate before another decision.

## Governed mixed-planning surface

Migration `0006` adds no table. It exposes one worker-only
`app.load_governed_mixed_planning_snapshot(...)` authority and extends the
existing task functions for the exact operation pair:

- `generate_planning_run_v1` with `deterministic_planning` / `m4a-v1`;
- `generate_governed_mixed_planning_run_v1` with
  `governed_mixed_planning` / `dra-mixed-v1`.

The mixed snapshot requires the current Case revision, `m3a-policy-v1`, and an
approved promoted source-pack revision. It permits exactly this external
mapping:

```text
australia_program_fit -> program_fit -> externally_verified
```

All remaining accepted facts are exact copies of the synthetic baseline. The
worker validates the complete strict snapshot and materializes a bounded
`GovernedMixedPlanningInput`; callers cannot select authority, adapter pair,
baseline pins, or promoted identities. The existing AgentTask queue, leases,
retry policy, fencing, events, SSE, AdvisorReview, DecisionBrief, family
decision, receipt, and timeline are reused without a second workflow.

The deterministic offline closure is exercised by `make db-check` and
`make compose-proof`. It imports the copied fixture, performs the atomic human
approval, creates the mixed task, reaches `review_required`, and closes through
the existing advisor and family gates. It does not call DRA or add browser
integration; the connected `/demo` remains the synthetic M5 walkthrough.

The three assigned-advisor HTTP routes are documented in
[HTTP API v1](http-api-v1.md). Mutations require exact Origin, session CSRF,
and idempotency. `NV003` is stale state; `NV006`, `NV011`, and `NV012` are
closed contract conflicts; `NV007` is non-enumerating authorization; `NV008`
is idempotency conflict. Unknown, permission, and connection failures propagate.

## Privacy and trust boundary

Public candidate responses expose only bounded server-generated identities and
terminal status. They exclude source bytes, Markdown, snippets, provider
payloads, credentials, local paths, token/cost data, traces, and internal
baseline pins. Caller DTOs cannot declare `externally_verified`, promoted IDs,
tenant claims, role, or authority.
