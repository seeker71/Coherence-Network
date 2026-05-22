"""Breath surface — the body's present-tense felt voice, observable to any cell."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import APIRouter

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BREATH_FILE = _REPO_ROOT / "docs" / "breath" / "now.md"
_BREATHS_DIR = _REPO_ROOT / "docs" / "breath" / "breaths"
_WITNESS_URL = "https://pulse.coherencycoin.com/pulse/now"


def _parse_breath(text: str) -> dict[str, Any]:
    """Split frontmatter from body and parse the strata."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {"frontmatter": {}, "sections": {}}
    frontmatter = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            current_heading = line[3:].strip()
            sections[current_heading] = []
        elif current_heading is not None:
            sections[current_heading].append(line)
    return {
        "frontmatter": frontmatter,
        "sections": {k: "\n".join(v).strip() for k, v in sections.items()},
    }


def _extract_bullets(section_text: str) -> list[dict[str, str]]:
    """Pull top-level bullets into structured entries.

    Supports two shapes side-by-side:
      - **Name** — body text continuing on this and following indented lines
      - body text without a name (plain bullet)
    """
    entries: list[dict[str, str]] = []
    current_name = ""
    current_body: list[str] | None = None

    def flush() -> None:
        nonlocal current_name, current_body
        if current_body is not None:
            joined = " ".join(current_body).strip()
            if joined:
                entries.append({"name": current_name, "body": joined})
        current_name = ""
        current_body = None

    for line in section_text.splitlines():
        if line.startswith("- "):
            flush()
            content = line[2:]
            named = re.match(r"^\*\*(.+?)\*\*\s*(?:—|--)\s*(.*)$", content)
            if named:
                current_name = named.group(1)
                current_body = [named.group(2)]
            else:
                current_name = ""
                current_body = [content]
        elif current_body is not None and line.startswith("  "):
            current_body.append(line.strip())
        elif not line.strip():
            flush()
    flush()
    return entries


async def _fetch_witness() -> dict[str, Any]:
    """Pull the witness pulse — degrade quietly if it's unreachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(_WITNESS_URL)
            if r.status_code == 200:
                data = r.json()
                return {
                    "overall": data.get("overall"),
                    "silences": len(data.get("ongoing_silences", []) or []),
                    "strained_organs": [
                        o.get("name")
                        for o in data.get("organs", [])
                        if o.get("status") and o.get("status") != "breathing"
                    ],
                    "source": "live",
                }
    except Exception:
        pass
    return {"overall": None, "silences": None, "strained_organs": [], "source": "unavailable"}


@router.get("/breath/now", summary="The body's present-tense felt voice")
async def breath_now() -> dict[str, Any]:
    if not _BREATH_FILE.exists():
        return {
            "voice": "The breath file is not present in this body.",
            "composed_at": None,
            "attendant": None,
            "witness": await _fetch_witness(),
            "substances": [],
            "lineage_shapes": [],
            "reach": [],
            "open_placements": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    parsed = _parse_breath(_BREATH_FILE.read_text(encoding="utf-8"))
    fm = parsed["frontmatter"]
    sections = parsed["sections"]
    witness = await _fetch_witness()

    return {
        "schema_version": fm.get("schema_version", 1),
        "attendant": fm.get("attendant"),
        "composed_at": fm.get("composed_at"),
        "voice": (fm.get("voice") or "").strip(),
        "witness": witness,
        "substances": _extract_bullets(sections.get("Substances arriving", "")),
        "lineage_shapes": _extract_bullets(sections.get("Lineage shapes active", "")),
        "reach": _extract_bullets(sections.get("Reach", "")),
        "open_placements": _extract_bullets(sections.get("Open placements", "")),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/breath/history", summary="Past breath compositions")
async def breath_history(limit: int = 20) -> dict[str, Any]:
    if not _BREATHS_DIR.exists():
        return {"breaths": [], "count": 0}
    files = sorted(_BREATHS_DIR.glob("*.md"), reverse=True)[:limit]
    items = []
    for path in files:
        parsed = _parse_breath(path.read_text(encoding="utf-8"))
        fm = parsed["frontmatter"]
        items.append({
            "file": path.name,
            "attendant": fm.get("attendant"),
            "composed_at": fm.get("composed_at"),
            "voice": (fm.get("voice") or "").strip(),
        })
    return {"breaths": items, "count": len(items)}
