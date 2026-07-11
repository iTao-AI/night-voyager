# Night Voyager

Night Voyager is currently at the **M0 bootstrap stage**. This repository provides a reproducible local foundation for a Python API, Next.js web application, PostgreSQL, and durable worker process. It does not yet implement study-abroad decision workflows, production tenancy, or live provider integrations.

## Prerequisites

- Python 3.12.13 managed by [uv](https://docs.astral.sh/uv/)
- Node.js 24.18.0 and npm
- Docker Desktop with Docker Compose
- GNU Make

## Bootstrap checks

```bash
cp .env.example .env
make doctor MODE=dev
make check
make demo
make proof
make down
```

`make demo` starts synthetic bootstrap services only. The API health endpoint is `http://localhost:8000/health`; the web bootstrap page is `http://localhost:3000`.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/README.md](docs/README.md). A Chinese version is available in [README_CN.md](README_CN.md).

## Current limits

- No domain state machine, evidence workflow, advisor/family UI, or tenant/RLS migration.
- No real DRA, MKE, OpenClaw, model, or messaging adapter.
- No production deployment or user/admissions outcome claim.

## License

MIT
