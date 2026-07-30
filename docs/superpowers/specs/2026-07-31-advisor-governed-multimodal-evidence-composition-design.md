# Advisor-Governed Multimodal Evidence Composition Design

**Status:** Re-audited and ready for implementation mandate
**Consumer and system of record:** Night Voyager
**Read-only evidence producers:** Multimodal Knowledge Engine (MKE) and Decision Research Agent
(DRA)
**Target release:** Night Voyager v0.1.6 only if all three slices complete
**Public claim level:** controlled, provider-free portfolio proof; no production or source-truth claim

## 1. Executive summary

Night Voyager should not build a feature merely because three repositories can be connected. The
next stage is justified only if a second, independently governed evidence source closes a
pre-registered decision gap that the current controlled Night Voyager evidence path does not close.

The stage is deliberately falsifiable:

1. **Slice 0 — read-only evaluation.** Night Voyager evaluates the same frozen Case/query suite under
   four arms: control, existing governed DRA baseline, MKE Evidence, and their deterministic
   combination. It performs no business mutation.
2. **Slice 1 — candidate governance.** Only a passed Slice 0 may introduce an MKE-specific immutable
   untrusted candidate and one assigned-advisor terminal decision: accept as planning input or
   reject.
3. **Slice 2 — atomic composition.** Only an accepted candidate may enter one Night Voyager-owned
   PostgreSQL transaction that stages a new source-pack/revision/planning task. Successful worker
   finalization atomically activates the successor; bounded terminal failure exposes an explicit
   assigned-advisor safe-abandon action that restores the still-current prior plan. Existing
   advisor, family-decision, planning-revision, timeline, execution, and recovery authorities remain
   authoritative.

If Slice 0 returns `no_incremental_value`, `inconclusive`, or `evaluation_invalid`, the stage ends
without candidate persistence, product integration, or a v0.1.6 release for this direction. That is
a valid engineering result.

This is not a runtime multi-agent system. MKE and DRA do not call each other, debate, delegate, or
share mutable state. Night Voyager is one governed workflow consuming two independent, read-only
evidence paths. Public documents therefore use **Advisor-Governed Multimodal Evidence Composition**.
The phrases “three-project” and “multi-agent” are not product or architecture claims.

## 2. Verified baseline and producer locks

### 2.1 Night Voyager

The planning baseline is the published Night Voyager v0.1.5 release:

- commit `3a82721a86f65353b849e9ee93050912d0cb079a`;
- tree `bbe32e5629b2758421d80598dbca1c795934fcb5`;
- annotated tag object `44000702c75fa3002e12245b8d7f762b564db944`;
- migration head `0015`.

Night Voyager already owns:

- tenant, Case, participant, role, revision, and current-state identity;
- immutable source-pack and planning-run lineage;
- assigned-advisor terminal verification;
- PostgreSQL atomic business mutations and forced-RLS boundaries;
- fresh AdvisorReview and current-only FamilyDecision authority;
- timeline planning, governed execution, recovery, and browser-to-database proof;
- a compatibility-only MKE v1 Search/Ask lane that is transient and non-promoting.

No v0.1.5 claim says that an MKE result can be persisted, accepted, composed, or used to mutate
planning.

### 2.2 MKE

Slice 0 binds the published MKE v0.1.5 release:

- annotated tag object `1ca0a0b348638369e8407270ca5f363b0e551a9e`;
- peeled commit `d258c10dc40bd9eccd67c858b56f4e4cf5fe4610`.

The eligible product-independent path is the local, read-only MCP contract:

- `search_library_v2`;
- `read_evidence_v1`;
- closed request/response schemas;
- loss-aware `complete|more_available|capped` retrieval state;
- policy-bound cursor identity;
- Source, Publication, Run, locator, Evidence digest, and exact UTF-8 chunk identity;
- terminal Evidence text digest;
- `content_trust="untrusted_evidence"`.

MKE does not decide a Case, accept a source pack, verify a claim, create a candidate, plan, or
execute an action. Its text and metadata are untrusted data.

The unreleased `codex/retrieval-coverage-stage1-spec` branch is not a capability dependency. A future
stage may separately evaluate ideas from it, but v0.1.6 cannot require, merge, or claim that branch.

### 2.3 DRA

Compatibility preflight binds the published DRA v0.1.8 release:

- annotated tag object `f828606741f636bca7ddbb66244ca60019eaa3c8`;
- peeled commit and current main at audit time
  `cb1f4660ee4ac7d81b04ffea014362e933487e61`.

DRA's stable consumer contract provides run-level Evidence identity and untrusted rendered output.
Its strict citation profile proves the presence of at least one exact admitted URL in the canonical
artifact. It does not prove citation correctness, completeness, entailment, source truth, or a typed
business fact.

The public consumer contract explicitly prohibits downstream parsing of result Markdown to
manufacture typed claims, limitations, conflicts, dates, or evidence references. Slice 0 therefore
does **not** normalize a current DRA Markdown result into new `fact_id` values.

The DRA arm uses `GovernedDraBaselineExportV1`, a frozen export of Night Voyager's existing, already
advisor-governed typed DRA-derived baseline. Its closed schema binds the typed row, Case/revision,
decision dimension, original producer/profile/run/Evidence identity, advisor verification receipt,
and export digest. A validator rejects missing or contradictory provenance. The export never parses
Markdown. If the required historical typed binding cannot be exported, Slice 0 is `inconclusive`.

A DRA v0.1.8 provider-free run may separately prove that the current consumer/profile remains
compatible. Its exact artifact bytes, terminal state, profile proof, and validator result are
recorded, but it cannot retroactively become the origin of historical Night Voyager rows or create
new typed facts.

## 3. Problem and falsifiable hypothesis

### 3.1 Problem

Night Voyager already demonstrates governed planning and execution. Adding another retrieval path is
valuable only when it supplies a source-bound observation that:

- is absent from the existing source pack and governed DRA-derived baseline;
- is relevant to a pre-authored decision gap;
- remains distinguishable from duplicates and contradictions;
- cannot execute instructions or cause a mutation;
- can later be accepted only by the assigned advisor under current Case/revision authority.

### 3.2 Frozen-suite hypothesis

The only eligible Slice 0 claim is:

> On a frozen, public-safe synthetic suite, the exact MKE v0.1.5 read-only MCP path contributes
> source-bound evidence units that close pre-registered Night Voyager decision gaps not closed by the
> control or existing governed DRA-derived baseline, while decoys remain non-novel, conflicts remain
> explicit, and all evaluation paths produce zero business mutation.

This is named `incremental_evidence_value_on_frozen_suite`. It is not a statistical population
estimate, a general information-gain claim, a producer ranking, or a source-quality claim.

## 4. Options and decision

| Option | Product truth | Advantages | Risks | Decision |
| --- | --- | --- | --- | --- |
| A. Consumer evaluation only | Night Voyager can compare bounded evidence paths without persistence | Lowest risk; strongest falsification discipline | No durable product loop | Mandatory Slice 0 |
| B. MKE-specific candidate and composition | Proven MKE Evidence can enter existing human/PostgreSQL governance | Reuses mature authority; strongest end-to-end portfolio story | Two migrations, recovery, UI, and release cost | Selected behind A |
| C. Generic provider-candidate framework | Multiple providers share a generalized bus/ledger | Potential future reuse | Premature abstraction, semantic erasure, double authority, broad migration surface | Rejected/deferred |

Option B plus the mandatory Option A gate has the highest expected portfolio value. It demonstrates
retrieval/tool contracts, evaluation, adversarial trust boundaries, human authority, transactional
state, recovery, and end-to-end verification. Option C would add architecture vocabulary without
evidence that a common abstraction is needed.

## 5. Authority graph

```text
MKE v0.1.5 tagged archive                    DRA historical governed baseline
read-only MCP Evidence                       exported from Night Voyager
untrusted text + provenance                  typed rows + original provenance
           |                                              |
           +-------------------+--------------------------+
                               |
                               v
                 Night Voyager Slice 0 evaluator
                 frozen suite / four arms / no DB
                               |
          no value / inconclusive / invalid ----> STOP
                               |
                    exact merged pass receipt
                               |
                               v
             Night Voyager MKE-specific candidate
             immutable untrusted evidence projection
                               |
                   assigned advisor terminal choice
                    reject | accept as planning input
                               |
                          accepted only
                               |
             existing advisor request_revision review
                               |
                               v
            Night Voyager PostgreSQL composition lock
        Case + current revision + source pack + candidate
                               |
                               v
       successor source-pack version / revision / queued task
                               |
                       worker claim / bounded attempts
                         | success          | terminal
                         v                  v
       atomic activate successor       advisor abandon
       revision + PlanningRun           prior plan stays current
                               |
                               v
       existing AdvisorReview -> FamilyDecision -> Timeline
                    -> governed execution/recovery
```

Only Night Voyager writes business state. MKE and DRA remain independent and read-only. There is no
shared mutable state, producer callback, producer-to-producer call, background promotion, or
automatic human decision.

## 6. Trust, tool, and instruction boundary

All retrieved text, tool output, producer metadata, and rendered evidence are data. They may contain
instructions, prompt injection, malformed Unicode, HTML, links, or claims that sound authoritative.
None of that content can:

- select a tool;
- alter a tool argument;
- create or mutate a database row;
- approve a candidate;
- change a role or session;
- create a planning task;
- approve a plan;
- make a family decision;
- start timeline execution.

The consumer uses closed schemas, fixed tool names, bounded parameters, exact producer locks, and
deterministic parsers. Text is rendered inertly and escaped. URLs are displayed as provenance, not
executed. The application independently authorizes every mutation from current server and
PostgreSQL state.

MCP is an interoperability boundary, not business authority. Cursor, cache, model output, runtime
trace, or producer receipt never becomes a Night Voyager approval.

## 7. Slice 0 — read-only frozen-suite evaluation

### 7.1 Product truth and non-goals

Slice 0 proves only that the exact consumer can detect bounded incremental evidence value on one
frozen suite. It is a non-default CLI/proof lane. It:

- creates no product candidate;
- writes no Night Voyager business table;
- changes no Case, revision, source pack, PlanningRun, task, family decision, timeline, or execution;
- exposes no default product UI;
- calls no real provider or paid service;
- does not compare model intelligence or producer quality;
- does not justify a generic provider framework.

### 7.2 Roles and freeze sequence

Three distinct logical roles are frozen:

The admitted author package is `author_revision=2`. Revision 1 is permanently
`rejected_pre_admission` and is not an eligible compatibility source.

1. **Dataset author** (`dataset_author_id=independent-dataset-author-v2`) prepares public-safe
   synthetic Case/query/source material, decision gaps, expected source identities, and finalizes
   the holdout payload and evaluator-independent oracle before A4 begins.
2. **Evaluator implementer**
   (`evaluator_implementer_id=night-voyager-slice0-evaluator-v1`) builds the consumer,
   canonicalization, metrics, sensitivity tests, reveal validator, native lane, frozen-suite
   harness, and terminal verifier using only development cases and public commitments.
3. **Holdout custodian**
   (`holdout_custodian_id=independent-holdout-custodian-v2`) independently verifies and seals the
   pre-authored payload and oracle, keeps them in a separate non-mounted custody workspace, reveals
   them only after evaluator, harness, threshold, mapping, and eligible-source freeze, and signs
   the final receipt.

The evaluator implementer cannot also author or custody the holdout answers for the receipt being
used. Mechanical publication and review roles may overlap, but the pre-reveal content boundary may
not.

The governed DRA baseline is a
`deterministic_public_safe_synthetic_governed_fixture`. It demonstrates the typed contract and
does not claim a production or historical-user receipt.

`EvidenceLoopWorkspaceV1` makes that separation executable:

| Root | Owner/mode | Allowed content | Lifecycle |
| --- | --- | --- | --- |
| `input_root` | execution owner, `0700`; admitted files become `0400` | exact tagged source archives, source manifest, governed baseline export | created before setup; read-only after producer lock |
| `work_root` | execution owner, `0700` | extracted source, locally built wheel, bounded logs, intermediate captures | task-owned; never committed; deleted at teardown |
| `store_root` | execution owner during preparation, then evaluation reader; `0700` then files `0400` | disposable MKE database/library and active-set metadata only | mutable only during preparation; sealed before pre-registration; deleted at teardown |
| `receipt_root` | execution owner, `0700`; public-safe files `0600` | setup, pre-registration, evaluation, and diagnostic receipts without raw Evidence or local paths | copied into a committed fixture only when the plan names that exact public artifact |
| `custody_root` | holdout custodian only, `0700`; files `0600` | unrevealed holdout bytes and oracle | repo-external, unmounted and unindexed before freeze; never logged or committed as a path |

No receipt persists any absolute root. It records only logical role, basename, bytes, digest, mode
class, and lifecycle state. The evaluator process can see `input_root`, sealed `store_root`, and
public-safe `receipt_root`; it cannot mount, enumerate, or receive `custody_root`. The public
holdout manifest exposes only opaque Case identity, decision dimension, `payload_byte_length`,
`payload_sha256`, `oracle_byte_length`, and `oracle_sha256`; it contains no payload, oracle,
physical path, or outcome mapping. The one reveal operation uses
`nv.slice0.one-way-reveal.v1` as the custodian after pre-registration, validates every boundary,
and atomically copies only the exact public-safe holdout bytes to the committed dataset
destination.

A3 implements the public corpus, manifests, store seal, and freeze tooling. A3 does not issue
`PreRegistrationReceiptV2`. A4 completes the reveal validator, tagged-wheel lane, frozen-suite
harness, terminal verifier, and runner before final pre-registration. Development cases may be
used to implement and test those surfaces while holdout payload and oracle bytes remain
unreachable.

A `PreRegistrationReceiptV2` freezes after the complete evaluator and reveal/verification harness
exist and before any eligible holdout producer observation:

- Night Voyager, MKE, and DRA identities;
- MKE wheel, MCP schema, tool-name, and corpus/active-set digests;
- historical DRA-baseline export identity and provenance;
- exact clean HEAD and tree plus evaluator and harness path digests;
- environment and dependency identities;
- eight Case/query identities and decision dimensions;
- the eligible source matrix;
- development dataset bytes;
- four separate holdout payload and oracle lengths/digests without content;
- canonicalization and deduplication rules;
- mechanism, target, and guardrail metrics;
- terminal thresholds and failure taxonomy;
- the three distinct role identities and pre-reveal reachability scan;
- `nv.slice0.one-way-reveal.v1`;
- the exact post-reveal generated-file allowlist.

Any eligible holdout producer observation before receipt creation, source addition after freeze,
custody/hash/order/freeze/mutation drift, or evaluator change after reveal returns
`evaluation_invalid` and ends this direction. Development-case observations before final freeze
remain allowed.

After a holdout has been revealed, it can never become sealed again. Any evaluator, threshold,
mapping, eligible-source, or oracle change retires the revealed holdouts into the development set
and requires a new independently authored sealed holdout set and new hashes.

Custody is a filesystem boundary, not a promise inside one checkout. Before reveal, the evaluator
worktree contains only the four opaque holdout identities/dimensions and separate payload/oracle
byte lengths and SHA-256 digests. The holdout custodian's directory is not mounted, copied,
indexed, or included in evaluator command arguments. The freeze receipt records a pre-reveal scan
proving that no holdout bytes, answer keys, or custody path are reachable. Reveal copies the exact
pre-authored bytes once and verifies all hashes. A5 is one-shot reveal and execution only. No
code, test, evaluator, oracle, threshold, mapping, or eligible-source change is permitted after
reveal. Apart from the preregistered three fresh-process determinism runs, no retry or repair uses
revealed holdouts.

An exhaustive active miss maps to `no_incremental_value`; bounded incomplete or unavailable
retrieval maps to `inconclusive`; custody, hash, order, freeze, mutation, or identity drift maps to
`evaluation_invalid`. Every non-confirming disposition ends this direction. Only the exact
`incremental_value_confirmed` receipt may unlock the next slice.

### 7.3 Disposable MKE store preparation and seal

MKE store preparation is a distinct setup phase, not part of the zero-mutation evaluation window.
After T0 source eligibility is frozen, the execution owner:

1. creates one task-owned disposable MKE store;
2. ingests only the allowlisted public-safe corpus through the exact v0.1.5 contract;
3. records library creation and ingest receipts;
4. freezes store artifact, corpus manifest, active-set fingerprint, startup arguments, and tool
   schema digests;
5. closes write capability and reopens the store for read-only Search/Read;
6. records cleanup ownership.

The sealed evaluation window begins only after that receipt. During the window there is:

- zero MKE store mutation;
- zero Night Voyager business/domain mutation;
- no producer or provider mutation.

The setup receipt truthfully records that corpus preparation itself was a bounded task-owned
mutation. It is never hidden inside a “zero mutation” claim.

Every Slice 0 CLI has the same operator contract: `--help`, a machine-readable `--json` success
projection, stable exit codes, and one bounded diagnostic object with
`stage`, `code`, `problem`, `cause`, and `recovery`. The first stderr line is a public-safe recovery
instruction. Raw Evidence, query text, cursor, credentials, idempotency keys, and physical root
paths never appear in stdout/stderr or committed receipts.

### 7.4 Evaluation set

The committed suite contains eight public-safe synthetic cases:

- four development cases used to implement and debug the evaluator;
- four sealed holdouts:
  - one positive-increment `program_requirements` case;
  - one positive-increment `application_timeline` case;
  - one zero-novelty decoy whose MKE evidence duplicates the governed baseline;
  - one conflict-retention case where MKE and the governed baseline disagree.

Each case contains:

- synthetic Night Voyager Case and revision identity;
- a control source pack and confirmed family facts;
- a frozen export of existing governed DRA-derived typed evidence with original provenance;
- an allowlisted MKE v0.1.5 library/query fixture;
- closed decision dimensions and pre-authored evidence gaps;
- eligible source identities;
- expected duplicate and conflict relationships;
- evaluator-independent accept/reject oracle data.

Development results may change implementation but cannot decide the gate. Holdouts decide the gate
without threshold or mapping changes.

### 7.5 Four arms

Every case executes in a fresh process with identical Case/query and deterministic ordering:

1. `control`: control source pack plus confirmed family facts;
2. `dra_baseline`: control plus the frozen Night Voyager-governed typed DRA-derived baseline;
3. `mke`: control plus source-bound MKE Evidence captured through
   `search_library_v2`/`read_evidence_v1`;
4. `combined`: deterministic union of `dra_baseline` and `mke`, retaining provenance and conflicts.

The DRA arm is not a fresh DRA Markdown-to-fact parser. The MKE arm does not promote chunks into
truth. Night Voyager owns the evaluation dimension mapping in the frozen dataset.

The MKE capture is performed once per Case/query and reused byte-for-byte by the `mke` and
`combined` arms. It is not re-queried per arm. Each Case is bounded to one exact query, at most four
Search pages of at most 20 observations, at most 32 Evidence reads, a 10-second timeout per MCP
call, a 120-second Case budget, and a 1 MiB combined stdout/stderr cap. Any budget exhaustion,
truncation, or extra tool call is `inconclusive`.

### 7.6 MKE observation identity

Every eligible MKE observation binds:

- MKE tag object, peeled commit, wheel digest, MCP schema digest, and tool name;
- corpus manifest and active-set fingerprint;
- query and policy-bound cursor identity;
- Source fingerprint;
- Publication identity and revision;
- Run identity;
- locator and Evidence identity;
- Evidence bytes and digest;
- selected UTF-8 byte range;
- terminal full-text digest;
- retrieval terminal state.

`capped` is terminal but not exhaustive. A case that requires exhaustive coverage and returns
`capped` or incomplete pagination is `inconclusive`, not a partial pass.

MKE opaque identifiers are observation trace only and are not assumed stable across stores. They do
not define cross-producer duplication.

### 7.7 Canonical source identity, duplication, and conflicts

Slice 0 and the product database need related but deliberately different identities:

- `evaluation_canonical_source_id` is frozen from the T0 eligible-source manifest. It binds source
  bytes or admitted URL, publication identity/revision, and normalized full-content digest. It
  deliberately excludes the locator and is used only for the ablation measurement.
- `source_entry_canonical_id_v1` is SHA-256 of the complete canonical
  `SourcePackEntryV1` business projection excluding only tenant/pack/version/entry IDs. Its inputs
  are exactly the fields already persisted on `source_pack_entries`: declared path, source
  SHA-256, snapshot date, publisher, institution, canonical URL, freshness, redistribution class,
  evidence class, sorted coverage, and sorted known gaps. The identical algorithm can therefore
  run against a locked retained row or a frozen candidate source projection.
- `evaluation_canonical_evidence_id` binds `evaluation_canonical_source_id`, locator/range,
  selected-byte digest, and terminal text digest. It is measurement identity, not an
  `evidence_refs.claim` or database row ID.

MKE Publication identity/revision remains immutable provenance on a candidate source. It is not
invented for legacy `source_pack_entries`, and a legacy snapshot date is never relabelled as a
publication revision. A candidate may reuse a retained source entry only when the complete
`source_entry_canonical_id_v1` projection and projection SHA-256 are exactly equal; URL
resemblance, publication metadata, or near-duplicate text is insufficient. Producer opaque IDs
remain separate observation identity.

The canonical JSON uses the public model key `path`; SQL maps persisted `declared_path` to that key.
It treats the persisted `canonical_url` text as already normalized, sorts `coverage` and
`known_gaps` by UTF-8 byte order, sorts object keys, uses compact UTF-8 JSON without ASCII escaping,
and excludes all identity columns. Python/SQL parity tests use the same retained and candidate
fixtures rather than independent examples.

The evaluator:

- collapses exact source/evidence duplicates;
- represents one exact evidence item with all of its bounded provenance paths rather than creating
  duplicate items;
- records near-duplicate text as related but not automatically identical;
- never merges conflicting values into one fact;
- records the decision dimension, relation, and source identities for every conflict;
- treats missing or ambiguous identity as an evaluation failure, not novelty.

### 7.8 Metrics

Metrics are separated by purpose.

**Mechanism metrics**

- producer/tool/schema identity closure;
- retrieval completeness and pagination closure;
- exact Evidence-byte reconstruction;
- canonical deduplication;
- explicit conflict retention;
- deterministic output across fresh runs.

**Target metrics**

- `novel_source_bound_units`: MKE units absent from control and DRA baseline;
- `source_access_gain`: value caused by an eligible source/modal corpus that only MKE can access;
- `extraction_gain`: value extracted by MKE from a source that is also available to the baseline;
- `pre_registered_gap_closure`: novel units that satisfy a pre-authored decision gap;
- `decision_dimension_coverage`: distinct closed dimensions with accepted increments;
- `advisor_rubric_relevance`: evaluator-independent relevance to the existing decision process.

**Guardrail metrics**

- zero Night Voyager business mutation;
- zero instruction/tool execution from retrieved content;
- zero private source or moving checkout;
- zero holdout/evaluator freeze violation;
- zero source-truth, provider-quality, or generalization claim;
- decoy novelty equals zero;
- conflict remains explicit.

Guardrail failure is a veto. It cannot be averaged into a target score.

`source_access_gain` and `extraction_gain` are reported separately. If all accepted novelty comes
from MKE-exclusive source allocation, the only eligible claim is modality/source-access
complementarity; the system may not claim superior extraction or general producer information gain.

### 7.9 Terminal rule

`incremental_value_confirmed` requires all of the following:

- every mechanism metric passes;
- every required query reaches exhaustive `selection.status=complete`;
- both positive holdouts each contain at least one source-bound MKE unit that closes its
  pre-registered gap;
- the two positive holdouts cover at least two distinct decision dimensions;
- the zero-novelty decoy reports zero novel accepted units;
- the conflict holdout retains the exact contradiction and both provenance paths;
- all guardrails pass;
- a removed positive unit removes its target gain;
- a forged duplicate does not create gain;
- an injected instruction remains inert and creates no mutation;
- results are byte-identical across three fresh-process evaluator runs.

`no_incremental_value` is eligible only when every required query is exhaustive and active. A
required `capped`, incomplete page/chunk sequence, unavailable baseline, expired/invalid cursor that
cannot be restarted under the same frozen policy, or non-active selection makes the disposition
`inconclusive`. `active` with an exhaustively completed empty result is an eligible no-match.

Terminal outcomes are:

- `incremental_value_confirmed`;
- `no_incremental_value`;
- `inconclusive`;
- `evaluation_invalid`.

Only the exact merged `incremental_value_confirmed` receipt unlocks Slice 1. The other three outcomes
end this direction and cancel candidate/product/release work.

### 7.10 Slice 0 public claim

Eligible:

> On an eight-case public-safe frozen suite, Night Voyager's exact MKE v0.1.5 read-only MCP consumer
> found source-bound evidence that closed two pre-registered decision gaps not closed by the control
> or existing governed DRA-derived baseline, while a duplicate decoy stayed non-novel, a conflict
> stayed explicit, and all arms produced zero business mutation.

Ineligible:

- MKE is more accurate or generally better than DRA;
- the system achieved statistically significant information gain;
- three agents collaborated;
- retrieved evidence is true;
- the feature improved real admissions outcomes;
- the path is production deployed.

## 8. Slice 1 — MKE-specific candidate and advisor decision

### 8.1 Entry condition

Slice 1 starts only from the exact merged Slice 0 pass receipt and its frozen MKE capture. Any
producer-lock, corpus, evaluator, dataset, or receipt mismatch blocks import.

### 8.2 Product truth

An assigned advisor can inspect one immutable, source-bound MKE candidate and make one terminal
decision:

- `accepted_for_planning`;
- `rejected`.

`accepted_for_planning` means the advisor accepts the bounded observation as an input to the existing
Night Voyager planning process. It does not mean the source is true, the producer is correct, or the
route is approved. Acceptance creates no new source pack, planning task, family decision, timeline,
or execution.

### 8.3 Candidate artifact

Slice 0 emits a canonical `MkeCaptureArtifactV2`. Each candidate observation contains:

- exact Slice 0 receipt and case/query identity;
- exact MKE producer/corpus/tool/source/publication/run/Evidence identity;
- selected evidence bytes/range and terminal text digest;
- Night Voyager-owned closed decision dimension;
- Night Voyager-owned candidate observation and conflict relation;
- untrusted display text;
- `evaluation_canonical_source_id` and `evaluation_canonical_evidence_id`;
- one or more bounded observation provenance paths for an exact deduplicated evidence item;
- capture and artifact digests.

The observation is a Night Voyager evaluation projection, not a producer-supplied typed fact.
For every candidate item, import also freezes a complete Night Voyager-owned
`CandidateSourceEntryProjectionV1`:

- a `source_pack_entry` subprojection containing the server-owned deterministic source-entry ID,
  `source_entry_canonical_id_v1`, traversal-safe `declared_path`, source SHA-256, canonical URL,
  publisher, institution, snapshot date, freshness days, redistribution/evidence classes,
  coverage, and known gaps—the complete existing `SourcePackEntryV1` business shape;
- a provenance extension containing exact MKE Source/Publication identities, publication date,
  source byte length, `evaluation_canonical_source_id`, and exact manifest identity.

For v0.1.6, `route_country` is one existing supported country and `decision_dimension` is the closed
enum `program_requirements | application_timeline`. These are the two pre-registered gap families
in the frozen suite; adding another dimension is a later contract change, not arbitrary imported
text.

Each canonical candidate evidence item separately freezes:

- `evaluation_canonical_evidence_id`;
- one closed `route_country` and `decision_dimension`;
- `normalized_value_sha256`, never raw text as an equality key;
- a storage claim
  `mke.<route_country>_<decision_dimension>.<evaluation_canonical_evidence_id>` matching
  `^mke\.[a-z0-9_]{1,48}\.[0-9a-f]{64}$`;
- the source projection, locator/range, selected-byte and terminal-text digests;
- a closed relation `novel | near_duplicate | conflicts_with`, an optional conflict-group ID, and
  every bounded provenance path.

Exact duplicate observations have one candidate item and multiple provenance paths. Different
locators/ranges have different evidence identities even when they use one source. Different
normalized values in the same decision dimension remain different items, storage claims, and
conflict evidence; they are never collapsed by decision dimension. The source projection's
`coverage` is the exact sorted unique set of storage claims for all of its candidate items. This
keeps the existing `evidence_refs` provenance trigger executable while leaving semantic dimensions
separate from storage uniqueness.

The source-entry ID is derived from SHA-256 over a versioned Night Voyager namespace, candidate ID,
and `source_entry_canonical_id_v1`, then encoded as a UUID with fixed version/variant bits. It is an
identity key, not a security digest; the complete canonical projection and source SHA-256 remain the
integrity authority. The application generates this projection from the committed Slice 0
artifact, never from browser fields. Two items for the same product source share one projection at
the `source_pack_entry` and source-level provenance layers while retaining distinct item
Evidence locators/ranges. A candidate projection that disagrees with an existing source entry for
the same `source_entry_canonical_id_v1` is ineligible rather than silently merged. Composition
materializes the `source_pack_entry` subprojection as the same-version row and retains the complete
MKE provenance extension on the immutable candidate/composition source mapping; no legacy
publication field is fabricated and no field is silently dropped.

The candidate ID is a proposed entry ID only. Canonical comparison excludes tenant, pack/version,
and entry IDs. On zero retained matches the proposed ID is inserted; on one exact retained match
the copied retained entry ID is authoritative and the composition-source mapping records both the
proposed candidate ID and resolved generated ID.

### 8.4 PostgreSQL model

Migration `0016` adds MKE-specific tables:

- `app.mke_evidence_candidates`;
- `app.mke_candidate_sources`;
- `app.mke_candidate_items`;
- `app.mke_candidate_decisions`.

The model binds tenant, Case, current revision, assigned advisor, Slice 0 receipt, producer lock,
corpus/active set, query, artifact, candidate, item, source, Evidence, conflict, state, and row
version. Candidate-source rows persist the complete source-entry projection,
`source_entry_canonical_id_v1`, projection SHA-256, and MKE provenance extension. Candidate-item
rows persist the unique storage claim, semantic decision dimension, normalized-value hash, exact
evidence identity, locator/range, relation/conflict group, and bounded provenance paths. Composite
foreign keys prevent cross-tenant/Case/revision/candidate/source substitution. A unique
candidate/evidence identity enforces prior exact-duplicate collapse; one source may own multiple
evidence items and one decision dimension may own multiple conflicting evidence items.

Candidate, source, and item rows are immutable after import. Exactly one assigned-advisor terminal
decision is allowed. Forced RLS applies. API has only the approved functions; worker has no
candidate decision privilege.

Import and decision are eligible only while the Case is still in `advisor_review`, the referenced
revision is current, its current PlanningRun is `review_required`, the same advisor remains
assigned, and no FamilyDecision or TimelinePlan has finalized the Case. A retry checks its prior
idempotency receipt only after locking the stable Case row; a committed same-key/same-body result
replays before later stale-state checks.

Migration `0016` must close the relational contract:

- candidate primary key `(organization_id,id)` plus a unique
  `(organization_id,case_id,case_revision,id)` identity;
- source primary key `(organization_id,candidate_id,id)`, unique
  `(organization_id,candidate_id,source_entry_canonical_id_v1)`, exact canonical projection/hash,
  and composite candidate foreign key;
- item primary key `(organization_id,candidate_id,id)`, unique ordinal, unique
  `evaluation_canonical_evidence_id`, unique storage claim, and composite candidate/source foreign
  keys;
- decision primary key `(organization_id,id)`, unique candidate terminal decision, and composite
  candidate/Case/revision/actor binding;
- foreign keys to organization, Case revision, and assigned participant actor;
- immutable 64-hex columns for the frozen Slice 0 receipt/artifact identities, revalidated against
  the committed allowlist by the import function rather than falsely represented as database FKs;
- checks for the storage-claim regex, closed decision dimensions/states/decisions/reasons/conflict
  relations, conflict-group/`conflicts_with` consistency, sorted unique provenance paths and
  source coverage, and all byte/count/version bounds;
- immutable candidate/source/item/decision triggers, delete denial, forced RLS, bounded list/detail
  indexes, and no API or worker direct table DML;
- migrator-owned `SECURITY DEFINER` import/decision/read functions with closed `search_path`, exact
  `EXECUTE` grants to the API role, and no `BYPASSRLS`.

Bounds:

- query at most 4096 UTF-8 bytes;
- at most 16 items and 16 closed decision observations;
- at most 16 KiB selected text per item;
- at most 256 KiB candidate payload;
- at most 16 explicit duplicate/conflict relations;
- list page at most 20 and exposes candidate summary identity only;
- candidate detail exposes at most 16 item summaries and remains below 32 KiB;
- selected text and full provenance appear only on a separate one-item detail read, with at most
  16 KiB text and a total response below 32 KiB;
- public problem body at most 32 KiB, matching the existing BFF cap.

### 8.5 Import and decision API

Import is server-owned. The client submits only an opaque `candidate_ref` plus expected current Case
revision. The server resolves the exact committed artifact and revalidates all locks and hashes.

The bounded read surface is:

```text
GET /api/v1/cases/{case_id}/mke-candidates
GET /api/v1/cases/{case_id}/mke-candidates/{candidate_id}
GET /api/v1/cases/{case_id}/mke-candidates/{candidate_id}/items/{item_id}
```

The decision mutation accepts only:

- `decision`;
- closed `reason_code`;
- `expected_candidate_version`.

Every mutation requires `Idempotency-Key` and returns an immutable receipt plus authoritative
projection. Same key/same body replays the receipt; same key/different body conflicts. Wrong tenant,
Case, revision, advisor, artifact, source, or receipt fails closed and non-enumerating.

Import and decision use the same recovery rule as composition: before a receipt is accepted, only
the exact same POST/body/key may be replayed; after receipt acceptance, only the authoritative GET
candidate-detail read may be retried. Item detail is display-only and never an operation-status
authority. Import recovery does not guess from the list: an exact replay
returns the original candidate identity. There is no operation-status polling endpoint and no
automatically minted key.

### 8.6 UI and recovery

The only product route is the existing `/demo` journey. `ConnectedDemo` remains the page owner and
one top-level controller owns all current-action, candidate, composition, planning, and recovery
state. A second independent candidate controller must not compete with the connected journey.

The server extends the advisor ledger with one closed `current_action` projection. Candidate,
composition, and existing planning components never derive or display a competing primary action.

The advisor UI shows:

- untrusted-content warning;
- exact source/publication/locator identity;
- selected excerpt;
- duplicate and conflict relationships;
- the closed decision dimension;
- one current action;
- explicit “accepted as planning input” or rejection copy;
- receipt and current server projection.

It never renders retrieved HTML, executes links, or describes acceptance as truth verification.

The terminal decision uses one labelled fieldset with:

- `用于下一版规划`;
- `本次规划不采用`;
- one closed reason choice;
- an explicit consequence summary;
- a separate confirmation action.

Acceptance confirms only planning-input eligibility. Its result copy is:

> 已标记为规划输入；Case 和计划尚未改变。

Recovery uses receipt-then-authoritative-GET. Transport uncertainty retains the exact body/key.
Confirmed session, role, Case, revision, candidate, or receipt contradiction clears unsafe state and
closes to recovery with zero later mutation.

## 9. Slice 2 — atomic composition into existing governance

### 9.1 Entry condition

Slice 2 requires:

- exact merged Slice 0 pass receipt;
- exact imported candidate and `accepted_for_planning` decision;
- current Case in `planning`, with its prior revision and `review_required` PlanningRun still
  current after the assigned advisor's `request_revision` review;
- the same assigned advisor;
- an exact current `review_required` PlanningRun with an assigned-advisor `request_revision` review;
- no current FamilyDecision, TimelinePlan, or active execution that would make recomposition stale.

### 9.2 Product truth

The assigned advisor explicitly chooses to compose the accepted MKE candidate into a new planning
input. The request is legal only after the current `review_required` PlanningRun has an
assigned-advisor `request_revision` review and before any FamilyDecision, TimelinePlan, or active
execution for the Case.

Night Voyager then performs one PostgreSQL transaction. Every competing Case mutation uses the same
first lock, and the composition function acquires rows in this order:

1. current Case `FOR UPDATE`;
2. prior composition idempotency record for the actor/key;
3. current revision;
4. current `review_required` PlanningRun and `request_revision` review;
5. current source-pack version;
6. accepted candidate and terminal decision;
7. any prior immutable composition or recovery record for the accepted decision.

The current source pack is resolved only through that locked current PlanningRun. It is never
inferred from creation time, maximum version, a browser-supplied standalone ID, or producer
metadata.

The stable Case lock serializes a first request when no idempotency row yet exists. After that lock,
a committed same-key/same-body receipt replays before current-state validation; same key/different
body conflicts. A new request then revalidates exact lineage and advisor authority and atomically:

1. creates the next version of the same source-pack ID and copies every retained source entry;
2. creates one immutable composition-source mapping for every retained entry by recomputing
   `source_entry_canonical_id_v1` from the locked row;
3. groups candidate sources by `source_entry_canonical_id_v1`; reuses a copied entry only when
   exactly one retained projection is byte-equal, rejects an ambiguous or disagreeing match, and
   otherwise creates exactly one missing same-version source entry from the frozen candidate
   projection;
4. copies retained Evidence and adds immutable candidate Evidence projections with the distinct
   `advisor_accepted_planning_input` authority for accepted candidate items while retaining
   conflicts;
5. computes and stores the canonical successor source-pack manifest over the complete retained and
   newly materialized source-entry set;
6. creates a staged next `student_case_revisions` row bound to the predecessor PlanningRun and
   `request_revision` review, without changing `student_cases.current_revision`;
7. keeps the predecessor PlanningRun current and the Case in `planning`;
8. creates an immutable composition receipt and item/source/evidence mapping;
9. creates one pinned queued `AgentTask`, dispatch row, and queued event bound to the staged
   revision/source-pack;
10. records the composition idempotency result;
11. commits all rows together or none.

The composition transaction does **not** create an `AgentExecution` or successor `PlanningRun`.
Worker claim creates the execution attempt. Generation-guarded worker finalization creates the
successor PlanningRun and, in the same Case-locked transaction, proves the old revision/run is still
current, marks the predecessor non-current, advances `student_cases.current_revision` to the staged
revision, makes the new run current, and returns the Case to fresh `advisor_review`. There is no
producer call inside the transaction or planning execution. Runtime planning reads only Night
Voyager-owned immutable rows.

The task pin is closed: operation `generate_composed_evidence_planning_run_v1`, Skill key
`evidence-composition-planning`, adapter `composed_evidence_planning@v1`, input contract
`night-voyager.composed-evidence-planning-input.v1`, and output contract
`night-voyager.composed-evidence-planning-result.v1`.
Migration `0017` adds one immutable Skill definition/version/evaluation/activation bundle and
extends the claim-time operation-to-adapter mapping. It does not edit an existing immutable Skill
version or silently reuse an incompatible adapter pin.

The adapter emits one closed `ComposedEvidencePlanningInputV1`, not a
`GovernedMixedPlanningInput` with extra fields. It contains the exact composition receipt,
candidate decision, predecessor PlanningRun, `request_revision` review, staged Case revision and
source pack, and a tuple of `ComposedPlanningEvidenceRefV1`. Each evidence ref binds storage claim,
semantic decision dimension, authority, source entry, composition source/item, canonical evidence
identity, normalized-value hash, relation/conflict group, receipt, and decision. The task policy
dispatches by an exact three-way operation allowlist:

- `generate_planning_run_v1 -> PlanningInput`;
- `generate_governed_mixed_planning_run_v1 -> GovernedMixedPlanningInput`;
- `generate_composed_evidence_planning_run_v1 -> ComposedEvidencePlanningInputV1`.

Unknown operations do not fall through to a mixed input. Ordinary planning continues accepting
only `accepted_synthetic_demo`; the DRA mixed path continues accepting its exact one
`externally_verified` baseline item; both reject `advisor_accepted_planning_input`. Only the
composition path accepts that new authority, and only when PostgreSQL receipt/item/source/decision
bindings all agree.

The shared `EvidenceAuthority`/`EvidenceRef` v1 models remain unchanged. A separate closed
`ComposedEvidenceAuthorityV1` admits the existing retained strings plus
`advisor_accepted_planning_input`; only `ComposedPlanningEvidenceRefV1` can carry the new value.
This preserves every v1 input schema/hash and prevents model parsing from bypassing the
operation-specific policy.

Composition policy does not key semantics by the unique storage claim. It first validates the
receipt-bound mapping, then groups by the closed semantic decision dimension. One unconflicted
value adds a route comparison dimension with outcome `conditional` and reason
`advisor_accepted_untrusted_input`; exact duplicate observations have already collapsed into one
item. Multiple different normalized-value hashes in a conflict group keep all Evidence and add a
`blocked` dimension with reason `accepted_input_conflict`. Neither path changes a route outcome
automatically. v0.1.6 creates no MKE-derived `cost_evidence` or `ranking_evidence`; those rows remain
the copied governed predecessor inputs. Raw retrieved text, MKE metadata, and candidate display
copy are not policy instructions.

The planner returns a separate `ComposedEvidencePlanningResultV1`. It contains an unchanged v1
`PlanningResult` base projection plus composition dimensions whose `ComposedEvidenceRoleV1` is
`program_requirements` or `application_timeline`. Generation-current finalization validates the
wrapper once, persists only its byte-equivalent v1 base projection and legacy Evidence links through
the existing PlanningRun tables, and stores the supplementary dimensions and their new Evidence
links in composition-owned tables. It never inserts a new role or authority into
`comparison_dimension_evidence_refs`, and it never reuses `program_fit` as an alias.

The PlanningRun's existing `output_sha256` remains the canonical v1 base-result hash. The
composition receipt remains fully immutable from synchronous creation and carries no future output.
Generation-current finalize instead inserts one immutable one-to-one composition-result row in the
same transaction as the generated PlanningRun and supplementary dimensions. That row stores the
new output contract ID, schema hash, complete wrapper hash, base v1 hash, task/execution generation,
and generated PlanningRun. Existing planning-revision and family-decision consumers therefore
continue receiving the same v1 projection; the composition GET left-joins the optional result and
is the only C1 projection that returns supplementary dimensions. C2 may display both projections
but must not reparse them as one v1 model.

The operation-specific finalize parameter `p_output_hash` means the complete composed-wrapper hash.
Finalize recomputes that hash from the supplied canonical wrapper, recomputes the nested base v1
hash independently, requires the worker/Skill output contract and schema pins, stores the wrapper
hash on the immutable composition result and execution result, and stores only the base hash on the
PlanningRun. Before finalize, GET returns `result=null`. An old generation, replay, contract/hash
mismatch, or partial dimension/result insert creates no PlanningRun, result, or supplementary row.

The shared `EvidenceRole`, `PlanningResult`, existing planning tables, and
`app.guard_link_provenance()` remain byte/schema/behavior unchanged. Migration `0017` instead adds
closed composition-dimension and composition-dimension-Evidence tables with their own role CHECK
and a new `app.guard_composed_evidence_link_provenance()` trigger function. The new guard accepts a
supplementary link only when route country, storage-claim prefix, new Evidence authority,
composition receipt/source/item, source pack, staged revision, and generated PlanningRun agree.
Wrong role, wrong country prefix, foreign receipt/item, wrong authority, or an old claim with a new
role fails without touching legacy projection behavior.

C1 is deployable only after a real PostgreSQL worker-finalize regression calls the existing
connected-demo journey-status, planning-comparison, and Evidence-disclosure reads. Those reads must
remain byte-equivalent to the legacy v1 base projection and must never deserialize a composed role
or authority. The composition receipt GET must independently return every supplementary dimension,
Evidence link, and wrapper hash. C2 consumes that separate projection for display; it does not
widen or synthesize a v1 `PlanningResult`.

The packaged Skill catalog is append-only. Existing
`runtime-manifest-v1.json`/`eval-manifest-v1.json` bytes, version `1.0.0`, and hashes remain
unchanged. A new `runtime-manifest-v2.json`/`eval-manifest-v2.json`, with `schema_version=2` and
`manifest_version=2.0.0`, contains the complete supported catalog plus the new Skill/evaluation
entry. A manifest catalog loads both
immutable generations and resolves worker validation by the task's exact
manifest-ID/version/SHA-256 tuple; `current` is used only when registering a new Skill version.
Migration `0017` replaces the single-pair `skill_versions` manifest CHECK with a closed two-pair
allowlist and stores the v2 pair only on the new version. Old Skill rows and old queued/reclaimed
tasks therefore continue validating against v1, while new composition tasks validate against v2.
Unknown, cross-generation, or partially updated pins fail closed. Release and migration tests prove
both old-task replay and new-task execution from installed-wheel resources.

Fresh demo seed and seed replay use a versioned seed envelope rather than one global manifest
tuple:

- `SkillSeedEnvelopeV1` remains accepted unchanged and applies its top-level v1 tuple to every
  historical entry exactly as migration `0008` did;
- `SkillSeedEnvelopeV2` requires an exact runtime/evaluation manifest binding on every entry;
  historical entries carry the original v1 pair and only the new composition entry carries v2;
- migration `0017` uses
  `CREATE OR REPLACE app.seed_demo_skill_registry(uuid,uuid,jsonb)` with the same signature, a
  closed schema-version dispatch, and byte-equivalent v1 behavior;
- fresh head seed emits v2, replay compares each row against its own binding, and neither path
  rewrites an existing historical row merely because v2 is current.

Unknown envelope versions, a missing entry binding, a v1 entry paired with v2, a v2 composition
entry paired with v1, or any per-entry/runtime/evaluation cross-pair fails before catalog mutation.
Historical-head runners continue invoking their historical seed shape.

The existing automatic task attempt ceiling remains unchanged. This operation is not cancellable
through the generic task-cancel path. Migration `0017` replaces the existing exact
`app.cancel_agent_task(uuid,uuid,uuid,integer,text,text)` function without changing its signature:
after its existing context/task lock it rejects
`generate_composed_evidence_planning_run_v1` with SQLSTATE `NV037`, mapped only to public HTTP 409
`composition_not_cancellable`; other operations retain byte-equivalent behavior. After its final
automatic attempt becomes terminal without a PlanningRun, the server-owned current action offers
one explicit assigned-advisor
`abandon_composition` operation. That Case-locked, idempotent transaction appends a recovery row,
proves the prior revision/run is still current, and returns the Case from `planning` to
`advisor_review` without advancing the current revision, changing the predecessor, or deleting
audit rows. The abandoned accepted decision is permanently closed for further composition in
v0.1.6. The exact post-abandon current actions are the existing `approve_for_consultation` or
`reject` actions for the unchanged prior plan; `request_revision`, another candidate composition
from the same predecessor, generic cancel, and retry are rejected by the read model and PostgreSQL
authority. This is the bounded safe-stop, not an automatic retry, rollback, or fabricated plan.

### 9.3 PostgreSQL model

Migration `0017` adds:

- `app.evidence_composition_receipts`;
- `app.evidence_composition_sources`;
- `app.evidence_composition_items`;
- `app.evidence_composition_dimensions`;
- `app.evidence_composition_dimension_evidence_refs`;
- `app.evidence_composition_results`;
- `app.evidence_composition_recoveries`.

Receipt rows bind old/new revision and source pack, candidate and decision, assigned advisor,
predecessor run, created task, request hash, idempotency key, and timestamps. Source rows bind a
generated same-version source entry to either a retained predecessor entry, a candidate source, or
both after an exact canonical match; they persist the complete canonical business projection and
hash. Item rows bind either a retained predecessor Evidence ref or a candidate item, the generated
new-version Evidence identity, source mapping, storage claim, semantic decision dimension,
normalized-value hash, and duplicate/conflict relation.
Dimension rows bind the completed generated PlanningRun, receipt, route country, exact
`program_requirements|application_timeline` role, outcome, and reason. Dimension-Evidence rows bind
those supplementary dimensions to composition items and generated Evidence; they are never read
through the v1 planning-result projection.
The result row is unique per receipt and generation-current task result. It binds receipt, terminal
task/execution/generation, generated PlanningRun, exact output contract/schema hash, wrapper hash,
and independently recomputed base v1 hash. It is inserted only by successful finalize and is
immutable thereafter.
Recovery rows bind the receipt, terminal task state and generation, assigned advisor, exact
`abandon_composition` request/idempotency identity, the unchanged prior Case revision/current run,
and an `abandoned` result.

The copy/remap contract is exact:

- every prior `source_pack_entries` row is copied to the next version with the same entry ID and
  byte-identical business columns;
- one composition-source row recomputes `source_entry_canonical_id_v1` and the complete canonical
  projection for every locked retained entry; it never invents publication metadata absent from
  that row;
- candidate sources are grouped by `source_entry_canonical_id_v1`;
- if a candidate projection has exactly one byte-equal retained match, the copied entry ID is
  reused and both origins are recorded on the source mapping; zero matches inserts exactly one new
  same-version entry from `CandidateSourceEntryProjectionV1`, even when several candidate items
  use different locators in that source; multiple or disagreeing matches fail closed;
- every retained `evidence_refs` row receives a new Evidence ID at the new pack version with
  byte-identical claim, authority, and source hash; legacy `evidence_refs` has no locator column;
- every candidate Evidence uses the resolved same-version source-entry ID and its frozen unique
  `mke.<route_country>_<decision_dimension>.<evaluation_canonical_evidence_id>` storage claim,
  while the item
  mapping separately retains locator/range, semantic decision dimension, normalized-value hash,
  relation/conflict group, and `advisor_accepted_planning_input` authority;
- one composition item records each old-Evidence-to-new-Evidence or
  candidate-item-to-new-Evidence mapping.

The source table enforces at least one of retained-entry or candidate-source origin and permits both
only for an exact canonical match. The item table enforces an XOR between
`predecessor_evidence_ref_id` and `candidate_item_id`. Exact duplicate candidate observations were
already one candidate item with multiple provenance paths. Different evidence in the same
decision dimension therefore creates distinct storage claims and Evidence rows; unresolved
different normalized-value hashes remain an explicit conflict group for deterministic policy
blocking rather than colliding on the legacy `(pack,version,claim)` uniqueness key.
The successor `manifest_sha256` is SHA-256 of a canonical UTF-8 JSON projection containing
schema version, organization ID, source-pack ID, successor version, and the complete successor
entry set sorted by lowercase UUID text. Object keys are sorted, arrays preserve that frozen entry
order, separators contain no insignificant whitespace, and UTF-8 characters are not ASCII-escaped.
The transaction computes the expected digest from locked rows plus the frozen candidate projection,
inserts the pack/entries, recomputes from inserted rows, and requires exact equality before creating
the staged revision or task. New PlanningRun children may reference only
new-version Evidence IDs whose same-version source entry exists. Missing, duplicate, disagreeing,
cross-pack, manifest-mismatched, or orphan source/evidence mappings roll back the entire
transaction.

The DDL must define, rather than merely name:

- primary and unique keys for receipt/source/item/result/recovery identity, one composition per accepted
  decision, and at most one terminal recovery per receipt;
- composite foreign keys across tenant, Case, old/new revision, source-pack ID/version,
  candidate/source/item/decision, predecessor PlanningRun, request-revision review, task, actor, and
  generated Evidence, terminal task/generation, and recovery actor;
- checks for the retained/candidate item XOR, closed operation/state/result kinds, positive
  versions, 64-hex hashes, bounded text and payload counts, and same-source-pack successor version;
- composite candidate-source/item-to-composition-source identity, exact generated source-entry
  coverage, canonical projection/hash equality, candidate storage-claim regex/coverage, and
  complete manifest coverage of every successor entry;
- a closed `evidence_refs.authority` extension for `advisor_accepted_planning_input`; it is not
  `externally_verified` and cannot be consumed without the matching composition receipt;
- closed composition-dimension role/outcome/reason CHECKs for `program_requirements` and
  `application_timeline`; the composed output contract owns its separate
  `ComposedEvidenceRoleV1`, while the shared v1 `EvidenceRole`, `PlanningResult`,
  `comparison_dimension_evidence_refs`, and `app.guard_link_provenance()` remain unchanged;
- a new `app.guard_composed_evidence_link_provenance()` on the composition-owned link table that
  accepts a supplementary role only when route country, storage-claim suffix,
  `advisor_accepted_planning_input` authority, composition receipt/source/item, source pack, staged
  revision, and generated PlanningRun all agree;
- immutable receipt/source/item/dimension/dimension-link/result/recovery triggers and
  delete/update denial;
- the unique effective planning-task constraint and query indexes used by current-action/list/detail
  reads;
- forced RLS, tenant policies, closed `SECURITY DEFINER` `search_path`, API `EXECUTE` only, and
  worker `EXECUTE` on exactly the operation-specific start and finalize functions in addition to
  its unchanged claim/failure functions; PUBLIC and API are revoked from start/finalize and neither
  API nor worker receives direct table DML or `BYPASSRLS`.

Migration and architecture tests freeze these operation signatures:

```text
app.compose_mke_candidate(
  uuid,uuid,uuid,integer,uuid,integer,uuid,uuid,uuid,uuid,integer,
  uuid,uuid,jsonb,text,text
)
app.read_evidence_composition(uuid,uuid,text,uuid,uuid)
app.abandon_evidence_composition(
  uuid,uuid,uuid,uuid,uuid,bigint,uuid,text,text
)
app.start_composed_evidence_agent_task(uuid,uuid,text,bigint,text)
app.finalize_composed_evidence_planning_result(
  uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid
)
app.cancel_agent_task(uuid,uuid,uuid,integer,text,text)
app.source_entry_canonical_identity_v1(jsonb)
app.canonical_source_pack_manifest_v1(uuid,uuid,integer)
```

The composition arguments are organization, actor, Case, expected current revision, candidate,
candidate version, decision, expected current PlanningRun, request-revision review, current pack,
current pack version, receipt, task, closed item projection, key hash, and request hash. Abandon
binds organization, actor, Case, receipt, terminal task, expected final generation, recovery ID,
key hash, and request hash. Operation-specific start matches the existing worker start shape but
validates the receipt's prior-current/staged split instead of requiring the task revision already be
current. Finalize deliberately matches the existing worker result shape but uses an
operation-specific function because staged revision activation has different authority from
ordinary current-revision finalization.

Catalog tests call both start and finalize under the worker role, assert successful `EXECUTE`, and
assert their absence from PUBLIC/API grants. This prevents a migration that names the start
function but leaves every leased composition task unable to enter `running`.

The architecture inventory also freezes the existing participating signatures
`app.review_planning_run(uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text)`
and
`app.decide_family_brief(uuid,uuid,text,uuid,integer,uuid,uuid,uuid,bigint,bigint,text,jsonb,uuid,text,uuid,jsonb,text,text)`.
Every new or existing Case-changing function on this journey takes the stable Case lock before any
operation-specific row lock; database concurrency tests call the exact signatures, not source-text
markers alone.

Downgrade refuses once composition data exists unless a separately reviewed, lossless reversal
contract is proven.

### 9.4 Planning and review invariants

The new operation is closed and explicit, not a generic provider workflow. Planning:

- consumes only immutable Night Voyager Evidence;
- distinguishes existing governed DRA-derived evidence from accepted MKE evidence;
- retains provenance and conflicts;
- emits a deterministic predecessor/current comparison;
- cannot mark a conflict resolved without an advisor decision;
- ends at fresh AdvisorReview;
- requires a current-only FamilyDecision before timeline progression;
- preserves all existing timeline execution/recovery authority.

The composition receipt stages the successor revision and pack but does not advance the Case or
retire the predecessor. While the queued task is pending or running, the prior revision and
`review_required` PlanningRun remain current and the Case remains `planning`. Only successful,
generation-current worker finalization may atomically retire the predecessor, activate the staged
revision/run, and return the Case to fresh `advisor_review`.

Crash/reclaim uses the existing bounded task attempts. Generic cancellation is rejected for this
operation in the database with `NV037 -> composition_not_cancellable`, so cancellation cannot race
activation. If the last attempt is terminal without a PlanningRun, the composition cannot be
retried or silently ignored: the exact server-owned action is assigned-advisor
`abandon_composition`. Its atomic recovery keeps the prior revision/run current, returns the Case
to `advisor_review`, appends immutable failure/recovery audit, and permanently closes this accepted
decision from another composition. PostgreSQL also rejects `request_revision` for that abandoned
Case/predecessor branch; the ledger may expose only `approve_for_consultation` or `reject` for the
unchanged current run. No failed, timed-out, reclaimed, generation-stale, or abandoned task can
later finalize.

Migration `0017` enforces that rule by replacing the existing exact
`app.review_planning_run(uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text)`
function without changing its signature. After its existing Case/run/advisor checks, a matching
abandoned composition makes `request_revision` fail with SQLSTATE `NV038`, mapped to public
`composition_branch_closed`; `approve_for_consultation`, `reject`, and every review without that
abandon lineage retain existing semantics. In particular, abandoned-branch `reject` follows the
existing non-approval transition to `planning` but creates no task or composition; the UI treats it
as a safe terminal stop for this v0.1.6 reference journey rather than inventing a retry.

### 9.5 UI and recovery

Before composition, the UI shows an impact preview:

- a new Case revision and source pack will be created;
- a new planning task will run;
- no family decision, timeline, or execution starts automatically;
- unresolved conflicts remain for fresh AdvisorReview.

The product journey then shows:

1. accepted MKE planning input and provenance;
2. the existing explicit advisor `request_revision` action on the current plan;
3. explicit composition action after that review stages the next revision while the Case remains
   `planning` on its prior current plan;
4. immutable composition receipt;
5. old/new planning comparison;
6. unresolved conflicts;
7. fresh AdvisorReview;
8. family decision and existing timeline journey.

The UI remains bilingual, keyboard operable, responsive, reduced-motion safe, and current-action
driven. Recovery binds Case, revision, source pack, candidate, decision, composition receipt, task,
execution when one exists, role, and cursor. A stale or foreign identity never installs or triggers
a new mutation.

The exact recovery state machine is:

1. before a receipt is accepted, uncertain transport replays the same composition POST with the
   same body and `Idempotency-Key`;
2. a prior committed transaction returns the immutable receipt with `replayed=true`; an uncommitted
   first attempt may commit once and return `replayed=false`;
3. after a receipt is accepted, recovery retries the exact
   `GET /api/v1/cases/{case_id}/evidence-compositions/{receipt_id}` only and never POSTs again;
4. request-hash mismatch, confirmed authority change, or receipt/projection contradiction clears the
   unsafe slot and fails closed without minting a new key;
5. worker retry/reclaim is automatic only within the existing attempt ceiling; generic cancellation
   is unavailable;
6. after terminal exhaustion, only the exact server-owned advisor action may POST
   `/api/v1/cases/{case_id}/evidence-compositions/{receipt_id}/abandon` with one stable
   idempotency slot; lost response follows same-body/key replay then recovery GET;
7. successful abandon returns the unchanged prior current revision/run and immutable recovery
   receipt. It never requeues, composes again, or fabricates a PlanningRun; its only subsequent
   review actions are `approve_for_consultation` or `reject`.

## 10. Product information architecture and interaction contract

### 10.1 Screen hierarchy

Desktop and mobile preserve the same semantic order:

1. Case, revision, active role, and synthetic-demo boundary;
2. one server-owned current action;
3. evidence summary and conflict state;
4. the current decision or composition form;
5. result summary and unresolved items;
6. progressively disclosed source/producer/receipt diagnostics;
7. existing planning/family/timeline continuation.

On desktop, evidence comparison may use a table with a mobile item selector equivalent. On mobile,
content stays one column in the same order. Technical hashes never precede the user decision.
`PlanningRevisionComparison` starts with “发生了什么” and “仍未解决什么”; the full table is secondary.

### 10.2 Trust and emotional arc

| Scene | Intended feeling | Interface support |
| --- | --- | --- |
| Correct Case | oriented | role, Case, revision, and synthetic boundary first |
| Evidence review | cautious clarity | warning, decision dimension, excerpt, source summary, conflict |
| Terminal choice | deliberate | labelled decision group, consequence, explicit confirmation |
| Decision readback | safe | states that Case/plan has not changed |
| Composition preview | informed | exact objects created and actions not taken |
| Uncertain response | protected | retained projection, “checking result,” no ordinary duplicate retry |
| Composition result | traceable | result summary before operation record |
| Fresh review | still responsible | unresolved conflicts and fresh AdvisorReview as sole next action |

There is no celebratory “verified” moment. Trust comes from bounded claims, visible provenance,
explicit consequences, and recoverable authority.

### 10.3 User-visible state matrix

| State | Heading/body | Available action | Preserved content | Focus/live behavior |
| --- | --- | --- | --- | --- |
| loading | 正在核对当前证据 | none | current Case shell | no repeated announcement |
| no candidate | 当前没有可审阅的补充证据 | continue existing journey | current ledger | heading |
| candidate unavailable | 补充证据暂不可用 | reconnect/exit | current ledger | recovery heading |
| wrong role/session/Case | 需要重新连接当前流程 | reconnect | no foreign candidate | recovery heading |
| pending review | 审阅外部证据 | decision group | evidence summary | action heading |
| duplicate | 与现有来源重复 | accept/reject still explicit | both provenance paths | relation label |
| conflict | 存在未解决分歧 | accept/reject with consequence | both values/sources | conflict summary |
| submitting decision | 正在记录决定 | none | exact submitted choice | one polite update |
| accepted | 已标记为规划输入；Case 和计划尚未改变 | compose only in Slice 2 | decision/receipt | result heading |
| rejected | 本次规划不采用 | continue existing journey | rejection record | result heading |
| concurrent terminal | 已有最终决定 | none/new server action | authoritative decision | result heading |
| composition ineligible | 当前不能创建新规划版本 | existing current action | accepted candidate | explanation |
| impact preview | 创建包含该证据的新规划版本 | explicit confirm/cancel | evidence and conflicts | preview heading |
| composition pending/running | 正在生成新规划版本 | none | receipt/task projection | bounded live updates |
| worker restarting/reclaimed | 正在恢复规划任务 | none | durable task projection | one polite update |
| composition success | 已创建新的规划版本 | fresh AdvisorReview | summary/conflicts/record | result heading |
| terminal task failure | 未创建可审阅的新规划结果 | assigned-advisor abandon only | prior current plan + durable failure | error heading |
| composition abandoned | 已停止本次证据组合；当前计划未改变 | approve or reject prior plan only | failure + recovery receipt | result heading |
| transport uncertainty | 正在核对操作是否完成 | none | prior projection and exact slot | one polite update |
| receipt found | 已找到操作记录 | server current action | authoritative projection | result heading |
| receipt absent, safe retry | 操作未完成，可以安全重试 | exact same-body/key retry | prior projection | retry control |
| identity changed | 当前流程已变化，已安全停止 | reconnect | no unsafe envelope | recovery heading |
| projection contradiction | 需要恢复 | reconnect/exit | prior safe projection | recovery heading |

The implementation also covers 0/1/16 items, long query/excerpt/locator, pagination/truncation,
malicious HTML/Unicode/control characters, inaccessible URL text, repeated source, and bilingual
copy expansion.

### 10.4 Copy and safe-link rules

Primary copy:

- warning: `这段外部证据可能不完整或有误。它不会自动修改 Case 或计划。`;
- accept: `用于下一版规划`;
- reject: `本次规划不采用`;
- accepted result: `已标记为规划输入；Case 和计划尚未改变。`;
- compose: `创建包含该证据的新规划版本`;
- conflict: `存在未解决分歧；新版本仍需顾问审阅。`;
- receipt label: `操作记录`;
- technical disclosure: `技术详情`.

Internal terms such as `compose`, `accepted_for_planning`, `source pack`, `immutable receipt`,
`current server projection`, producer/corpus/tool/hash, and the architecture title do not appear as
primary interface copy.

Source URLs and locators are displayed as non-executing text with copy affordance. This release does
not navigate to retrieved links. Raw HTML is never rendered.

### 10.5 Accessibility and responsive contract

- one `main` landmark and ordered section headings;
- decision controls in `fieldset`/`legend`;
- errors associated with the relevant control;
- deterministic focus after every user mutation and recovery;
- one polite live region owned by the top-level controller;
- full keyboard completion, including decision and details disclosure;
- 44 px minimum touch targets;
- WCAG AA contrast and status not conveyed by color alone;
- 200% zoom and 320 px viewport without clipped text/action/status;
- reduced motion with bounded transition/animation duration;
- locale switch preserves server authority and safe local presentation state.

The default layout adds no dashboard, tab system, card grid, or navigation level. It reuses
`PresentationShell`, the existing connected journey, current-action hierarchy, comparison,
recovery, focus, and live-region patterns.

## 11. Evaluation and test strategy

### 11.1 Slice 0

RED/GREEN includes:

- exact tagged-wheel MCP schema and tool calls;
- pagination, capped/incomplete, and evidence-byte reconstruction;
- source identity and cross-projection deduplication;
- separation of evaluation identity from exact `SourcePackEntryV1` persistence identity;
- positive, decoy, conflict, and instruction-injection holdouts;
- removed-novelty and forged-duplicate sensitivity;
- frozen evaluator/holdout and role separation;
- three fresh-process byte-identical runs;
- zero database and filesystem mutation outside task-owned artifacts.

### 11.2 Slice 1

Real PostgreSQL and HTTP tests cover:

- migration upgrade/downgrade and catalog ownership;
- forced RLS and cross-tenant/Case/revision denial;
- artifact/receipt/producer/corpus/source mismatch;
- assigned-advisor enforcement;
- immutable candidate/sources/items;
- source projection/hash parity, unique candidate storage claims, exact-duplicate provenance
  collapse, and same-dimension conflict preservation;
- terminal decision concurrency;
- same-key/same-body and same-key/different-body;
- receipt-then-GET and session/role/Case recovery;
- inert untrusted-content rendering;
- every row in the user-visible state matrix;
- decision fieldset, consequence, confirmation, focus, and single live region;
- zero promotion after acceptance.

### 11.3 Slice 2

Real PostgreSQL, HTTP, worker, and browser tests cover:

- all-or-nothing composition;
- stale current revision/source pack/run;
- rejected, foreign, or stale candidate;
- advisor change;
- conflict retention;
- exact worker start/finalize grants and PUBLIC/API revocation;
- operation-specific typed-input dispatch and wrong-operation authority rejection;
- receipt/source/item/decision-bound composed policy validation;
- unique storage claims with semantic-dimension conflict blocking;
- v1/v2 installed-wheel manifest pin selection and per-entry seed-envelope replay;
- predecessor/successor run lineage;
- task/execution/request/idempotency identity;
- concurrent same-key replay, different-key serialization, and composition against every other
  Case-mutating authority under the common Case lock;
- failure injection after each insert and before commit;
- worker crash/reclaim, old-generation finalize, and revision change before finalize;
- bounded list/detail query plans and response sizes;
- runtime-role grants, `search_path`, non-`BYPASSRLS`, and direct-DML denial;
- rollback on every mid-transaction counterfactual;
- worker restart/reclaim and SSE/public read convergence;
- bilingual full browser-to-database journey;
- planning-revision and existing governed-execution regression suites.
- impact preview and all completion/uncertainty results;
- one server-owned current action with no competing ledger/candidate/composition action.

### 11.4 Native vertical proof

The release archive, not a moving checkout, drives the MKE native lane:

```text
tagged archive
-> verified wheel and MCP schema
-> local stdio MCP server
-> search_library_v2
-> every required read_evidence_v1 chunk
-> canonical MkeCaptureArtifactV2
-> frozen-suite evaluator
```

Moving source, editable installation, provider call, HTTP service, or v1 fallback is not an
acceptable substitute.

## 12. Failure and recovery taxonomy

Closed public codes include:

```text
producer_contract_mismatch
producer_identity_mismatch
corpus_identity_mismatch
retrieval_incomplete
evidence_identity_mismatch
baseline_unavailable
source_identity_ambiguous
evaluation_invalid
no_incremental_value
candidate_unavailable
candidate_stale
candidate_decision_conflict
composition_stale
composition_conflict
composition_not_cancellable
composition_terminal
composition_abandon_conflict
composition_branch_closed
session_changed
resource_unavailable
```

Producer or transport failures do not fall back to another contract, moving checkout, partial
evidence, or automatic retry loop. Evaluation failures cause no product mutation. Product mutation
uncertainty preserves one exact operation slot and uses receipt-then-GET. Confirmed identity change
clears the slot and fails closed.

## 13. Security and threat model

Required counterfactuals include:

- indirect prompt injection in Evidence text;
- HTML/script/link payload;
- forged cursor or tool schema;
- source/publication/run/Evidence digest substitution;
- cross-corpus and cross-active-set candidate;
- DRA Markdown-to-fact parser attempt;
- cross-tenant/Case/revision candidate;
- non-advisor decision;
- replay with changed body;
- stale accepted candidate;
- cross-Case composition item;
- lost response and role/session rotation;
- conflict erasure;
- automatic planning/promotion attempt.
- generic cancel, second composition, or stale-generation finalize after terminal failure;
- abandon by a non-assigned advisor or before the task is terminal.

Every counterfactual is either a deterministic evaluator rejection or a PostgreSQL/HTTP fail-closed
path with zero unauthorized mutation.

## 14. Performance, budgets, and observability

Slice 0 has explicit ceilings:

- eight cases;
- four arms;
- one capture per Case/query, reused by both MKE-bearing arms;
- at most four Search pages of 20 observations;
- at most 32 Evidence reads per Case;
- 10 seconds per MCP call and 120 seconds per Case;
- 1 MiB combined stdout/stderr;
- at most 16 accepted candidate observations per case;
- fixed process/time budget recorded in the receipt;
- no open-ended agent loop.

Public-safe receipts record identities, counts, states, hashes, and bounded error codes, not raw
private content, credentials, cookies, CSRF, or provider secrets.

Structured logs may record stage duration, terminal code, task/execution IDs, attempt/reclaim count,
and hashed idempotency identity. They must not record the raw key, Evidence text, candidate payload,
request body, cookie, CSRF value, or credential.

Product read models remain bounded and paginated. Existing public response caps and browser recovery
budgets remain authoritative. Candidate lists contain at most 20 summaries; candidate detail
contains at most 16 item summaries. Composition receipt/task summaries are at most 16 KiB;
candidate-item and composition detail responses are at most 32 KiB, matching the current BFF
`maxJsonBytes`. C1 repository plans are frozen in
`tests/integration/evidence_composition/test_query_plans.py`; the C2 connected read-model plans are
owned by `tests/integration/connected_demo/test_evidence_composition_query_plans.py`. Both use a
seeded fixture of at least 512 historical composition receipts plus one current composition and
`EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)` after one untimed warm-up. Hard gates require the named
current-action/receipt/item indexes, prohibit sequential scans of candidate/composition tables and
unbounded join/sort nodes, cap total examined rows (including rows removed times loops) at 256 for
summary and 512 for detail, and cap shared-hit blocks at 128/192. Query duration is recorded as a
local observation only; it is not a pass/fail threshold, SLA, or production claim.

## 15. Delivery and release sequence

Default delivery uses six reviewable PRs:

1. **PR A — Slice 0.** Public design/plan/ADR, producer locks, MKE v2 adapter, frozen suite,
   evaluator, native vertical, and exact terminal receipt.
2. **PR B1 — Slice 1 backend.** Migration `0016`, candidate artifact/import, repository, forced-RLS
   authority, authenticated API, and real PostgreSQL/HTTP proof.
3. **PR B2 — Slice 1 product.** Advisor UI, recovery, provider-free candidate browser/database
   proof, and exact accepted/rejected receipts.
4. **PR C1 — Slice 2 headless authority.** Migration `0017`, complete stage/finalize/abandon
   database functions, public composition/read/abandon routes, pinned task/worker operation,
   worker-finalized PlanningRun, repository, API documentation, rollback/reclaim/terminal-recovery/
   concurrency proof, and a deployable headless operation.
5. **PR C2 — Slice 2 product journey.** Current-action/read-model/BFF/controller, old/new
   comparison, bilingual UI/recovery, full browser/database proof, and product documentation.
6. **PR D — release preparation.** v0.1.6 identity, release notes/how-to, current docs, immutable
   v0.1.0-v0.1.5 verification, and release gates.

If C1 becomes too large during authority review, do not land dormant schema or an orphan queued task.
Split only on a complete deployable boundary approved before implementation; otherwise keep the
headless operation atomic. C2 never carries backend runtime required to execute C1.

Every PR uses:

```text
ordinary non-force push
-> Draft PR create/update
-> persisted title/body/head/base readback
-> exact reviewed HEAD + required checks/platform review binding
-> mark Ready only after merge gates pass
-> conditional non-admin squash merge
-> post-merge exact-SHA readback
-> task-owned cleanup
```

After exact-head proof, the Draft PR body carries `StageReadinessCandidateV1` bound to the reviewed
HEAD/tree and committed proof artifact. Only after squash merge, exact-merge checks, tree equality,
main sync, and terminal body reconciliation does it become `StageReadinessReceiptV1` with merge
identity and cleanup state. The next stage mechanically verifies that persisted terminal receipt.
A local pass, candidate, Draft/Ready PR, unmerged receipt, or successful check on a different SHA
does not unlock work.

There is no v0.1.6 release when Slice 0 stops. The full version is prepared only after Slice 2 is
merged and verified. Publication remains a separate annotated-tag/GitHub-Release authority gate.

## 16. Docker and Compose governance

Before any Docker gate, record both host and Docker VM filesystem availability and enforce the
project minimum. Host free space never substitutes for VM evidence.

Every run:

- uses a unique task-owned `COMPOSE_PROJECT_NAME`;
- records projects, containers, images, networks, volumes, and BuildKit cache before/after;
- builds once for the frozen source candidate and reuses only project-native no-build paths;
- retains `night-voyager_postgres-data` and shared base/proof images/cache;
- removes only task-owned containers, networks, ephemeral volumes, and local images;
- runs task-specific `make evidence-loop-down`, whose exact-project teardown includes
  `--volumes --remove-orphans --rmi local`, plus readback; the retention-oriented general
  `make down` is not used to claim zero task residue;
- never performs broad prune, daemon/proxy/source change, disk resize, or shared-resource deletion
  without separate user authority.

Slice 0 does not require product Compose. B2, C2, merged-main release Gate C, Git-free Gate D, and
public-archive Gate E each use the documented normal task-scoped proof when applicable.

Real PostgreSQL gates use task-owned ephemeral volumes and never reuse the retained
`night-voyager_postgres-data` volume as test authority. Teardown also inventories task-owned
process groups, temporary files, open ports, and the disposable MKE store. Signals and gate failure
must execute the same idempotent cleanup path.

## 17. Rollback

- Slice 0 has no business-data rollback. Disable/remove the non-default evaluator lane and retain its
  receipt as historical evidence.
- Slice 1 first stops import. Migration `0016` downgrade is allowed only when no candidate/history
  rows exist or a separately reviewed lossless reversal is proven.
- Slice 2 first stops new composition. Existing activated successors, abandoned staged revisions,
  receipts, and recovery audit remain immutable. Migration `0017` downgrade refuses when any
  composition or recovery history exists.
- A merged or published defect is fixed by a new commit/release; tags and historical release records
  are never rewritten.

## 18. Non-goals and non-claims

- no MKE or DRA producer change;
- no dependency on unreleased producer branches;
- no real provider, paid call, credential, or private corpus;
- no MKE↔DRA call;
- no shared mutable state or generic cross-project bus;
- no runtime multi-agent claim;
- no generic provider-candidate framework;
- no automatic candidate creation, verification, promotion, composition, planning, family decision,
  or execution;
- no source-truth, citation-correctness, provider-quality, statistical-generalization, real-user,
  admissions-outcome, production-deployment, HA/SLA, or business-benefit claim;
- no arbitrary local-library import;
- no claim that the frozen committed capture workflow is a general arbitrary-corpus intake product;
- no second planning, decision, timeline, or execution authority.

## 19. Success and safe-stop statements

If Slice 0 stops:

> Night Voyager evaluated a second read-only Evidence producer under a pre-registered, adversarial,
> zero-mutation suite and found no sufficient incremental value for product integration. The team
> stopped before adding persistence or workflow complexity.

If all slices complete:

> On a frozen public-safe suite, Night Voyager proved bounded incremental MKE Evidence value,
> preserved retrieved content as untrusted data, required assigned-advisor acceptance, composed the
> accepted input through one atomic staging transaction plus generation-guarded success
> finalization, proved assigned-advisor safe abandonment after bounded terminal failure, and reused
> its existing planning, family decision, timeline, execution, and recovery authorities end to end.

Both statements are technically defensible. Only the second authorizes a v0.1.6 feature release.
