# Coherence Network — common targets

.PHONY: test test-quick run setup dev-setup lint seed web-dev api-dev build web-worktree-validate spec-quality pr-preflight start-guide prompt-guide start-gate prompt-gate install-pre-push-hook wellness circulation carrier-tissue-census carrier-vitality carrier-tending cell-voice-tissue json-lens-tending audit-evidence-tending audit-evidence-index-cache native-route-goal-tending

test:
	cd api && .venv/bin/pytest -v

test-quick:
	cd api && .venv/bin/pytest -x -q

run:
	cd api && uvicorn app.main:app --reload --port 8000

setup:
	cd api && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

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

start-guide:
	@/usr/bin/python3 scripts/start_gate.py

prompt-guide:
	./scripts/prompt_entry_gate.sh

start-gate: start-guide

prompt-gate: prompt-guide

wellness:
	@python3 scripts/wellness_check.py

circulation:
	@python3 scripts/sense_subscription_circulation.py

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
