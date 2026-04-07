"""MVP acceptance summary and judge endpoint tests.

Validates the acceptance-summary and acceptance-judge contract including
cost rollups, budget/revenue economics, public validator quorum,
transparency-log anchoring, and trust-adjusted revenue proof.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from nacl.signing import SigningKey

from app.main import app
from app.services import runtime_service


AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def _write_mvp_acceptance_policy(
    *,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    override: dict[str, Any],
) -> None:
    base = json.loads(json.dumps(runtime_service._DEFAULT_MVP_ACCEPTANCE_POLICY))
    payload = _deep_merge(base, override)
    path = tmp_path / "mvp_acceptance_policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_service, "_mvp_acceptance_policy_path", lambda: path)
    runtime_service.reset_mvp_acceptance_policy_cache()


@pytest.fixture(autouse=True)
def _reset_mvp_policy_cache_per_test():
    runtime_service.reset_mvp_acceptance_policy_cache()
    yield
    runtime_service.reset_mvp_acceptance_policy_cache()


# ---------------------------------------------------------------------------
# R3: acceptance-summary endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_summary_reports_cost_rollups_and_accepted_reviews(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.1,
                "provider_base_budget_usd": 0.2,
            },
            "revenue": {"per_accepted_review_usd": 0.5},
            "reinvestment": {"ratio": 0.4},
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 140.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_pass",
                    "infrastructure_cost_usd": 0.011,
                    "external_provider_cost_usd": 0.029,
                    "total_cost_usd": 0.04,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 5.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_pass",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "4/4",
                },
            },
        )
        assert completion_event.status_code == 201

        impl_tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:codex.exec",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 80.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_impl_done",
                    "infrastructure_cost_usd": 0.008,
                    "external_provider_cost_usd": 0.0,
                    "total_cost_usd": 0.008,
                    "is_paid_provider": False,
                },
            },
        )
        assert impl_tool_event.status_code == 201

        impl_completion = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 3.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_impl_done",
                    "task_type": "impl",
                    "task_final_status": "completed",
                },
            },
        )
        assert impl_completion.status_code == 201

        summary = await client.get(
            "/api/runtime/mvp/acceptance-summary",
            params={"seconds": 3600, "limit": 2000},
        )
        assert summary.status_code == 200
        payload = summary.json()
        totals = payload["totals"]
        assert totals["tasks_seen"] == 2
        assert totals["completed_tasks"] == 2
        assert totals["review_tasks_completed"] == 1
        assert totals["accepted_reviews"] == 1
        assert totals["acceptance_rate"] == 1.0
        assert totals["infrastructure_cost_usd"] == 0.019
        assert totals["external_provider_cost_usd"] == 0.029
        assert totals["total_cost_usd"] == 0.048
        assert payload["budget"]["base_budget_usd"] == 0.3
        assert payload["revenue"]["estimated_revenue_usd"] == 0.5
        assert payload["reinvestment"]["reinvestment_pool_usd"] == 0.1808
        assert len(payload["tasks"]) == 2
        review_row = next(
            row for row in payload["tasks"] if row["task_id"] == "task_review_pass"
        )
        assert review_row["task_type"] == "review"
        assert review_row["final_status"] == "completed"
        assert review_row["review_pass_fail"] == "PASS"
        assert review_row["verified_assertions"] == "4/4"
        assert review_row["review_accepted"] is True


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_summary_empty_window_returns_zero_totals(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = await client.get(
            "/api/runtime/mvp/acceptance-summary",
            params={"seconds": 3600, "limit": 2000},
        )
        assert summary.status_code == 200
        payload = summary.json()
        totals = payload["totals"]
        assert totals["tasks_seen"] == 0
        assert totals["completed_tasks"] == 0
        assert totals["review_tasks_completed"] == 0
        assert totals["accepted_reviews"] == 0
        assert totals["acceptance_rate"] == 0.0
        assert totals["infrastructure_cost_usd"] == 0.0
        assert totals["external_provider_cost_usd"] == 0.0
        assert totals["total_cost_usd"] == 0.0
        assert payload["budget"]["base_budget_usd"] == 0.0
        assert payload["revenue"]["estimated_revenue_usd"] == 0.0
        assert payload["reinvestment"]["reinvestment_pool_usd"] == 0.0
        assert payload["tasks"] == []


# ---------------------------------------------------------------------------
# R4: acceptance-judge endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_contract_passes_when_budget_and_revenue_cover_cost(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.05,
                "provider_base_budget_usd": 0.05,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 1.0,
                "require_budget_coverage": True,
                "require_revenue_coverage": True,
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 100.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_pass",
                    "infrastructure_cost_usd": 0.01,
                    "external_provider_cost_usd": 0.02,
                    "total_cost_usd": 0.03,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 2.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_pass",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "3/3",
                },
            },
        )
        assert completion_event.status_code == 201

        judge = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert judge.status_code == 200
        payload = judge.json()
        assert payload["pass"] is True
        assert isinstance(payload["assertions"], list)
        assert payload["assertions"]
        ids = {str(row["id"]) for row in payload["assertions"]}
        assert "accepted_reviews_minimum" in ids
        assert "acceptance_rate_minimum" in ids
        assert "base_budget_covers_total_cost" in ids
        assert "estimated_revenue_covers_total_cost" in ids
        assert payload["contract"]["judge_id"] == "coherence_mvp_acceptance_judge_v1"
        assert (
            payload["contract"]["external_validation_endpoint"]
            == "/api/runtime/mvp/acceptance-judge"
        )
        summary = payload["summary"]
        assert summary["totals"]["accepted_reviews"] == 1
        assert summary["totals"]["total_cost_usd"] == 0.03
        assert summary["budget"]["base_budget_usd"] == 0.1
        assert summary["revenue"]["estimated_revenue_usd"] == 0.1


# ---------------------------------------------------------------------------
# R5: public validator quorum
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_requires_public_validator_quorum(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    signing_key = SigningKey.generate()
    validator_id = "validator_public_1"
    public_key_b64 = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.05,
                "provider_base_budget_usd": 0.05,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 0.7,
                "require_budget_coverage": True,
                "require_revenue_coverage": True,
            },
            "trust": {
                "public_validator": {
                    "required": True,
                    "quorum": 1,
                    "keys": [
                        {
                            "id": validator_id,
                            "public_key_base64": public_key_b64,
                            "source": "public_validator_demo",
                        }
                    ],
                    "attestations": [],
                }
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 100.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_public",
                    "infrastructure_cost_usd": 0.01,
                    "external_provider_cost_usd": 0.02,
                    "total_cost_usd": 0.03,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 2.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_public",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "2/2",
                },
            },
        )
        assert completion_event.status_code == 201

        # Without attestation signatures, required public validator quorum must fail.
        missing_sig = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert missing_sig.status_code == 200
        missing_payload = missing_sig.json()
        assert missing_payload["pass"] is False
        assert any(
            item["id"] == "public_validator_quorum" and item["pass"] is False
            for item in missing_payload["assertions"]
        )

        # Build a valid Ed25519 attestation over the claim payload.
        summary = await client.get(
            "/api/runtime/mvp/acceptance-summary",
            params={"seconds": 3600, "limit": 2000},
        )
        assert summary.status_code == 200
        summary_payload = summary.json()
        claim_payload = {
            "judge_id": "coherence_mvp_acceptance_judge_v1",
            "window_seconds": int(summary_payload.get("window_seconds") or 0),
            "event_limit": int(summary_payload.get("event_limit") or 0),
            "totals": {
                "accepted_reviews": int(
                    summary_payload.get("totals", {}).get("accepted_reviews") or 0
                ),
                "acceptance_rate": float(
                    summary_payload.get("totals", {}).get("acceptance_rate") or 0.0
                ),
                "total_cost_usd": float(
                    summary_payload.get("totals", {}).get("total_cost_usd") or 0.0
                ),
            },
            "budget": {
                "base_budget_usd": float(
                    summary_payload.get("budget", {}).get("base_budget_usd") or 0.0
                )
            },
            "revenue": {
                "estimated_revenue_usd": float(
                    summary_payload.get("revenue", {}).get("estimated_revenue_usd")
                    or 0.0
                )
            },
        }
        claim_bytes = json.dumps(
            claim_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        sig_b64 = base64.b64encode(signing_key.sign(claim_bytes).signature).decode(
            "ascii"
        )

        # Re-write policy with a valid attestation so quorum passes.
        _write_mvp_acceptance_policy(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            override={
                "budget": {
                    "hosted_base_budget_usd": 0.05,
                    "provider_base_budget_usd": 0.05,
                },
                "revenue": {"per_accepted_review_usd": 0.1},
                "acceptance": {
                    "min_accepted_reviews": 1,
                    "min_acceptance_rate": 0.7,
                    "require_budget_coverage": True,
                    "require_revenue_coverage": True,
                },
                "trust": {
                    "public_validator": {
                        "required": True,
                        "quorum": 1,
                        "keys": [
                            {
                                "id": validator_id,
                                "public_key_base64": public_key_b64,
                                "source": "public_validator_demo",
                            }
                        ],
                        "attestations": [
                            {
                                "id": validator_id,
                                "signature_base64": sig_b64,
                            }
                        ],
                    }
                },
            },
        )

        with_sig = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert with_sig.status_code == 200
        with_sig_payload = with_sig.json()
        assert with_sig_payload["pass"] is True
        assert any(
            item["id"] == "public_validator_quorum" and item["pass"] is True
            for item in with_sig_payload["assertions"]
        )
        public_validator = with_sig_payload["contract"]["public_validator"]
        assert public_validator["required"] is True
        assert public_validator["required_quorum"] == 1
        assert public_validator["valid_signatures"] == 1
        assert public_validator["pass"] is True


# ---------------------------------------------------------------------------
# R6: transparency-log anchoring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_requires_public_transparency_anchor(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.05,
                "provider_base_budget_usd": 0.05,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 0.7,
                "require_budget_coverage": True,
                "require_revenue_coverage": True,
            },
            "trust": {
                "public_validator": {"required": False},
                "public_transparency_anchor": {
                    "required": True,
                    "min_anchors": 1,
                    "trusted_domains": ["rekor.sigstore.dev"],
                    "anchors": [],
                },
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 95.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_anchor",
                    "infrastructure_cost_usd": 0.01,
                    "external_provider_cost_usd": 0.02,
                    "total_cost_usd": 0.03,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 2.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_anchor",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "2/2",
                },
            },
        )
        assert completion_event.status_code == 201

        # Without any anchor entries the required gate must fail.
        missing_anchor = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert missing_anchor.status_code == 200
        missing_payload = missing_anchor.json()
        assert missing_payload["pass"] is False
        assert any(
            item["id"] == "public_transparency_anchor" and item["pass"] is False
            for item in missing_payload["assertions"]
        )

        # Extract claim_sha256 and re-write policy with a matching anchor.
        claim_sha = str(missing_payload["contract"]["claim_sha256"])
        anchor_url = "https://rekor.sigstore.dev/api/v1/log/entries/demo"
        _write_mvp_acceptance_policy(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            override={
                "budget": {
                    "hosted_base_budget_usd": 0.05,
                    "provider_base_budget_usd": 0.05,
                },
                "revenue": {"per_accepted_review_usd": 0.1},
                "acceptance": {
                    "min_accepted_reviews": 1,
                    "min_acceptance_rate": 0.7,
                    "require_budget_coverage": True,
                    "require_revenue_coverage": True,
                },
                "trust": {
                    "public_validator": {"required": False},
                    "public_transparency_anchor": {
                        "required": True,
                        "min_anchors": 1,
                        "trusted_domains": ["rekor.sigstore.dev"],
                        "anchors": [
                            {
                                "id": "rekor_demo_entry",
                                "url": anchor_url,
                                "claim_sha256": claim_sha,
                                "source": "rekor",
                            }
                        ],
                    },
                },
            },
        )

        # Fake the HTTP fetch so the test does not make real network calls.
        class _FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                _ = args, kwargs

            def __enter__(self) -> "_FakeClient":
                return self

            def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                _ = exc_type, exc, tb
                return False

            def get(self, url: str) -> _FakeResponse:
                assert url == anchor_url
                return _FakeResponse(f"entry payload contains {claim_sha}")

        monkeypatch.setattr(runtime_service.httpx, "Client", _FakeClient)
        with_anchor = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert with_anchor.status_code == 200
        with_anchor_payload = with_anchor.json()
        assert with_anchor_payload["pass"] is True
        assert any(
            item["id"] == "public_transparency_anchor" and item["pass"] is True
            for item in with_anchor_payload["assertions"]
        )
        anchor_report = with_anchor_payload["contract"]["public_transparency_anchor"]
        assert anchor_report["required"] is True
        assert anchor_report["valid_anchors"] == 1
        assert anchor_report["pass"] is True


# ---------------------------------------------------------------------------
# R9: trust-adjusted revenue proof
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_trust_adjusted_revenue_proves_uplift_and_payout_readiness(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    signing_key = SigningKey.generate()
    validator_id = "validator_revenue_trust_1"
    public_key_b64 = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.0,
                "provider_base_budget_usd": 0.0,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 0.7,
                "require_budget_coverage": False,
                "require_revenue_coverage": False,
            },
            "trust": {
                "require_trust_adjusted_revenue_coverage": True,
                "require_payout_readiness": True,
                "require_trust_for_payout": True,
                "revenue_multipliers": {
                    "validator": 1.25,
                    "anchor": 1.25,
                    "cap": 2.0,
                },
                "public_validator": {
                    "required": True,
                    "quorum": 1,
                    "keys": [
                        {
                            "id": validator_id,
                            "public_key_base64": public_key_b64,
                            "source": "public_validator_demo",
                        }
                    ],
                    "attestations": [],
                },
                "public_transparency_anchor": {
                    "required": True,
                    "min_anchors": 1,
                    "trusted_domains": ["rekor.sigstore.dev"],
                    "anchors": [],
                },
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 150.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_revenue_trust",
                    "infrastructure_cost_usd": 0.04,
                    "external_provider_cost_usd": 0.08,
                    "total_cost_usd": 0.12,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 3.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_revenue_trust",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "2/2",
                },
            },
        )
        assert completion_event.status_code == 201

        # Without trust evidence, trust-adjusted revenue and payout must fail.
        without_trust = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert without_trust.status_code == 200
        without_payload = without_trust.json()
        assert without_payload["pass"] is False
        assert any(
            item["id"] == "trust_adjusted_revenue_covers_total_cost"
            and item["pass"] is False
            for item in without_payload["assertions"]
        )
        assert any(
            item["id"] == "payout_readiness" and item["pass"] is False
            for item in without_payload["assertions"]
        )

        # Build a valid attestation and anchor to activate trust multipliers.
        claim_payload = without_payload["contract"]["claim_payload"]
        claim_bytes = json.dumps(
            claim_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        sig_b64 = base64.b64encode(signing_key.sign(claim_bytes).signature).decode(
            "ascii"
        )
        claim_sha = str(without_payload["contract"]["claim_sha256"])
        anchor_url = "https://rekor.sigstore.dev/api/v1/log/entries/revenue-proof"

        _write_mvp_acceptance_policy(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            override={
                "budget": {
                    "hosted_base_budget_usd": 0.0,
                    "provider_base_budget_usd": 0.0,
                },
                "revenue": {"per_accepted_review_usd": 0.1},
                "acceptance": {
                    "min_accepted_reviews": 1,
                    "min_acceptance_rate": 0.7,
                    "require_budget_coverage": False,
                    "require_revenue_coverage": False,
                },
                "trust": {
                    "require_trust_adjusted_revenue_coverage": True,
                    "require_payout_readiness": True,
                    "require_trust_for_payout": True,
                    "revenue_multipliers": {
                        "validator": 1.25,
                        "anchor": 1.25,
                        "cap": 2.0,
                    },
                    "public_validator": {
                        "required": True,
                        "quorum": 1,
                        "keys": [
                            {
                                "id": validator_id,
                                "public_key_base64": public_key_b64,
                                "source": "public_validator_demo",
                            }
                        ],
                        "attestations": [
                            {
                                "id": validator_id,
                                "signature_base64": sig_b64,
                            }
                        ],
                    },
                    "public_transparency_anchor": {
                        "required": True,
                        "min_anchors": 1,
                        "trusted_domains": ["rekor.sigstore.dev"],
                        "anchors": [
                            {
                                "id": "rekor_revenue_entry",
                                "url": anchor_url,
                                "claim_sha256": claim_sha,
                                "source": "rekor",
                            }
                        ],
                    },
                },
            },
        )

        class _FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                _ = args, kwargs

            def __enter__(self) -> "_FakeClient":
                return self

            def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                _ = exc_type, exc, tb
                return False

            def get(self, url: str) -> _FakeResponse:
                assert url == anchor_url
                return _FakeResponse(f"rekor entry proof {claim_sha}")

        monkeypatch.setattr(runtime_service.httpx, "Client", _FakeClient)
        with_trust = await client.get(
            "/api/runtime/mvp/acceptance-judge",
            params={"seconds": 3600, "limit": 2000},
        )
        assert with_trust.status_code == 200
        with_payload = with_trust.json()
        assert with_payload["pass"] is True
        assert any(
            item["id"] == "trust_adjusted_revenue_covers_total_cost"
            and item["pass"] is True
            for item in with_payload["assertions"]
        )
        assert any(
            item["id"] == "payout_readiness" and item["pass"] is True
            for item in with_payload["assertions"]
        )
        business_proof = with_payload["contract"]["business_proof"]
        revenue_proof = business_proof["revenue"]
        assert revenue_proof["estimated_revenue_usd"] == 0.1
        assert revenue_proof["trust_adjusted_revenue_usd"] == 0.15625
        assert revenue_proof["trust_revenue_uplift_usd"] == 0.05625
        assert revenue_proof["trust_adjusted_operating_surplus_usd"] == 0.03625
        assert business_proof["trust"]["public_validator_pass"] is True
        assert business_proof["trust"]["public_transparency_anchor_pass"] is True
        assert business_proof["payout_ready"] is True
