"""Selection and recovery witnesses for Form federation admission."""
from __future__ import annotations

import hashlib
import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

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


def test_federation_offers_the_actual_values_to_form(monkeypatch):
    observed = {}

    def run_recipe(source, *, timeout):
        observed.update(source=source, timeout=timeout)
        return f"1|msg_{'a' * 64}|edge_{'b' * 64}"

    monkeypatch.setattr(form_kernel_bridge, "run_recipe", run_recipe)
    message_id, edge_id = carrier._offer_identity(
        "R2lsZXM", "QXJpZWw", "bGlnaHQtY29kZQ", "MzM", "e30", "MjAyNg"
    )

    assert (
        '(pfgc-offer-receipt "R2lsZXM" "QXJpZWw" "bGlnaHQtY29kZQ" '
        '"MzM" "e30" "MjAyNg")'
    ) in observed["source"]
    assert "sha256-stream-string" in observed["source"]
    assert "(pfgc-band)" not in observed["source"]
    assert observed["timeout"] == carrier._OFFER_IDENTITY_TIMEOUT_SECONDS
    assert message_id == f"msg_{'a' * 64}"
    assert edge_id == f"edge_{'b' * 64}"


def test_federation_form_refusal_stops_the_carrier(monkeypatch):
    monkeypatch.setattr(form_kernel_bridge, "run_recipe", lambda *_, **__: "0")

    with pytest.raises(RuntimeError, match="admission was not witnessed"):
        carrier._admit(2, 8, 0, 0, 0, 0, 0)


def test_federation_form_identity_refusal_stops_the_carrier(monkeypatch):
    monkeypatch.setattr(form_kernel_bridge, "run_recipe", lambda *_, **__: "0||")

    with pytest.raises(RuntimeError, match="identity receipt is invalid"):
        carrier._offer_identity("a", "", "b", "c", "d", "e")


def test_federation_admission_recipe_is_static_and_present():
    assert carrier._RECIPE.is_file()
    source = carrier._RECIPE.read_text(encoding="utf-8")
    assert "pfgc-admit" in source
    assert "pfgc-offer" in source
    assert "pfgc-offer-receipt" in source
    assert "pfgc-message-id" in source
    assert "pfgc-edge-id" in source
    assert "1111" not in source


def test_federation_message_and_edge_identities_are_computed_by_form():
    values = ("R2lsZXM", "QXJpZWw", "bGlnaHQtY29kZQ", "MzM", "e30", "MjAyNg")

    def field(value: str) -> str:
        return f"{len(value)}:{value}"

    def digest(canonical: str) -> str:
        return hashlib.sha256(
            b"form-cli-carrier-challenge-v1\n" + canonical.encode("ascii")
        ).hexdigest()

    expected_message = "msg_" + digest(
        "federation-message-v1|" + "".join(field(value) for value in values)
    )
    expected_edge = "edge_" + digest(
        "federation-edge-v1|"
        + "".join(field(value) for value in (*values[:3], expected_message))
    )

    assert carrier._offer_identity(*values) == (expected_message, expected_edge)


def test_form_bridge_stages_large_source_outside_the_process_arguments(
    tmp_path,
    monkeypatch,
):
    observed = {}
    runner = tmp_path / "fkwu_run.sh"
    large_source = '(do (let offered "' + ("x" * 150_000) + '") "1")'

    def run(command, **kwargs):
        source_path = Path(command[-1])
        observed.update(
            command=command,
            source=source_path.read_text(encoding="utf-8"),
            source_path=source_path,
            kwargs=kwargs,
        )
        return SimpleNamespace(returncode=0, stdout="1\n", stderr="")

    monkeypatch.setattr(form_kernel_bridge, "kernel_available", lambda: True)
    monkeypatch.setattr(form_kernel_bridge, "_source_runner_path", lambda: runner)
    monkeypatch.setattr(form_kernel_bridge, "_bash_path", lambda: "bash")
    monkeypatch.setattr(form_kernel_bridge.subprocess, "run", run)

    assert form_kernel_bridge.run_recipe(large_source) == "1"
    assert observed["command"][:3] == ["bash", str(runner), "--src"]
    assert large_source not in observed["command"]
    assert observed["source"] == large_source + "\n"
    assert not observed["source_path"].exists()


def test_form_bridge_resolves_configured_git_bash_off_windows_path(
    tmp_path,
    monkeypatch,
):
    program_files = tmp_path / "Program Files"
    git_bash = program_files / "Git" / "bin" / "bash.exe"
    git_bash.parent.mkdir(parents=True)
    git_bash.write_bytes(b"git-bash")
    monkeypatch.setattr(form_kernel_bridge.sys, "platform", "win32")
    monkeypatch.setattr(form_kernel_bridge.shutil, "which", lambda _: None)
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.delenv("ProgramW6432", raising=False)

    assert form_kernel_bridge._bash_path() == str(git_bash)


def test_large_federation_identity_crosses_the_file_backed_form_transport():
    message_id, edge_id = carrier._offer_identity(
        "a",
        "b",
        "c",
        "x" * 150_000,
        "e",
        "f",
    )

    assert carrier._ID.fullmatch(message_id)
    assert carrier._EDGE_ID.fullmatch(edge_id)


def test_federation_identity_kernel_runs_are_serialized(monkeypatch):
    entered_first = threading.Event()
    entered_second = threading.Event()
    release_first = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def run_recipe(*_, **__):
        nonlocal calls
        with calls_lock:
            calls += 1
            call = calls
        if call == 1:
            entered_first.set()
            assert release_first.wait(2)
        else:
            entered_second.set()
        return f"1|msg_{'a' * 64}|edge_{'b' * 64}"

    monkeypatch.setattr(form_kernel_bridge, "run_recipe", run_recipe)
    values = ("a", "b", "c", "d", "e", "f")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(carrier._offer_identity, *values)
        assert entered_first.wait(1)
        second = pool.submit(carrier._offer_identity, *values)
        assert not entered_second.wait(0.2)
        release_first.set()
        assert first.result(timeout=2)[0].startswith("msg_")
        assert second.result(timeout=2)[1].startswith("edge_")

    assert entered_second.is_set()


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


def test_atomic_write_syncs_the_parent_after_publish(tmp_path, monkeypatch):
    destination = tmp_path / "message"
    events = []
    real_replace = carrier.os.replace

    def replace(source, target):
        events.append(("replace", Path(target)))
        real_replace(source, target)

    monkeypatch.setattr(carrier.os, "replace", replace)
    monkeypatch.setattr(
        carrier,
        "_fsync_directory",
        lambda path: events.append(("directory-fsync", path)),
    )

    carrier._atomic_write_ascii(destination, "embodied=yes\n")

    assert destination.read_text(encoding="ascii") == "embodied=yes\n"
    assert events == [
        ("replace", destination),
        ("directory-fsync", tmp_path),
    ]


@pytest.mark.skipif(
    carrier.sys.platform == "win32",
    reason="Windows does not expose directory fsync through os.open",
)
def test_directory_sync_opens_syncs_and_closes_the_directory(tmp_path, monkeypatch):
    events = []
    real_open = carrier.os.open
    real_fsync = carrier.os.fsync
    real_close = carrier.os.close

    def open_directory(path, flags):
        descriptor = real_open(path, flags)
        events.append(("open", Path(path), descriptor))
        return descriptor

    def sync_directory(descriptor):
        events.append(("fsync", descriptor))
        real_fsync(descriptor)

    def close_directory(descriptor):
        events.append(("close", descriptor))
        real_close(descriptor)

    monkeypatch.setattr(carrier.os, "open", open_directory)
    monkeypatch.setattr(carrier.os, "fsync", sync_directory)
    monkeypatch.setattr(carrier.os, "close", close_directory)

    carrier._fsync_directory(tmp_path)

    descriptor = events[0][2]
    assert events == [
        ("open", tmp_path, descriptor),
        ("fsync", descriptor),
        ("close", descriptor),
    ]


def test_retry_repairs_indexes_after_message_publish_interruption(tmp_path, monkeypatch):
    monkeypatch.setattr(carrier, "get_str", lambda *_, **__: str(tmp_path))
    monkeypatch.setattr(carrier, "_admit", lambda *_, **__: None)
    message_id = f"msg_{'c' * 64}"
    edge_id = f"edge_{'d' * 64}"
    monkeypatch.setattr(
        carrier,
        "_offer_identity",
        lambda *_: (message_id, edge_id),
    )
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
    assert message_files[0].name.removeprefix("message-") == message_id

    monkeypatch.setattr(carrier, "_append_id", real_append)
    retried = carrier.offer(**values)

    assert retried["message_id"] == message_id
    assert retried["message_node"] == message_id
    assert retried["edge_node"] == edge_id
    assert (tmp_path / f"edge-{edge_id}").is_file()
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
