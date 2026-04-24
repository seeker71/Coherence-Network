"""Tests for POST /api/translations and GET /api/translations/{entity_type}/{entity_id}.

Covers the multilingual-web spec gap: anyone signed-in can submit a
translation and it becomes canonical immediately; prior canonical is
preserved as superseded.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _payload(**overrides):
    base = {
        "entity_type": "concept",
        "entity_id": "lc-test-concept",
        "lang": "de",
        "content_title": "Der Puls",
        "content_description": "Eine kurze Beschreibung",
        "content_markdown": "# Der Puls\n\nDer Puls ist der Herzschlag des Feldes.",
        "author_type": "translation_human",
        "author_id": "contributor:alice",
        "translated_from_lang": "en",
    }
    base.update(overrides)
    return base


def test_submit_translation_returns_201_canonical(client):
    response = client.post("/api/translations", json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["entity_type"] == "concept"
    assert body["lang"] == "de"
    assert body["content_title"] == "Der Puls"
    assert body["author_type"] == "translation_human"
    assert body["status"] == "canonical"
    assert body["content_hash"] != ""


def test_human_submission_supersedes_prior_canonical(client):
    first = client.post(
        "/api/translations",
        json=_payload(
            entity_id="lc-supersede-test",
            content_markdown="# v1",
            author_type="translation_machine",
            translator_model="test-model",
        ),
    ).json()
    assert first["status"] == "canonical"
    assert first["author_type"] == "translation_machine"

    second = client.post(
        "/api/translations",
        json=_payload(
            entity_id="lc-supersede-test",
            content_markdown="# v2 — human voice",
            author_type="translation_human",
            author_id="contributor:bob",
        ),
    ).json()
    assert second["status"] == "canonical"
    assert second["author_type"] == "translation_human"
    assert second["content_markdown"] != first["content_markdown"]

    # The history endpoint should now return both; first is superseded
    history = client.get(
        "/api/translations/concept/lc-supersede-test",
        params={"lang": "de"},
    ).json()
    assert history["total"] >= 2
    canonicals = [v for v in history["items"] if v["status"] == "canonical"]
    superseded = [v for v in history["items"] if v["status"] == "superseded"]
    assert len(canonicals) == 1
    assert canonicals[0]["author_type"] == "translation_human"
    assert any(v["author_type"] == "translation_machine" for v in superseded)


def test_list_translations_across_languages(client):
    for lang in ("de", "es", "id"):
        client.post(
            "/api/translations",
            json=_payload(
                entity_id="lc-multi-lang",
                lang=lang,
                content_markdown=f"# content in {lang}",
            ),
        )
    response = client.get("/api/translations/concept/lc-multi-lang")
    assert response.status_code == 200
    langs = {v["lang"] for v in response.json()["items"]}
    assert {"de", "es", "id"}.issubset(langs)


def test_submit_rejects_missing_entity_id(client):
    payload = _payload()
    del payload["entity_id"]
    response = client.post("/api/translations", json=payload)
    assert response.status_code == 422


def test_submit_rejects_missing_content_markdown(client):
    payload = _payload()
    del payload["content_markdown"]
    response = client.post("/api/translations", json=payload)
    assert response.status_code == 422


def test_list_history_filters_to_single_lang(client):
    client.post(
        "/api/translations",
        json=_payload(entity_id="lc-lang-filter", lang="de", content_markdown="de"),
    )
    client.post(
        "/api/translations",
        json=_payload(entity_id="lc-lang-filter", lang="es", content_markdown="es"),
    )
    de_history = client.get(
        "/api/translations/concept/lc-lang-filter", params={"lang": "de"}
    ).json()
    assert all(v["lang"] == "de" for v in de_history["items"])
