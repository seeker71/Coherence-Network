"""Flow test: /api/vedic/ask carries a question to the native vedic-chat.fk cell and the words back."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import vedic
from app.services.form_kernel_bridge import (
    _form_source_parent,
    app_recipes_dir,
    inject_bindings,
    kernel_available,
    load_recipe,
    resolve_recipe_path,
)


def _kernel_carries_the_cell() -> bool:
    """The live test needs fkwu AND a kernel checkout that already holds vedic-chat.fk."""
    cell = _form_source_parent() / "form" / "form-stdlib" / "vedic-chat.fk"
    return kernel_available() and cell.is_file()


def test_recipe_is_api_owned_and_rides_the_kernel_cell():
    resolved = resolve_recipe_path(vedic.RECIPE)
    assert resolved == app_recipes_dir() / vedic.RECIPE
    src = load_recipe(vedic.RECIPE)
    # the body lives in the kernel; the recipe only preludes it and prints its words
    assert "form-stdlib/vedic-chat.fk" in src
    assert "(print_str (vedic-respond-for question" in src


def test_bindings_cover_every_route_input():
    src = load_recipe(vedic.RECIPE)
    injected = inject_bindings(
        src,
        {
            "question": 'where is my "moon"?',
            "year": 2026.72,
            "y": 1971, "m": 10, "d": 6, "uth": 8, "utm": 15,
            "lat": 47.05, "lon": 8.31,
        },
    )
    assert '(let question "where is my \\"moon\\"?")' in injected
    assert "(let year 2026.72)" in injected
    assert "(let lat 47.05)" in injected


def test_route_is_mounted_under_api():
    # routers are included lazily, so the OpenAPI document is the mounted truth
    assert "/api/vedic/ask" in app.openapi()["paths"]


def test_ground_names_urs_only_for_the_attested_moment():
    assert vedic._ground(1971, 10, 6, 8, 15, 47.05, 8.31).startswith("Urs")
    assert vedic._ground(2000, 1, 1, 12, 0, 47.05, 8.31).startswith("2000-01-01 12:00 UT")


def test_route_refuses_plainly_when_the_body_is_unreachable(monkeypatch):
    def unreachable(*_args, **_kwargs):
        raise RuntimeError("fkwu unavailable in this test")

    monkeypatch.setattr(vedic, "serve_text_via_kernel", unreachable)
    client = TestClient(app)
    res = client.get("/api/vedic/ask", params={"q": "moon"})
    assert res.status_code == 503
    assert "not reachable" in res.json()["detail"]


@pytest.mark.skipif(
    not _kernel_carries_the_cell(),
    reason="needs the c-bootstrapped fkwu and a kernel checkout carrying form-stdlib/vedic-chat.fk",
)
def test_live_moon_answer_names_bharani():
    client = TestClient(app)
    res = client.get("/api/vedic/ask", params={"q": "where is my moon?", "year": 2026.7})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["runtime"] == "fkwu"
    assert "Bharani" in body["answer"]
    assert body["ground"].startswith("Urs")
