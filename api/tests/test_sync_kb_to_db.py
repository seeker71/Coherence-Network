from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import kb_common
import sync_kb_to_db


def _write_concept(tmp_path: Path, concept_id: str = "lc-test-sync") -> Path:
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
        raise RuntimeError("404 missing")

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
        raise RuntimeError("404 missing")

    def fake_post(url: str, body: dict, timeout: int = 30, retries: int = 3, headers: dict[str, str] | None = None):
        return 401

    monkeypatch.setattr(sync_kb_to_db, "api_get", fake_get)
    monkeypatch.setattr(sync_kb_to_db, "api_post", fake_post)

    exit_code = sync_kb_to_db.main(
        ["lc-test-fail", "--api-url", "https://api.example.test", "--api-key", "bad-key"]
    )

    assert exit_code == 1
