# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT

.PHONY: help install dev test lint format type-check security verify-versions clean check demo

PYTHON ?= python3
VENV ?= .venv
PYTEST ?= $(if $(wildcard $(VENV)/bin/pytest),$(VENV)/bin/pytest,pytest)
RUFF ?= $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)
BLACK ?= $(if $(wildcard $(VENV)/bin/black),$(VENV)/bin/black,black)
MYPY ?= $(if $(wildcard $(VENV)/bin/mypy),$(VENV)/bin/mypy,mypy)
VHS ?= $(shell which vhs 2>/dev/null || echo /opt/homebrew/bin/vhs)

demo: ## Generate terminal demo animation gif using vhs
	$(VHS) .github/demo.tape


help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -e .

dev: ## Install all dependencies (including dev)
	pip install -e ".[ilp]" pytest pytest-cov ruff black mypy bandit

test: ## Run unit tests with the 100% line+branch coverage gate
	$(PYTEST) tests/ \
		--cov=reconcile_mcp --cov-branch \
		--cov-report=term-missing --cov-fail-under=100 -v

lint: ## Run linters (ruff + black check)
	$(RUFF) check reconcile_mcp/ tests/
	$(BLACK) --check reconcile_mcp/ tests/

format: ## Auto-format code (ruff fix + black)
	$(RUFF) check --fix reconcile_mcp/ tests/
	$(BLACK) reconcile_mcp/ tests/

type-check: ## Run mypy type checking
	$(MYPY) reconcile_mcp/

security: ## Run security scan (bandit)
	bandit -r reconcile_mcp/ -c pyproject.toml 2>/dev/null || bandit -r reconcile_mcp/ -ll 2>/dev/null || true

verify-versions: ## Verify version consistency across all project manifests
	$(PYTHON) scripts/verify_versions.py

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/
	rm -rf coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

check: lint type-check test verify-versions ## Run all verification gates
