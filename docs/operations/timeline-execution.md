# Governed timeline execution operations

This is a local synthetic, provider-free development walkthrough. It does not
submit applications, upload documents, call a remote model, or represent a
production deployment.

## Run the focused database lane

```bash
COMPOSE_PROJECT_NAME=night-voyager-timeline-execution \
  scripts/run_db_tests.sh timeline-execution seed
```

The lane migrates to `0015`, seeds the deterministic Happy and Blocked
`governed-plan-execution-v1` Cases twice, verifies exact replay and complete child
authority, and proves that no execution exists before an explicit start. The
task-owned project and volume are removed on exit; the protected shared
`night-voyager_postgres-data` volume is not pruned.

## Run the browser journey

```bash
make demo
```

Open `http://127.0.0.1:3000/demo/plan` for Happy or
`http://127.0.0.1:3000/demo/plan?scenario=blocked` for Blocked.

1. Connect as the assigned student and start the seeded timeline.
2. Submit progress or completion for each student-owned checkpoint.
3. Switch through server-side session revoke/bootstrap/mint to the assigned
   advisor. Verify the completion or request an update.
4. Repeat until the arrival checkpoint becomes current, then use the assigned
   parent for its attestation and the advisor for final verification.
5. Confirm the authoritative GET reports `completed`.

Every mutation persists an operation fingerprint and idempotency key, captures
its immutable receipt, and then performs a fresh GET. Role, checkpoint, risk, and
current state come from server projections. Do not use browser storage or query
parameters as authority.

The Blocked route accepts one closed blocked attestation, then exposes the
assigned-advisor reassessment stop and successor-safe terminal handoff. See the
[complete walkthrough](plan-execution-walkthrough.md) for recovery and proof details.

Stop the stack with:

```bash
make down
```

## Troubleshooting

- A session or role mismatch requires safe reconnect; do not edit storage.
- A stale expected version requires a fresh GET and a new operation fingerprint.
- An unavailable projection must remain non-enumerating.
- An `0014 -> 0013` downgrade is valid only before any execution history exists.
  With history, retain the database until a separately approved data migration.
- An `0015 -> 0014` downgrade is valid only before scenario principals or their
  session history exist. Refusal occurs before function or constraint mutation.
