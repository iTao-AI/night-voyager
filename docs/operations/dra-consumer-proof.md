# DRA consumer proof

The required DRA lane is deterministic and offline:

```bash
make dra-check
```

It validates the copied v1 fixture, strict v0.1.6 live models and transport,
candidate projection, checked-in synthetic source snapshot, fake client,
deterministic evaluation, exact producer/baseline pins, the provider-free Stage 1
capture rehearsal, application contracts, and architecture boundary. The rehearsal
crosses an inspection pause, copies the recovery bundle, resumes in a fresh process,
imports one `UNTRUSTED_CANDIDATE`, and proves that no second provider run occurs. It
requires no DRA service, network access, API key, or provider credential.

## Dedicated database proof

Migration and HTTP integration tests use `DRA_PROOF_CASE_ID`, separate from the
M3A and connected-demo Cases. Migrations `0005` and `0010` are seed-free. When an operator
needs the explicit idempotent test/development seed against a migrated database:

```bash
NIGHT_VOYAGER_DEMO_MODE=true uv run python scripts/seed_dra_proof.py
```

`make db-check` proves forced RLS, API/worker grants, immutable ledgers,
idempotency, concurrency, rollback, reject-without-promotion, and approval with
exactly one external Evidence plus the synthetic baseline. Its isolated `0010`
lane also proves the closed v0.1.6 producer tuple, historical-row readability,
API-only outcome projection, downgrade refusal with live history, and clean
re-upgrade.

The complete deterministic closure is also part of the isolated Compose proof:

```bash
make compose-proof
make down
docker compose ps --all
```

Before the unchanged M4A/M5 reset lanes, it seeds the dedicated DRA proof Case,
imports the checked-in v0.1.6 scenario candidate as `UNTRUSTED_CANDIDATE`,
performs the atomic advisor approval/promotion, creates
`generate_governed_mixed_planning_run_v1`, runs the existing worker and SSE
path, and closes through the existing AdvisorReview and family-decision
authorities. The historical v0.1.3 fixture remains a separate byte-identity
compatibility proof. Both use checked-in synthetic bytes and never call a DRA
service.

## Separately authorized live proof

Live provider proof was not run. PR A, PR B, and PR C are implemented provider-free,
but the capability remains
`INCOMPLETE_PENDING_LIVE_ACCEPTANCE`. There is no governed-live success claim.
The live command is not a required CI gate and is excluded from `make check`,
`make proof`, and Compose. Run it only after separate approval for one provider
attempt and its cost/deadline.

The command journey is deliberately two-step. First freeze the exact Case, actor,
tenant, query identity, receipt root, and one-attempt authorization; then create the
provider-free preflight receipt:

```bash
uv run python scripts/verify_dra_live_closure.py freeze-intent \
  --receipt-root '<private-mode-0700-root>' \
  --query-file '<bounded-public-safe-utf8-file>' \
  --organization-id '<organization-uuid>' \
  --case-id '<case-uuid>' \
  --expected-case-revision '<revision>' \
  --advisor-actor-id '<advisor-uuid>' \
  --deadline-seconds '<approved-integer>' \
  --poll-seconds '<approved-number>' \
  --one-attempt-ack separately-authorized-one-attempt --json
uv run python scripts/verify_dra_live_closure.py preflight-live \
  --receipt-root '<same-private-root>' --json
```

`preflight-live` reads no environment values and performs no provider access. Its
receipt binds the intent, exact v0.1.6 producer, scenario/schema identities,
filesystem readiness, frozen monotonic deadline/poll interval,
`UNTRUSTED_CANDIDATE` freeze, and one-shot budget.

Only after the preflight receipt exists, inject the required process-only values:

```bash
export DRA_LIVE_PROOF_ACK
export DECISION_RESEARCH_AGENT_API_KEY
export DRA_BASE_URL
export DRA_QUERY_FILE
export DRA_POLL_DEADLINE_SECONDS
export DRA_LIVE_RECEIPT_ROOT
export NIGHT_VOYAGER_LIVE_ORGANIZATION_ID
export NIGHT_VOYAGER_LIVE_ACTOR_ID
export NIGHT_VOYAGER_LIVE_SESSION_ID
make dra-consumer-proof
```

Set all values in the operator environment before exporting the names; do not place
credential or session values in shell history, files, command arguments, receipts,
logs, or proof output. `DRA_POLL_DEADLINE_SECONDS` must equal the deadline frozen by
`freeze-intent`; the frozen poll interval is not read from ambient state.
`capture-live` re-reads the exact query bytes immediately
before `/health` and create. It performs at most one keyed create, validates the
strict terminal projection, polls at the frozen interval until the frozen monotonic
deadline, writes the canonical artifact only under the private receipt root, then
stops with `operator_action_required`. If the descriptor-bound receipt root and its
operator-visible pathname no longer identify the same directory and artifact,
inspection fails closed instead of returning a pathname to replacement bytes.

The operator privately inspects that artifact and the same-run Evidence inventory.
Stage 1 accepts no source snapshot. The only resumed input is a URL-only declaration
for the unique cited raw URL:

```bash
export NIGHT_VOYAGER_LIVE_API_BASE_URL
export NIGHT_VOYAGER_LIVE_SESSION
export NIGHT_VOYAGER_LIVE_CSRF
uv run python scripts/verify_dra_live_closure.py select-and-import \
  --receipt-root '<same-private-root>' \
  --declared-raw-url '<exact-cited-raw-url>' --json
```

`select-and-import` is provider-free. It revalidates the frozen intent, run,
artifact, Evidence ownership, advisor and tenant identities; imports only the exact
operator-selected Evidence row as the existing `UNTRUSTED_CANDIDATE`; confirms that
no verification/promotion exists; and deletes artifact bytes. Other cited rows from
the same run are not added to that candidate import. It does not promote Evidence,
start planning, create an AdvisorReview, or make a family decision.

## Canonical resumable operator transcript

The frozen live journey is one ordered transcript. Each mutation prints a bounded
actor, tenant, Case, target, and action preview and requires a distinct
acknowledgement; no global acknowledgement authorizes a later stage.

| Step | Command | Durable predecessor | Ephemeral input | Provider / mutation | Success output | Recovery |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `preflight-live` | frozen intent | none | no provider, no business mutation | preflight receipt | rerun exact preflight |
| 2 | `capture-live` | preflight receipt | provider access for one frozen attempt | one provider create plus same-run polling | inspection-required receipt | `reconcile-create` or `resume-poll` |
| 3 | `select-and-import` | inspection-required receipt | assigned advisor session | candidate import only | capture receipt | `inspect-recovery` |
| 4 | `promote` | capture receipt plus re-supplied snapshot | fresh assigned advisor session and `acknowledge-promote` | atomic existing promotion authority | `promotion_recorded` | exact-key authority reconciliation |
| 5 | `review` | promotion receipt | fresh assigned advisor session and `acknowledge-review` | existing task/worker/SSE and AdvisorReview | `review_recorded` | exact-key authority reconciliation |
| 6 | `decide` | review receipt | fresh parent session and `acknowledge-decide` | existing family decision authority | `decision_recorded` | exact-key authority reconciliation |
| 7 | `evaluate` | decision receipt | fresh assigned advisor session and `acknowledge-evaluate` | read-only migration `0010` projection | `closure_passed` or bounded failure | re-run evaluation only |
| 8 | `cleanup` | exact receipt root | cleanup acknowledgement | task-owned filesystem cleanup only | cleanup receipt | inspect residue, then exact cleanup |

Stage 2 never fetches a source. The operator supplies a task-owned mode-`0700`
root containing the declared mode-`0600` snapshot. Descriptor-bound no-follow
traversal reads the exact bytes once, checks the original selected URL,
byte length, SHA-256, and required known gaps, then removes the snapshot on
success, handled failure, `SIGINT`, or `SIGTERM`. Hard-termination residue is
detected on the next open and blocks progress until explicit cleanup. Durable
receipts retain URL identity, length, hash, and bounded metadata only.

Every Stage 2–4 recovery re-reads current product authority before deciding
whether to synthesize success, replay the exact request/key, or fail closed on
partial/conflicting state. Fresh processes must re-inject the assigned-advisor
or parent session. Session identifiers, cookies, headers, auth-file paths, and
credential material are never receipt, bundle, log, or cleanup content.
HTTP mutation transport loss is converted to a bounded ambiguous outcome only
at the POST boundary. Candidate and decision recovery use their existing narrow
reads; planning-task and AdvisorReview recovery use actor/key-bound recovery
reads backed by the existing idempotency records. They do not expose a generic
task, review, or idempotency query surface.

Each provider-free command consumes one bounded public-safe JSON input whose
embedded parent receipt must byte-match the durable predecessor. The snapshot
root is supplied only to `promote`; session values remain process-only:

```bash
uv run python scripts/verify_dra_live_closure.py promote \
  --receipt-root '<same-private-root>' \
  --input-file '<promotion-input.json>' \
  --snapshot-root '<private-snapshot-root>' \
  --ack acknowledge-promote --json
uv run python scripts/verify_dra_live_closure.py review \
  --receipt-root '<same-private-root>' \
  --input-file '<review-input.json>' \
  --ack acknowledge-review --json
uv run python scripts/verify_dra_live_closure.py decide \
  --receipt-root '<same-private-root>' \
  --input-file '<decision-input.json>' \
  --ack acknowledge-decide --json
uv run python scripts/verify_dra_live_closure.py evaluate \
  --receipt-root '<same-private-root>' \
  --input-file '<receipt-derived-expected-outcome.json>' \
  --ack acknowledge-evaluate --json
```

After input and acknowledgement validation, each mutation command writes a
content-free preview to standard error before accessing product authority. The
preview binds only the stage and canonical input SHA-256; the final JSON result
is written separately to standard output.

The evaluator rejects an expected outcome that is not exactly derivable from the
four typed durable stage receipts. Migration `0010` separately proves the exact
execution, terminal event/SSE cursor, five-field Skill pin, AdvisorReview,
DecisionReceipt, and TimelinePlan identities.

`decision_recorded` is not capability completion. A failed evaluator after a
committed decision leaves a recoverable incomplete state and must not repeat or
roll back that decision. A bounded retained failure receipt is safe-stop evidence
only. After a second substantive failure in the same terminal lane, stop and
investigate; do not authorize another live attempt from the failure receipt.

Auxiliary provider-free checks remain separate:

```bash
uv run python scripts/verify_dra_live_closure.py rehearse-capture \
  --receipt-root '<private-rehearsal-root>' --phase capture --json
uv run python scripts/verify_dra_live_closure.py rehearse-full --json
```

`rehearse-full` uses the deterministic fixture through real PostgreSQL, FastAPI,
worker, SSE, review, decision, and the migration `0010` outcome inspector. It
does not consume the live provider budget. Stage 2, Stage 3, Stage 4, and final
evaluation each run in a separate subprocess, reopen the durable receipt store,
and re-inject only the role-specific ephemeral authority. The rehearsal also
proves that a missing predecessor and a forged predecessor are rejected before
mutation.

## Candidate freeze

After PR A/B/C merge and exact merged-main `python`, `frontend`, and `compose`
checks succeed, produce an executable readiness receipt. First record the
repository-required Docker host/VM preflight and before/after task inventory in
one public-safe file, with task-scoped teardown complete and retained
volumes/shared images/cache preserved. Then run:

```bash
uv run python scripts/verify_dra_live_closure.py freeze-candidate \
  --receipt-root '<private-mode-0700-root>' \
  --merged-main-sha '<exact-40-hex-merged-main>' \
  --docker-inventory-file '<verified-docker-evidence.json>' \
  --hosted-check-evidence-file '<exact-head-checks.json>' \
  --recovery-evidence-file '<recovery-matrix.json>' \
  --authority-review-evidence-file '<authority-review.json>' \
  --hosted-check python --hosted-check frontend --hosted-check compose \
  --authorization-placeholder PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION \
  --json
```

Each evidence JSON is bound to the same exact merged-main SHA, but its status is
not trusted. Freeze rejects any recovery command outside the closed command
allowlist before starting a subprocess, then re-runs the accepted command. It
removes any caller threshold override, runs the repository `MODE=dev` host and
Docker VM preflight, enforces the default `8,388,608 KiB` VM minimum, and captures
the fixed task project's before/after Compose, container, image, build-cache,
network, and volume inventories. It also reads the exact GitHub check-run,
merged-PR, final-head, reviewed-tree, and merge-tree identities. Independent
human review authority is supplied only through the explicit attestation
receipt described below; it is not inferred from the PR body, merge state,
automation, or a GitHub Review. Machine-observable identities and hashes must
match the independently observed results; the human verdict must arrive through
the closed attestation rather than a caller-written status-only file.
Feature-branch HEADs, missing/failed checks, stale attestations, dirty main,
residual task resources, or local/origin/live main drift fail closed.

The four files use closed schemas:
`night-voyager.dra-live-docker-evidence.v3`,
`night-voyager.dra-live-hosted-checks-evidence.v1`,
`night-voyager.dra-live-recovery-evidence.v2`, and
`night-voyager.dra-live-authority-review-evidence.v2`. Extra keys are rejected;
the superseded Docker v1/v2, recovery v1, and authority-review v1 shapes are not
accepted.
Docker evidence binds the canonical task project, default host and Docker VM
thresholds, observed host/VM free space, a semantic preflight hash, all six
before/after inventory hashes, and the exact retained image, volume, and
build-cache identities. Recorded and freshly observed free-space values are each
validated against their threshold; above-threshold numeric drift between the two
observations is not treated as contract drift. The semantic preflight projection
normalizes only those two availability numbers and retains every other expected
`make doctor MODE=dev` pass marker. Missing, altered, reordered, or additional
preflight output, threshold override leakage, or a below-threshold observation
fails closed. Hosted evidence binds repository and the three exact check run IDs.
Recovery evidence binds the closed command and its positive exact passed count.
Freeze runs the allowlisted command fresh with `check=True`, parses the closed
successful pytest summary, and ignores only elapsed-time presentation. A count
change or any failed, error, skipped, xfailed, xpassed, warning, or malformed
summary fails closed.

Docker evidence v3 hashes a closed semantic projection, not Docker CLI
presentation bytes. Compose inventory is parsed as a JSON array; container,
image, build-cache, network, and volume inventories are parsed as JSON records,
with build cache collected by `docker buildx du --format json`. The projection
sorts records and object keys, normalizes unordered label, network, and parent
sets, and converts cache sizes to bytes. Relative or presentation-only fields
such as `CreatedSince`, `CreatedAt`, and `LastUsedAt` are excluded. Resource
identity and state, task residue, retained images and volumes, and the canonical
build-cache identity remain bound. Malformed JSON, missing or wrongly typed
required fields, duplicate resource identities, and malformed set values fail
closed.

Authority-review evidence is a public-neutral human attestation with this exact
closed shape:

```json
{
  "schema_version": "night-voyager.dra-live-authority-review-evidence.v2",
  "head_sha": "<exact-merged-main-40-hex>",
  "repository": "<owner/repository>",
  "pull_request": 70,
  "reviewed_head_sha": "<exact-reviewed-head-40-hex>",
  "verdict": "CLEAN",
  "review_record_id": "<opaque-public-neutral-record-id>",
  "review_record_sha256": "<sha256-of-the-independent-review-record>",
  "acknowledgement": "independent_authority_review_attested"
}
```

The attesting human supplies the opaque record identity and SHA-256 without
copying private review content into this repository or the durable readiness
receipt. Missing, malformed, non-`CLEAN`, stale, cross-head, wrongly
acknowledged, or extra-field evidence fails closed. Freeze live-requeries that
the final PR head equals `reviewed_head_sha`, the PR merged as `head_sha`, and
the reviewed and merge commits have the same tree. A repository whose ruleset
requires zero GitHub approvals, including a PR whose GitHub reviews list is
empty, therefore remains compatible with an explicit independent human review;
GitHub review state is neither required nor treated as human-review authority.

The readiness receipt binds the exact merged main, spec and PR C plan hashes,
producer pin, scenario, intent/receipt/CLI schema identities, required hosted
checks, recovery-matrix result, Docker preflight/inventory, cleanup state, and
the explicit authorization placeholder. A successful freeze still reports
`INCOMPLETE_PENDING_LIVE_ACCEPTANCE`. Only a separately authorized frozen live
attempt whose complete evaluator reports `closure_passed` can change that claim.

## Recovery and cleanup

There is no remote cancellation command. An ambiguous create stops before replay:

```bash
uv run python scripts/verify_dra_live_closure.py reconcile-create \
  --receipt-root '<same-private-root>' \
  --query-file '<same-bounded-file>' \
  --exact-replay-ack separately-authorized-one-attempt --json
```

This is a separately acknowledged replay of the exact frozen request and create key.
The controller requires the supplied reconciliation receipt to equal its durable
receipt and predecessor identities before provider access. A poll deadline stores the
accepted run identity; `resume-poll` revalidates the durable preflight and poll receipt,
polls only the same run at the frozen interval, and never creates another:

```bash
uv run python scripts/verify_dra_live_closure.py resume-poll \
  --receipt-root '<same-private-root>' --json
uv run python scripts/verify_dra_live_closure.py inspect-recovery \
  --receipt-root '<same-private-root>' --json
```

`inspect-recovery` is provider-free and read-only. Output uses the closed exit
classes `success`, `safe_pause`, `recoverable_incomplete`, `terminal_failure`, and
`cleanup_incomplete`; it contains bounded identities, receipt hashes, exact next
command, artifact/session cleanup state, and no raw exception or private value.

Cleanup defaults to a dry run for one exact root. Deletion needs its own acknowledgement:

```bash
uv run python scripts/verify_dra_live_closure.py cleanup \
  --receipt-root '<same-private-root>' --json
uv run python scripts/verify_dra_live_closure.py cleanup \
  --receipt-root '<same-private-root>' \
  --delete-ack delete-exact-live-artifact --json
```

Normal completion, handled failure, `SIGINT`, and `SIGTERM` clean task-owned artifact
bytes synchronously. `SIGKILL`, host crash, and power loss cannot guarantee cleanup;
an orphaned artifact blocks recovery until explicit cleanup. Identity/preflight,
inspection, recovery, failure, capture, and cleanup receipts are retained for audit;
query, artifact, credential, and session bytes are not durable receipt content.

For the required provider-free proof, `rehearse-capture` performs the same inspection
pause/resume contract with fake transport. It is already run by `make dra-check`;
do not substitute it for separate live authorization.
