.DEFAULT_GOAL := help
export UV_BUILD_CONSTRAINT := build-constraints.txt
export UV_REQUIRE_HASHES := 1

.PHONY: help doctor demo proof compose-proof check logs down fixtures-check reset-demo

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Verify evaluator prerequisites; MODE=dev adds contributor tools
	@scripts/doctor.sh

demo: ## Build and start the local bootstrap stack
	docker compose up --build --wait

proof: ## Run config, hygiene, and wheel proof using Docker only
	docker build --file Dockerfile.proof --target proof --tag night-voyager-proof:local .

compose-proof: ## Prove service health, probes, and teardown
	@scripts/verify_compose.sh

check: ## Run backend, frontend, Compose, and proof checks
	uv lock --check
	uv run pytest -q
	uv run ruff check .
	uv run pyright
	uv build --build-constraints build-constraints.txt --require-hashes
	npm --prefix web ci
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run test
	npm --prefix web run build
	docker compose config --quiet
	$(MAKE) fixtures-check
	$(MAKE) proof

logs: ## Follow local bootstrap service logs
	docker compose logs --follow

down: ## Stop the stack and preserve database data
	docker compose down --remove-orphans

fixtures-check: ## Confirm M0 has no domain fixtures
	@test ! -d fixtures || (echo "M0 must not contain domain fixtures" && exit 1)
	@echo "fixtures-check: no M0 domain fixtures"

reset-demo: ## Delete local demo volumes only with RESET_DEMO=1
	@test "$(RESET_DEMO)" = "1" || (echo "Refusing destructive reset; rerun with RESET_DEMO=1" && exit 1)
	docker compose down --volumes --remove-orphans
