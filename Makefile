.PHONY: help install panel refresh index sc sd models release notebook test test-backend lint format api \n	frontend-install frontend-dev frontend-build frontend-test frontend-lint clean

PYTHON ?= python
VENV   := .venv
BIN    := $(VENV)/bin
ifeq ($(OS),Windows_NT)
BIN    := $(VENV)/Scripts
endif

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-10s %s\n", $$1, $$2}'

install:  ## Create the venv and install the project with dev extras
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev]"

panel:  ## Build the tidy panel, using cached raw pulls where present
	$(BIN)/python scripts/build_panel.py

refresh:  ## Rebuild the panel, re-pulling every indicator from the World Bank
	$(BIN)/python scripts/build_panel.py --refresh

index:  ## Build the development index and render the charts (needs `make panel`)
	$(BIN)/python scripts/build_index.py

sc:  ## Synthetic-control counterfactual: tables + charts (needs `make index`)
	$(BIN)/python scripts/build_synthetic_control.py

sd:  ## System-dynamics scenarios: tables + charts (needs `make panel`; `make sc` for the SC check)
	$(BIN)/python scripts/build_system_dynamics.py

models: sc sd  ## Both model layers: counterfactual, then future scenarios

release:  ## Snapshot the served tables into the committed data/release (after `make models`)
	$(BIN)/python scripts/build_release.py

notebook:  ## Execute the notebook into build/ (pip install -e ".[notebook]" first)
	$(BIN)/python -m nbconvert --to notebook --execute --output-dir build/notebooks notebooks/*.ipynb

test: test-backend frontend-test  ## Backend suite plus the frontend smoke test (no network)

test-backend:  ## Run the Python test suite (no network)
	$(BIN)/python -m pytest

lint: frontend-lint  ## Check style and formatting, both sides
	$(BIN)/python -m ruff check .
	$(BIN)/python -m ruff format --check .

format:  ## Apply formatting and autofixes
	$(BIN)/python -m ruff format .
	$(BIN)/python -m ruff check --fix .

api:  ## Serve the API locally (AMBER_DATA_SOURCE=processed to serve `make models` output)
	$(BIN)/python -m uvicorn amber.api.main:app --reload

frontend-install:  ## Install the frontend's pinned dependencies
	cd frontend && npm ci

frontend-dev:  ## Vite dev server on :5173 (needs `make api` running)
	cd frontend && npm run dev

frontend-build:  ## Typecheck and build the frontend into frontend/dist
	cd frontend && npm run build

frontend-test:  ## Frontend typecheck and the honesty smoke test
	cd frontend && npm run typecheck && npm test

frontend-lint:  ## ESLint the frontend
	cd frontend && npm run lint

clean:  ## Remove processed outputs, keeping the raw cache
	rm -rf data/processed/*.csv data/processed/*.parquet
	rm -rf .pytest_cache .ruff_cache
