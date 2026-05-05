"""Lineage importer replays explicit graph edges from manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import import_lineage  # noqa: E402


class _Response:
    def __init__(self, status_code: int, payload: dict | list | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._payload


class _FakeClient:
    posts: list[tuple[str, dict | None]]

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def get(self, path: str, timeout: float = 0):
        return _Response(200, {"id": "contributor:source"})

    def post(self, path: str, json: dict | None = None, timeout: float = 0):
        self.posts.append((path, json))
        if path == "/api/graph/nodes":
            return _Response(200, {"id": json["id"]})
        if path == "/api/graph/edges":
            return _Response(200, {"id": "edge-1", **(json or {})})
        return _Response(200, {})

    def patch(self, path: str, json: dict | None = None, timeout: float = 0):
        return _Response(200, {"id": json["id"], **(json or {})})


def test_import_lineage_replays_manifest_edges(tmp_path, monkeypatch):
    manifest = {
        "presences": [
            {"kind": "manual", "id": "contributor:source", "type": "contributor", "name": "Source"},
            {"kind": "manual", "id": "story:target", "type": "story", "name": "Target"},
        ],
        "gatherings": [],
        "edges": [
            {
                "from_id": "contributor:source",
                "to_id": "story:target",
                "type": "inspires",
                "strength": 0.8,
                "created_by": "manifest-test",
                "properties": {"source_document": "docs/test.md"},
            }
        ],
    }
    manifest_path = tmp_path / "lineage.graph.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    created_clients: list[_FakeClient] = []

    def _client_factory(base_url: str):
        client = _FakeClient(base_url)
        created_clients.append(client)
        return client

    monkeypatch.setattr(import_lineage.httpx, "Client", _client_factory)

    counts = import_lineage.replay(
        manifest_path,
        "http://api.test",
        "contributor:source",
        dry_run=False,
    )

    assert counts["edges"] == 1
    edge_posts = [payload for path, payload in created_clients[0].posts if path == "/api/graph/edges"]
    assert edge_posts == [
        {
            "from_id": "contributor:source",
            "to_id": "story:target",
            "type": "inspires",
            "strength": 0.8,
            "created_by": "manifest-test",
            "properties": {"source_document": "docs/test.md"},
        }
    ]
