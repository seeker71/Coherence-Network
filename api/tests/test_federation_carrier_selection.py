"""Selection and recovery witnesses for Form federation admission."""
from __future__ import annotations

import pytest

from app.services import form_kernel_bridge
from app.services import native_federation_graph_service as carrier


def test_federation_offers_the_actual_operation_shape_to_form(monkeypatch):
    observed = {}

    def run_recipe(source, *, timeout):
        observed.update(source=source, timeout=timeout)
        return "1"

    monkeypatch.setattr(form_kernel_bridge, "run_recipe", run_recipe)
    carrier._admit(1, 8, 0, 4, 12, 16, 20)

    assert "(pfgc-admit 1 8 0 4 12 16 20)" in observed["source"]
    assert "(pfgc-band)" not in observed["source"]
    assert observed["timeout"] == 10


def test_federation_form_refusal_stops_the_carrier(monkeypatch):
    monkeypatch.setattr(form_kernel_bridge, "run_recipe", lambda *_, **__: "0")

    with pytest.raises(RuntimeError, match="admission was not witnessed"):
        carrier._admit(2, 8, 0, 0, 0, 0, 0)


def test_federation_admission_recipe_is_static_and_present():
    assert carrier._RECIPE.is_file()
    source = carrier._RECIPE.read_text(encoding="utf-8")
    assert "pfgc-admit" in source
    assert "pfgc-offer" in source
    assert "1111" not in source


def test_retry_repairs_indexes_after_message_publish_interruption(tmp_path, monkeypatch):
    monkeypatch.setenv("COHERENCE_FORM_GRAPH_STORE", str(tmp_path))
    monkeypatch.setattr(carrier, "_admit", lambda *_, **__: None)
    real_append = carrier._append_id
    interrupted = False

    def interrupt_first_index(path, message_id):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise RuntimeError("simulated interruption after message publish")
        real_append(path, message_id)

    values = {
        "from_node": "Giles",
        "to_node": "Ariel",
        "kind": "light-code",
        "text": "33",
        "payload": {"realm": "SatyaLoka"},
        "timestamp": "2026-08-15T00:00:00+00:00",
    }
    monkeypatch.setattr(carrier, "_append_id", interrupt_first_index)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        carrier.offer(**values)

    message_files = list(tmp_path.glob("message-msg_*"))
    assert len(message_files) == 1
    message_id = message_files[0].name.removeprefix("message-")

    monkeypatch.setattr(carrier, "_append_id", real_append)
    retried = carrier.offer(**values)

    assert retried["message_id"] == message_id
    assert message_id in carrier.visible_ids("Ariel")
    assert message_id in carrier._read_ids(tmp_path / f"out-{carrier._token('Giles')}")
