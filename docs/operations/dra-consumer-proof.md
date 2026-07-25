# DRA consumer proof

The required DRA lane is deterministic and offline:

```bash
make dra-check
```

It validates the copied v1 fixture, strict v0.1.6 live models and transport,
candidate projection, checked-in synthetic source snapshot, fake client,
deterministic evaluation, exact producer/baseline pins, application contracts,
and architecture boundary. It requires no DRA service, network access, API key,
or provider credential.

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

Live provider proof was not run. It is not a required CI gate and is excluded from
`make check`, `make proof`, and Compose. Run it only after separate approval for
one provider attempt and its cost/deadline:

```bash
export DRA_LIVE_PROOF_ACK=separately-authorized-one-attempt
export DRA_ADVISOR_ATTESTATION_ACK=source-inspected-for-bounded-program-fit
export DECISION_RESEARCH_AGENT_API_KEY
export DRA_IDEMPOTENCY_KEY
export DRA_BASE_URL='http://127.0.0.1:<port>'
export DRA_QUERY_FILE='<approved public-safe UTF-8 file>'
export DRA_POLL_DEADLINE_SECONDS='<approved integer>'
export DRA_SOURCE_ROOT='<approved source root>'
export DRA_SOURCE_LOGICAL_PATH='<approved relative source path>'
export DRA_SOURCE_SHA256='<approved lowercase SHA-256>'
make dra-consumer-proof
```

Set `DECISION_RESEARCH_AGENT_API_KEY` and `DRA_IDEMPOTENCY_KEY` in the operator
environment before exporting them; do not place their values in shell history,
files, command arguments, logs, or proof output.

The client accepts loopback HTTP only, disables environment proxy trust and
redirects, performs one keyed create, and applies bounded response/deadline
checks. Ambiguous delivery stops without automatic lost-ack replay; any
recovery attempt needs separate authorization and the same idempotency
identity. Canonical Markdown is written only
to an owned temporary file and is not printed. Output contains bounded
IDs/hashes/statuses and never the API key, query, raw provider response, source
bytes, or local path.

This command proves only the bounded provider consumer surface; it is not the
full governed-live closure. The additional advisor acknowledgement records that
source inspection has occurred, but it does not itself submit a verification
decision or grant promotion authority. Any later approval still requires
source attestation and the atomic API authority gate. Failure is terminal for
the attempt; there is no automatic provider retry.

PR B and PR C remain approved but not implemented. Live provider proof was not
run, and PR A provides no governed-live success claim.
