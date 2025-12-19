.PHONY: help venv install run docker-build docker-run up down test verify ingest-demo lint format clean tree

# Variables
VENV := graph_env
TAG ?= graph-api:dev
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
DOCKER_COMPOSE := docker compose

# Default target
help:
	@echo "Graph Project Makefile"
	@echo "----------------------"
	@echo "  make venv           Create local virtualenv ($(VENV))"
	@echo "  make install        Install requirements into $(VENV)"
	@echo "  make run            Run FastAPI (uvicorn) on :8000"
	@echo "  make up             Start Neo4j via Docker"
	@echo "  make down           Stop Neo4j Docker container"
	@echo "  make docker-build   Build project Docker image (TAG=$(TAG))"
	@echo "  make docker-run     Run project Docker container on :8000"
	@echo "  make test           Run unit tests (pytest)"
	@echo "  make verify         Run the MVP verification script"
	@echo "  make ingest-demo    Ingest sample data (Tesla) - Server must be running!"
	@echo "  make lint           Run pylint (if installed)"
	@echo "  make format         Run black code formatter (if installed)"
	@echo "  make clean          Remove caches and temp files"
	@echo "  make tree           Show project tree (depth 3)"

venv:
	@if [ ! -d "$(VENV)" ]; then \
		python3 -m venv $(VENV); \
		. $(VENV)/bin/activate && pip install --upgrade pip; \
		echo "Created $(VENV)"; \
	else echo "$(VENV) already exists"; fi
	@echo "To activate: source $(VENV)/bin/activate"

install: venv
	@. $(VENV)/bin/activate && pip install -r requirements.txt

run: install
	@. $(VENV)/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Neo4j Docker Management
up:
	$(DOCKER_COMPOSE) up -d neo4j

down:
	$(DOCKER_COMPOSE) down

# Project Docker Management
docker-build:
	docker build -t $(TAG) .

docker-run:
	docker run --rm -it -p 8000:8000 --env-file .env $(TAG)

# Testing & Verification
test: install
	@. $(VENV)/bin/activate && pytest tests/test_api.py

test-integration: install
	@echo "Starting Test Database..."
	$(DOCKER_COMPOSE) -f docker-compose.test.yml up -d --wait
	@echo "Running Integration Tests..."
	@# Run pytest with test env vars. If it fails, catch error, down docker, and re-throw.
	@. $(VENV)/bin/activate && NEO4J_URI=bolt://localhost:7688 NEO4J_PASSWORD=password pytest tests/test_integration.py || \
		($(DOCKER_COMPOSE) -f docker-compose.test.yml down && exit 1)
	@echo "Stopping Test Database..."
	$(DOCKER_COMPOSE) -f docker-compose.test.yml down

verify: install
	@. $(VENV)/bin/activate && python verify_mvp.py

ingest-demo:
	@echo "Ingesting TSLA prices..."
	curl -X POST "http://localhost:8000/api/stocks/sync" \
		-H "Content-Type: application/json" \
		-d '{"stock": "TSLA", "start_date": "2021-09-30", "end_date": "2022-09-30"}'
	@echo "\nIngesting TSLA tweets..."
	curl -X POST "http://localhost:8000/api/social/import" \
		-H "Content-Type: application/json" \
		-d '{"stock": "TSLA", "start_date": "2021-09-30", "end_date": "2022-09-30"}'
	@echo "\nDone."

# Code Quality
lint:
	@if . $(VENV)/bin/activate && command -v pylint >/dev/null 2>&1; then \
		. $(VENV)/bin/activate && pylint app || true; \
	else echo "pylint not installed (pip install pylint)"; fi

format:
	@if . $(VENV)/bin/activate && command -v black >/dev/null 2>&1; then \
		. $(VENV)/bin/activate && black app -l 120; \
	else echo "black not installed (pip install black)"; fi

# Utilities
clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} \; || true
	find . -type f -name "*.pyc" -delete || true
	rm -rf .pytest_cache

tree:
	@if command -v tree >/dev/null 2>&1; then \
		tree -L 3 -I "node_modules|dist|.git|$(VENV)|__pycache__|.pytest_cache"; \
	else \
		find . -maxdepth 3 -type d -not -path '*/\.*' | sort; \
	fi
