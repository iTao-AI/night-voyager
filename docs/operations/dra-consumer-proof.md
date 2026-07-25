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

Live provider proof was not run. PR B is implemented provider-free; PR C remains approved but not implemented.
Stage 1 therefore has no governed-live success claim.
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
  --one-attempt-ack separately-authorized-one-attempt --json
uv run python scripts/verify_dra_live_closure.py preflight-live \
  --receipt-root '<same-private-root>' --json
```

`preflight-live` reads no environment values and performs no provider access. Its
receipt binds the intent, exact v0.1.6 producer, scenario/schema identities,
filesystem readiness, `UNTRUSTED_CANDIDATE` freeze, and one-shot budget.

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
logs, or proof output. `capture-live` re-reads the exact query bytes immediately
before `/health` and create. It performs at most one keyed create, validates the
strict terminal projection, writes the canonical artifact only under the private
receipt root, then stops with `operator_action_required`.

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
artifact, Evidence ownership, advisor and tenant identities; imports only the
existing `UNTRUSTED_CANDIDATE`; confirms that no verification/promotion exists; and
deletes artifact bytes. It does not promote Evidence, start planning, create an
AdvisorReview, or make a family decision.

## Recovery and cleanup

There is no remote cancellation command. An ambiguous create stops before replay:

```bash
uv run python scripts/verify_dra_live_closure.py reconcile-create \
  --receipt-root '<same-private-root>' \
  --query-file '<same-bounded-file>' \
  --exact-replay-ack separately-authorized-one-attempt --json
```

This is a separately acknowledged replay of the exact frozen request and create key.
A poll deadline stores the accepted run identity; `resume-poll` polls only the same run
and never creates another:

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
