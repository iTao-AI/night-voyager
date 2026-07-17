# Domain and source-manifest reference

M3A uses immutable `StudentCase` revisions with separate student and family
preferences. A source pack version declares relative paths and lowercase
SHA-256 hashes. Each entry records snapshot date, publisher, institution,
canonical URL, freshness rule, redistribution class, evidence class, coverage,
and known gaps. `EvidenceRef` binds one exact covered claim to that entry hash,
tenant, pack and version. Checked-in inputs may use only
`accepted_synthetic_demo`; `externally_verified` cannot be caller-asserted.

`BudgetEnvelope` distinguishes refusal, preferred budget, hard ceiling and a
bounded elasticity. Complete `CostEvidence` uses Decimal FX, explicit intake and
period, tuition/living amounts, FX source/date, and three Evidence references.
The bounded M3A fixture accepts `AUD` as the ISO 4217 source currency and binds
tuition, living, FX and ranking IDs to their exact claims. Duplicate claims or
role mismatches are invalid provenance.
Policy derives the bounded Australia/Japan/Malaysia outcomes; callers cannot
submit outcome or required-claim authority. Narrative, ranking and ordering
have no authority.

The checked-in M3A manifest is public-safe synthetic data. Validate it without
a database using `scripts/seed_demo.py --validate-only`.

Migration `0005` adds a separate immutable DRA candidate ledger. Import stores
only bounded identities, ordered Evidence metadata, artifact byte length/hash,
and fixed `untrusted_candidate` authority; it does not create a source pack or
Evidence. An assigned advisor may atomically approve exactly one external
`australia_program_fit` claim or reject it. Approval creates one derived source
pack with that one `externally_verified` Evidence and exact synthetic copies of
all other accepted facts. Public caller DTOs cannot assert that authority.
See [the governed DRA evidence reference](dra-governed-evidence.md).

Migration `0006` adds no persistence table. Its worker-only snapshot boundary
loads the exact promoted pack, verifies the single allowlisted external
`australia_program_fit` claim, and requires every other accepted fact to match
the canonical synthetic pack. `PlanningInput` remains the public all-synthetic
contract; the mixed path uses the separate strict
`GovernedMixedPlanningInput` type.

Migration `0007` adds a separate governed collaboration authority. A shared
`MessageEvent` is communication only. A participant-authored `MemoryCandidate` is a
strict proposal pinned to one Case revision, not a fact. Only an assigned advisor's
terminal confirmation creates a versioned `ConfirmedFact`, clones the current Case
revision, records the complete current fact-reference set, and advances the Case by
compare-and-swap in one transaction. Rejection creates no fact or revision.

Confirmed facts retain source-message, subject, candidate, verification, advisor,
version, and supersession lineage. Participant projections expose only current safe
values and their own proposal status; advisor projections retain the bounded
authority history. See [Collaboration and confirmed facts](collaboration-and-confirmed-facts.md).
