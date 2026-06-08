"""Proof that mutation auth has a native Form parity carrier."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_PORT_PATH = ROOT / "form" / "form-stdlib" / "auth-port.fk"
AUTH_BAND_PATH = ROOT / "form" / "form-stdlib" / "tests" / "auth-port-band.fk"
PY_AUTH_PATH = ROOT / "api" / "app" / "middleware" / "auth.py"
CONTRIBUTOR_KEY_STORE_PATH = ROOT / "api" / "app" / "services" / "contributor_key_store.py"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_auth_port_names_fastapi_parity_surface():
    form_text = _text(AUTH_PORT_PATH)
    py_auth = _text(PY_AUTH_PATH)
    key_store = _text(CONTRIBUTOR_KEY_STORE_PATH)

    for required in (
        "defn auth-require-api-key",
        "defn auth-require-api-key-from-headers",
        "defn auth-contributor-key-hash",
        "defn auth-contributor-key-active?",
        "defn auth-parity-test",
        "Invalid or missing X-API-Key header",
        "API key not configured for production",
    ):
        assert required in form_text

    assert "def require_api_key" in py_auth
    assert 'Header(None, alias="X-API-Key")' in py_auth
    assert "contributor_key_store.verify(x_api_key)" in py_auth
    assert "hashlib.sha256" in key_store
    assert "revoked_at is not None" in key_store


def test_auth_band_proves_shared_key_contributor_key_and_denials():
    text = _text(AUTH_BAND_PATH)

    assert "Band verdict: 1111" in text
    assert "auth-parity-test" in text
    assert "kh-request" in text
    assert "cc_alice_native_auth" in text
    assert "cc_revoked_native_auth" in text
    assert hashlib.sha256(b"cc_alice_native_auth").hexdigest() in text


def test_form_auth_band_executes():
    result = subprocess.run(
        [
            "./validate.sh",
            "form-stdlib/core.fk",
            "form-stdlib/kernel-http.fk",
            "form-stdlib/sha256.fk",
            "form-stdlib/hex.fk",
            "form-stdlib/auth-port.fk",
            "form-stdlib/tests/auth-port-band.fk",
        ],
        cwd=ROOT / "form",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "→ 1111" in result.stdout


def test_idea_and_spec_forms_name_auth_carrier_before_front_door_flip():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "form/form-stdlib/auth-port.fk::auth-require-api-key" in text
        assert "auth-port-band.fk" in text
        assert "public mutable" in text
        assert "graph_nodes Postgres writes" in text
