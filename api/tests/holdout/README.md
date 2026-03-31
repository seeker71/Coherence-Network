# Holdout Tests

Tests in this directory are **excluded from agent context** during implementation.
CI runs them to prevent implementations that "game" tests (e.g. returning true without real logic).

- Add tests that verify behavior the agent must not see during impl
- Exclude via pytest: `pytest --ignore=tests/holdout/` for agent runs
- CI runs full suite including holdout: `pytest -v`

See docs/PLAN.md Risk Register: "Test swapping" mitigation.
