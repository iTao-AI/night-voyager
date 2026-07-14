# Verify the v0.1.0 release candidate

This procedure reproduces the local synthetic portfolio release evidence. Run it from a clean checkout of the v0.1.0 candidate revision with Docker Desktop, Docker Compose, GNU Make, Python 3.12.13 through uv, and Node.js 24.18.0 available.

## 1. Verify the contributor environment

```bash
make doctor MODE=dev
uv lock --check
```

## 2. Run code, database, and packaged-source gates

```bash
make check
make proof
```

`make check` includes the frontend lint, typecheck, Vitest, and production build gates plus the disposable PostgreSQL/RLS suite. `make proof` validates the Docker snapshot and installed-wheel path.

## 3. Run the connected browser proof

```bash
make compose-proof
make down
docker compose ps --all
```

The final command must show no remaining project containers. `make compose-proof` uses the local synthetic FastAPI, worker, SSE, PostgreSQL, and Chromium flow; mocks or static screenshots are not substitutes.

## 4. Verify the clean release tree

After all intended files are committed, run:

```bash
uv run python scripts/verify_release.py --tree-mode release
git diff --check
git status --short
```

The verifier requires a clean Git tree, consistent v0.1.0 package identity, the release documentation contract, public-hygiene checks, valid browser screenshots, and an isolated installed-wheel import.

## Evidence boundary

Passing these commands proves the checked-out local synthetic candidate. It does not establish production deployment, real users, admissions outcomes, SLA, availability, or business impact. The only release artifacts are GitHub-generated source archives.
