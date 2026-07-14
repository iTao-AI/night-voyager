# Night Voyager

Night Voyager turns a synthetic study-abroad comparison into a traceable advisor-to-family decision with durable Agent tasks, explicit human review, and a persisted receipt and timeline.

![Advisor Ledger at review-required](docs/assets/m5-advisor-ledger.png)

![Family decision receipt and timeline](docs/assets/m5-family-receipt-timeline.png)

## Engineering proof

- **PostgreSQL and forced RLS:** tenant-scoped runtime roles read and mutate through narrow authority paths backed by the exact `0001 -> 0002 -> 0003 -> 0004` migration graph.
- **Durable task and SSE:** an `AgentTask` survives worker/API restarts, uses bounded leases and generation fencing, and resumes an authorized event stream.
- **Human gates:** deterministic evidence policy, advisor review, and explicit family confirmation remain separate authorities; model or adapter output cannot promote itself.
- **Browser to database:** the connected `/demo` drives the real Next.js BFF, FastAPI, worker, SSE, and PostgreSQL synthetic flow in Chromium.

## Evaluate the release

Evaluators need Docker Desktop, Docker Compose, and GNU Make:

```bash
make help
make doctor
make demo
make proof
make down
```

Open the connected local synthetic demo at `http://127.0.0.1:3000/demo`. Follow the [connected demo runbook](docs/operations/connected-demo.md) for the advisor-to-family walkthrough, or use the [v0.1.0 verification guide](docs/how-to/verify-v0.1.0-release.md) for the complete release-candidate evidence sequence.

`make doctor` checks Docker, Compose capability, disk space, and local ports. `make demo` migrates and seeds a fresh synthetic stack. `make proof` verifies configuration, public hygiene, and an isolated installed wheel without requiring host Python, uv, Node.js, or npm. `make compose-proof` additionally exercises the browser-to-database flow in real Chromium.

## Synthetic and local limits

- v0.1.0 is a local synthetic portfolio release, not a production deployment or tenancy claim.
- The repository contains no real student records and makes no admissions outcome, real-user, SLA, availability, or business-impact claim.
- The worker and SSE evidence is deterministic local proof, not distributed high availability.
- DRA, OpenClaw, remote providers, messaging, and product-path MKE are not connected. M4B remains an optional read-only compatibility adapter whose projections are `UNTRUSTED_CANDIDATE`.

## Milestones and history

- [v0.1.0 release notes](docs/releases/v0.1.0.md)
- [Architecture and milestone history](DESIGN.md)
- [Documentation index](docs/README.md)
- [Historical M1 visual contract](docs/superpowers/specs/2026-07-11-m1-demo-design.md)

## Contributor lane

Contributors additionally need Python 3.12.13 managed by [uv](https://docs.astral.sh/uv/), Node.js 24.18.0, and npm:

```bash
make doctor MODE=dev
make check
make db-check
make mke-check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). A Chinese version is available in [README_CN.md](README_CN.md).

## License

MIT
