.DEFAULT_GOAL := help

.PHONY: help doctor demo proof check logs down fixtures-check reset-demo

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Verify required local tool versions (MODE=dev)
	@test "$(MODE)" = "dev" || (echo "MODE must be dev" && exit 1)
	@uv python find 3.12.13 >/dev/null
	@test "$$(node --version)" = "v24.18.0" || (echo "Node 24.18.0 required; found $$(node --version)" && exit 1)
	@docker --version
	@docker compose version
	@echo "doctor: bootstrap prerequisites available"

demo: ## Build and start the local bootstrap stack
	docker compose up --build --wait

proof: ## Run release skeleton, wheel smoke, and public-hygiene proof
	uv run python scripts/verify_release.py

check: ## Run backend, frontend, Compose, and proof checks
	uv lock --check
	uv run pytest -q
	uv run ruff check .
	uv run pyright
	uv build
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
