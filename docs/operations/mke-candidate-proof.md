# Run the MKE candidate proof

This maintainer-only runbook verifies an operator-supplied exact MKE artifact. The proof is
local, synthetic, read-only, and always projects `UNTRUSTED_CANDIDATE`. It does not connect
`PlanningAdapter`, M4A tasks, API, worker, SSE, Compose, frontend, or `/demo`.

## Quick path

```bash
export MKE_WHEEL=/path/to/candidate.whl MKE_RECEIPT=/path/to/candidate-artifact-receipt.json
make mke-doctor MKE_WHEEL="$MKE_WHEEL" MKE_RECEIPT="$MKE_RECEIPT"
make mke-artifact-check MKE_WHEEL="$MKE_WHEEL" MKE_RECEIPT="$MKE_RECEIPT"
make mke-check
make mke-consumer-proof MKE_WHEEL="$MKE_WHEEL" MKE_RECEIPT="$MKE_RECEIPT"
```

The checked lock currently records `artifact_locator=operator_supplied`. If the exact
wheel or receipt is unavailable, stop. Do not rebuild substitute bytes from a checkout,
and do not copy either artifact into this repository.

## What the proof does

The controller verifies wheel bytes, SHA-256, receipt self-hash, package metadata, Python
range, console entry point, source commit, and upstream same-wheel proof before install.
It then creates one temporary environment and store, installs the exact wheel, ingests only
the committed one-page synthetic PDF, verifies active counts of one, calls List/Search/Ask
with `limit=1`, projects and pairs the positive result, proves the scoped absent-token
result, closes the consumer, and removes all owned state.

The success JSON is `night_voyager.m4b_proof.v1`. It contains stable identities, schema
names, bounded counts/states, verification booleans, and a canonical receipt SHA only. It
contains no path, source/query text, MKE opaque ID, timestamp, or elapsed time.

## Upgrade and rollback

Treat the lock, upstream receipt, and wheel as one atomic candidate. For an upgrade, obtain
an independently reviewed wheel/receipt pair, run `record-lock` only after identity checks
pass, review the lock diff, and run all four quick-path gates. Keep the previous exact pair
available until the new branch lands. To roll back, restore the previous lock and use its
matching wheel/receipt; never mix candidates or edit digests by hand.

## Failure recovery

Failure stdout contains only the stable code. Correct the owned input or environment and
rerun the named command; never bypass a failed check.

| Code | Recovery command or action |
|---|---|
| `mke_candidate_inputs_missing` | Restore the exact wheel/receipt, then run `make mke-doctor`. |
| `mke_candidate_mismatch` | Obtain the reviewed matching pair; run `make mke-artifact-check`. |
| `mke_environment_failed` | Restore Python 3.12 and `uv`; run `make mke-doctor`. |
| `mke_install_failed` | Check local disk/package readability; rerun `make mke-consumer-proof`. |
| `mke_store_setup_failed` | Verify the committed fixture; rerun `make mke-consumer-proof`. |
| `mke_contract_incompatible` | Stop and review the public v1 contract before retrying. |
| `mke_response_invalid` | Stop and review the exact candidate response contract. |
| `mke_store_empty` | Rerun `make mke-consumer-proof` from a fresh temporary store. |
| `mke_no_active_publication` | Rerun the full proof; do not reuse the failed store. |
| `mke_active_store_no_match` | Review the positive synthetic assertion and candidate. |
| `mke_manifest_mapping_failed` | Restore the checked manifest/source pair and rerun proof. |
| `mke_evidence_role_mismatch` | Restore the exact approved claim and `EvidenceRole`. |
| `mke_locator_mismatch` | Restore the one-page fixture/manifest and rerun proof. |
| `mke_source_snapshot_changed` | Regenerate the owned fixture deterministically and review. |
| `mke_snapshot_pair_mismatch` | Rerun the disposable no-writer proof from the start. |
| `mke_startup_timeout` | Confirm local capacity, then rerun `make mke-consumer-proof`. |
| `mke_tool_timeout` | Confirm local capacity, then rerun `make mke-consumer-proof`. |
| `mke_transport_failed` | Run `make mke-check`, then rerun the real proof. |
| `mke_server_exit` | Run `make mke-check` and inspect local bounded diagnostics. |
| `mke_output_limit_exceeded` | Stop; review the candidate contract rather than raising bounds. |
| `mke_cleanup_failed` | Confirm no owned MKE process remains before rerunning. |
| `mke_consumer_failed` | Run `make mke-check`, then repeat the full proof. |

The proof never accepts Evidence. Acceptance, MKE-backed planning, and visible integration
remain deferred beyond M4B.
