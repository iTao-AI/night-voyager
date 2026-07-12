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
Policy derives the bounded Australia/Japan/Malaysia outcomes; callers cannot
submit outcome or required-claim authority. Narrative, ranking and ordering
have no authority.

The checked-in M3A manifest is public-safe synthetic data. Validate it without
a database using `scripts/seed_demo.py --validate-only`.
