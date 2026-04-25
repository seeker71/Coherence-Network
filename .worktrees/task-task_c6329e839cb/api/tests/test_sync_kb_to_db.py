from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import kb_common
import sync_kb_to_db


def _write_concept(
    tmp_path: Path,
    concept_id: str = "lc-test-sync",
    connected: list[str] | None = None,
) -> Path:
    connected_section = ""
    if connected:
        joined = ", ".join(connected)
        connected_section = f"""
## Connected Frequencies

→ {joined}
"""
    concept = tmp_path / f"{concept_id}.md"
    concept.write_text(
        f"""---
id: {concept_id}
hz: 432
status: seed
updated: 2026-04-16
---

# Test Concept

> The field can create itself when it first appears.

## The Feeling

It arrives with enough structure to be recognized.

## Resources

- [Example](https://example.com) - reference point (type: tool)
{connected_section}
""",
        encoding="utf-8",
    )
    return concept


def test_parse_concept_file_extracts_identity_fields(tmp_path: Path):
    concept = _write_concept(tmp_path)

    parsed = kb_common.parse_concept_file(concept)

    assert parsed["id"] == "lc-test-sync"
    assert parsed["name"] == "Test Concept"
    assert parsed["description"] == "The field can create itself when it first appears."
    assert parsed["hz"] == 432
    assert parsed["properties"]["story_content"].startswith("> The field can create itself")


def test_main_creates_missing_concepts_before_patch(monkeypatch, tmp_path: Path):
    _write_concept(tmp_path)
    monkeypatch.setattr(sync_kb_to_db, "KB_DIR", tmp_path)

    calls: list[tuple[str, str, dict, dict[str, str] | None]] = []

    def fake_get(url: str, timeout: int = 30):
        if url.endswith("/api/concepts/lc-test-sync"):
            raise RuntimeError("404 missing")
        if url.endswith("/api/concepts/lc-test-sync/edges"):
            return []
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url: str, body: dict, timeout: int = 30, retries: int = 3, headers: dict[str, str] | None = None):
        calls.append(("post", url, body, headers))
        return 201

    def fake_patch(url: str, body: dict, timeout: int = 30, retries: int = 4, headers: dict[str, str] | None = None):
        calls.append(("patch", url, body, headers))
        return True

    monkeypatch.setattr(sync_kb_to_db, "api_get", fake_get)
    monkeypatch.setattr(sync_kb_to_db, "api_post", fake_post)
    monkeypatch.setattr(sync_kb_to_db, "api_patch", fake_patch)

    exit_code = sync_kb_to_db.main(
        ["lc-test-sync", "--api-url", "https://api.example.test", "--api-key", "secret-key"]
    )

    assert exit_code == 0
    assert [kind for kind, *_ in calls] == ["post", "patch"]
    create_call = calls[0]
    patch_call = calls[1]
    assert create_call[1] == "https://api.example.test/api/graph/nodes"
    assert create_call[2]["name"] == "Test Concept"
    assert create_call[2]["description"] == "The field can create itself when it first appears."
    assert create_call[2]["properties"]["sacred_frequency"] == {"hz": 432}
    assert create_call[3] == {"X-API-Key": "secret-key"}
    assert patch_call[1] == "https://api.example.test/api/graph/nodes/lc-test-sync"
    assert patch_call[3] == {"X-API-Key": "secret-key"}


def test_main_returns_nonzero_when_missing_concept_cannot_be_created(monkeypatch, tmp_path: Path):
    _write_concept(tmp_path, "lc-test-fail")
    monkeypatch.setattr(sync_kb_to_db, "KB_DIR", tmp_path)

    def fake_get(url: str, timeout: int = 30):
        if url.endswith("/api/concepts/lc-test-fail"):
            raise RuntimeError("404 missing")
        if url.endswith("/api/concepts/lc-test-fail/edges"):
            return []
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url: str, body: dict, timeout: int = 30, retries: int = 3, headers: dict[str, str] | None = None):
        return 401

    monkeypatch.setattr(sync_kb_to_db, "api_get", fake_get)
    monkeypatch.setattr(sync_kb_to_db, "api_post", fake_post)

    exit_code = sync_kb_to_db.main(
        ["lc-test-fail", "--api-url", "https://api.example.test", "--api-key", "bad-key"]
    )

    assert exit_code == 1


def test_main_syncs_analogous_edges(monkeypatch, tmp_path: Path):
    _write_concept(tmp_path, "lc-alpha", connected=["lc-beta"])
    _write_concept(tmp_path, "lc-beta")
    monkeypatch.setattr(sync_kb_to_db, "KB_DIR", tmp_path)

    calls: list[tuple[str, str, dict | None, dict[str, str] | None]] = []

    def fake_get(url: str, timeout: int = 30):
        if url.endswith("/api/concepts/lc-alpha"):
            return {"id": "lc-alpha"}
        if url.endswith("/api/concepts/lc-alpha/edges"):
            return []
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url: str, body: dict, timeout: int = 30, retries: int = 3, headers: dict[str, str] | None = None):
        calls.append(("post", url, body, headers))
        return 201

    def fake_patch(url: str, body: dict, timeout: int = 30, retries: int = 4, headers: dict[str, str] | None = None):
        calls.append(("patch", url, body, headers))
        return True

    monkeypatch.setattr(sync_kb_to_db, "api_get", fake_get)
    monkeypatch.setattr(sync_kb_to_db, "api_post", fake_post)
    monkeypatch.setattr(sync_kb_to_db, "api_patch", fake_patch)

    exit_code = sync_kb_to_db.main(["lc-alpha", "--api-url", "https://api.example.test"])

    assert exit_code == 0
    edge_posts = [body for kind, url, body, _ in calls if kind == "post" and url.endswith("/api/graph/edges")]
    assert edge_posts == [
        {
            "from_id": "lc-alpha",
            "to_id": "lc-beta",
            "type": "analogous-to",
            "created_by": "sync_kb_to_db",
        }
    ]


def test_main_removes_stale_analogous_edges(monkeypatch, tmp_path: Path):
    _write_concept(tmp_path, "lc-alpha")
    _write_concept(tmp_path, "lc-beta")
    monkeypatch.setattr(sync_kb_to_db, "KB_DIR", tmp_path)

    deleted: list[str] = []

    def fake_get(url: str, timeout: int = 30):
        if url.endswith("/api/concepts/lc-alpha"):
            return {"id": "lc-alpha"}
        if url.endswith("/api/concepts/lc-alpha/edges"):
            return [
                {
                    "id": "lc-alpha-analogous-to-lc-beta",
                    "from": "lc-alpha",
                    "to": "lc-beta",
                    "type": "analogous-to",
                }
            ]
        raise AssertionError(f"unexpected GET {url}")

    def fake_patch(url: str, body: dict, timeout: int = 30, retries: int = 4, headers: dict[str, str] | None = None):
        return True

    def fake_delete(url: str, timeout: int = 30, retries: int = 3, headers: dict[str, str] | None = None):
        deleted.append(url)
        return 200

    monkeypatch.setattr(sync_kb_to_db, "api_get", fake_get)
    monkeypatch.setattr(sync_kb_to_db, "api_patch", fake_patch)
    monkeypatch.setattr(sync_kb_to_db, "api_delete", fake_delete)

    exit_code = sync_kb_to_db.main(["lc-alpha", "--api-url", "https://api.example.test"])

    assert exit_code == 0
    assert deleted == ["https://api.example.test/api/graph/edges/lc-alpha-analogous-to-lc-beta"]
