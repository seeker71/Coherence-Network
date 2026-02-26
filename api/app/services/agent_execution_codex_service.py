"""Codex execution fallback helpers for agent task execution."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any

from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service


def _extract_underlying_model(task_model: str) -> str:
    cleaned = (task_model or "").strip()
    if cleaned.startswith("openclaw/") or cleaned.startswith("clawwork/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("cursor/"):
        return cleaned.split("/", 1)[1].strip()
    return cleaned


def _runtime_cost_per_second() -> float:
    raw = os.getenv("RUNTIME_COST_PER_SECOND", "0.002").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 0.002
    return value if value > 0.0 else 0.002


def _runtime_cost_usd(runtime_ms: int) -> float:
    return max(0.0, float(runtime_ms)) / 1000.0 * _runtime_cost_per_second()


def _record_codex_tool_event(
    *,
    task_id: str,
    model: str,
    is_paid_provider: bool,
    elapsed_ms: int,
    ok: bool,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    usage_json: str = "{}",
    error: str | None = None,
    actual_cost_usd: float | None = None,
) -> None:
    status_code = 200 if ok else 500
    metadata: dict[str, str | float | int | bool] = {
        "tracking_kind": "agent_tool_call",
        "task_id": task_id,
        "model": model,
        "provider": "openai-codex",
        "is_openai_codex": True,
        "is_paid_provider": bool(is_paid_provider),
    }
    if actual_cost_usd is not None:
        metadata["runtime_cost_usd"] = round(float(actual_cost_usd), 6)
    if ok:
        metadata.update(
            {
                "usage_prompt_tokens": int(prompt_tokens),
                "usage_completion_tokens": int(completion_tokens),
                "usage_total_tokens": int(total_tokens),
                "usage_json": str(usage_json)[:2000],
            }
        )
    else:
        metadata["error"] = (error or "unknown")[:800]

    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:codex.exec",
            method="RUN",
            status_code=status_code,
            runtime_ms=float(max(1, int(elapsed_ms))),
            idea_id="coherence-network-agent-pipeline",
            metadata=metadata,
        )
    )


def _extract_usage_from_codex_jsonl(output: str) -> dict[str, int]:
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if str(payload.get("type") or "").strip() != "turn.completed":
            continue
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def should_fallback_to_codex_exec(model: str, error: str) -> bool:
    underlying = _extract_underlying_model(model).strip().lower()
    if "codex" not in underlying:
        return False
    return "OPENROUTER_API_KEY is not configured" in error


def _failure_result(
    *,
    task_id: str,
    model: str,
    route_is_paid: bool,
    elapsed_ms: int,
    error: str,
) -> dict[str, Any]:
    _record_codex_tool_event(
        task_id=task_id,
        model=model,
        is_paid_provider=route_is_paid,
        elapsed_ms=elapsed_ms,
        ok=False,
        error=error,
        actual_cost_usd=_runtime_cost_usd(elapsed_ms),
    )
    return {"ok": False, "elapsed_ms": elapsed_ms, "error": error}


def _read_output_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_codex_exec(
    *,
    task_id: str,
    model: str,
    prompt: str,
    route_is_paid: bool,
    started_perf: float,
    cost_budget: dict[str, float | None],
) -> dict[str, Any]:
    resolved_model = _extract_underlying_model(model).strip() or "gpt-5.3-codex-spark"
    with tempfile.NamedTemporaryFile(prefix="codex_exec_", suffix=".txt", delete=False) as tmp_out:
        out_path = tmp_out.name

    cmd = [
        "codex",
        "exec",
        prompt,
        "--model",
        resolved_model,
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--json",
        "-o",
        out_path,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:
        elapsed_ms = max(1, int(round((time.perf_counter() - started_perf) * 1000)))
        return _failure_result(
            task_id=task_id,
            model=model,
            route_is_paid=route_is_paid,
            elapsed_ms=elapsed_ms,
            error=f"Execution failed (Codex): {exc}",
        )

    elapsed_ms = max(1, int(round((time.perf_counter() - started_perf) * 1000)))
    content = _read_output_file(out_path)

    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "codex exec failed").strip()
        return _failure_result(
            task_id=task_id,
            model=model,
            route_is_paid=route_is_paid,
            elapsed_ms=elapsed_ms,
            error=f"Execution failed (Codex): {err[:1000]}",
        )

    if not content:
        content = (completed.stdout or "").strip() or "Codex execution completed with no output."

    usage = _extract_usage_from_codex_jsonl(completed.stdout or "")
    usage_json = json.dumps(usage, sort_keys=True)[:2000]
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    cost_usd = _runtime_cost_usd(elapsed_ms)
    _record_codex_tool_event(
        task_id=task_id,
        model=model,
        is_paid_provider=route_is_paid,
        elapsed_ms=elapsed_ms,
        ok=True,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        usage_json=usage_json,
        actual_cost_usd=cost_usd,
    )
    return {
        "ok": True,
        "elapsed_ms": elapsed_ms,
        "content": content,
        "usage_json": usage_json,
        "provider_request_id": "",
        "actual_cost_usd": cost_usd,
        "max_cost_usd": cost_budget.get("max_cost_usd"),
        "cost_slack_ratio": cost_budget.get("cost_slack_ratio"),
    }
