# Governed DRA evidence reference

PR 1 is implemented: candidate import and atomic human verification/promotion are implemented.
The governed mixed PlanningRun is not implemented. The existing
`generate_planning_run_v1` path remains all-synthetic, and `/demo` is unchanged.

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
Candidate authority is fixed to `untrusted_candidate`.

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
