"""Consent and native delegation at the existing local MCP carrier boundary."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_MCP = Path(__file__).resolve().parents[2] / "mcp-server"
sys.path.insert(0, str(_MCP))

from coherence_mcp_server import capture_hook, capture_worker  # noqa: E402
from coherence_mcp_server import form_cli_tools as fct  # noqa: E402


def _forbid(*args, **kwargs):
    raise AssertionError("Unexpected read, process, or write")


@pytest.mark.parametrize("consent", [None, "", True, "true", "all-future-turns", {}])
def test_capture_denies_before_configuration_or_io(consent, monkeypatch):
    monkeypatch.setattr(fct, "load_settings", _forbid)
    monkeypatch.setattr(fct.os, "open", _forbid)
    monkeypatch.setattr(Path, "mkdir", _forbid)
    result = fct.catalog_capture(
        "private request", "private answer", "reviewed answer", "chat", "turn",
        capture_consent=consent,
    )
    assert result["captured"] is False
    assert "private" not in json.dumps(result)


def test_explicit_capture_persists_selected_copy_and_returns_receipt(tmp_path, monkeypatch):
    catalog = tmp_path / "learning" / "catalog.jsonl"
    monkeypatch.setattr(fct, "load_settings", lambda: {"catalog_path": str(catalog)})
    result = fct.catalog_capture(
        "selected request", "original warning", "reviewed warning", "chat", "reviewed",
        capture_consent=fct.CAPTURE_CONSENT,
    )
    entry = json.loads(catalog.read_text())
    assert result["captured"] is True
    assert result["catalog_path"] == str(catalog)
    assert "selected request" not in json.dumps(result)
    assert entry["request"] == "selected request"
    assert entry["raw"] == "original warning"
    assert entry["transmuted"] == "reviewed warning"
    assert entry["capture_consent"] == fct.CAPTURE_CONSENT
    assert entry["pairs"]["raw"] == [entry["request_sig"], entry["raw_sig"]]
    assert entry["pairs"]["reasoning"] == [entry["request_sig"], entry["transmuted_sig"]]
    assert stat.S_IMODE(catalog.stat().st_mode) == 0o600
    assert stat.S_IMODE(catalog.parent.stat().st_mode) == 0o700

    catalog.chmod(0o644)
    fct.catalog_capture("r2", "o2", "w2", "chat", "reviewed", capture_consent=fct.CAPTURE_CONSENT)
    assert len(catalog.read_text().splitlines()) == 2
    assert stat.S_IMODE(catalog.stat().st_mode) == 0o600


@pytest.mark.parametrize("link_type", ["symlink", "hardlink"])
def test_capture_refuses_links(tmp_path, monkeypatch, link_type):
    target = tmp_path / "other-file"
    target.write_text("unchanged")
    catalog = tmp_path / "catalog"
    if link_type == "symlink":
        catalog.symlink_to(target)
    else:
        os.link(target, catalog)
    monkeypatch.setattr(fct, "load_settings", lambda: {"catalog_path": str(catalog)})
    result = fct.catalog_capture("r", "o", "w", "chat", "reviewed", capture_consent=fct.CAPTURE_CONSENT)
    assert result["captured"] is False
    assert target.read_text() == "unchanged"


def test_capture_failure_returns_no_raw_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(fct, "load_settings", lambda: {"catalog_path": str(tmp_path / "catalog")})
    def unavailable(*args, **kwargs):
        raise OSError("storage unavailable")
    monkeypatch.setattr(fct.os, "open", unavailable)
    result = fct.catalog_capture("private request", "private answer", "reviewed", "chat", "turn", capture_consent=fct.CAPTURE_CONSENT)
    assert result["captured"] is False
    assert "private" not in json.dumps(result)
    assert not (tmp_path / "catalog").exists()


def test_capture_sync_failure_reports_possible_retention(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.jsonl"
    monkeypatch.setattr(fct, "load_settings", lambda: {"catalog_path": str(catalog)})

    def interrupted_sync(fd):
        raise OSError("storage sync interrupted after the row was flushed")

    monkeypatch.setattr(fct.os, "fsync", interrupted_sync)
    result = fct.catalog_capture(
        "selected private request", "selected private original", "selected private rewrite",
        "chat", "reviewed", capture_consent=fct.CAPTURE_CONSENT,
    )

    saved = json.loads(catalog.read_text())
    assert result["captured"] is None
    assert result["status"] == "indeterminate"
    assert result["may_be_retained"] is True
    assert result["catalog_path"] == str(catalog)
    for field in ("request_sig", "raw_sig", "transmuted_sig"):
        assert result[field] == saved[field]
    assert "before retrying" in result["next_step"]
    assert "selected private" not in json.dumps(result)


@pytest.mark.parametrize("raw,reviewed", [("", "rewrite"), ("original", ""), ("x" * 8001, "rewrite")])
def test_capture_rejects_missing_review_or_oversized_excerpt_before_io(raw, reviewed, monkeypatch):
    monkeypatch.setattr(fct, "load_settings", _forbid)
    assert fct.catalog_capture("request", raw, reviewed, "chat", "reviewed", capture_consent=fct.CAPTURE_CONSENT)["captured"] is False


def test_rewrite_stays_in_current_chat_and_preserves_warning_contract(monkeypatch):
    monkeypatch.setattr(fct.subprocess, "run", _forbid)
    monkeypatch.setattr(fct, "catalog_capture", _forbid)
    monkeypatch.setattr(fct, "load_settings", _forbid)
    text = "Do not proceed: this may be dangerous. I am uncertain."
    result = fct.transmute_text(text)
    assert result["raw"] == text
    assert result["route"] == "current-chat"
    assert result["captured"] is False
    assert result["transmuted"] == ""
    for meaning in ("warnings", "risks", "refusals", "negation", "uncertainty", "untrusted"):
        assert meaning in result["instruction"]


def test_retired_hooks_and_automatic_capture_do_no_work(monkeypatch):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(read=_forbid))
    monkeypatch.setattr(Path, "read_text", _forbid)
    monkeypatch.setattr(subprocess, "Popen", _forbid)
    monkeypatch.setattr(fct, "catalog_capture", _forbid)
    monkeypatch.setattr(sys, "argv", ["capture_worker.py", "/private/queued-payload.json"])
    assert capture_hook.main() == 0
    assert capture_worker.main() == 0
    assert fct.transmute_and_capture("private", "private")["captured"] is False


def test_stop_hook_is_no_longer_registered():
    settings = json.loads((_MCP.parent / ".claude" / "settings.json").read_text())
    assert "capture_hook.py" not in json.dumps(settings)


def test_route_rejects_invalid_axes_before_configuration(monkeypatch):
    monkeypatch.setattr(fct, "load_settings", _forbid)
    assert "error" in fct.kernel_route({"trust": "100"}, {})
    assert "error" in fct.kernel_route({"trust": True}, {})
    assert "error" in fct.kernel_route({"trust": 101}, {})


def test_route_uses_fkwu_and_preserves_failed_execution(tmp_path, monkeypatch):
    kernel = tmp_path / "fkwu"
    kernel.write_text("native runtime stand-in")
    kernel.chmod(0o700)
    recipe = tmp_path / "route.fk"
    recipe.write_text("; native recipe")
    monkeypatch.setattr(fct, "load_settings", lambda: {"kernel_path": str(kernel)})
    monkeypatch.setattr(fct, "_ROUTER_FK", recipe)
    calls = []
    def run(command, **kwargs):
        calls.append((command, Path(command[1]).read_text()))
        return SimpleNamespace(returncode=0, stdout="form-native\n")
    monkeypatch.setattr(fct.subprocess, "run", run)
    result = fct.kernel_route({"trust": 100}, {"trust": 50})
    assert result["winner"] == "form-native"
    assert result["runtime"] == "fkwu"
    assert result["selection_only"] is True
    assert result["external_model_invoked"] is False
    assert calls[0][0][0] == str(kernel)
    assert "import form-stdlib/form-cli-router.fk;" in calls[0][1]
    assert "fcr-route(fcr-backend(" in calls[0][1]
    assert calls[0][0][1].endswith(".bml")
    assert not Path(calls[0][0][1]).exists()
    monkeypatch.setattr(fct.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="form-native\n"))
    assert "error" in fct.kernel_route({}, {})


def _corpus_module():
    spec = importlib.util.spec_from_file_location("training_corpus", _MCP.parent / "scripts" / "training_corpus.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_import_denies_before_iteration_or_reads(monkeypatch):
    corpus = _corpus_module()
    class UnreadSources:
        def __iter__(self):
            pytest.fail("Sources read before consent")
    with pytest.raises(ValueError, match="consent"):
        corpus.feed(UnreadSources())
    monkeypatch.setattr(sys, "argv", ["training_corpus.py", "--source", "all"])
    monkeypatch.setattr(corpus, "SOURCES", {"git": _forbid, "chain": _forbid})
    with pytest.raises(SystemExit) as failure:
        corpus.main()
    assert failure.value.code == 2


def test_source_import_passes_consent_and_counts_only_saved_rows(monkeypatch):
    corpus = _corpus_module()
    calls = []
    def save(*args, **kwargs):
        calls.append(kwargs)
        return {"captured": True}
    monkeypatch.setattr(corpus, "catalog_capture", save)
    pairs = [("intent", "source", "spec", "verified")]
    assert corpus.feed(pairs, capture_consent=fct.CAPTURE_CONSENT) == {"spec": 1}
    assert calls == [{"capture_consent": fct.CAPTURE_CONSENT}]
    monkeypatch.setattr(corpus, "catalog_capture", lambda *args, **kwargs: {"captured": False, "error": "unavailable"})
    with pytest.raises(RuntimeError, match="unavailable"):
        corpus.feed(pairs, capture_consent=fct.CAPTURE_CONSENT)


def test_source_import_does_not_count_an_indeterminate_save(monkeypatch):
    corpus = _corpus_module()
    calls = []

    def interrupted_save(*args, **kwargs):
        calls.append(args)
        return {
            "captured": None,
            "status": "indeterminate",
            "error": "Saving was interrupted; some or all of the local copy may remain",
        }

    monkeypatch.setattr(corpus, "catalog_capture", interrupted_save)
    pairs = [("first", "source", "spec", "verified"), ("second", "source", "spec", "verified")]
    with pytest.raises(RuntimeError, match="local copy may remain"):
        corpus.feed(pairs, capture_consent=fct.CAPTURE_CONSENT)
    assert len(calls) == 1
