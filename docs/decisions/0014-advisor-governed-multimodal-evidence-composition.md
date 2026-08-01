# ADR 0014: Advisor-governed multimodal Evidence composition

Status: Accepted

Implementation status: Slice 0 permanently ended in a local `evaluation_invalid` safe stop
after its one-way reveal; later slices remain locked and no readiness receipt exists. PR #87
is merged, and hosted CI/publication cleanup are complete. The approved architecture and its
historical execution record remain the public contract.

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
   `StageReadinessReceiptV1` may unlock candidate authority. Slice 0 has no predecessor;
   every later stage receipt must bind the exact prior merged stage, merge commit/tree, receipt
   digest, legal disposition, and the complete recursively verified predecessor chain. The verifier
   canonicalizes the exact hosted checks `python`, `frontend`, and `compose` and rejects missing,
   duplicate, extra, non-pass, or URL-mismatched readback. A local result, unmerged candidate,
   evaluation-invalid/non-confirming predecessor, or receipt bound to another tree cannot unlock
   later work.
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

## Publication and stage-unlock boundary

Only a PR that intends to unlock the next stage and has an allowed terminal disposition plus its
committed proof artifact carries `StageReadinessCandidateV1`. After merge, that candidate becomes
`StageReadinessReceiptV1`. GitHub `Ready` means code is merge-ready; it does not mean the next stage
is unlocked. A terminal safe-stop PR with `evaluation_invalid`, `no_incremental_value`, or
`inconclusive` (or missing required proof) may be marked `Ready` and merged after exact-head CI,
platform review, and format gates pass. Its body must state `no stage unlock` and must not contain
`StageReadinessCandidateV1`, `StageReadinessReceiptV1`, or fabricated proof. Only an exact merged
`incremental_value_confirmed` `StageReadinessReceiptV1` unlocks the next stage. A safe-stop merged
body records only actual merge/tree/check/main-sync/cleanup facts and safe-stop non-claims.

## Slice 0 execution disposition

The local Slice 0 execution permanently ended with terminal status `evaluation_invalid`. The one-way
reveal succeeded once. The frozen evaluator then rejected a noncanonical input path before
MKE capture because the operator invocation did not expand its temporary run-root variable
for the evaluator command. No `MkeCaptureArtifactV2`, Slice 0 terminal receipt, or
information-gain result exists.

The revealed holdout suite is retained as retired evidence and MUST NOT be reused. This is a
fail-closed operator/evaluation-protocol safe stop; it is neither evidence of
`no_incremental_value` nor evidence about MKE or DRA quality. No candidate or product
persistence, Slice 1/2 work, v0.1.6 release, provider action, production claim, or
incremental-value claim is authorized for this direction. PR #87 is merged; hosted CI and publication cleanup are complete. The executed `evaluation_invalid` Slice 0 follows the
safe-stop publication path, and no later stage is unlocked.

## Rejected alternatives

A direct MKE-to-DRA collaboration loop is rejected because it creates no product
authority and would blur independent provenance. A generic provider candidate bus
is deferred because no cross-provider persistence abstraction is justified.
Automatic promotion is rejected because producer confidence cannot replace
deterministic policy and assigned-advisor authority. Reusing revealed holdouts after
an evaluator or threshold change is rejected because reveal is irreversible.
