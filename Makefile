# ==============================================================================
# Wolinet AI Platform - Developer & Operations Makefile
# ==============================================================================

SHELL := /usr/bin/env bash
PYTHON := .venv/bin/python3
XINFERENCE := .venv/bin/xinference

.PHONY: help start stop restart gateway mock register test health agent web docker-up docker-down

help:
	@echo "Wolinet AI Enterprise Platform"
	@echo "=============================="
	@echo "Available commands:"
	@echo "  make start        - Start both Inference Engine and Gateway"
	@echo "  make gateway      - Start only the LiteLLM Gateway"
	@echo "  make mock         - Run zero-GPU Mock Gateway (:4010) for UI & CI testing"
	@echo "  make web          - Open Wolinet AI Studio in web browser (:8080)"
	@echo "  make register     - Register all GGUF models into Xinference"
	@echo "  make list         - List active models running on Xinference"
	@echo "  make health       - Run full platform health check"
	@echo "  make agent        - Launch interactive autonomous coding agent"
	@echo "  make docker-up    - Run production platform via Docker Compose"
	@echo "  make docker-down  - Stop Docker Compose platform"

start:
	@./scripts/start_platform.sh

gateway:
	@./gateway/run_gateway.sh

mock:
	@$(PYTHON) scripts/mock_server.py

sdk:
	@$(PYTHON) scripts/generate_sdk.py

register:
	@./scripts/register_models.sh

list:
	@$(XINFERENCE) list

health:
	@./scripts/healthcheck.sh

agent:
	@$(PYTHON) apps/agentic-coder/main.py

web:
	@open http://localhost:8080 || xdg-open http://localhost:8080 || echo "Open http://localhost:8080 in your browser"

docker-up:
	@docker compose up -d

docker-down:
	@docker compose down
