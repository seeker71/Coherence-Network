"""Persistent public dialogue cells attended by one native CPU worker.

Form owns the envelope.  This carrier keeps public text in a dedicated table,
serializes native work across API processes with a database advisory lock, and
publishes only grounded output from explicit public source paths.  Dialogue
content is unlisted, expires, and can be released with a capability token.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import re
import secrets
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator

from fastapi import HTTPException
from sqlalchemy import text

from app.services import form_kernel_bridge
from app.services import public_dialogue_store as store
from app.services import unified_db


WORKER_NAME = "vpc-form-dialogue-cpu"
MAX_ACTIVE_DIALOGUES = 8
MAX_CHANNEL_TIMEOUT_SECONDS = 120
MAX_DIALOGUE_ATTEMPTS = 3
DEFAULT_RETENTION_DAYS = 7
START_WINDOW_SECONDS = 60
STARTS_PER_WINDOW = 6
WORKER_ADVISORY_LOCK_KEY = 0x434F484449414C57  # "COHDIALW"
SOURCE_LOCALE = "en"
PUBLIC_SOURCE_PREFIXES = (
    "docs/",
    "form/",
    "ideas/",
    "references/",
    "seedbank/",
    "specs/",
)
PUBLIC_SOURCE_FILES = {"README.md", "WELCOME.md", "HOMECOMING.md"}
_DIALOGUE_ENVELOPE_RECIPE = (
    Path(__file__).resolve().parent.parent
    / "form_recipes"
    / "public_dialogue_envelope.fk"
)
_DIALOGUE_BAND_ENTRY = "(dialogue-band))"
_SHA256_RECIPE_CANDIDATES = (
    Path(__file__).resolve().parents[3]
    / "form"
    / "form"
    / "form-stdlib"
    / "sha256.fk",
    Path("/app/form/form-stdlib/sha256.fk"),
)
_FORM_DIGEST_PREFIX = b"form-cli-carrier-challenge-v1\n"

_BCP47_RE = re.compile(
    r"^(?:"
    r"(?:[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})"
    r"(?:-[A-Za-z]{4})?"
    r"(?:-(?:[A-Za-z]{2}|[0-9]{3}))?"
    r"(?:-(?:[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*"
    r"(?:-[0-9A-WY-Za-wy-z](?:-[A-Za-z0-9]{2,8})+)*"
    r"(?:-x(?:-[A-Za-z0-9]{1,8})+)?"
    r"|x(?:-[A-Za-z0-9]{1,8})+"
    r")$"
)
_GRANDFATHERED_LOCALES = {
    "art-lojban": "art-lojban",
    "cel-gaulish": "cel-gaulish",
    "en-gb-oed": "en-GB-oed",
    "i-ami": "i-ami",
    "i-bnn": "i-bnn",
    "i-default": "i-default",
    "i-enochian": "i-enochian",
    "i-hak": "i-hak",
    "i-klingon": "i-klingon",
    "i-lux": "i-lux",
    "i-mingo": "i-mingo",
    "i-navajo": "i-navajo",
    "i-pwn": "i-pwn",
    "i-tao": "i-tao",
    "i-tay": "i-tay",
    "i-tsu": "i-tsu",
    "no-bok": "no-bok",
    "no-nyn": "no-nyn",
    "sgn-be-fr": "sgn-BE-FR",
    "sgn-be-nl": "sgn-BE-NL",
    "sgn-ch-de": "sgn-CH-DE",
    "zh-guoyu": "zh-guoyu",
    "zh-hakka": "zh-hakka",
    "zh-min": "zh-min",
    "zh-min-nan": "zh-min-nan",
    "zh-xiang": "zh-xiang",
}

_RUN_ID = f"{WORKER_NAME}:{uuid.uuid4().hex}"
_WORKER_LOCK = threading.Lock()
_LOCAL_LEASE_LOCK = threading.Lock()
_WORKER_WAKE = threading.Event()
_WORKER_STOP = threading.Event()
_WORKER_THREAD: threading.Thread | None = None
_GROUNDED_ASK_RUNNER: Callable[..., Any] | None = None
log = logging.getLogger(__name__)


class DialogueRateLimitError(RuntimeError):
    def __init__(self, retry_after: int = START_WINDOW_SECONDS):
        super().__init__("this network peer has filled its present dialogue interval")
        self.retry_after = retry_after


def set_grounded_ask_runner(runner: Callable[..., Any]) -> None:
    """Join the native carrier to this organ at the application boundary."""
    global _GROUNDED_ASK_RUNNER
    _GROUNDED_ASK_RUNNER = runner


def _admit_dialogue_envelope(
    *,
    locale: str,
    point: str,
    question: str,
    disclosure: str,
    parent: str,
    timeout_seconds: int,
) -> bool:
    """Offer content-bound encodings of all six fields to Form."""
    values = tuple(
        value.encode("utf-8").hex()
        for value in (locale, point, question, disclosure, parent)
    ) + (str(timeout_seconds),)
    source = _native_dialogue_recipe_source()
    if source.count(_DIALOGUE_BAND_ENTRY) != 1:
        raise RuntimeError("native Form dialogue admission entry is unavailable")
    invocation = (
        "(dialogue-envelope-receipt "
        + " ".join(f'"{value}"' for value in values[:-1])
        + f" {timeout_seconds}))"
    )
    receipt = form_kernel_bridge.run_recipe(
        source.replace(_DIALOGUE_BAND_ENTRY, invocation),
        timeout=10,
    )
    pieces = receipt.split("|")
    if pieces == ["0", ""]:
        return False
    if len(pieces) != 2 or pieces[0] != "1" or not re.fullmatch(
        r"[0-9a-f]{64}", pieces[1]
    ):
        raise RuntimeError("native Form dialogue admission returned an invalid verdict")
    canonical = "public-dialogue-envelope-v2|" + "".join(
        f"{len(value)}:{value}" for value in values
    )
    expected = hashlib.sha256(
        _FORM_DIGEST_PREFIX + canonical.encode("ascii")
    ).hexdigest()
    if not secrets.compare_digest(pieces[1], expected):
        raise RuntimeError("native Form dialogue receipt did not bind the offered envelope")
    return True


def _native_dialogue_recipe_source() -> str:
    for candidate in _SHA256_RECIPE_CANDIDATES:
        if candidate.is_file():
            sha256_source = candidate.read_text(encoding="utf-8")
            break
    else:
        raise RuntimeError("native Form SHA-256 recipe is unavailable")
    source = sha256_source + "\n" + _DIALOGUE_ENVELOPE_RECIPE.read_text(
        encoding="utf-8"
    )
    return "\n".join(
        line
        for line in source.splitlines()
        if not line.lstrip().startswith("; preludes:")
    )


def _contains_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def canonicalize_locale(value: str) -> str:
    tag = value.strip()
    grandfathered = _GRANDFATHERED_LOCALES.get(tag.lower())
    if grandfathered is not None:
        return grandfathered
    if not _BCP47_RE.fullmatch(tag):
        raise ValueError("locale must be a well-formed BCP-47 language tag")
    parts = tag.split("-")
    if parts[0].lower() == "x":
        return "-".join(part.lower() for part in parts)
    out = [parts[0].lower()]
    in_extension = False
    for part in parts[1:]:
        if len(part) == 1:
            in_extension = True
            out.append(part.lower())
        elif not in_extension and len(part) == 4 and part.isalpha():
            out.append(part.title())
        elif not in_extension and (
            (len(part) == 2 and part.isalpha())
            or (len(part) == 3 and part.isdigit())
        ):
            out.append(part.upper())
        else:
            out.append(part.lower())
    return "-".join(out)


def _public_source_path(value: Any) -> str | None:
    source = str(value or "").replace("\\", "/").strip()
    if not source:
        return None
    path = PurePosixPath(source)
    if path.is_absolute() or ".." in path.parts or source.startswith("."):
        return None
    normalized = str(path)
    if normalized in PUBLIC_SOURCE_FILES or normalized.startswith(PUBLIC_SOURCE_PREFIXES):
        return normalized
    return None


def _dialogue_view(row: dict[str, Any], *, removal_token: str | None = None) -> dict[str, Any]:
    result = row.get("output") if isinstance(row.get("output"), dict) else {}
    view = {
        "id": row["id"],
        "state": row["state"],
        "question": row["question"],
        "question_sha256": row["question_sha256"],
        "point_of_view": row["point_of_view"],
        "requested_locale": row["requested_locale"],
        "canonical_locale": row["canonical_locale"],
        "input_language_status": "passed-to-native-unmeasured",
        "public_disclosure_ack": row["disclosure_ack"],
        "visibility": row["visibility"],
        "content_trust": "untrusted-public-input-and-grounded-public-output",
        "parent_dialogue_id": row.get("parent_dialogue_id"),
        "channel_timeout_seconds": row["channel_timeout_seconds"],
        "attempt": row.get("attempt", 0),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "expires_at": row.get("expires_at"),
        "result": result or None,
        "poll_url": f"/api/dialogues/{row['id']}",
        "release_url": f"/api/dialogues/{row['id']}",
    }
    if removal_token is not None:
        view["removal_token"] = removal_token
        view["removal_token_note"] = (
            "Shown once. Keep it to release the public text before automatic expiry."
        )
    return view


def submit_dialogue(
    *,
    question: str,
    point_of_view: str,
    locale: str,
    public_disclosure_ack: str,
    network_peer: str,
    parent_dialogue_id: str | None = None,
    channel_timeout_seconds: int = 90,
) -> dict[str, Any]:
    """Persist one unlisted public turn and wake the attending CPU worker."""
    if public_disclosure_ack != store.PUBLIC_DISCLOSURE_ACK:
        raise ValueError(
            f"public_disclosure_ack must equal {store.PUBLIC_DISCLOSURE_ACK!r}"
        )
    question = question.strip()
    point_of_view = point_of_view.strip()
    requested_locale = locale.strip()
    if not question or not point_of_view or not requested_locale:
        raise ValueError("question, point_of_view, and locale must contain text")
    if _contains_control(question) or _contains_control(point_of_view):
        raise ValueError("question and point_of_view may not contain control characters")
    if len(question) > 1200 or len(point_of_view) > 240:
        raise ValueError("question or point_of_view exceeds the public dialogue envelope")
    if len(point_of_view) + 1 + len(question) > 1500:
        raise ValueError("combined point_of_view and question exceed the native query envelope")
    canonical_locale = canonicalize_locale(requested_locale)
    if not 10 <= channel_timeout_seconds <= MAX_CHANNEL_TIMEOUT_SECONDS:
        raise ValueError(
            f"channel_timeout_seconds must be between 10 and {MAX_CHANNEL_TIMEOUT_SECONDS}"
        )
    if parent_dialogue_id is not None and len(parent_dialogue_id) > 80:
        raise ValueError("parent_dialogue_id exceeds the public dialogue envelope")
    network_peer_sha256 = hashlib.sha256(
        (network_peer or "unknown")[:200].encode("utf-8")
    ).hexdigest()
    question_sha256 = hashlib.sha256(question.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=DEFAULT_RETENTION_DAYS)
    try:
        with store.serialized_dialogue_admission(
            network_peer_sha256=network_peer_sha256,
            parent_dialogue_id=parent_dialogue_id,
            max_active=MAX_ACTIVE_DIALOGUES,
            starts_per_window=STARTS_PER_WINDOW,
            start_window_seconds=START_WINDOW_SECONDS,
        ) as admission_session:
            if not _admit_dialogue_envelope(
                locale=requested_locale,
                point=point_of_view,
                question=question,
                disclosure=public_disclosure_ack,
                parent=parent_dialogue_id or "",
                timeout_seconds=channel_timeout_seconds,
            ):
                raise RuntimeError("native Form declined the public dialogue envelope")
            row, removal_token = store.create_dialogue(
                question=question,
                question_sha256=question_sha256,
                point_of_view=point_of_view,
                requested_locale=requested_locale,
                canonical_locale=canonical_locale,
                parent_dialogue_id=parent_dialogue_id,
                channel_timeout_seconds=channel_timeout_seconds,
                network_peer_sha256=network_peer_sha256,
                expires_at=expires_at,
                max_active=MAX_ACTIVE_DIALOGUES,
                starts_per_window=STARTS_PER_WINDOW,
                start_window_seconds=START_WINDOW_SECONDS,
                admission_session=admission_session,
            )
    except store.PublicDialogueRateLimitError as exc:
        raise DialogueRateLimitError(exc.retry_after) from exc
    ensure_dialogue_worker()
    _WORKER_WAKE.set()
    return _dialogue_view(row, removal_token=removal_token)


def get_dialogue(dialogue_id: str) -> dict[str, Any] | None:
    ensure_dialogue_worker()
    row = store.get_dialogue(dialogue_id)
    if row is None:
        return None
    _WORKER_WAKE.set()
    return _dialogue_view(row)


def release_dialogue(dialogue_id: str, removal_token: str) -> bool:
    token_hash = hashlib.sha256(removal_token.encode("utf-8")).hexdigest()
    released = store.tombstone_dialogue(dialogue_id, token_hash)
    if released is False:
        return False
    if isinstance(released, int) and not isinstance(released, bool):
        _reap_recorded_process_group(released)
    return True


@contextlib.contextmanager
def _organism_worker_lease() -> Iterator[bool]:
    """Hold one worker lease across all API processes and deploy replicas."""
    engine = unified_db.engine()
    if engine.dialect.name == "postgresql":
        connection = engine.connect()
        acquired = False
        try:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": WORKER_ADVISORY_LOCK_KEY},
                ).scalar()
            )
            connection.commit()
            yield acquired
        finally:
            if acquired:
                try:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_key)"),
                        {"lock_key": WORKER_ADVISORY_LOCK_KEY},
                    )
                    connection.commit()
                finally:
                    connection.close()
            else:
                connection.close()
        return
    acquired = _LOCAL_LEASE_LOCK.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            _LOCAL_LEASE_LOCK.release()


def _reap_recorded_process_group(pgid: Any) -> None:
    if not isinstance(pgid, int) or pgid <= 1:
        return
    if not _recorded_process_group_is_native(pgid):
        return
    if _windows_host():
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pgid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        return
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _windows_host() -> bool:
    return os.name == "nt"


def _recorded_process_group_is_native(pgid: int) -> bool:
    """Refuse delayed signals when a recycled process group is not our carrier."""
    if _windows_host():
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$p = Get-CimInstance Win32_Process -Filter \"ProcessId = "
                f"{pgid}\"; if ($null -ne $p) {{ [Console]::Out.Write($p.CommandLine) }}"
            ),
        ]
    else:
        command = ["ps", "-axo", "pgid=,command="]
    try:
        observed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if _windows_host():
        rows = [observed.stdout.lower()] if observed.stdout else []
    else:
        rows = []
        for line in observed.stdout.splitlines():
            pieces = line.strip().split(maxsplit=1)
            if len(pieces) == 2 and pieces[0].isdigit() and int(pieces[0]) == pgid:
                rows.append(pieces[1].lower())
    markers = ("form-cli", "fkwu", "form_cli_rag.py")
    return bool(rows) and any(any(marker in row for marker in markers) for row in rows)


def _controlled_failure(exc: Exception, *, locale: str) -> dict[str, Any]:
    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    if status_code == 504:
        reason = "channel-timeout"
    elif status_code == 413:
        reason = "native-envelope-rejected"
    elif status_code == 503:
        reason = "native-carrier-unavailable"
    else:
        reason = "worker-failed"
    return {
        "outcome": "failed",
        "reason": reason,
        "status_code": status_code,
        "requested_locale": locale,
        "source_locale": SOURCE_LOCALE,
    }


def _public_result(native: dict[str, Any], *, locale: str) -> tuple[str, dict[str, Any]]:
    native.pop("query", None)
    answer = str(native.get("answer") or "")
    trust_fields = native.get("trust_fields")
    trust_fields = trust_fields if isinstance(trust_fields, dict) else {}
    path = str(trust_fields.get("path") or "")

    if path == "rented":
        if answer:
            raise ValueError("rented dialogue result attempted to publish an answer")
        return "miss", {
            "outcome": "miss",
            "miss_reason": "no-grounded-cell",
            "trust": native.get("trust"),
            "trust_fields": trust_fields,
            "answer": "",
            "requested_locale": locale,
            "source_locale": SOURCE_LOCALE,
            "projection_status": "not-attempted-no-source-answer",
            "lane": "public-dialogue",
        }

    if path != "native":
        raise ValueError("dialogue result did not carry native trust")

    source_path = _public_source_path(native.get("source_path"))
    grounded_node = str(native.get("grounded_node_id") or "")
    if not answer or not source_path or not grounded_node:
        return "miss", {
            "outcome": "miss",
            "miss_reason": "public-ground-not-available",
            "trust": native.get("trust"),
            "trust_fields": trust_fields,
            "answer": "",
            "requested_locale": locale,
            "source_locale": SOURCE_LOCALE,
            "projection_status": "not-attempted-no-public-source-answer",
            "lane": "public-dialogue",
        }

    source_digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    native["source_path"] = source_path
    native["source_answer"] = answer
    native["source_answer_sha256"] = source_digest
    native["answer"] = answer
    native["projected_answer_sha256"] = source_digest
    native["requested_locale"] = locale
    native["source_locale"] = SOURCE_LOCALE
    native["projection_status"] = (
        "source" if locale.lower() == SOURCE_LOCALE else "source-fallback"
    )
    native["projection_reason"] = (
        "requested-source-locale"
        if locale.lower() == SOURCE_LOCALE
        else "no-grounded-form-native-locale-projection"
    )
    native["projection_identity"] = "form-native-ground-only-v1"
    native["outcome"] = "answered"
    native["lane"] = "public-dialogue"
    return "answered", native


def process_dialogue_once() -> bool:
    """Attend at most one dialogue while holding the global CPU lease."""
    with _organism_worker_lease() as acquired:
        if not acquired:
            return False
        row = store.claim_next_dialogue(_RUN_ID)
        if row is None:
            return False
        dialogue_id = row["id"]
        _reap_recorded_process_group(row.get("carrier_pgid"))
        if int(row.get("attempt") or 0) > MAX_DIALOGUE_ATTEMPTS:
            store.finish_dialogue(
                dialogue_id,
                _RUN_ID,
                state="failed",
                output={
                    "outcome": "failed",
                    "reason": "attempts-exhausted",
                    "requested_locale": row["canonical_locale"],
                    "source_locale": SOURCE_LOCALE,
                },
            )
            return True
        try:
            prompt = f"{row['point_of_view']}\n{row['question']}"

            def record_started_carrier(pid: int) -> None:
                if not store.record_carrier_pgid(dialogue_id, _RUN_ID, pid):
                    raise RuntimeError("dialogue was released before carrier start")

            runner = _GROUNDED_ASK_RUNNER
            if runner is None:
                raise RuntimeError("native grounded ask runner is not joined")
            receipt = runner(
                prompt,
                timeout_seconds=int(row["channel_timeout_seconds"]),
                allow_escalation_miss=True,
                on_process_start=record_started_carrier,
            )
            state, result = _public_result(
                receipt.model_dump(mode="json"),
                locale=str(row["canonical_locale"]),
            )
            store.finish_dialogue(dialogue_id, _RUN_ID, state=state, output=result)
        except Exception as exc:
            failure = _controlled_failure(exc, locale=str(row["canonical_locale"]))
            store.finish_dialogue(
                dialogue_id,
                _RUN_ID,
                state="failed",
                output=failure,
            )
        return True


def _worker_loop() -> None:
    while not _WORKER_STOP.is_set():
        try:
            store.tombstone_expired()
            moved = process_dialogue_once()
        except Exception as exc:
            log.warning("public dialogue worker recovered from %s", type(exc).__name__)
            moved = False
        if moved:
            continue
        if _WORKER_STOP.is_set():
            break
        _WORKER_WAKE.wait(timeout=5.0)
        _WORKER_WAKE.clear()


def ensure_dialogue_worker() -> None:
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return
        _WORKER_STOP.clear()
        _WORKER_THREAD = threading.Thread(
            target=_worker_loop,
            name=WORKER_NAME,
            daemon=True,
        )
        _WORKER_THREAD.start()


def stop_dialogue_worker() -> None:
    global _WORKER_THREAD
    with _WORKER_LOCK:
        _WORKER_STOP.set()
        _WORKER_WAKE.set()
        thread = _WORKER_THREAD
        if thread is None:
            return
        if thread is threading.current_thread():
            return
        thread.join()
        if _WORKER_THREAD is thread:
            _WORKER_THREAD = None
