"""Auto-discover node executors, tools, hardware, and routed models."""

from __future__ import annotations

import json
import os
import platform
import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from pathlib import Path

from app.models.federation import NodeCapabilities

_EXECUTOR_COMMANDS = {
    "claude": "claude",
    "cursor": "cursor",
    "agent": "agent",
}

_SYSTEM_TOOLS = ("docker", "git", "python3", "node", "npm", "gh")
_PER_CHECK_TIMEOUT_SECONDS = 2.0
_PROBE_TIMEOUT_SECONDS = 5.0
_MAX_WORKERS = 6


class CapabilityProbe:
    """Detect local node capability metadata for federation registration."""

    @staticmethod
    def _check_command_available(command: str) -> bool:
        return shutil.which(command) is not None

    @classmethod
    def _probe_command_map(
        cls,
        mapping: dict[str, str],
        *,
        deadline_monotonic: float,
    ) -> list[str]:
        """Return keys whose command is available, with bounded timeouts."""
        available: list[str] = []
        lock = threading.Lock()
        pool = ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, max(1, len(mapping))))
        try:
            futures: dict[str, Future[bool]] = {
                name: pool.submit(cls._check_command_available, command)
                for name, command in mapping.items()
            }
            for name, future in futures.items():
                remaining = max(0.0, deadline_monotonic - _monotonic())
                if remaining <= 0:
                    continue
                timeout = min(_PER_CHECK_TIMEOUT_SECONDS, remaining)
                try:
                    if future.result(timeout=timeout):
                        with lock:
                            available.append(name)
                except (TimeoutError, Exception):
                    continue
        finally:
            pool.shutdown(wait=False)
        return sorted(available)

    @staticmethod
    def _load_models_by_executor() -> dict[str, list[str]]:
        """Load declared models from config/model_routing.json when present."""
        candidates = [
            Path(__file__).resolve().parents[2] / "config" / "model_routing.json",
            Path(__file__).resolve().parents[3] / "config" / "model_routing.json",
        ]
        config_path = next((p for p in candidates if p.exists()), candidates[0])
        if not config_path.exists():
            return {}
        try:
            with config_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}

        out: dict[str, list[str]] = {}

        tiers = data.get("tiers_by_executor")
        if isinstance(tiers, dict):
            for executor, tier_map in tiers.items():
                if not isinstance(tier_map, dict):
                    continue
                models = [str(v).strip() for v in tier_map.values() if isinstance(v, str) and v.strip()]
                if models:
                    out[str(executor)] = sorted(set(models))

        by_task_type = data.get("openrouter_models_by_task_type") or data.get("routing")
        if isinstance(by_task_type, dict):
            openrouter_models = [
                str(v).strip() for v in by_task_type.values() if isinstance(v, str) and v.strip()
            ]
            if openrouter_models:
                existing = out.get("openrouter", [])
                out["openrouter"] = sorted(set(existing + openrouter_models))

        fallback_chains = data.get("fallback_chains")
        if isinstance(fallback_chains, dict):
            for executor, chain in fallback_chains.items():
                if not isinstance(chain, list):
                    continue
                chain_models = [str(v).strip() for v in chain if isinstance(v, str) and v.strip()]
                if not chain_models:
                    continue
                existing = out.get(str(executor), [])
                out[str(executor)] = sorted(set(existing + chain_models))

        return out

    @staticmethod
    def _detect_memory_total_bytes() -> int | None:
        try:
            import psutil  # type: ignore

            memory = psutil.virtual_memory()
            return int(memory.total)
        except Exception:
            pass

        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            try:
                text = meminfo.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            return int(parts[1]) * 1024
            except OSError:
                return None
        return None

    @classmethod
    def _detect_hardware(cls) -> dict:
        cpu_count = os.cpu_count() or 0
        memory_total_bytes = cls._detect_memory_total_bytes()
        memory_total_gb = (
            round(memory_total_bytes / (1024**3), 2) if isinstance(memory_total_bytes, int) else None
        )

        gpu_available = False
        gpu_type: str | None = None
        if shutil.which("nvidia-smi"):
            gpu_available = True
            gpu_type = "nvidia"
        else:
            processor = (platform.processor() or "").lower()
            machine = (platform.machine() or "").lower()
            if platform.system() == "Darwin" and ("arm" in processor or machine == "arm64"):
                gpu_available = True
                gpu_type = "apple_silicon"

        return {
            "cpu_count": int(cpu_count),
            "memory_total_gb": memory_total_gb,
            "gpu_available": gpu_available,
            "gpu_type": gpu_type,
        }

    @classmethod
    def probe(cls) -> NodeCapabilities:
        """Probe capabilities with bounded execution time."""
        deadline = _monotonic() + _PROBE_TIMEOUT_SECONDS

        executors = cls._probe_command_map(_EXECUTOR_COMMANDS, deadline_monotonic=deadline)
        if os.getenv("OPENROUTER_API_KEY", "").strip():
            executors = sorted(set(executors + ["openrouter"]))

        tools = cls._probe_command_map(
            {tool: tool for tool in _SYSTEM_TOOLS},
            deadline_monotonic=deadline,
        )
        models_by_executor = cls._load_models_by_executor()
        hardware = cls._detect_hardware()
        probed_at = datetime.now(tz=timezone.utc)

        return NodeCapabilities(
            executors=executors,
            tools=tools,
            hardware=hardware,
            models_by_executor=models_by_executor,
            probed_at=probed_at,
        )


def _monotonic() -> float:
    # Imported lazily to keep module import deterministic in tests.
    import time

    return time.monotonic()
