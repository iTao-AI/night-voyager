# Night Voyager

Night Voyager has an **M0 bootstrap foundation**, an **M1 fixture-only design contract**, and an **M2 backend identity/session/RLS security foundation**. The repository provides a reproducible local foundation for a Python API, Next.js web application, PostgreSQL, and durable worker process. The `/demo` route demonstrates the approved advisor-to-family product flow with synthetic fixtures; it is not connected to a domain backend and does not implement mutations, production tenancy, or live provider integrations.

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
`make compose-proof` to verify health plus the real bootstrap and session-mint
API path without connecting the fixture-only UI.

The fixture-only M1 prototype is available at `http://127.0.0.1:3000/demo`. Its visual and product contracts are documented in [DESIGN.md](DESIGN.md) and [docs/design/](docs/design/).

## Contributor lane

Contributors additionally need Python 3.12.13 managed by [uv](https://docs.astral.sh/uv/), Node.js 24.18.0, and npm.

```bash
make doctor MODE=dev
make check
make db-check
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/README.md](docs/README.md). A Chinese version is available in [README_CN.md](README_CN.md).

`make db-check` uses a disposable PostgreSQL 18 volume to prove migrations, synthetic identity seed idempotency, non-owner runtime roles, restricted auth functions, forced RLS, session lifecycle, and pool cleanup. It always removes the test volume.

## Current limits

- The backend security foundation is not wired to the fixture-only `/demo`; no domain state machine, evidence workflow backend, or advisor/family mutation exists.
- No real DRA, MKE, OpenClaw, model, or messaging adapter.
- No production deployment or user/admissions outcome claim.

## License

MIT
