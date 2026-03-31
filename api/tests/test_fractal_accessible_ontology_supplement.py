"""Fractal Accessible Ontology — supplemental contract tests (list filters, views, PATCH).

Idea: fractal-accessible-ontology

These tests import the self-contained ontology test app from
``test_fractal_accessible_ontology`` and verify behavior implied by the same
spec (query filters on GET /api/ontology/concepts, view_count, domain PATCH)
without duplicating the sixteen numbered AC tests.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from test_fractal_accessible_ontology import _reset_store, _seed_relation, test_app


@pytest.fixture(autouse=True)
def reset_store() -> None:
    _reset_store()
    yield
    _reset_store()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(test_app, raise_server_exceptions=True)


def test_list_filter_by_domain_excludes_other_domains(client: TestClient) -> None:
    a = client.post(
        "/api/ontology/concepts",
        json={"title": "A", "body": "In ecology.", "domains": ["ecology"]},
    ).json()["id"]
    b = client.post(
        "/api/ontology/concepts",
        json={"title": "B", "body": "In music.", "domains": ["music"]},
    ).json()["id"]

    r = client.get("/api/ontology/concepts", params={"domain": "ecology"})
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()}
    assert a in ids
    assert b not in ids


def test_list_filter_by_status(client: TestClient) -> None:
    p = client.post(
        "/api/ontology/concepts",
        json={"title": "Pending one", "body": "Still pending."},
    ).json()["id"]
    c = client.post(
        "/api/ontology/concepts",
        json={"title": "Confirmed one", "body": "Will confirm."},
    ).json()["id"]
    client.patch(f"/api/ontology/concepts/{c}", json={"status": "confirmed"})

    only_pending = client.get("/api/ontology/concepts", params={"status": "pending"})
    assert only_pending.status_code == 200
    pend_ids = {item["id"] for item in only_pending.json()}
    assert p in pend_ids
    assert c not in pend_ids

    only_conf = client.get("/api/ontology/concepts", params={"status": "confirmed"})
    conf_ids = {item["id"] for item in only_conf.json()}
    assert c in conf_ids
    assert p not in conf_ids


def test_list_search_title_substring(client: TestClient) -> None:
    client.post(
        "/api/ontology/concepts",
        json={"title": "UniqueAlphaToken", "body": "First body."},
    )
    client.post(
        "/api/ontology/concepts",
        json={"title": "Other", "body": "Second body without token."},
    )

    r = client.get("/api/ontology/concepts", params={"search": "uniquealpha"})
    assert r.status_code == 200
    titles = [item["title"] for item in r.json()]
    assert any("UniqueAlphaToken" in t for t in titles)
    assert len(titles) >= 1


def test_get_increments_view_count(client: TestClient) -> None:
    cid = client.post(
        "/api/ontology/concepts",
        json={"title": "Viewed", "body": "Count views."},
    ).json()["id"]

    first = client.get(f"/api/ontology/concepts/{cid}").json()["view_count"]
    second = client.get(f"/api/ontology/concepts/{cid}").json()["view_count"]
    assert second == first + 1


def test_patch_title_and_body_updates_response(client: TestClient) -> None:
    cid = client.post(
        "/api/ontology/concepts",
        json={"title": "Old", "body": "Old body."},
    ).json()["id"]

    patched = client.patch(
        f"/api/ontology/concepts/{cid}",
        json={"title": "New", "body": "New body."},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["title"] == "New"
    assert body["body"] == "New body."


def test_list_includes_inferred_relations_on_each_row(client: TestClient) -> None:
    src = client.post(
        "/api/ontology/concepts",
        json={"title": "Src", "body": "Source."},
    ).json()["id"]
    dst = client.post(
        "/api/ontology/concepts",
        json={"title": "Dst", "body": "Destination."},
    ).json()["id"]
    _seed_relation(src, dst, confidence=0.5)

    listed = client.get("/api/ontology/concepts").json()
    row = next(item for item in listed if item["id"] == src)
    assert len(row["inferred_relations"]) == 1
    assert row["inferred_relations"][0]["dst_concept_id"] == dst


def test_delete_nonexistent_returns_404(client: TestClient) -> None:
    r = client.delete(f"/api/ontology/concepts/{uuid.uuid4()}")
    assert r.status_code == 404


def test_related_nonexistent_returns_404(client: TestClient) -> None:
    r = client.get(f"/api/ontology/concepts/{uuid.uuid4()}/related")
    assert r.status_code == 404
