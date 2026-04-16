"""LibreTranslate backend — verifies translation + glossary post-substitution.

We stub httpx.Client.post so these tests are deterministic and don't touch the
public LibreTranslate instance. The important surface is the post-processing:
anchor terms from the per-language glossary must appear in the output even
when LibreTranslate rendered them as something else.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.translator_backends import (
    LibreTranslateBackend,
    _apply_glossary,
    register_default_backend,
)
from app.services import translator_service


def _mock_translate_response(text: str):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"translatedText": text})
    return resp


def test_translates_plain_text():
    backend = LibreTranslateBackend(base_url="http://stub")
    with patch("httpx.Client") as ClientCls:
        client = MagicMock()
        client.post = MagicMock(return_value=_mock_translate_response("Hallo Welt"))
        ClientCls.return_value.__enter__ = MagicMock(return_value=client)
        ClientCls.return_value.__exit__ = MagicMock(return_value=False)
        title, desc, md = backend.attune(
            source_markdown="Hello world",
            source_title="Hello",
            source_description="Hello friend",
            source_lang="en",
            target_lang="de",
            glossary_prompt="",
        )
        assert "Hallo" in title
        assert client.post.called


def test_applies_glossary_post_substitution():
    """When the glossary has tending→hüten for de, the word should appear in output."""
    glossary = [("tending", "hüten"), ("ripening", "reifen")]
    out = _apply_glossary("The practice is tending and ripening.", glossary)
    assert "hüten" in out
    assert "reifen" in out


def test_preserves_code_fences_and_urls():
    glossary = [("tending", "hüten")]
    raw = "Read tending at `tending.md` or https://example.com/tending for details."
    out = _apply_glossary(raw, glossary)
    # Code and URL preserved
    assert "`tending.md`" in out
    assert "https://example.com/tending" in out
    # Plain word substituted
    assert "Read hüten at" in out


def test_case_insensitive_word_boundary():
    glossary = [("tending", "hüten")]
    raw = "Tending is tending. Pretending? No."
    out = _apply_glossary(raw, glossary)
    assert "hüten" in out.lower()
    # "Pretending" shouldn't match "tending" as a word
    assert "Pretending" in out or "pretending" in out.lower()


def test_preserves_image_syntax():
    glossary = [("tending", "hüten")]
    raw = "See ![the tending](visuals:tending prompt) and tending."
    out = _apply_glossary(raw, glossary)
    # Image prompt preserved
    assert "visuals:tending prompt" in out
    # Outside segment substituted
    assert "hüten" in out


def test_register_default_prefers_libretranslate_without_key(monkeypatch):
    """With no COHERENCE_TRANSLATOR set and no anthropic key, installs LibreTranslate."""
    # Clean slate
    translator_service.set_backend(None)
    monkeypatch.delenv("COHERENCE_TRANSLATOR", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Avoid picking up a real keystore by faking Path.home()
    with patch("app.services.translator_backends._read_keystore_key", return_value=None):
        name = register_default_backend()
    assert name == "libretranslate"
    assert translator_service.has_backend() is True
    translator_service.set_backend(None)
