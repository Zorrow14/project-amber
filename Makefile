.PHONY: help install panel refresh test lint format api clean

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

test:  ## Run the test suite (no network)
	$(BIN)/python -m pytest

lint:  ## Check style and formatting
	$(BIN)/python -m ruff check .
	$(BIN)/python -m ruff format --check .

format:  ## Apply formatting and autofixes
	$(BIN)/python -m ruff format .
	$(BIN)/python -m ruff check --fix .

api:  ## Serve the (stub) API locally
	$(BIN)/python -m uvicorn amber.api.main:app --reload

clean:  ## Remove processed outputs, keeping the raw cache
	rm -rf data/processed/*.csv data/processed/*.parquet
	rm -rf .pytest_cache .ruff_cache
