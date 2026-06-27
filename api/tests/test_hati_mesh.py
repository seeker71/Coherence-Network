from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_hati_mesh_organ_announce_records_identity_receipt() -> None:
    client = TestClient(app)
    payload = {
        "organ_id": "hati-organ-test-android-001",
        "organ_kind": "android-phone",
        "app": "coherence-sense",
        "app_version": "0.2",
        "target": "android-arm64",
        "steward_cell_id": "cell:urs",
        "capabilities": ["cap.sensor.read", "cap.http.request"],
        "lanes": ["sensor:signal", "hati.mesh:presence"],
    }

    response = client.post("/api/hati/mesh/organs/announce", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["mesh"] == "hati.mesh"
    assert body["status"] == "announced"
    assert body["identity"]["organ_id"] == payload["organ_id"]
    assert body["identity"]["steward_cell_id"] == "cell:urs"
    assert body["receipt"]["runtime_event_id"].startswith("rt_")


def test_hati_mesh_organs_lists_announced_organ() -> None:
    client = TestClient(app)
    payload = {
        "organ_id": "hati-organ-test-camera-001",
        "organ_kind": "camera",
        "target": "macos-arm64",
        "display_name": "Mac witness A",
        "dwelling_name": "North house",
        "location_label": "ridge room",
        "map_x": 31.0,
        "map_y": 47.0,
        "discovery_state": "trusted",
        "trust_score_ppm": 910000,
        "signal_strength_ppm": 780000,
        "battery_level_ppm": 660000,
        "power_cost_ppm": 180000,
        "capabilities": ["cap.video.frame"],
        "lanes": ["video:rgba-time"],
    }

    created = client.post("/api/hati/mesh/organs/announce", json=payload)
    assert created.status_code == 201

    listed = client.get("/api/hati/mesh/organs")
    assert listed.status_code == 200
    items = listed.json()["items"]
    organ = next(item for item in items if item["organ_id"] == payload["organ_id"])
    assert organ["display_name"] == "Mac witness A"
    assert organ["dwelling_name"] == "North house"
    assert organ["map_x"] == 31.0
    assert organ["discovery_state"] == "trusted"
    assert organ["trust_score_ppm"] == 910000
    assert organ["signal_strength_ppm"] == 780000


def test_hati_mesh_channel_offer_records_flow_and_route_receipt() -> None:
    client = TestClient(app)
    payload = {
        "from_organ_id": "hati-organ-test-android-002",
        "to_organ_id": "hati-organ-test-macos-001",
        "protocol": "audio:pcm16",
        "interface": "offer:listen-speak",
        "capability": "cap.audio.sample",
        "codec": "pcm16",
        "data_type": "audio-pcm16",
        "direction": "bidirectional",
        "status": "offered",
        "sample_rate_hz": 16000.0,
        "bytes_per_second": 32000.0,
        "latency_ms": 18.5,
        "error_rate_ppm": 2500,
        "packet_loss_ppm": 1000,
        "branch_success_rate_ppm": 860000,
        "infer_error_rate_ppm": 120000,
        "signal_strength_ppm": 760000,
        "power_cost_ppm": 220000,
        "trust_score_ppm": 820000,
        "route_quality_ppm": 790000,
        "model_id": "speech-native-v0",
    }

    response = client.post("/api/hati/mesh/channels/offer", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["mesh"] == "hati.mesh"
    assert body["channel"]["protocol"] == "audio:pcm16"
    assert body["channel"]["data_type"] == "audio-pcm16"
    assert body["channel"]["direction"] == "bidirectional"
    assert body["receipt"]["runtime_event_id"].startswith("rt_")

    listed = client.get("/api/hati/mesh/channels", params={"organ_id": payload["from_organ_id"]})
    assert listed.status_code == 200
    channel = next(item for item in listed.json()["items"] if item["protocol"] == "audio:pcm16")
    assert channel["latency_ms"] == 18.5
    assert channel["branch_success_rate_ppm"] == 860000
    assert channel["infer_error_rate_ppm"] == 120000
    assert channel["signal_strength_ppm"] == 760000
    assert channel["power_cost_ppm"] == 220000
    assert channel["trust_score_ppm"] == 820000
    assert channel["route_quality_ppm"] == 790000


def test_hati_mesh_heartbeat_marks_organ_listening() -> None:
    client = TestClient(app)
    organ_id = "hati-organ-test-heartbeat-001"

    response = client.post(
        "/api/hati/mesh/organs/heartbeat",
        json={
            "organ_id": organ_id,
            "listening": True,
            "active_channels": ["sensor:signal"],
            "sample_rate_hz": 1.5,
            "bytes_per_second": 480.0,
            "discovery_state": "seen",
            "trust_score_ppm": 500000,
            "signal_strength_ppm": 720000,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "listening"

    listed = client.get("/api/hati/mesh/organs")
    assert listed.status_code == 200
    organ = next(item for item in listed.json()["items"] if item["organ_id"] == organ_id)
    assert organ["listening"] is True
    assert organ["discovery_state"] == "streaming"
    assert organ["active_channels"] == ["sensor:signal"]
    assert organ["signal_strength_ppm"] == 720000


def test_hati_mesh_organ_survives_event_firehose() -> None:
    """The roster must return an announced organ even when buried under a flood of
    unrelated API events. This reproduces the prod symptom (GET /organs -> count 0):
    the announce is receipt-logged, but the general API event firehose pushed it out
    of the limit window. The endpoint_prefix filter pulls mesh events at the DB level
    so a low-volume being stays discoverable — the precondition for mutual sensing.
    """
    from app.models.runtime import RuntimeEventCreate
    from app.services import runtime_service

    client = TestClient(app)
    organ_id = "hati-organ-firehose-windows-001"
    created = client.post(
        "/api/hati/mesh/organs/announce",
        json={
            "organ_id": organ_id,
            "organ_kind": "host-kernel",
            "steward_label": "urs",
            "capabilities": ["presence", "clock"],
        },
    )
    assert created.status_code == 201

    # flood with unrelated api events, well past the roster's limit window (limit*4)
    for _ in range(240):
        runtime_service.record_event(
            RuntimeEventCreate(
                source="api",
                endpoint="/api/health",
                raw_endpoint="/api/health",
                method="GET",
                status_code=200,
                runtime_ms=1.0,
                idea_id="health",
            )
        )

    listed = client.get("/api/hati/mesh/organs")
    assert listed.status_code == 200
    ids = [item["organ_id"] for item in listed.json()["items"]]
    assert organ_id in ids, "announced organ drowned by the event firehose — roster not mutual-sensing"
