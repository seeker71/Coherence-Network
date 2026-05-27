"""Deploy log surface — public visibility into auto-deploy progress on the VPS."""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

DEFAULT_LOG_PATH = "/docker/coherence-network/deploy.log"
DEFAULT_ENV_PATH = "/docker/coherence-network/.env"
MAX_TAIL_LINES = 2000
DEFAULT_TAIL_LINES = 200
IN_PROGRESS_WINDOW_SECONDS = 30
STREAM_POLL_SECONDS = 0.5
STREAM_KEEPALIVE_SECONDS = 15.0

# Patterns that look like secrets — strip the value portion if a deploy log
# ever accidentally echoed one. The deploy script shouldn't, but defense in
# depth costs nothing.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(ssh-(?:rsa|ed25519|dss)\s+)[A-Za-z0-9+/=]{20,}"),
    re.compile(r"(?i)(-----BEGIN [A-Z ]+PRIVATE KEY-----).*?(-----END [A-Z ]+PRIVATE KEY-----)", re.DOTALL),
    re.compile(r"(?i)\b(ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)\b(sk-[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)(authorization:\s*\S+\s+)[A-Za-z0-9._\-]{10,}"),
]


def _log_path() -> Path:
    return Path(os.environ.get("COH_DEPLOY_LOG_PATH", DEFAULT_LOG_PATH))


def _env_path() -> Path:
    return Path(os.environ.get("COH_DEPLOY_ENV_PATH", DEFAULT_ENV_PATH))


def _sanitize(line: str) -> str:
    """Best-effort redact tokens/keys that should never have landed in the log."""
    out = line
    for pat in _SECRET_PATTERNS:
        if pat.groups >= 2:
            out = pat.sub(lambda m: m.group(1) + "[redacted]" + (m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(m.lastindex) and m.group(m.lastindex) != m.group(1) else ""), out)
        else:
            out = pat.sub("[redacted]", out)
    return out


def _read_last_lines(path: Path, n: int) -> tuple[list[str], int]:
    """Return (last_n_lines, total_lines) by seeking from end — no full-file load.

    Reads chunks backwards until we have n+1 newlines or hit start of file.
    Total line count is computed by a single forward scan for files small enough
    to count cheaply; for very large files we return -1 to indicate "unknown".
    """
    if not path.exists():
        return [], 0
    size = path.stat().st_size
    if size == 0:
        return [], 0
    chunk = 8192
    data = b""
    with path.open("rb") as f:
        pos = size
        lines_found = 0
        while pos > 0 and lines_found <= n:
            read_size = min(chunk, pos)
            pos -= read_size
            f.seek(pos)
            data = f.read(read_size) + data
            lines_found = data.count(b"\n")
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        tail = lines[-n:] if len(lines) > n else lines

    # Total line count: cheap forward scan, but cap effort on huge files.
    total = 0
    if size <= 50 * 1024 * 1024:  # 50MB cap on counting
        with path.open("rb") as f:
            for _ in f:
                total += 1
    else:
        total = -1

    return [_sanitize(line) for line in tail], total


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        return {}
    return out


def _api_config_deployed_sha() -> str | None:
    """Pull deployed_sha from api/config/api.json if present."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "api" / "config" / "api.json",  # repo root layout
        here.parents[2] / "config" / "api.json",          # /app layout
        Path("/app/config/api.json"),
    ]
    for cfg in candidates:
        if not cfg.exists():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sha = data.get("deployed_sha")
        if sha:
            return str(sha)
        # nested location seen in api.json
        for key in ("deploy", "runtime", "api"):
            sub = data.get(key)
            if isinstance(sub, dict) and sub.get("deployed_sha"):
                return str(sub["deployed_sha"])
        return None
    return None


@router.get("/deploy/log/tail", summary="Tail of the auto-deploy log")
async def deploy_log_tail(
    lines: int = Query(DEFAULT_TAIL_LINES, ge=1, le=MAX_TAIL_LINES),
) -> dict[str, Any]:
    """Return the last N lines of the deploy log as JSON.

    Public, no-auth. If the file doesn't exist (e.g. running locally), returns
    `exists: false` with empty lines — never 404, so the consuming page renders.
    """
    path = _log_path()
    if not path.exists():
        return {"lines": [], "total": 0, "exists": False, "path": str(path)}
    tail, total = _read_last_lines(path, lines)
    return {
        "lines": tail,
        "total": total,
        "exists": True,
        "path": str(path),
    }


async def _tail_stream(request: Request) -> AsyncIterator[bytes]:
    """SSE generator: emit each new line as `data: <line>\n\n`.

    Polls the file every STREAM_POLL_SECONDS. Handles truncation/rotation by
    re-opening from start if the file shrinks. Closes cleanly on disconnect.
    """
    path = _log_path()
    loop = asyncio.get_event_loop()
    last_keepalive = loop.time()
    pos = 0
    inode: int | None = None
    buffer = b""

    # Emit existing tail first so the consumer immediately sees recent state.
    if path.exists():
        try:
            initial, _ = _read_last_lines(path, DEFAULT_TAIL_LINES)
            for line in initial:
                payload = json.dumps({"line": line, "at": datetime.now(timezone.utc).isoformat()}, separators=(",", ":"))
                yield f"data: {payload}\n\n".encode("utf-8")
            stat = path.stat()
            pos = stat.st_size
            inode = stat.st_ino
        except OSError:
            pass

    while True:
        if await request.is_disconnected():
            return

        now = loop.time()
        try:
            if path.exists():
                stat = path.stat()
                # Rotation / truncation: file shrank or inode changed.
                if inode is not None and (stat.st_ino != inode or stat.st_size < pos):
                    pos = 0
                    inode = stat.st_ino
                    buffer = b""
                elif inode is None:
                    inode = stat.st_ino

                if stat.st_size > pos:
                    with path.open("rb") as f:
                        f.seek(pos)
                        chunk = f.read(stat.st_size - pos)
                        pos = stat.st_size
                    buffer += chunk
                    while b"\n" in buffer:
                        raw, _, buffer = buffer.partition(b"\n")
                        line = _sanitize(raw.decode("utf-8", errors="replace"))
                        payload = json.dumps(
                            {"line": line, "at": datetime.now(timezone.utc).isoformat()},
                            separators=(",", ":"),
                        )
                        yield f"data: {payload}\n\n".encode("utf-8")
                    last_keepalive = now
        except OSError:
            # Don't kill the stream on transient FS errors.
            pass

        if now - last_keepalive >= STREAM_KEEPALIVE_SECONDS:
            yield b": keepalive\n\n"
            last_keepalive = now

        await asyncio.sleep(STREAM_POLL_SECONDS)


@router.get("/deploy/log/stream", summary="Live deploy log via Server-Sent Events")
async def deploy_log_stream(request: Request) -> StreamingResponse:
    """Stream the deploy log line-by-line over SSE.

    Public, no-auth. Each event is a JSON `{line, at}` payload. Closes cleanly
    on client disconnect. Survives log rotation/truncation by re-anchoring.
    """
    return StreamingResponse(
        _tail_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/deploy/status", summary="Deploy status — current/deployed SHA + in-progress flag")
async def deploy_status() -> dict[str, Any]:
    """Return the deploy state the web page needs to render its banner.

    - `current_sha`: what the VPS is currently building / last targeted (from .env DEPLOYED_SHA).
    - `deployed_sha`: what the running API records as live (from api/config/api.json).
    - `in_progress`: True if deploy.log has activity within the last 30 seconds.
    - `started_at`: mtime of the deploy log when it last changed (ISO 8601 UTC).

    Public, no-auth.
    """
    env = _read_env_file(_env_path())
    current_sha = env.get("DEPLOYED_SHA") or env.get("GIT_SHA") or env.get("DEPLOY_SHA")
    deployed_sha = _api_config_deployed_sha()

    log = _log_path()
    in_progress = False
    started_at: str | None = None
    if log.exists():
        try:
            stat = log.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            started_at = mtime.isoformat()
            age = (datetime.now(timezone.utc) - mtime).total_seconds()
            in_progress = age <= IN_PROGRESS_WINDOW_SECONDS
        except OSError:
            pass

    return {
        "current_sha": current_sha,
        "deployed_sha": deployed_sha,
        "in_progress": in_progress,
        "started_at": started_at,
        "log_exists": log.exists(),
        "log_path": str(log),
    }
