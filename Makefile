# Coherence Network — common targets

.PHONY: test run setup lint web-worktree-validate spec-quality pr-preflight start-gate

test:
	cd api && .venv/bin/pytest -v

run:
	cd api && uvicorn app.main:app --reload --port 8000

setup:
	cd api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

lint:
	cd api && .venv/bin/ruff check . 2>/dev/null || true

web-worktree-validate:
	./scripts/verify_worktree_local_web.sh

spec-quality:
	python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

pr-preflight:
	python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main

start-gate:
	python3 scripts/ensure_worktree_start_clean.py --json
