# Domain and source-manifest reference

M3A uses immutable `StudentCase` revisions with separate student and family
preferences. A source pack version declares relative paths and lowercase
SHA-256 hashes. `EvidenceRef` binds one claim to one declared entry and records
one authority value: `untrusted_candidate`, `accepted_synthetic_demo`, or
`externally_verified`.

Unknown Cost or Ranking values remain null and are never zero-filled. Policy
accepts exactly one fully evidenced `recommended_with_condition` route for
`review_required`; recommendation cardinality or missing Evidence blocks, and
invalid/untrusted material fails. Narrative and ordering have no authority.

The checked-in M3A manifest is public-safe synthetic data. Validate it without
a database using `scripts/seed_demo.py --validate-only`.
