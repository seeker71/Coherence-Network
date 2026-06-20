# Coherence Network — common targets

ifeq ($(OS),Windows_NT)
PYTHON ?= py -3
GIT_BASH ?= C:/Program Files/Git/bin/bash.exe
NPM ?= npm.cmd
API_VENV_PYTHON ?= .venv/Scripts/python.exe
API_VENV_PIP ?= .venv/Scripts/pip.exe
API_VENV_PYTEST ?= .venv/Scripts/pytest.exe
API_VENV_RUFF ?= .venv/Scripts/ruff.exe
API_VENV_UVICORN ?= .venv/Scripts/uvicorn.exe
else
PYTHON ?= python3
GIT_BASH ?= bash
NPM ?= npm
API_VENV_PYTHON ?= .venv/bin/python
API_VENV_PIP ?= .venv/bin/pip
API_VENV_PYTEST ?= .venv/bin/pytest
API_VENV_RUFF ?= .venv/bin/ruff
API_VENV_UVICORN ?= .venv/bin/uvicorn
endif

.PHONY: test test-quick run setup dev-setup lint seed web-dev api-dev build web-worktree-validate spec-quality pr-preflight start-guide prompt-guide start-gate prompt-gate install-pre-push-hook wellness circulation carrier-tissue-census carrier-vitality carrier-tending cell-voice-tissue json-lens-tending audit-evidence-tending audit-evidence-index-cache native-route-goal-tending

test:
	cd api && $(API_VENV_PYTEST) -v

test-quick:
	cd api && $(API_VENV_PYTEST) -x -q

run:
	cd api && $(API_VENV_UVICORN) app.main:app --reload --port 8000

setup:
	cd api && $(PYTHON) -m venv .venv && $(API_VENV_PIP) install -e ".[dev]"

dev-setup: setup
	cd web && $(NPM) install

lint:
ifeq ($(OS),Windows_NT)
	cd api && $(API_VENV_RUFF) check . || exit 0
else
	cd api && $(API_VENV_RUFF) check . 2>/dev/null || true
endif

seed:
ifeq ($(OS),Windows_NT)
	api/.venv/Scripts/python.exe scripts/seed_db.py
else
	api/.venv/bin/python scripts/seed_db.py
endif

api-dev:
	cd api && $(API_VENV_UVICORN) app.main:app --reload --port 8000

web-dev:
	cd web && $(NPM) run dev

build:
	cd web && $(NPM) run build

web-worktree-validate:
ifeq ($(OS),Windows_NT)
	@"$(GIT_BASH)" -lc "THREAD_RUNTIME_AUTO_HEAL=1 ./scripts/verify_worktree_local_web.sh"
else
	THREAD_RUNTIME_AUTO_HEAL=1 ./scripts/verify_worktree_local_web.sh
endif

spec-quality:
	$(PYTHON) scripts/validate_spec_quality.py --base origin/main --head HEAD

pr-preflight:
	$(PYTHON) scripts/worktree_pr_guard.py --mode local --base-ref origin/main

install-pre-push-hook:
ifeq ($(OS),Windows_NT)
	@"$(GIT_BASH)" ./scripts/setup_pre_push_hook.sh
else
	./scripts/setup_pre_push_hook.sh
endif

start-guide:
	@$(PYTHON) scripts/start_gate.py

prompt-guide:
ifeq ($(OS),Windows_NT)
	@"$(GIT_BASH)" ./scripts/prompt_entry_gate.sh
else
	./scripts/prompt_entry_gate.sh
endif

start-gate: start-guide

prompt-gate: prompt-guide

wellness:
	@$(PYTHON) scripts/wellness_check.py

circulation:
	@$(PYTHON) scripts/sense_subscription_circulation.py

carrier-tissue-census:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/carrier-tissue.fk form-stdlib/queries/carrier-tissue-census.fk

carrier-vitality:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/carrier-tissue.fk form-stdlib/queries/carrier-vitality.fk

carrier-tending:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/carrier-tissue.fk form-stdlib/queries/carrier-tending.fk

cell-voice-tissue:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/carrier-tissue.fk form-stdlib/queries/cell-voice-tissue.fk

json-lens-tending:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/json.fk form-stdlib/json-lens-tissue.fk form-stdlib/queries/json-lens-tending.fk

audit-evidence-tending:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/json.fk form-stdlib/audit-evidence-cells.fk form-stdlib/queries/audit-evidence-tending.fk

audit-evidence-index-cache:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust form-stdlib/json.fk form-stdlib/audit-evidence-cells.fk form-stdlib/queries/audit-evidence-index-cache.fk

native-route-goal-tending:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust run --stdlib form-stdlib form-stdlib/core.fk form-stdlib/kernel-http.fk form-stdlib/native-route-goal-cells.fk form-stdlib/queries/native-route-goal-tending.fk

static-to-dynamic-tending:
	@cd form/form-kernel-rust && cargo build --release --quiet
	@cd form && form-kernel-rust/target/release/form-kernel-rust run --stdlib form-stdlib form-stdlib/core.fk form-stdlib/static-to-dynamic-cells.fk form-stdlib/queries/static-to-dynamic-tending.fk
