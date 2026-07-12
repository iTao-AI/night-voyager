# Contributing

Night Voyager is in bootstrap stage. Keep changes focused, public-neutral, and reproducible without remote credentials. Use Python 3.12.13, Node.js 24.18.0, a short-lived `codex/` branch, and test-first development for behavior.

## Change-to-test matrix

| Change | Minimum verification |
|---|---|
| Python behavior or configuration | Focused pytest first, then `uv run pytest -q`, Ruff, and Pyright |
| Web behavior or build configuration | Focused Vitest, then lint, typecheck, test, and production build |
| Compose, Dockerfile, ports, or healthcheck | Architecture contract tests, `docker compose config --quiet`, and `make compose-proof` |
| Identity, migration, database role, or RLS | Focused tests, then the disposable PostgreSQL 18 gate with `make db-check` |
| Package identity, dependencies, or release proof | Regenerate the affected lockfile, build artifacts, then `make proof` and `make check` |
| Documentation or public claim | Link and command review plus public-hygiene proof |

## Guardrails

- Migrations and RLS changes require `make db-check` using runtime-equivalent roles. The M2 backend remains separate from the fixture-only `/demo`.
- Fixtures must be synthetic, provenance-labelled, deterministic, and pass `make fixtures-check`; real student records are prohibited.
- Public claims must match reproducible repository evidence and must not imply production use, real users, admissions outcomes, or measured business impact.
- Never commit `.env`, credentials, private paths, personal data, or generated proof noise.
- Run `make check` and `git diff --check`, inspect the exact diff, and stage exact paths before committing.

Pull requests should state scope, actual verification, documentation impact, and remaining risk.
