# Coherence Network — common targets

.PHONY: test test-quick run setup dev-setup lint seed web-dev api-dev build web-worktree-validate spec-quality pr-preflight start-gate prompt-gate install-pre-push-hook

test:
	cd api && .venv/bin/pytest -v

test-quick:
	cd api && .venv/bin/pytest -x -q

run:
	cd api && uvicorn app.main:app --reload --port 8000

setup:
	cd api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

dev-setup: setup
	cd web && npm install

lint:
	cd api && .venv/bin/ruff check . 2>/dev/null || true

seed:
	api/.venv/bin/python scripts/seed_db.py

api-dev:
	cd api && .venv/bin/uvicorn app.main:app --reload --port 8000

web-dev:
	cd web && npm run dev

build:
	cd web && npm run build

web-worktree-validate:
	THREAD_RUNTIME_AUTO_HEAL=1 ./scripts/verify_worktree_local_web.sh

spec-quality:
	python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

pr-preflight:
	python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main

install-pre-push-hook:
	./scripts/setup_pre_push_hook.sh

start-gate:
	@/usr/bin/python3 scripts/start_gate.py

prompt-gate:
	./scripts/prompt_entry_gate.sh
