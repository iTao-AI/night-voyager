# Contributing

Night Voyager v0.1.1 is a local synthetic portfolio release with deterministic offline governed DRA capability. Keep changes focused, public-neutral, and reproducible without remote credentials. Use Python 3.12.13, Node.js 24.18.0, a short-lived `codex/` branch, and test-first development for behavior.

M1 fixture-only material is retained as historical visual context; current `/demo`
behavior is the connected M5 local synthetic walkthrough.

## Change-to-test matrix

| Change | Minimum verification |
|---|---|
| Python behavior or configuration | Focused pytest first, then `uv run pytest -q`, Ruff, and Pyright |
| Web behavior or build configuration | Focused Vitest, then lint, typecheck, test, and production build |
| Compose, Dockerfile, ports, or healthcheck | Architecture contract tests, `docker compose config --quiet`, and `make compose-proof` |
| Identity, migration, database role, or RLS | Focused tests, then the disposable PostgreSQL 18 gate with `make db-check` |
| Package identity, dependencies, or release proof | Regenerate the affected lockfile, build artifacts, then `make proof` and `make check` |
| Optional MKE contract or process adapter | `make mke-check`; maintainers additionally run the exact-artifact proof runbook |
| Governed DRA candidate, promotion, or mixed-planning authority | `make dra-check`, `make db-check`, and `make compose-proof`; live provider proof requires separate authorization |
| Governed collaboration, confirmed fact, or revision authority | `make collaboration-check`, the focused `collaboration-db-check` suite, `make db-check`, and `make compose-proof` |
| Documentation or public claim | Link and command review plus public-hygiene proof |

Plain `uv run pytest -q` and the required hosted `python` job run the
non-database suite. The required hosted `compose` job and local `make check`
both force the real PostgreSQL suite through `make db-check`. MKE/MCP process tests are
optional and isolated; required CI runs committed synthetic fake-process coverage without
an external artifact, while the real candidate proof remains maintainer-operated.

## Guardrails

- Migrations and RLS changes require `make db-check` using runtime-equivalent roles. The connected `/demo` must continue to consume role-scoped backend projections rather than reproduce authority in the BFF or client.
- Connected-demo transport or UI changes require focused backend/frontend tests plus the real `make compose-proof` Chromium flow; mocks and static screenshots are not browser-to-database evidence.
- M3A fixtures must pass offline `scripts/seed_demo.py --validate-only`; `accepted_synthetic_demo` must never be described as externally verified Evidence.
- Fixtures must be synthetic, provenance-labelled, deterministic, and pass `make fixtures-check`; real student records are prohibited.
- Public claims must match reproducible repository evidence and must not imply production use, real users, admissions outcomes, or measured business impact.
- Never commit `.env`, credentials, private paths, personal data, or generated proof noise.
- Never rebuild or commit an operator-supplied MKE wheel/receipt. Follow [the candidate proof runbook](docs/operations/mke-candidate-proof.md); all projected Evidence remains `UNTRUSTED_CANDIDATE` and cannot enter `PlanningAdapter`.
- DRA import must remain `UNTRUSTED_CANDIDATE`; verification and promotion stay one atomic database authority. Mixed planning may use external authority only for `australia_program_fit` and must preserve the exact synthetic baseline for all other facts. Never put `make dra-consumer-proof` in required CI or run it without the [separate authorization gate](docs/operations/dra-consumer-proof.md).
- Collaboration messages never grant Case authority. Participant proposals remain revision-pinned candidates until an assigned advisor confirms them through the atomic PostgreSQL gate; runtime code must not restore the legacy whole-revision writer.
- Run `make check` and `git diff --check`, inspect the exact diff, and stage exact paths before committing.

Pull requests should state scope, actual verification, documentation impact, and remaining risk.
