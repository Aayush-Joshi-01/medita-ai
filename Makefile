# medita-ai developer commands.
# Targets marked (step N) are placeholders until that build step lands —
# they call into code that does not exist yet.

COMPOSE = docker compose

.PHONY: up down restart logs ps build tools observability \
        migrate seed test lint fmt gen-client clean

## Core stack
up: ## Start the core service stack
	$(COMPOSE) up -d

down: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) down

restart: ## Restart the core stack
	$(COMPOSE) down && $(COMPOSE) up -d

logs: ## Tail logs for all core services
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

build: ## Rebuild application images
	$(COMPOSE) build

## Optional profiles
tools: ## Start dev tools (mailhog, adminer)
	$(COMPOSE) --profile tools up -d

observability: ## Start prometheus + grafana
	$(COMPOSE) --profile observability up -d

## Application (step 2+)
migrate: ## Apply database migrations
	$(COMPOSE) exec backend alembic upgrade head

seed: ## Load seed / demo data
	$(COMPOSE) exec backend python -m app.seeds.load

test: ## Run backend + frontend test suites
	$(COMPOSE) exec backend pytest
	$(COMPOSE) exec frontend npm test

lint: ## Lint backend + frontend
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec backend mypy .
	$(COMPOSE) exec frontend npm run lint

fmt: ## Format backend + frontend
	$(COMPOSE) exec backend ruff format .
	$(COMPOSE) exec frontend npm run format

gen-client: ## Regenerate the frontend's typed API client from the backend's OpenAPI schema
	$(COMPOSE) exec backend python -m app.scripts.export_openapi > frontend/openapi.json
	$(COMPOSE) exec frontend npm run gen-client

## Housekeeping
clean: ## Remove containers, networks and volumes (destructive)
	$(COMPOSE) down -v
