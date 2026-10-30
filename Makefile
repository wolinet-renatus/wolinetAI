# ==============================================================================
# Wolinet AI Platform - Developer & Operations Makefile
# ==============================================================================

# Dynamic Host Path Determination (Defaults to current directory path where make is run)
WORKSPACE_ROOT ?= $(shell pwd)
WOLINET_DATA_DIR ?= /var/lib/wolinet

SHELL := /usr/bin/env bash
PYTHON := .venv/bin/python3
XINFERENCE := .venv/bin/xinference

.PHONY: help start stop restart gateway memory mock register test health web docker-up docker-down dev-env prod-deploy backup-models backup-db backup-all pod-status sdk sdk-build sdk-test

dev-env:
	@echo "🔧 Running platform locally on Mac development paths..."
	@podman machine stop || true
	@podman machine set --cpus 4 --memory 11264
	@podman machine start
	@# Inject dynamic local folder mappings using the runtime workspace variable
	@podman run -d --pod wolinetai-core-pod -v $(WORKSPACE_ROOT)/models:/app/models:Z localhost/wolinetai-inference:local-source

prod-deploy:
	@echo "🚀 Deploying platform onto sovereign Linux production targets..."
	@mkdir -p $(WOLINET_DATA_DIR)/models
	@# Production maps straight to standard corporate Linux volume boundaries
	@podman run -d --pod wolinetai-core-pod -v $(WOLINET_DATA_DIR)/models:/app/models:Z localhost/wolinetai-inference:local-source

backup-models:
	@echo "📦 Creating timestamped backup of local model weights..."
	@mkdir -p $(WORKSPACE_ROOT)/backups
	@tar -czf $(WORKSPACE_ROOT)/backups/models_$$(date +%Y%m%d_%H%M%S).tar.gz -C $(WORKSPACE_ROOT) models
	@echo "✅ Models backup completed in $(WORKSPACE_ROOT)/backups/"

backup-db:
	@echo "💾 Creating snapshot of PostgreSQL, Redis, and Mitambo databases..."
	@mkdir -p $(WORKSPACE_ROOT)/backups
	@if podman ps -q -f name=wolinet-postgres | grep -q .; then \
		podman exec wolinet-postgres pg_dumpall -U postgres | gzip > $(WORKSPACE_ROOT)/backups/postgres_$$(date +%Y%m%d_%H%M%S).sql.gz; \
		echo "✅ PostgreSQL snapshot captured."; \
	else \
		echo "⚠️ wolinet-postgres container not active; skipping live SQL dump."; \
	fi
	@if [ -d "$(WORKSPACE_ROOT)/data" ]; then \
		tar --exclude="data/mitambo/huggingface" --exclude="data/mitambo/cache" --exclude="data/cache" -czf $(WORKSPACE_ROOT)/backups/data_state_$$(date +%Y%m%d_%H%M%S).tar.gz -C $(WORKSPACE_ROOT) data; \
		echo "✅ Persistent data folder snapshot captured."; \
	fi
	@echo "✅ Database backup completed in $(WORKSPACE_ROOT)/backups/"

backup-all: backup-models backup-db
	@echo "🎉 Complete sovereign platform backup finalized."

pod-status:
	@echo "🔍 Inspecting Wolinet Core Pod and Container Status..."
	@podman pod ps --filter name=wolinetai-core-pod
	@echo ""
	@podman ps --filter pod=wolinetai-core-pod --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"

help:
	@echo "Wolinet AI Enterprise Platform"
	@echo "=============================="
	@echo "Available commands:"
	@echo "  make dev-env      - Launch Mac development environment with decoupled paths"
	@echo "  make prod-deploy  - Deploy sovereign Linux target with /var/lib/wolinet boundaries"
	@echo "  make pod-status   - Check Podman pod and container health status"
	@echo "  make backup-models- Snapshot local model weights and registrations"
	@echo "  make backup-db    - Snapshot PostgreSQL, Redis, and Mitambo databases"
	@echo "  make backup-all   - Full backup of models and persistent databases"
	@echo "  make start        - Start both Inference Engine and Gateway"
	@echo "  make gateway      - Start only the LiteLLM Gateway"
	@echo "  make memory       - Start LiteLLM Sovereign Memory Service (:8000)"
	@echo "  make mock         - Run zero-GPU Mock Gateway (:4010) for UI & CI testing"
	@echo "  make web          - Start Wolinet AI Web Portal (Open WebUI on :3080)"
	@echo "  make register     - Register all GGUF models into Xinference"
	@echo "  make list         - List active models running on Xinference"
	@echo "  make health       - Run full platform health check"
	@echo "  make docker-up    - Run production platform via Docker Compose"
	@echo "  make docker-down  - Stop Docker Compose platform"

start:
	@./scripts/start_platform.sh

gateway:
	@./gateway/run_gateway.sh

memory:
	@./gateway/litellm-memory/start-memory.sh

mock:
	@$(PYTHON) scripts/mock_server.py

sdk:
	@$(PYTHON) scripts/generate_sdk.py

sdk-build:
	@echo "📦 Building client SDKs..."
	@cd packages/wolinet-sdk && pnpm run build
	@echo "✅ Client SDKs built successfully."

sdk-test:
	@echo "🧪 Running client SDK test suites..."
	@cd packages/wolinet-sdk && pnpm test
	@cd packages/wolinet-go && go test -v ./...
	@if [ -x inference/.venv/bin/python3 ]; then \
		PYTHONPATH=packages/wolinet-python inference/.venv/bin/python3 -m unittest discover -s packages/wolinet-python/tests -v; \
	elif [ -x .venv/bin/python3 ]; then \
		PYTHONPATH=packages/wolinet-python .venv/bin/python3 -m unittest discover -s packages/wolinet-python/tests -v; \
	else \
		PYTHONPATH=packages/wolinet-python python3 -m unittest discover -s packages/wolinet-python/tests -v; \
	fi
	@echo "✅ All SDK test suites passed."

register:
	@./scripts/register_models.sh

list:
	@$(XINFERENCE) list

health:
	@./scripts/healthcheck.sh

web:
	@./apps/wolinex/run_webui.sh

docker-up:
	@docker compose up -d

docker-down:
	@docker compose down
