# Coherence Network — common targets

.PHONY: test run setup lint web-worktree-validate spec-quality worktree-setup local-ci-context

test:
	cd api && .venv/bin/pytest -v

run:
	cd api && uvicorn app.main:app --reload --port 8000

setup:
	cd api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

lint:
	cd api && .venv/bin/ruff check . 2>/dev/null || true

web-worktree-validate:
	THREAD_RUNTIME_AUTO_HEAL=1 ./scripts/verify_worktree_local_web.sh

spec-quality:
	python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

worktree-setup:
	./scripts/setup_worktree_context.sh

local-ci-context:
	./scripts/run_local_ci_context.sh
