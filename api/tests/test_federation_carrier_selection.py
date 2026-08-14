"""Selection and recovery witnesses for Form federation admission."""
from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from app.services import form_kernel_bridge
from app.services import native_federation_graph_service as carrier


def _append_from_process(store: str, message_id: str, ready, start) -> None:
    atomic_write = carrier._atomic_write_ascii

    def delayed_write(path, content):
        time.sleep(0.2)
        atomic_write(path, content)

    carrier._atomic_write_ascii = delayed_write
    ready.put(True)
    if not start.wait(5):
        raise RuntimeError("concurrent index witness did not start")
    carrier._append_id(Path(store) / "broadcast", message_id)


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


def test_federation_recipe_path_follows_the_application_package():
    package_root = Path(carrier.__file__).resolve().parent.parent
    assert carrier._RECIPE == (
        package_root / "form_recipes" / "public_federation_graph_cli.fk"
    )

    deployed_module = Path("/app/app/services/native_federation_graph_service.py")
    assert (
        deployed_module.parent.parent
        / "form_recipes"
        / "public_federation_graph_cli.fk"
    ) == Path("/app/app/form_recipes/public_federation_graph_cli.fk")


def test_federation_store_path_uses_file_backed_configuration(tmp_path, monkeypatch):
    observed = {}

    def get_str(section, key, default):
        observed.update(section=section, key=key, default=default)
        return str(tmp_path)

    monkeypatch.setattr(carrier, "get_str", get_str)

    assert carrier.store_path() == tmp_path
    assert observed == {
        "section": "federation",
        "key": "form_graph_store_path",
        "default": "~/.coherence-network/federation-graph",
    }


def test_retry_repairs_indexes_after_message_publish_interruption(tmp_path, monkeypatch):
    monkeypatch.setattr(carrier, "get_str", lambda *_, **__: str(tmp_path))
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


def test_index_updates_are_serialized_across_processes(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    start = context.Event()
    message_ids = [f"msg_{'a' * 64}", f"msg_{'b' * 64}"]
    processes = [
        context.Process(
            target=_append_from_process,
            args=(str(tmp_path), message_id, ready, start),
        )
        for message_id in message_ids
    ]

    for process in processes:
        process.start()
    for _ in processes:
        assert ready.get(timeout=5) is True
    start.set()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    assert set(carrier._read_ids(tmp_path / "broadcast")) == set(message_ids)
