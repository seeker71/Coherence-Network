"""Model listing and routing configuration endpoints.

GET   /api/models          — list all configured models grouped by executor
GET   /api/models/routing  — current task-type → model routing config
PATCH /api/models/routing  — update routing config at runtime
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/models", tags=["models"])
log = logging.getLogger("coherence.api")

_API_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _API_ROOT / "config"
_ROUTING_PATH = _CONFIG_DIR / "model_routing.json"
_EVIDENCE_DIR = _REPO_ROOT / "docs" / "system_audit"
_PROOF_LEDGER_DIR = _EVIDENCE_DIR / "model_executor_run_ledger"

_LEARNING_EVIDENCE_KEYWORDS = (
    "learning",
    "model",
    "oracle",
    "witness",
    "android",
    "jit",
    "native",
)


# ── Response models ─────────────────────────────────────────────────


class ModelEntry(BaseModel):
    model_id: str
    tier: str  # "strong" | "fast" | "fallback"
    executor: str


class ModelsListResponse(BaseModel):
    executors: dict[str, list[ModelEntry]]
    total: int


class RoutingConfigResponse(BaseModel):
    task_type_tier_mapping: dict[str, str]
    executor_tiers: dict[str, dict[str, list[str]]]
    fallback_chains: dict[str, list[str]]
    openrouter_task_overrides: dict[str, str]


class RoutingUpdateRequest(BaseModel):
    """Partial update to model routing config."""
    task_type_tier_set: dict[str, str] | None = None  # e.g. {"spec": "fast"}
    executor_tier_add: dict[str, Any] | None = None   # e.g. {"claude": {"fast": ["claude-3-5-haiku"]}}
    openrouter_override_set: dict[str, str] | None = None


class LearningDashboardModel(BaseModel):
    executor: str
    model_id: str
    tiers: list[str] = Field(default_factory=list)
    fallback_rank: int | None = None
    task_types: list[str] = Field(default_factory=list)
    role: str


class LearningSurface(BaseModel):
    surface_id: str
    title: str
    kind: str
    state: str
    proof_status: str
    training_metadata: dict[str, Any]
    north_star_alignment: str
    next_step: str | None = None
    evidence_path: str


class LearningProofRun(BaseModel):
    run_id: str
    model_used: str
    pass_fail: str
    attempts: int
    commands_run: list[str]
    source_path: str | None = None


class LearningDashboardSummary(BaseModel):
    routed_model_count: int
    proof_run_count: int
    proof_pass_count: int
    learning_surface_count: int
    trained_native_model_count: int
    proven_floor_count: int
    blocked_or_pending_count: int


class LearningDashboardResponse(BaseModel):
    summary: LearningDashboardSummary
    north_star: str
    floor: str
    models: list[LearningDashboardModel]
    learning_surfaces: list[LearningSurface]
    recent_proof_runs: list[LearningProofRun]
    guidance: list[str]


# ── Helpers ─────────────────────────────────────────────────────────


def _load_routing() -> dict:
    """Load model_routing.json with safe fallback."""
    try:
        return json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.warning("Could not load model_routing.json: %s", exc)
        return {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalized_executor_tiers(config: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    raw = config.get("executor_tiers") or config.get("tiers_by_executor") or {}
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict[str, list[str]]] = {}
    for executor, tiers in raw.items():
        if not isinstance(tiers, dict):
            continue
        normalized[str(executor)] = {
            str(tier): _as_list(models)
            for tier, models in tiers.items()
            if _as_list(models)
        }
    return normalized


def _task_type_tiers(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("task_type_tier_mapping") or config.get("task_type_tier") or {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def _openrouter_overrides(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("openrouter_task_overrides") or config.get("openrouter_models_by_task_type") or {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _short_path(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _validation_commands(record: dict[str, Any]) -> list[str]:
    local = record.get("local_validation")
    commands = local.get("commands") if isinstance(local, dict) else None
    if not isinstance(commands, list):
        return []
    out: list[str] = []
    for command in commands:
        if isinstance(command, str):
            out.append(command)
        elif isinstance(command, dict) and command.get("command"):
            out.append(str(command["command"]))
    return out[:6]


def _proof_status(record: dict[str, Any]) -> str:
    for key in ("e2e_validation", "local_validation", "ci_validation"):
        value = record.get(key)
        if isinstance(value, dict) and value.get("status"):
            return str(value["status"])
    return "unknown"


def _surface_state(record: dict[str, Any]) -> str:
    phase_gate = record.get("phase_gate")
    if isinstance(phase_gate, dict):
        state = phase_gate.get("state")
        if state:
            return str(state)
        if phase_gate.get("can_move_next_phase") is True:
            return "ready"
    status = _proof_status(record)
    if status == "pass":
        return "proven_floor"
    if status in {"pending", "blocked", "fail"}:
        return status
    return "observed"


def _surface_kind(record: dict[str, Any], path: Path) -> str:
    text = " ".join(
        [
            path.name,
            str(record.get("commit_scope") or ""),
            " ".join(str(item) for item in record.get("idea_ids") or []),
            " ".join(str(item) for item in record.get("spec_ids") or []),
        ]
    ).lower()
    if "oracle" in text or "witness" in text:
        return "oracle or witness learning"
    if "jit" in text or "native" in text:
        return "native lowering learning"
    if "routing" in text or "executor" in text:
        return "model routing"
    if "retire" in text:
        return "retirement gate"
    return "learning proof"


def _north_star_alignment(record: dict[str, Any]) -> str:
    ideas = [str(item) for item in record.get("idea_ids") or []]
    specs = [str(item) for item in record.get("spec_ids") or []]
    if ideas or specs:
        return " / ".join((ideas + specs)[:4])
    return "Form-native learning with proof-backed receipts"


def _next_step(record: dict[str, Any]) -> str | None:
    phase_gate = record.get("phase_gate")
    if isinstance(phase_gate, dict) and phase_gate.get("next"):
        return str(phase_gate["next"])
    e2e = record.get("e2e_validation")
    if isinstance(e2e, dict) and e2e.get("summary"):
        return str(e2e["summary"])
    return None


def _is_learning_evidence(path: Path, record: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            path.name,
            str(record.get("commit_scope") or ""),
            " ".join(str(item) for item in record.get("idea_ids") or []),
            " ".join(str(item) for item in record.get("spec_ids") or []),
            " ".join(str(item) for item in record.get("task_ids") or []),
        ]
    ).lower()
    return any(keyword in haystack for keyword in _LEARNING_EVIDENCE_KEYWORDS)


def _collect_learning_surfaces(limit: int = 14) -> list[LearningSurface]:
    surfaces: list[LearningSurface] = []
    if not _EVIDENCE_DIR.exists():
        return surfaces
    for path in sorted(_EVIDENCE_DIR.glob("commit_evidence_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = _load_json_file(path)
        if not record or not _is_learning_evidence(path, record):
            continue
        task_ids = [str(item) for item in record.get("task_ids") or [] if str(item).strip()]
        surface_id = task_ids[0] if task_ids else path.stem.replace("commit_evidence_", "")
        commands = _validation_commands(record)
        refs = [str(item) for item in record.get("evidence_refs") or []][:6]
        state = _surface_state(record)
        surfaces.append(
            LearningSurface(
                surface_id=surface_id,
                title=str(record.get("commit_scope") or surface_id).strip(),
                kind=_surface_kind(record, path),
                state=state,
                proof_status=_proof_status(record),
                training_metadata={
                    "commands": commands,
                    "evidence_refs": refs,
                    "contributors": record.get("contributors") or [],
                    "trained_native_weights": False,
                    "note": (
                        "No weight artifact is claimed here; this is a proven learning/receipt floor."
                        if "trained" not in state.lower()
                        else "Training state is reported from the evidence receipt."
                    ),
                },
                north_star_alignment=_north_star_alignment(record),
                next_step=_next_step(record),
                evidence_path=_short_path(path),
            )
        )
        if len(surfaces) >= limit:
            break
    return surfaces


def _collect_models(config: dict[str, Any]) -> list[LearningDashboardModel]:
    tiers = _normalized_executor_tiers(config)
    fallback_chains = config.get("fallback_chains") if isinstance(config.get("fallback_chains"), dict) else {}
    task_tiers = _task_type_tiers(config)
    openrouter_overrides = _openrouter_overrides(config)
    model_map: dict[tuple[str, str], LearningDashboardModel] = {}

    for executor, tier_map in tiers.items():
        for tier, model_ids in tier_map.items():
            for model_id in model_ids:
                key = (executor, model_id)
                row = model_map.setdefault(
                    key,
                    LearningDashboardModel(
                        executor=executor,
                        model_id=model_id,
                        tiers=[],
                        fallback_rank=None,
                        task_types=[],
                        role="configured route",
                    ),
                )
                if tier not in row.tiers:
                    row.tiers.append(tier)

    for executor, chain_value in fallback_chains.items():
        for index, model_id in enumerate(_as_list(chain_value), start=1):
            key = (str(executor), model_id)
            row = model_map.setdefault(
                key,
                LearningDashboardModel(
                    executor=str(executor),
                    model_id=model_id,
                    tiers=[],
                    fallback_rank=index,
                    task_types=[],
                    role="fallback route",
                ),
            )
            row.fallback_rank = index if row.fallback_rank is None else min(row.fallback_rank, index)

    for task_type, tier in task_tiers.items():
        for executor, tier_map in tiers.items():
            for model_id in tier_map.get(tier, []):
                row = model_map[(executor, model_id)]
                if task_type not in row.task_types:
                    row.task_types.append(task_type)

    for task_type, model_id in openrouter_overrides.items():
        key = ("openrouter", model_id)
        row = model_map.setdefault(
            key,
            LearningDashboardModel(
                executor="openrouter",
                model_id=model_id,
                tiers=["override"],
                fallback_rank=None,
                task_types=[],
                role="task override",
            ),
        )
        if task_type not in row.task_types:
            row.task_types.append(task_type)

    return sorted(model_map.values(), key=lambda row: (row.executor, row.model_id))


def _collect_recent_proof_runs(limit: int = 10) -> list[LearningProofRun]:
    runs: list[LearningProofRun] = []
    if not _PROOF_LEDGER_DIR.exists():
        return runs
    for path in sorted(_PROOF_LEDGER_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = _load_json_file(path)
        if not record:
            continue
        source = record.get("source")
        runs.append(
            LearningProofRun(
                run_id=str(record.get("run_id") or path.stem),
                model_used=str(record.get("model_used") or "unknown"),
                pass_fail=str(record.get("pass_fail") or "unknown"),
                attempts=int(record.get("attempts") or 0),
                commands_run=[str(item) for item in record.get("commands_run") or []][:5],
                source_path=str(source.get("path")) if isinstance(source, dict) and source.get("path") else None,
            )
        )
        if len(runs) >= limit:
            break
    return runs


def _save_routing(config: dict) -> None:
    """Persist model_routing.json."""
    _ROUTING_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    log.info("model_routing.json updated and saved")


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("", summary="List all configured models grouped by executor with tier info")
async def list_models() -> ModelsListResponse:
    """List all configured models grouped by executor with tier info."""
    config = _load_routing()
    executor_tiers = _normalized_executor_tiers(config)

    result: dict[str, list[ModelEntry]] = {}
    total = 0

    for executor, tiers in executor_tiers.items():
        entries = []
        for tier_name, models in tiers.items():
            if isinstance(models, list):
                for m in models:
                    entries.append(ModelEntry(model_id=m, tier=tier_name, executor=executor))
                    total += 1
        result[executor] = entries

    # Also include openrouter task overrides as a virtual executor group
    or_overrides = _openrouter_overrides(config)
    if or_overrides:
        or_entries = []
        for task_type, model_id in or_overrides.items():
            or_entries.append(ModelEntry(
                model_id=model_id,
                tier=f"task:{task_type}",
                executor="openrouter",
            ))
            total += 1
        # Merge with existing openrouter entries
        existing = result.get("openrouter", [])
        # Deduplicate by model_id
        seen = {e.model_id for e in existing}
        for e in or_entries:
            if e.model_id not in seen:
                existing.append(e)
                seen.add(e.model_id)
        result["openrouter"] = existing

    return ModelsListResponse(executors=result, total=total)


@router.get("/routing", summary="Return current task-type → model routing configuration")
async def get_routing_config() -> RoutingConfigResponse:
    """Return current task-type → model routing configuration."""
    config = _load_routing()
    return RoutingConfigResponse(
        task_type_tier_mapping=_task_type_tiers(config),
        executor_tiers=_normalized_executor_tiers(config),
        fallback_chains=config.get("fallback_chains", {}),
        openrouter_task_overrides=_openrouter_overrides(config),
    )


@router.get("/learning-dashboard", summary="Return model training and learning metadata for the dashboard")
async def get_learning_dashboard() -> LearningDashboardResponse:
    """Expose routed models, proof runs, and learning receipts in one dashboard shape."""
    config = _load_routing()
    models = _collect_models(config)
    surfaces = _collect_learning_surfaces()
    proof_runs = _collect_recent_proof_runs()
    proof_pass_count = sum(1 for run in proof_runs if run.pass_fail == "pass")
    proven_floor_count = sum(1 for surface in surfaces if surface.proof_status == "pass")
    blocked_or_pending_count = sum(1 for surface in surfaces if surface.proof_status in {"pending", "blocked", "fail"})
    trained_native_model_count = sum(
        1 for surface in surfaces if bool(surface.training_metadata.get("trained_native_weights"))
    )

    return LearningDashboardResponse(
        summary=LearningDashboardSummary(
            routed_model_count=len(models),
            proof_run_count=len(proof_runs),
            proof_pass_count=proof_pass_count,
            learning_surface_count=len(surfaces),
            trained_native_model_count=trained_native_model_count,
            proven_floor_count=proven_floor_count,
            blocked_or_pending_count=blocked_or_pending_count,
        ),
        north_star=(
            "Form-native models and learning recipes produce measurable receipts, compare against "
            "third-party oracles, and retire oracle dependence only after sustained native wins."
        ),
        floor=(
            "The current floor exposes configured executor models, recent proof runs, and learning "
            "surface evidence; no native weight artifact is claimed until a receipt names one."
        ),
        models=models,
        learning_surfaces=surfaces,
        recent_proof_runs=proof_runs,
        guidance=[
            "Treat configured provider models as teachers or routes, not trained native artifacts.",
            "Move attention to surfaces with pass receipts and explicit next steps before broadening scope.",
            "Promote a surface from proof floor to trained model only when the ledger names weights, data, evals, and retirement criteria.",
        ],
    )


@router.patch("/routing", summary="Update model routing configuration at runtime")
async def update_routing_config(body: RoutingUpdateRequest) -> RoutingConfigResponse:
    """Update model routing configuration at runtime.

    Changes are persisted to model_routing.json immediately.
    """
    config = _load_routing()

    if body.task_type_tier_set:
        mapping = config.setdefault("task_type_tier_mapping", {})
        for task_type, tier in body.task_type_tier_set.items():
            if tier not in ("strong", "fast"):
                raise HTTPException(400, f"Invalid tier '{tier}' for task type '{task_type}'. Use 'strong' or 'fast'.")
            mapping[task_type] = tier
            log.info("Routing update: %s → %s", task_type, tier)

    if body.executor_tier_add:
        tiers = config.setdefault("executor_tiers", {})
        for executor, tier_models in body.executor_tier_add.items():
            exec_tiers = tiers.setdefault(executor, {})
            for tier_name, models in tier_models.items():
                existing = exec_tiers.setdefault(tier_name, [])
                for m in (models if isinstance(models, list) else [models]):
                    if m not in existing:
                        existing.append(m)
                        log.info("Model added: %s/%s → %s", executor, tier_name, m)

    if body.openrouter_override_set:
        overrides = config.setdefault("openrouter_task_overrides", {})
        for task_type, model in body.openrouter_override_set.items():
            overrides[task_type] = model
            log.info("OpenRouter override: %s → %s", task_type, model)

    _save_routing(config)

    # Reload the routing loader cache if available
    try:
        from app.services.agent_routing import model_routing_loader
        if hasattr(model_routing_loader, "_reload_config"):
            model_routing_loader._reload_config()
    except Exception:
        pass  # best effort

    return RoutingConfigResponse(
        task_type_tier_mapping=_task_type_tiers(config),
        executor_tiers=_normalized_executor_tiers(config),
        fallback_chains=config.get("fallback_chains", {}),
        openrouter_task_overrides=_openrouter_overrides(config),
    )
