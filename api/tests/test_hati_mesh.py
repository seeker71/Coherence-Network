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
        "capabilities": ["cap.video.frame"],
        "lanes": ["video:rgba-time"],
    }

    created = client.post("/api/hati/mesh/organs/announce", json=payload)
    assert created.status_code == 201

    listed = client.get("/api/hati/mesh/organs")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(item["organ_id"] == payload["organ_id"] for item in items)


def test_hati_mesh_channel_offer_records_flow_receipt() -> None:
    client = TestClient(app)
    payload = {
        "from_organ_id": "hati-organ-test-android-002",
        "to_organ_id": "hati-organ-test-macos-001",
        "protocol": "audio:pcm16",
        "interface": "offer:listen-speak",
        "capability": "cap.audio.sample",
        "codec": "pcm16",
        "status": "offered",
        "sample_rate_hz": 16000.0,
        "bytes_per_second": 32000.0,
    }

    response = client.post("/api/hati/mesh/channels/offer", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["mesh"] == "hati.mesh"
    assert body["channel"]["protocol"] == "audio:pcm16"
    assert body["receipt"]["runtime_event_id"].startswith("rt_")

    listed = client.get("/api/hati/mesh/channels", params={"organ_id": payload["from_organ_id"]})
    assert listed.status_code == 200
    assert any(item["protocol"] == "audio:pcm16" for item in listed.json()["items"])


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
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "listening"

    listed = client.get("/api/hati/mesh/organs")
    assert listed.status_code == 200
    organ = next(item for item in listed.json()["items"] if item["organ_id"] == organ_id)
    assert organ["listening"] is True
    assert organ["active_channels"] == ["sensor:signal"]
