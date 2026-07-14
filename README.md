# Night Voyager

Night Voyager has an **M0 bootstrap foundation**, an **M1 fixture-only design contract**, an **M2 identity/session/RLS boundary**, an **M3A deterministic planning foundation**, an **M3B local synthetic advisor-to-family backend proof**, an **M4A deterministic durable task/worker/SSE proof**, and an **M4B optional read-only MKE candidate proof**. M4B consumes an exact reviewed artifact only in an isolated local lane and keeps every projection `UNTRUSTED_CANDIDATE`. The default product path and fixture-only `/demo` remain disconnected from MKE.

## Evaluator lane

Evaluators need only Docker Desktop, Docker Compose, and GNU Make. The golden sequence is:

```bash
make help
make doctor
make demo
make proof
make down
```

`make doctor` checks the Docker daemon, required Compose capability, disk space, and local ports. `make proof` runs config, public-hygiene, and installed-wheel checks inside Docker; it does not require host Python, uv, Node.js, or npm.

`make demo` migrates the local database, runs the fail-closed and idempotent
`demo-seed` service, then waits for the synthetic bootstrap stack. The API
health endpoint is `http://127.0.0.1:8000/health`; the web bootstrap page is
`http://127.0.0.1:3000`. Published ports bind to IPv4 loopback only. Run
`make compose-proof` to verify health, real identity and M3B paths, the M4A
HTTP-to-worker-to-PlanningRun-to-SSE path, and API/worker restart durability
without connecting the fixture-only UI.

The fixture-only M1 prototype is available at `http://127.0.0.1:3000/demo`. Its visual and product contracts are documented in [DESIGN.md](DESIGN.md) and [docs/design/](docs/design/).

## Contributor lane

Contributors additionally need Python 3.12.13 managed by [uv](https://docs.astral.sh/uv/), Node.js 24.18.0, and npm.

```bash
make doctor MODE=dev
make check
make db-check
make mke-check
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/README.md](docs/README.md). A Chinese version is available in [README_CN.md](README_CN.md).

`make db-check` uses a disposable PostgreSQL 18 volume to exercise the exact
`0001 -> 0002 -> 0003 -> 0004` graph, idempotent canonical synthetic seed,
two-tenant forced RLS, runtime grants, Case and PlanningRun authority,
payload-free dispatch, leases, generation fencing, retry/cancel/reclaim races,
SSE replay, bounded local concurrency, downgrade/re-upgrade, and pool cleanup.
`accepted_synthetic_demo`
Evidence is local proof; callers cannot assert `externally_verified`.

`make mke-check` runs synthetic fake-process compatibility tests in a disposable optional
environment. Maintainers with the exact operator-supplied wheel and receipt can follow the
[MKE candidate proof runbook](docs/operations/mke-candidate-proof.md). Evaluators and
default `make check` do not need MKE or candidate artifacts.

## Current limits

- M3B/M4A backend paths are not wired to the fixture-only `/demo`; no task or decision frontend mutation exists.
- The worker and SSE proof is local and deterministic, not distributed high availability or a production SLA.
- No DRA, OpenClaw, model, messaging, or product-path MKE `PlanningAdapter`; M4B is a local read-only compatibility adapter only.
- No production deployment or user/admissions outcome claim.

## License

MIT
