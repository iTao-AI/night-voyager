.DEFAULT_GOAL := help
export UV_BUILD_CONSTRAINT := build-constraints.txt
export UV_REQUIRE_HASHES := 1

.PHONY: help doctor demo proof compose-proof db-check fact-to-plan-db-check collaboration-db-check collaboration-check skills-db-check skills-check check dra-check dra-consumer-proof \
	mke-doctor mke-artifact-check mke-check mke-consumer-proof logs down fixtures-check reset-demo

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Verify evaluator prerequisites; MODE=dev adds contributor tools
	@scripts/doctor.sh

demo: ## Migrate, explicitly seed synthetic identity, and start the local stack
	docker compose up --build --wait

proof: ## Run config, hygiene, and wheel proof using Docker only
	docker build --file Dockerfile.proof --target proof --tag night-voyager-proof:local .

compose-proof: ## Prove M3B/M4A flows, restart durability, health, and teardown
	@scripts/verify_compose.sh

db-check: ## Prove migrations, roles, sessions, catalog, and forced RLS on a fresh database
	@scripts/run_db_tests.sh

fact-to-plan-db-check: ## Prove the isolated 0009 planning-start migration parity lane
	@scripts/run_db_tests.sh fact-to-plan

collaboration-db-check: ## Run one disposable governed-collaboration database suite
	@SUITE="$(SUITE)" scripts/run_collaboration_db_tests.sh

collaboration-check: ## Run the deterministic offline collaboration contract lane
	uv run pytest -q tests/unit/collaboration tests/unit/test_api.py \
	  tests/unit/test_release_surface.py tests/architecture/test_collaboration_contract.py \
	  tests/security/test_collaboration_catalog.py tests/security/test_database_catalog.py
	uv run pytest -o addopts= -q -m "not database" \
	  tests/integration/collaboration/test_http_collaboration.py

skills-db-check: ## Run one disposable versioned-Skill database suite
	@SUITE="$(SUITE)" sh scripts/run_skill_db_tests.sh

skills-check: ## Run the deterministic offline versioned-Skill contract lane
	uv run pytest -q tests/unit/skills tests/unit/identity/test_seed_demo.py \
	  tests/contracts/test_skill_runtime_registry.py \
	  tests/architecture/test_skills_contract.py tests/unit/test_release_surface.py \
	  tests/security/test_database_catalog.py

mke-doctor: ## Verify an operator-supplied MKE candidate without installing it
	@uv run python scripts/verify_mke_consumer.py doctor --wheel "$(MKE_WHEEL)" --candidate-receipt "$(MKE_RECEIPT)"

mke-artifact-check: ## Emit the verified MKE candidate identity
	@uv run python scripts/verify_mke_consumer.py artifact-check --wheel "$(MKE_WHEEL)" --candidate-receipt "$(MKE_RECEIPT)" --json

mke-check: ## Run the isolated optional MKE/MCP process tests
	@scripts/run_mke_lane.sh test

mke-consumer-proof: ## Run the real exact-candidate read-only proof
	@scripts/run_mke_lane.sh proof --wheel "$(MKE_WHEEL)" --candidate-receipt "$(MKE_RECEIPT)" --json

dra-check: ## Run the deterministic offline DRA consumer contract lane
	uv run pytest -q tests/contracts/test_dra_v1_contract.py \
	  tests/contracts/test_dra_reconciliation.py tests/unit/dra \
	  tests/architecture/test_dra_contract.py
	uv run python scripts/verify_dra_consumer.py fixture --json

dra-consumer-proof: ## Run one separately authorized live DRA proof attempt
	@scripts/run_dra_lane.sh live --json

check: ## Run backend, frontend, Compose, and proof checks
	uv lock --check
	uv run pytest -q -m "not database and not mke"
	uv run ruff check .
	uv run pyright
	uv build --build-constraints build-constraints.txt --require-hashes
	$(MAKE) dra-check
	$(MAKE) collaboration-check
	$(MAKE) skills-check
	npm --prefix web ci
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run test
	npm --prefix web run build
	docker compose config --quiet
	$(MAKE) db-check
	$(MAKE) collaboration-db-check SUITE=authority
	$(MAKE) fixtures-check
	$(MAKE) proof

logs: ## Follow local bootstrap service logs
	docker compose logs --follow

down: ## Stop the stack and preserve database data
	docker compose down --remove-orphans

fixtures-check: ## Validate the public-safe synthetic M3A manifest without database access
	@uv run python scripts/seed_demo.py --validate-only

reset-demo: ## Delete local demo volumes only with RESET_DEMO=1
	@test "$(RESET_DEMO)" = "1" || (echo "Refusing destructive reset; rerun with RESET_DEMO=1" && exit 1)
	docker compose down --volumes --remove-orphans
