"""Public kernel-image proposal preview contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]
KERNEL_CORE_SOURCE = ROOT / "form" / "form-stdlib" / "bml" / "kernel-core.bml"


@pytest.mark.asyncio
async def test_kernel_image_proposal_accepts_canonical_core_preview() -> None:
    source = KERNEL_CORE_SOURCE.read_text(encoding="utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/kernel-image/proposals",
            json={
                "expression": source,
                "grammar": "bml",
                "source_label": "test:canonical-kernel-core",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "kernel-image-proposal-preview"
    assert body["proposal_status"] == "accepted-preview"
    assert body["proof_passed"] is True
    assert body["source_hash"].startswith("sha256:")
    assert body["canonical_source_hash"] == body["source_hash"]
    assert body["diff"]["same_as_current_source"] is True
    assert body["diff"]["count_delta"] == {
        "primitive_count": 0,
        "dispatch_count": 0,
        "proof_count": 0,
    }

    image = body["candidate_image"]
    assert image["kind"] == "KERNEL-CORE-IMAGE"
    assert image["image_kind"] == "kernel-core-self"
    assert image["primitive_count"] == 8
    assert image["dispatch_count"] == 15
    assert image["proof_count"] == 6
    assert image["image_hash"].startswith("sha256:")

    envelope = body["trust_envelope"]
    assert envelope["choice_success"] == 1
    assert envelope["bma"] == "kernel-image-proposal"
    assert envelope["mutation_allowed"] is False
    assert envelope["mutation_performed"] is False
    assert body["mutation"]["performed"] is False
    assert body["mutation"]["next_gate"] == (
        "commit evidence -> PR -> CI -> deploy -> public SHA verification"
    )


@pytest.mark.asyncio
async def test_kernel_image_proposal_apply_intent_is_preview_only() -> None:
    source = KERNEL_CORE_SOURCE.read_text(encoding="utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/kernel-image/proposals",
            json={
                "expression": source,
                "grammar": "bml",
                "requested_action": "apply",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proof_passed"] is True
    assert body["mutation"]["requested"] is True
    assert body["mutation"]["allowed"] is False
    assert body["mutation"]["performed"] is False
    assert body["trust_envelope"]["requested_action"] == "apply"
    assert body["trust_envelope"]["rollback"] == "no production state changed by this route"


@pytest.mark.asyncio
async def test_kernel_image_proposal_rejects_unproven_source_with_trace() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/kernel-image/proposals",
            json={"expression": "class SomethingElse {}", "grammar": "bml"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposal_status"] == "rejected-preview"
    assert body["proof_passed"] is False
    assert body["candidate_image"] is None
    assert body["trust_envelope"]["choice_success"] == 0
    assert body["mutation"]["allowed"] is False
    trace_by_name = {step["name"]: step for step in body["proof_trace"]}
    assert trace_by_name["kernel-core-self-class"]["status"] == "fail"
    assert trace_by_name["required-counts-present"]["status"] == "fail"
