"""Registry submission inventory backed by static repo-tracked evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.registry_discovery import (
    RegistrySubmissionInventory,
    RegistrySubmissionRecord,
    RegistrySubmissionStatus,
    RegistrySubmissionSummary,
)

_INVENTORY_PATH = "docs/registry-submissions.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(repo_root: Path, rel_path: str) -> dict[str, Any]:
    path = repo_root / rel_path
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_list(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    values: list[str] = []
    for item in raw_value:
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def _as_text(raw_value: Any) -> str | None:
    text = str(raw_value).strip() if raw_value is not None else ""
    return text or None


def _missing_paths(repo_root: Path, rel_paths: list[str]) -> list[str]:
    missing: list[str] = []
    for rel_path in rel_paths:
        if not (repo_root / rel_path).exists():
            missing.append(rel_path)
    return missing


def _load_records(repo_root: Path) -> list[RegistrySubmissionRecord]:
    payload = _read_json(repo_root, _INVENTORY_PATH)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []

    items: list[RegistrySubmissionRecord] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        source_paths = _as_list(raw_item.get("source_paths"))
        required_files = _as_list(raw_item.get("required_files"))
        proof_url = _as_text(raw_item.get("proof_url"))
        proof_path = _as_text(raw_item.get("proof_path"))

        check_paths = list(dict.fromkeys([*source_paths, *required_files, *([proof_path] if proof_path else [])]))
        missing_files = _missing_paths(repo_root, check_paths)
        has_proof = bool(proof_url or proof_path)

        items.append(
            RegistrySubmissionRecord(
                registry_id=str(raw_item.get("registry_id") or "").strip(),
                registry_name=str(raw_item.get("registry_name") or "").strip(),
                category=str(raw_item.get("category") or "").strip(),
                asset_name=str(raw_item.get("asset_name") or "").strip(),
                status=(
                    RegistrySubmissionStatus.SUBMISSION_READY
                    if not missing_files and has_proof
                    else RegistrySubmissionStatus.MISSING_ASSETS
                ),
                install_hint=str(raw_item.get("install_hint") or "").strip(),
                source_paths=source_paths,
                required_files=required_files,
                missing_files=missing_files,
                proof_url=proof_url,
                proof_path=proof_path,
                proof_note=str(raw_item.get("proof_note") or "").strip(),
                notes=str(raw_item.get("notes") or "").strip(),
            )
        )
    return items


def build_registry_submission_inventory() -> RegistrySubmissionInventory:
    repo_root = _repo_root()
    items = _load_records(repo_root)

    items.sort(key=lambda item: (item.category, item.registry_name.lower()))
    ready_items = [item for item in items if item.status == RegistrySubmissionStatus.SUBMISSION_READY]

    category_counts: dict[str, int] = {}
    for item in ready_items:
        category_counts[item.category] = category_counts.get(item.category, 0) + 1

    core_requirement_met = (
        len(ready_items) >= 5
        and category_counts.get("mcp", 0) >= 2
        and category_counts.get("skill", 0) >= 2
    )

    return RegistrySubmissionInventory(
        summary=RegistrySubmissionSummary(
            target_count=len(items),
            submission_ready_count=len(ready_items),
            missing_asset_count=sum(item.status == RegistrySubmissionStatus.MISSING_ASSETS for item in items),
            categories=category_counts,
            core_requirement_met=core_requirement_met,
        ),
        items=items,
    )
