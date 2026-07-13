# Night Voyager

Night Voyager has an **M0 bootstrap foundation**, an **M1 fixture-only design contract**, an **M2 identity/session/RLS boundary**, an **M3A deterministic planning foundation**, and an **M3B local synthetic advisor-to-family backend proof**. M3B records advisor review, a family-safe Brief, an explicit decision receipt, and a deterministic timeline. The `/demo` route remains fixture-only and disconnected.

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

`make db-check` uses a disposable PostgreSQL 18 volume to exercise the exact
`0001 -> 0002` graph, idempotent canonical synthetic seed, two-tenant RLS,
runtime function grants, Case CAS, terminal immutability, provenance mismatch,
revision-pinned `review_required` Case handoff,
downgrade/re-upgrade, and size-one pool cleanup. `accepted_synthetic_demo`
Evidence is local proof; callers cannot assert `externally_verified`.

## Current limits

- The M3A backend foundation is not wired to the fixture-only `/demo`; no advisor review, family brief/decision, worker/SSE execution, or domain frontend mutation exists.
- No real DRA, MKE, OpenClaw, model, or messaging adapter.
- No production deployment or user/admissions outcome claim.

## License

MIT
