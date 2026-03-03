# Coherence Network — common targets

.PHONY: test run setup lint web-worktree-validate spec-quality pr-preflight start-gate prompt-gate install-pre-push-hook

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

pr-preflight:
	python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main

install-pre-push-hook:
	./scripts/setup_pre_push_hook.sh

start-gate:
	@if [ ! -f .git ]; then \
	  echo "start-gate: missing .git marker" && exit 1; \
	fi
	@if [ "$$(cat .git | awk '{print $$1}')" != "gitdir:" ]; then \
	  echo "start-gate: expected linked worktree (.git file). Refuse to run in primary workspace." && exit 1; \
	fi
	@if [ -n "$$(git status --short)" ]; then \
	  echo "start-gate: current worktree has local changes. Clean it before starting a task." && exit 1; \
	fi
	@python3 scripts/start_gate.py
