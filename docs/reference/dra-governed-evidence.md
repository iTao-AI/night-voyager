# Governed DRA evidence reference

Candidate import, atomic human verification/promotion, and governed mixed
PlanningRun generation are implemented as a deterministic provider-free proof.
AdvisorReview, family decision, and final evaluation are included. The existing
`generate_planning_run_v1` path remains all-synthetic, and `/demo` is unchanged.
Two separately authorized bounded live attempts returned 25 and 83 same-run
Evidence rows, all `uncited`, and both stopped before candidate import. No third
provider attempt is authorized; strict live acceptance remains incomplete and
capability status remains `INCOMPLETE_PENDING_LIVE_ACCEPTANCE`.

## Pinned consumer contract

| Field | Exact value |
| --- | --- |
| Historical fixture DRA release | `v0.1.3` |
| Historical fixture DRA commit | `87b2a8e335385eb865086f7a69fe2b190567cfa2` |
| Contract schema | `dra.downstream-consumer.v1` |
| Copied fixture SHA-256 | `cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157` |
| New live-import DRA release | `v0.1.6` |
| New live-import DRA commit | `7d43324b469cb5e445c2e8be83af3be4d841cf1c` |
| New live-import DRA tag object | `9e0b0b443c435cf636dfce932c3c77d91d0a43e4` |
| Strict post-release DRA ref kind | `commit` |
| Strict post-release DRA commit/ref | `01ba21f2996769e68cbc88f4bb0596740df27f6b` |
| Strict profile | `generic-strict-citation@1` |
| Strict proof schema | `dra.strict-citation-profile.v1` |
| Baseline source pack | `50000000-0000-0000-0000-000000000001`, version `1` |
| Canonical manifest SHA-256 | `84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28` |
| Raw manifest SHA-256 | `5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25` |

The historical copied fixture remains byte-identical and readable under its
v0.1.3 producer identity. Migration `0010` historically admitted the exact
v0.1.6 producer tuple. Current migration `0011` preserves that legacy branch and
requires new strict work to use the separate exact-commit tuple above. The strict
profile is not included in DRA v0.1.6.

The closed v1/v2 import DTOs accept bounded request/run identities, canonical
`research-report.md`, and ordered six-field Evidence projections. Artifact
content exists only at the import boundary; persistence retains its byte length
and SHA-256, never Markdown. Exactly one ordered Evidence item must be
promotable through its original public HTTPS raw URL. Candidate authority is
fixed to `untrusted_candidate`.

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

Migration `0010` closes new import authority to the exact v0.1.6 producer tuple
without rewriting or invalidating historical rows. It adds the API-only
`app.project_dra_live_outcome(...)` read boundary, which returns the bounded
candidate and verification outcome needed by live reconciliation. The function
is migrator-owned and tenant-scoped; the API receives only `EXECUTE`.
`night_voyager_api` receives no new table DML, the worker receives no new
authority, and forced RLS remains enabled. Downgrade removes only the additive
v0.1.6 boundary after refusing incompatible live history.

Migration `0011` adds a strict overload without replacing the legacy
`app.import_dra_research_candidate(...)` signature. Exact function identity is
the pair of function name and `oidvectortypes(p.proargtypes)`. Both import
signatures and the exact verification signature are API-only;
`night_voyager_worker` and `PUBLIC` cannot execute them. The worker receives no
new table authority and forced RLS remains enabled.

Strict rows store repository, commit ref, contract, fixture, profile version,
proof schema, request identity, and observed profile as one closed identity.
Legacy rows cannot be inferred as strict and mixed identities fail closed.
Downgrade to `0010` refuses before mutation when strict history exists; an empty
or legacy-only database can downgrade safely.

## Provider-free live foundation

The PR A live boundary is deliberately narrower than a provider workflow:

- `/health` is the only preflight endpoint.
- A live run is accepted only when request ownership, exact producer identity,
  artifact metadata, and ordered Evidence all agree.
- The selected raw URL retains its original string identity through candidate
  import and later source attestation; URL normalization cannot grant authority.
- Ambiguous create delivery is not replayed automatically. A separate,
  authorized recovery action is required.
- Evaluation observes persisted projections and receipt identities only.
  Canonical evaluation bytes exclude clocks, durations, and ambient time.
- Required CI uses deterministic scenario data and a fake transport. It does
  not contact a provider or promote a candidate.

PR A, PR B, PR C, and the strict-consumer prerequisite are implemented
provider-free. They supply no governed-live success claim.

## Stage 1 live-capture boundary

PR B adds a closed command sequence: `freeze-intent`, `preflight-live`,
`capture-live`, `select-and-import`, `reconcile-create`, `resume-poll`,
`inspect-recovery`, `rehearse-capture`, and `cleanup`.

`capture-live` owns one frozen attempt. It validates exact request bytes immediately
before provider access, polls on the frozen monotonic deadline and interval, accepts
only the strict terminal projection, persists a private artifact plus same-run
Evidence inventory, and stops at `operator_action_required`. An operator-visible
artifact pathname is returned only while it resolves to the same descriptor-bound
directory and artifact; pathname replacement fails closed. Operator selection is a
separate URL-only, provider-free action. `select-and-import` accepts exactly one
byte-identical cited raw URL, imports only that selected Evidence row through existing
assigned-advisor authority, confirms `UNTRUSTED_CANDIDATE`, and removes artifact
bytes.

Ambiguous create delivery requires an explicit exact replay. Poll recovery observes
only the same run. Both recovery paths require an exact match to their durable
receipt and validated predecessor chain before provider access. No second workflow
or remote cancellation exists. Recovery
receipts contain identity hashes and bounded metadata, never query, artifact,
credential, session, provider payload, or environment values. Stage 1 performs no
source snapshot validation, promotion, planning, AdvisorReview, or family decision.
Stage 2–4 now reuse the existing product authorities. Stage 2 validates an
operator-supplied snapshot using descriptor-bound no-follow I/O and binds the
exact selected raw URL, length, and SHA-256 before promotion. Stage 3 observes
the existing governed task, five-field Skill pin, terminal event/SSE, PlanningRun,
and AdvisorReview. Stage 4 records the family decision, DecisionReceipt, and
TimelinePlan. Each stage has a distinct acknowledgement and lost-ack
reconciliation; no session material enters a receipt.
Real HTTP transport loss is mapped to the bounded ambiguity type at the mutation
POST boundary. Fresh-process task and AdvisorReview recovery are exact
actor/idempotency-key reads over existing product records; they are not
process-local caches or generic read APIs.

The outcome inspector executes only the current migration `0011` form of
`app.project_dra_live_outcome(...)`. It has no table `SELECT`, generic SQL, DML,
privileged role, or cross-tenant path. `decision_recorded` is not completion;
only the complete evaluator may produce `closure_passed`.
The capture receipt additionally binds the domain-separated provider create key,
the accepted run, and every observed run identity. The two provider-cardinality
assertions require one unique key and one unique accepted run; the consumed
boolean alone is not evidence of either assertion.

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
`make compose-proof`. It imports the checked-in v0.1.6 scenario candidate,
performs the atomic human approval, creates the mixed task, reaches
`review_required`, and closes through the existing advisor and family gates.
The historical copied v0.1.3 fixture retains its separate compatibility proof.
Neither path calls DRA or adds browser integration; the connected `/demo`
remains the synthetic M5 walkthrough.

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
Lost acknowledgements retain a bounded stage-specific ambiguity receipt containing
only the parent receipt identity, domain-separated mutation key, exact request
hash, and target identity hash. A current result is accepted only when all
request/result fields match; partial or conflicting authority fails closed.

Final trajectory evaluation accepts only the typed `capture`, `promotion`,
`review`, and `decision` receipts. Caller-supplied assertion identifiers are not
authority. The current migration `0011` projection correlates the promoted mapping
with the exact task execution, terminal event/SSE cursor, five-field Skill pin,
AdvisorReview/brief, family decision, DecisionReceipt, and TimelinePlan.
