"""Behavioral observation of the deployed kernel and form-cli carriers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess
import threading
import time
from typing import Any


SCHEMA = "native-runtime-observation-v1"
KERNEL_EXPRESSION = "(add 20 22)"
KERNEL_EXPECTED = 42
FORM_CLI_SCHEMA = "form-cli-carrier-v2"
FORM_CLI_BUILD_ID = "coherence-kernel-fkwu-native-v2"
FORM_CLI_CHALLENGE_DOMAIN = b"form-cli-carrier-challenge-v1\n"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_CACHE_SECONDS = 15.0
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None
_CACHE_AT = 0.0
_CACHE_FINGERPRINT = ""


class NativeRuntimeObservationError(RuntimeError):
    """A native carrier failed identity or behavioral verification."""


def _root() -> Path:
    api_root = Path(__file__).resolve().parents[2]
    if (api_root / "form" / "form-cli").is_file():
        return api_root
    return api_root.parent


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _expected_form_cli_digest(root: Path) -> tuple[str, str]:
    manifest = root / "form" / "form-cli.sha256"
    if manifest.is_file():
        expected = manifest.read_text(encoding="ascii").strip()
        if not _HEX64.fullmatch(expected):
            raise NativeRuntimeObservationError("form-cli digest manifest malformed")
        return expected, str(manifest)
    system = platform.system().lower()
    machine = platform.machine().lower()
    machine = {"aarch64": "arm64", "amd64": "x86_64"}.get(machine, machine)
    committed = (
        root
        / "form"
        / "form-stdlib"
        / "bootstrap"
        / f"form-cli-{system}-{machine}"
    )
    if not committed.is_file():
        raise NativeRuntimeObservationError(
            "no committed or image-built form-cli digest authority"
        )
    return _sha256_file(committed), str(committed)


def _run_cli_line(binary: Path, command: str, *, cwd: Path) -> str:
    process = subprocess.run(
        [str(binary)],
        cwd=cwd,
        input=(command + "\n").encode("ascii"),
        capture_output=True,
        timeout=10,
        check=False,
    )
    if process.returncode != 0 or process.stderr:
        raise NativeRuntimeObservationError(
            f"form-cli challenge failed with exit {process.returncode}"
        )
    try:
        output = process.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise NativeRuntimeObservationError(
            "form-cli challenge emitted invalid UTF-8"
        ) from exc
    lines = output.splitlines()
    if len(lines) != 1 or output != lines[0] + "\n":
        raise NativeRuntimeObservationError("form-cli challenge framing invalid")
    return lines[0]


def _observe_form_cli(
    root: Path, *, challenge_input: str | None = None
) -> dict[str, Any]:
    binary = root / "form" / "form-cli"
    table = root / "form" / "form-stdlib" / "bootstrap" / "form-cli-table.txt"
    stamp_file = root / "form" / "form-stdlib" / "bootstrap" / "form-cli.stamp"
    source_digest_file = (
        root
        / "form"
        / "form-stdlib"
        / "bootstrap"
        / "form-cli.source.sha256"
    )
    wrapper = root / "bin" / "form-cli"
    wrapper_manifest = root / "bin" / "form-cli.sha256"
    for path in (
        binary,
        table,
        stamp_file,
        source_digest_file,
        wrapper,
        wrapper_manifest,
    ):
        if not path.is_file():
            raise NativeRuntimeObservationError(f"form-cli artifact missing: {path}")
    if not os.access(binary, os.X_OK):
        raise NativeRuntimeObservationError("form-cli is not executable")
    binary_sha = _sha256_file(binary)
    expected_sha, digest_authority = _expected_form_cli_digest(root)
    if binary_sha != expected_sha:
        raise NativeRuntimeObservationError("form-cli executable digest mismatch")
    wrapper_sha = _sha256_file(wrapper)
    expected_wrapper_sha = wrapper_manifest.read_text(encoding="ascii").strip()
    if not _HEX64.fullmatch(expected_wrapper_sha):
        raise NativeRuntimeObservationError("form-cli wrapper digest manifest malformed")
    if wrapper_sha != expected_wrapper_sha:
        raise NativeRuntimeObservationError("form-cli wrapper digest mismatch")
    freshness_stamp = stamp_file.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{16}", freshness_stamp):
        raise NativeRuntimeObservationError("form-cli freshness stamp malformed")
    source_stamp = source_digest_file.read_text(encoding="ascii").strip()
    if not _HEX64.fullmatch(source_stamp):
        raise NativeRuntimeObservationError("form-cli source digest malformed")
    identity = _run_cli_line(binary, "carrier-id", cwd=root)
    identity_fields = identity.split("|")
    if identity_fields != [
        "carrier-id",
        FORM_CLI_SCHEMA,
        source_stamp,
        FORM_CLI_BUILD_ID,
    ]:
        raise NativeRuntimeObservationError("form-cli carrier identity mismatch")
    nonce = challenge_input or secrets.token_hex(32)
    if not _HEX64.fullmatch(nonce):
        raise NativeRuntimeObservationError("form-cli challenge input malformed")
    expected_response = hashlib.sha256(
        FORM_CLI_CHALLENGE_DOMAIN + nonce.encode("ascii")
    ).hexdigest()
    challenge = _run_cli_line(
        binary,
        f"carrier-challenge {nonce}",
        cwd=root,
    )
    challenge_fields = challenge.split("|")
    if challenge_fields != [
        "carrier-challenge-v1",
        source_stamp,
        nonce,
        expected_response,
    ]:
        raise NativeRuntimeObservationError("form-cli nonce challenge mismatch")
    return {
        "verified": True,
        "schema": FORM_CLI_SCHEMA,
        "build_id": FORM_CLI_BUILD_ID,
        "source_stamp": source_stamp,
        "freshness_stamp": freshness_stamp,
        "source_digest_authority": str(source_digest_file),
        "binary_sha256": binary_sha,
        "digest_authority": digest_authority,
        "table_sha256": _sha256_file(table),
        "stamp_sha256": _sha256_file(stamp_file),
        "wrapper_sha256": wrapper_sha,
        "wrapper_digest_authority": str(wrapper_manifest),
        "challenge_nonce": nonce,
        "challenge_response_sha256": expected_response,
    }


def _observe_kernel(*, challenge_input: str | None = None) -> dict[str, Any]:
    from app.services import form_kernel_bridge
    if challenge_input is None:
        expression = KERNEL_EXPRESSION
        expected = KERNEL_EXPECTED
        value, runtime = form_kernel_bridge.run_kernel(
            expression,
            parse=int,
            timeout=10,
        )
    else:
        from app.services.deployment_observer_service import (
            fkwu_challenge_expected,
            fkwu_challenge_expression,
        )

        expression = fkwu_challenge_expression(challenge_input)
        expected = int(fkwu_challenge_expected(challenge_input))
        value, runtime = form_kernel_bridge.run_kernel(
            expression,
            parse=int,
            timeout=10,
        )
    if value != expected or runtime != "fkwu":
        raise NativeRuntimeObservationError("kernel known-answer challenge failed")
    binary = form_kernel_bridge.kernel_bin_path()
    binary_sha = _sha256_file(binary) if binary.is_file() else None
    if binary_sha is None:
        raise NativeRuntimeObservationError("kernel carrier digest unavailable")
    return {
        "verified": True,
        "runtime": runtime,
        "expression": expression,
        "expected": expected,
        "result": value,
        "binary_sha256": binary_sha,
        "execution_authority": "c-bootstrap-fkwu",
        "sibling_kernel_role": "differential-reference-only",
    }


def _artifact_fingerprint(root: Path) -> str:
    paths = [
        root / "form" / "form-cli",
        root / "form" / "form-cli.sha256",
        root / "form" / "form-stdlib" / "bootstrap" / "form-cli.stamp",
        root
        / "form"
        / "form-stdlib"
        / "bootstrap"
        / "form-cli.source.sha256",
        root / "form" / "form-stdlib" / "bootstrap" / "form-cli-table.txt",
        root / "bin" / "form-cli",
        root / "bin" / "form-cli.sha256",
    ]
    try:
        from app.services.form_kernel_bridge import kernel_bin_path

        paths.append(kernel_bin_path())
    except Exception:
        pass
    digest = hashlib.sha256(b"native-runtime-artifacts-v1\n")
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(_sha256_file(path).encode("ascii"))
        else:
            digest.update(b"missing")
        digest.update(b"\0")
    return digest.hexdigest()


def _observe_uncached(root: Path) -> dict[str, Any]:
    kernel = _observe_kernel()
    form_cli = _observe_form_cli(root)
    stable = {
        "schema": SCHEMA,
        "kernel": kernel,
        "form_cli": {
            key: value
            for key, value in form_cli.items()
            if key not in {"challenge_nonce", "challenge_response_sha256"}
        },
    }
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return {
        **stable,
        "root": str(root.resolve()),
        "form_cli": form_cli,
        "verified": True,
        "observed_at": _iso_now(),
        "challenge_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def observe_native_runtime(*, force: bool = False) -> dict[str, Any]:
    """Run or return a short-lived, digest-invalidated native challenge."""
    global _CACHE, _CACHE_AT, _CACHE_FINGERPRINT
    root = _root()
    fingerprint = _artifact_fingerprint(root)
    now = time.monotonic()
    with _CACHE_LOCK:
        if (
            not force
            and _CACHE is not None
            and fingerprint == _CACHE_FINGERPRINT
            and now - _CACHE_AT <= _CACHE_SECONDS
        ):
            return json.loads(json.dumps(_CACHE))
        try:
            result = _observe_uncached(root)
        except Exception as exc:
            result = {
                "schema": SCHEMA,
                "verified": False,
                "observed_at": _iso_now(),
                "challenge_digest": None,
                "kernel": {"verified": False},
                "form_cli": {"verified": False},
                "error": f"{type(exc).__name__}:{exc}",
            }
        _CACHE = result
        _CACHE_AT = now
        _CACHE_FINGERPRINT = fingerprint
        return json.loads(json.dumps(result))


def observe_native_runtime_challenge(challenge_input: str) -> dict[str, Any]:
    """Execute both carriers against an external observer's exact challenge."""
    if not _HEX64.fullmatch(challenge_input):
        raise NativeRuntimeObservationError("observer challenge input malformed")
    root = _root()
    kernel = _observe_kernel(challenge_input=challenge_input)
    form_cli = _observe_form_cli(root, challenge_input=challenge_input)
    return {
        "schema": "native-carrier-observation-v1",
        "verified": True,
        "kernel": kernel,
        "form_cli": form_cli,
    }


def reset_native_runtime_observation_cache() -> None:
    """Test/deploy hook: discard the cached challenge immediately."""
    global _CACHE, _CACHE_AT, _CACHE_FINGERPRINT
    with _CACHE_LOCK:
        _CACHE = None
        _CACHE_AT = 0.0
        _CACHE_FINGERPRINT = ""
