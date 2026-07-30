# ADR 0014: Advisor-governed multimodal Evidence composition

Status: Accepted

Implementation status: Slice 0 is approved for implementation; later slices remain
gated by exact merged readiness receipts.

ADR 0014 extends the read-only Evidence boundary in ADR 0005 without weakening its
artifact, authority, optional-dependency, or cleanup rules.

## Decision

1. Night Voyager remains the sole consumer and business system of record. MKE and
   DRA are independent, read-only, untrusted Evidence producers. They do not call
   each other, share mutable state, select a Case, approve Evidence, or mutate Night
   Voyager.
2. Slice 0 is a file-based, provider-free falsification gate over one frozen,
   public-safe synthetic suite. Its sealed evaluation window creates no product
   candidate and writes no Night Voyager business table, API route, Web behavior,
   Case, source pack, revision, PlanningRun, task, family decision, timeline, or
   execution state.
3. MKE is consumed only through the exact tagged v0.1.5 source archive, locally built
   wheel, closed `search_library_v2` and `read_evidence_v1` schemas, and a task-owned
   disposable store sealed read-only before evaluation. Moving checkouts, v1
   fallback, real providers, private corpora, and post-seal ingest are prohibited.
4. The DRA arm consumes only `GovernedDraBaselineExportV1`: already governed,
   typed Night Voyager rows with their original producer and advisor-verification
   provenance. Current DRA Markdown is never parsed to manufacture typed facts.
5. Evaluation identity and product persistence identity remain distinct.
   `evaluation_canonical_source_id` measures the frozen eligible source independent
   of locator, while `source_entry_canonical_id_v1` covers the complete existing
   `SourcePackEntryV1` business projection. Producer opaque identifiers remain
   observation trace only.
6. The evaluator runs control, governed DRA baseline, MKE, and deterministic
   combined arms. Guardrails are vetoes. Required `capped`, incomplete, non-active,
   or unavailable retrieval is `inconclusive`, never a partial pass or a
   `no_incremental_value` result.
7. Slice 0 records exactly one terminal disposition:
   `incremental_value_confirmed`, `no_incremental_value`, `inconclusive`, or
   `evaluation_invalid`. Only an exact merged `incremental_value_confirmed`
   `StageReadinessReceiptV1` may unlock candidate authority. A local result,
   unmerged candidate, or receipt bound to another tree cannot unlock later work.
8. Slice 1, if unlocked, is MKE-specific and requires one assigned-advisor terminal
   decision. Slice 2, if unlocked, composes accepted input through one Night
   Voyager-owned PostgreSQL authority and generation-guarded worker finalization.
   A generic provider framework and runtime multi-agent architecture are rejected.

## Consequences

The project gains a falsifiable evaluation lane before any product persistence or
workflow complexity. A non-confirming result is valid and ends this direction
without threshold, corpus, producer, evaluator, or holdout substitution.

Producer archives, store state, receipts, and cleanup are task-owned and bounded.
Retrieved content and producer metadata remain inert data: they cannot choose tools,
alter tool arguments, approve, promote, plan, or mutate business state.

The only eligible public claim is the exact frozen-suite result and its stated
limits. This ADR does not establish source truth, citation correctness, provider
quality, statistical generalization, real-user impact, production deployment, or
admissions outcomes.

## Rejected alternatives

A direct MKE-to-DRA collaboration loop is rejected because it creates no product
authority and would blur independent provenance. A generic provider candidate bus
is deferred because no cross-provider persistence abstraction is justified.
Automatic promotion is rejected because producer confidence cannot replace
deterministic policy and assigned-advisor authority. Reusing revealed holdouts after
an evaluator or threshold change is rejected because reveal is irreversible.
