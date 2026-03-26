"""Supplementary tests for deploy-latest-to-vps edge cases and error handling.

Covers spec sections: Edge Cases and Error Handling Expectations,
Concurrency Behavior, and additional contract validation from
specs/156-deploy-latest-to-vps.md.
"""

from __future__ import annotations

import pytest

from api.tests.test_deploy_latest_to_vps import (
    COMPOSE_PATH,
    PUBLIC_API_BASE,
    PUBLIC_WEB_BASE,
    REPO_PATH,
    SSH_KEY_FRAGMENT,
    SSH_USER_HOST,
    VPS_HOST,
    assert_health_contract,
    assert_services_payload_ok,
    compose_ps_indicates_api_web_running,
    deploy_ssh_commands,
)


# ---------------------------------------------------------------------------
# Edge case: health contract boundary validation
# ---------------------------------------------------------------------------


class TestHealthContractEdgeCases:
    """Spec: health JSON must include schema_ok=true and status=ok."""

    def test_missing_schema_ok_key_rejected(self) -> None:
        """Spec edge case: /api/health returns 200 but lacks schema_ok."""
        with pytest.raises(AssertionError):
            assert_health_contract({"status": "ok"})

    def test_missing_status_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            assert_health_contract({"schema_ok": True})

    def test_empty_payload_rejected(self) -> None:
        with pytest.raises(AssertionError):
            assert_health_contract({})

    def test_extra_fields_accepted(self) -> None:
        """Spec note: health payload may include additional metadata."""
        assert_health_contract(
            {"status": "ok", "schema_ok": True, "version": "1.2.3", "uptime": 3600}
        )

    def test_schema_ok_none_rejected(self) -> None:
        with pytest.raises(AssertionError):
            assert_health_contract({"status": "ok", "schema_ok": None})

    def test_schema_ok_string_true_rejected(self) -> None:
        """schema_ok must be boolean True, not string."""
        with pytest.raises(AssertionError):
            assert_health_contract({"status": "ok", "schema_ok": "true"})


# ---------------------------------------------------------------------------
# Edge case: services contract boundary validation
# ---------------------------------------------------------------------------


class TestServicesContractEdgeCases:
    """Spec: /api/services returns JSON with service list structure."""

    def test_empty_list_accepted(self) -> None:
        """Empty service list is still valid structure."""
        assert_services_payload_ok([])

    def test_wrapped_empty_list_accepted(self) -> None:
        assert_services_payload_ok({"services": []})

    def test_missing_id_rejected(self) -> None:
        with pytest.raises(AssertionError):
            assert_services_payload_ok([{"name": "A"}])

    def test_missing_name_rejected(self) -> None:
        with pytest.raises(AssertionError):
            assert_services_payload_ok([{"id": "a"}])

    def test_string_payload_rejected(self) -> None:
        with pytest.raises((AssertionError, AttributeError)):
            assert_services_payload_ok("not json list")

    def test_numeric_payload_rejected(self) -> None:
        with pytest.raises((AssertionError, AttributeError, TypeError)):
            assert_services_payload_ok(42)

    def test_extra_fields_in_service_accepted(self) -> None:
        """Spec note: response may contain additional fields."""
        assert_services_payload_ok(
            [{"id": "a", "name": "A", "description": "desc", "status": "active"}]
        )


# ---------------------------------------------------------------------------
# Edge case: compose ps parser robustness
# ---------------------------------------------------------------------------


class TestComposePsEdgeCases:
    """Spec: docker compose ps must show api and web as running/healthy."""

    def test_empty_output(self) -> None:
        assert compose_ps_indicates_api_web_running("") is False

    def test_header_only(self) -> None:
        header = "NAME  IMAGE  COMMAND  SERVICE  CREATED  STATUS  PORTS"
        assert compose_ps_indicates_api_web_running(header) is False

    def test_only_one_service_up_api(self) -> None:
        """Spec edge case: docker compose up -d starts only one service."""
        sample = (
            "NAME                          IMAGE  COMMAND   SERVICE  CREATED      STATUS         PORTS\n"
            "coherence-network-api-1       x      uvicorn   api      1 min ago    Up 1 minute    0.0.0.0:8000->8000/tcp\n"
            "coherence-network-web-1       y      node      web      1 min ago    Exited (1)     -"
        )
        assert compose_ps_indicates_api_web_running(sample) is False

    def test_both_exited_is_failure(self) -> None:
        sample = (
            "NAME                          IMAGE  COMMAND   SERVICE  CREATED      STATUS             PORTS\n"
            "coherence-network-api-1       x      uvicorn   api      1 min ago    Exited (137)       -\n"
            "coherence-network-web-1       y      node      web      1 min ago    Exited (137)       -"
        )
        assert compose_ps_indicates_api_web_running(sample) is False

    def test_healthy_annotation_accepted(self) -> None:
        """Status may include '(healthy)' qualifier."""
        sample = (
            "NAME                          IMAGE  COMMAND   SERVICE  CREATED      STATUS                  PORTS\n"
            "coherence-network-api-1       x      uvicorn   api      1 hr ago     Up 1 hour (healthy)     0.0.0.0:8000->8000/tcp\n"
            "coherence-network-web-1       y      node      web      1 hr ago     Up 1 hour (healthy)     0.0.0.0:3000->3000/tcp"
        )
        assert compose_ps_indicates_api_web_running(sample) is True

    def test_restarting_not_treated_as_up(self) -> None:
        sample = (
            "NAME                          IMAGE  COMMAND   SERVICE  CREATED      STATUS          PORTS\n"
            "coherence-network-api-1       x      uvicorn   api      1 hr ago     Restarting      -\n"
            "coherence-network-web-1       y      node      web      1 hr ago     Restarting      -"
        )
        assert compose_ps_indicates_api_web_running(sample) is False


# ---------------------------------------------------------------------------
# Deploy command contract validation
# ---------------------------------------------------------------------------


class TestDeployCommandContract:
    """Spec task card: exact deploy sequence and constraints."""

    def test_three_step_sequence(self) -> None:
        cmds = deploy_ssh_commands()
        assert len(cmds) == 3

    def test_step1_git_pull(self) -> None:
        cmds = deploy_ssh_commands()
        assert "git pull origin main" in cmds[0]
        assert REPO_PATH in cmds[0]

    def test_step2_build_no_cache(self) -> None:
        """Spec: rebuild both images with no cache."""
        cmds = deploy_ssh_commands()
        assert "--no-cache" in cmds[1]
        assert "api" in cmds[1]
        assert "web" in cmds[1]
        assert COMPOSE_PATH in cmds[1]

    def test_step3_up_detached(self) -> None:
        cmds = deploy_ssh_commands()
        assert "up -d" in cmds[2]
        assert "api" in cmds[2]
        assert "web" in cmds[2]

    def test_all_commands_use_correct_ssh_key(self) -> None:
        for cmd in deploy_ssh_commands():
            assert SSH_KEY_FRAGMENT in cmd

    def test_all_commands_target_correct_host(self) -> None:
        for cmd in deploy_ssh_commands():
            assert SSH_USER_HOST in cmd

    def test_no_destructive_commands(self) -> None:
        """Spec constraint: no destructive docker cleanup commands."""
        for cmd in deploy_ssh_commands():
            for forbidden in ["prune", "rm -f", "down", "kill", "volume rm"]:
                assert forbidden not in cmd, f"Found forbidden '{forbidden}' in: {cmd}"


# ---------------------------------------------------------------------------
# Spec constant validation
# ---------------------------------------------------------------------------


class TestSpecConstants:
    """Verify spec constants match CLAUDE.md and spec document."""

    def test_vps_host(self) -> None:
        assert VPS_HOST == "187.77.152.42"

    def test_ssh_user_host(self) -> None:
        assert SSH_USER_HOST == "root@187.77.152.42"

    def test_ssh_key_path(self) -> None:
        assert SSH_KEY_FRAGMENT == "~/.ssh/hostinger-openclaw"

    def test_repo_path(self) -> None:
        assert REPO_PATH == "/docker/coherence-network/repo"

    def test_compose_path(self) -> None:
        assert COMPOSE_PATH == "/docker/coherence-network"

    def test_api_base_https(self) -> None:
        assert PUBLIC_API_BASE.startswith("https://")

    def test_web_base_https(self) -> None:
        assert PUBLIC_WEB_BASE.startswith("https://")
