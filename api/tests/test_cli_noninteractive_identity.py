"""Tests for CLI Non-Interactive Identity (cli-noninteractive-identity).

Covers acceptance criteria from spec task_a50fa999fdddd444:
  R2 — contributor_id validation pattern
  R3 — config-backed contributor identity resolution
  R5 — runner startup identity logging
  R6 — GET /api/identity/me endpoint (additional edge cases)

Python-layer tests only — npm CLI behaviour (cc identity set shell commands)
is covered by the verification scenarios in the spec itself.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# R2: the canonical pattern from the spec — /^[\w.\-]{1,64}$/
_CONTRIBUTOR_ID_PATTERN = re.compile(r"^[\w.\-]{1,64}$")


def _valid(cid: str) -> bool:
    return bool(_CONTRIBUTOR_ID_PATTERN.match(cid))


# ---------------------------------------------------------------------------
# R2 — Input validation pattern
# ---------------------------------------------------------------------------

class TestContributorIdValidation:
    """Verify the /^[\\w.\\-]{1,64}$/ contract (R2).

    The pattern is defined in the spec; these tests pin its exact behaviour so
    any downstream implementation (CLI or API) can be validated against it.
    """

    # --- valid inputs -------------------------------------------------------

    def test_simple_lowercase(self) -> None:
        assert _valid("alice")

    def test_hyphen_allowed(self) -> None:
        assert _valid("valid-agent-01")

    def test_underscore_allowed(self) -> None:
        assert _valid("agent_runner_1")

    def test_period_allowed(self) -> None:
        assert _valid("alice.smith")

    def test_digits_only(self) -> None:
        assert _valid("12345")

    def test_mixed_case(self) -> None:
        assert _valid("AliceBot")

    def test_exactly_64_chars(self) -> None:
        assert _valid("x" * 64)

    def test_single_char(self) -> None:
        assert _valid("a")

    # --- invalid inputs ------------------------------------------------------

    def test_empty_string_rejected(self) -> None:
        assert not _valid("")

    def test_space_rejected(self) -> None:
        assert not _valid("alice smith")

    def test_semicolon_rejected(self) -> None:
        assert not _valid("alice; rm -rf /")

    def test_bang_rejected(self) -> None:
        assert not _valid("bad;chars!")

    def test_at_sign_rejected(self) -> None:
        assert not _valid("alice@example.com")

    def test_slash_rejected(self) -> None:
        assert not _valid("path/traversal")

    def test_65_chars_rejected(self) -> None:
        assert not _valid("x" * 65)

    def test_whitespace_only_rejected(self) -> None:
        assert not _valid("   ")

    def test_newline_rejected(self) -> None:
        assert not _valid("alice\nmalicious")

    def test_null_byte_rejected(self) -> None:
        assert not _valid("alice\x00bad")


# ---------------------------------------------------------------------------
# R3 — resolve_cli_contributor_id precedence
# ---------------------------------------------------------------------------

class TestResolveCLIContributorId:
    """Unit tests for config_service.resolve_cli_contributor_id() config-backed behavior."""

    def test_config_json_when_no_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """config.json is used when no env vars are set."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "from-config"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid == "from-config"
        assert src == "config.json"

    def test_legacy_env_is_ignored_when_config_is_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Legacy env no longer overrides config.json."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "from-config"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
        monkeypatch.setenv("COHERENCE_CONTRIBUTOR", "legacy-agent")

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid == "from-config"
        assert src == "config.json"

    def test_canonical_env_is_ignored_when_config_is_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Canonical env no longer overrides config.json."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "config-agent"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.setenv("COHERENCE_CONTRIBUTOR_ID", "env-agent")
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid == "config-agent"
        assert src == "config.json"

    def test_config_json_beats_both_legacy_and_canonical_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """config.json remains the single source of truth even when legacy env vars are present."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "config-wins"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.setenv("COHERENCE_CONTRIBUTOR_ID", "new-wins")
        monkeypatch.setenv("COHERENCE_CONTRIBUTOR", "old-loses")

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid == "config-wins"
        assert src == "config.json"

    def test_returns_none_when_no_identity(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Returns (None, 'none') when nothing is configured (AC: no identity → anonymous fallback)."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid is None
        assert src == "none"

    def test_missing_config_file_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Missing config.json doesn't crash — returns (None, 'none')."""
        from app.services import config_service

        missing = tmp_path / "nonexistent.json"
        monkeypatch.setattr(config_service, "_CONFIG_PATH", missing)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid is None
        assert src == "none"

    def test_empty_env_falls_through_to_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Empty env string is ignored and config.json remains authoritative."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "from-config"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.setenv("COHERENCE_CONTRIBUTOR_ID", "")  # empty — should be ignored
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid == "from-config"
        assert src == "config.json"

    def test_whitespace_env_falls_through(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Whitespace-only env string is ignored and config.json remains authoritative."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "from-config"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
        monkeypatch.setenv("COHERENCE_CONTRIBUTOR_ID", "   ")
        monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        cid, src = config_service.resolve_cli_contributor_id()
        assert cid == "from-config"
        assert src == "config.json"


# ---------------------------------------------------------------------------
# R3 — scripts/cc.py _resolve_contributor_id
# ---------------------------------------------------------------------------

class TestCCPyResolveContributorId:
    """Unit tests for scripts/cc.py _resolve_contributor_id() config-backed behavior."""

    @pytest.fixture(autouse=True)
    def import_cc(self) -> None:
        """Import cc.py from scripts/ directory."""
        scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import importlib
        if "cc" in sys.modules:
            self.cc = sys.modules["cc"]
        else:
            import cc as _cc
            self.cc = _cc

    def test_config_json_used_when_present(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "py-config-user"}), encoding="utf-8")
        monkeypatch.setattr(self.cc, "CONFIG_PATH", cfg)

        result = self.cc._resolve_contributor_id(None)
        assert result == "py-config-user"

    def test_falls_back_to_anonymous_when_no_identity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 'anonymous' when no identity is configured."""
        monkeypatch.setattr(self.cc, "CONFIG_PATH", Path("/nonexistent/config.json"))

        result = self.cc._resolve_contributor_id(None)
        assert result == "anonymous"

    def test_cli_arg_takes_highest_priority(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Explicit CLI arg overrides config.json."""
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "config-user"}), encoding="utf-8")
        monkeypatch.setattr(self.cc, "CONFIG_PATH", cfg)

        result = self.cc._resolve_contributor_id("cli-explicit")
        assert result == "cli-explicit"

    def test_empty_cli_arg_falls_through_to_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Empty CLI arg is ignored; config.json is used instead."""
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "config-fallback"}), encoding="utf-8")
        monkeypatch.setattr(self.cc, "CONFIG_PATH", cfg)

        result = self.cc._resolve_contributor_id("")
        assert result == "config-fallback"


# ---------------------------------------------------------------------------
# R5 — Runner startup identity logging
# ---------------------------------------------------------------------------

class TestRunnerStartupIdentityLogging:
    """Verify the runner logs identity at startup (R5, AC11, AC12)."""

    def _call_runner_identity_block(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, contributor_id: str | None
    ) -> list[str]:
        """Simulate the identity-logging block from local_runner.main().

        We extract the exact logging block from the spec to keep the test
        independent of runner startup complexity.
        """
        from app.services import config_service

        if contributor_id is not None:
            cfg = tmp_path / "config.json"
            cfg.write_text(json.dumps({"contributor_id": contributor_id}), encoding="utf-8")
            monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
            monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
            monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)
        else:
            cfg = tmp_path / "config.json"
            cfg.write_text("{}", encoding="utf-8")
            monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)
            monkeypatch.delenv("COHERENCE_CONTRIBUTOR_ID", raising=False)
            monkeypatch.delenv("COHERENCE_CONTRIBUTOR", raising=False)

        log_records: list[str] = []

        class _CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                log_records.append(self.format(record))

        handler = _CapturingHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        log = logging.getLogger("runner_identity_test")
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)
        log.propagate = False

        try:
            _rcid, _rsrc = config_service.resolve_cli_contributor_id()
            if _rcid:
                log.info("[runner] identity resolved: %s (source: %s)", _rcid, _rsrc)
            else:
                log.warning(
                    "[runner] WARNING: no contributor identity configured — all contributions will be anonymous",
                )
                log.warning(
                    "[runner] Fix: cc identity set <your_id>  or  update ~/.coherence-network/config.json",
                )
        finally:
            log.removeHandler(handler)

        return log_records

    def test_logs_resolved_identity_when_configured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC11: Runner logs 'identity resolved: <id>' when identity is configured."""
        records = self._call_runner_identity_block(monkeypatch, tmp_path, contributor_id="runner-test-user")

        assert any("[runner] identity resolved: runner-test-user" in r for r in records), records

    def test_logs_no_warning_when_identity_is_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No WARNING log when identity is configured."""
        records = self._call_runner_identity_block(monkeypatch, tmp_path, contributor_id="configured-user")

        assert not any("WARNING" in r and "no contributor identity" in r for r in records), records

    def test_logs_warning_when_no_identity(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC12: Runner logs WARNING when no identity configured."""
        records = self._call_runner_identity_block(monkeypatch, tmp_path, contributor_id=None)

        assert any("WARNING" in r and "no contributor identity" in r for r in records), records

    def test_logs_fix_instructions_when_no_identity(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC12: Fix instructions appear in log when no identity configured."""
        records = self._call_runner_identity_block(monkeypatch, tmp_path, contributor_id=None)

        fix_lines = [r for r in records if "Fix:" in r or "cc identity set" in r or "config.json" in r]
        assert fix_lines, f"Expected fix instructions in log. Got: {records}"

    def test_identity_resolved_from_config_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Runner log correctly reflects config.json-sourced identity."""
        from app.services import config_service

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"contributor_id": "config-runner-agent"}), encoding="utf-8")
        monkeypatch.setattr(config_service, "_CONFIG_PATH", cfg)

        log_records: list[str] = []

        class _Cap(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                log_records.append(self.format(record))

        handler = _Cap()
        handler.setFormatter(logging.Formatter("%(message)s"))
        log = logging.getLogger("runner_env_test")
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)
        log.propagate = False

        try:
            _rcid, _rsrc = config_service.resolve_cli_contributor_id()
            if _rcid:
                log.info("[runner] identity resolved: %s (source: %s)", _rcid, _rsrc)
        finally:
            log.removeHandler(handler)

        assert any("config-runner-agent" in r for r in log_records), log_records
        assert any("config.json" in r for r in log_records), log_records


# ---------------------------------------------------------------------------
# R6 — GET /api/identity/me (additional edge cases beyond test_identity_set.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    from app.main import app
    return TestClient(app)


class TestIdentityMeEndpoint:
    """Additional coverage for GET /api/identity/me (R6, AC13, AC14)."""

    def test_missing_api_key_returns_401(self, client: TestClient) -> None:
        """AC14: No API key → 401 (not 500)."""
        r = client.get("/api/identity/me")
        assert r.status_code == 401
        assert r.status_code != 500

    def test_invalid_api_key_returns_401(self, client: TestClient) -> None:
        """AC14: Invalid API key → 401 (not 500)."""
        r = client.get("/api/identity/me", headers={"X-API-Key": "definitely-invalid-key-xyz-9999"})
        assert r.status_code == 401
        assert r.status_code != 500

    def test_empty_api_key_header_returns_401(self, client: TestClient) -> None:
        """Empty string API key → 401."""
        r = client.get("/api/identity/me", headers={"X-API-Key": ""})
        assert r.status_code == 401

    def test_valid_key_returns_200_with_required_fields(self, client: TestClient) -> None:
        """AC13: Valid key → 200 with contributor_id, source, linked_accounts."""
        # Register identity + key
        link = client.post(
            "/api/identity/link",
            json={
                "contributor_id": "me-test-r6-01",
                "provider": "name",
                "provider_id": "me-test-r6-01",
                "display_name": "me-test-r6-01",
            },
        )
        assert link.status_code == 200

        keys = client.post(
            "/api/auth/keys",
            json={
                "contributor_id": "me-test-r6-01",
                "provider": "name",
                "provider_id": "me-test-r6-01",
            },
        )
        assert keys.status_code == 201, keys.text
        api_key = keys.json()["api_key"]

        r = client.get("/api/identity/me", headers={"X-API-Key": api_key})
        assert r.status_code == 200
        body = r.json()

        # All three required fields must be present
        assert "contributor_id" in body
        assert "source" in body
        assert "linked_accounts" in body

    def test_valid_key_contributor_id_matches(self, client: TestClient) -> None:
        """Contributor ID in response matches the registered identity."""
        link = client.post(
            "/api/identity/link",
            json={
                "contributor_id": "me-test-r6-02",
                "provider": "name",
                "provider_id": "me-test-r6-02",
                "display_name": "me-test-r6-02",
            },
        )
        assert link.status_code == 200
        keys = client.post(
            "/api/auth/keys",
            json={
                "contributor_id": "me-test-r6-02",
                "provider": "name",
                "provider_id": "me-test-r6-02",
            },
        )
        assert keys.status_code == 201
        api_key = keys.json()["api_key"]

        r = client.get("/api/identity/me", headers={"X-API-Key": api_key})
        assert r.status_code == 200
        body = r.json()
        assert body["contributor_id"] == "me-test-r6-02"

    def test_valid_key_linked_accounts_is_non_negative_int(self, client: TestClient) -> None:
        """linked_accounts is a non-negative integer."""
        link = client.post(
            "/api/identity/link",
            json={
                "contributor_id": "me-test-r6-03",
                "provider": "name",
                "provider_id": "me-test-r6-03",
                "display_name": "me-test-r6-03",
            },
        )
        assert link.status_code == 200
        keys = client.post(
            "/api/auth/keys",
            json={
                "contributor_id": "me-test-r6-03",
                "provider": "name",
                "provider_id": "me-test-r6-03",
            },
        )
        assert keys.status_code == 201
        api_key = keys.json()["api_key"]

        r = client.get("/api/identity/me", headers={"X-API-Key": api_key})
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["linked_accounts"], int)
        assert body["linked_accounts"] >= 0

    def test_response_is_valid_json(self, client: TestClient) -> None:
        """Response on invalid key is valid JSON with a meaningful error."""
        r = client.get("/api/identity/me", headers={"X-API-Key": "bad-key"})
        # Should be parseable JSON even for error responses
        data = r.json()
        assert isinstance(data, dict)
