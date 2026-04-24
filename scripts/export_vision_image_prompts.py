#!/usr/bin/env python3
"""Export persistent prompt records for Living Collective vision images.

This is a one-time migration helper and a repeatable audit tool. Current image
files carry Pollinations JSON metadata, but that metadata is not a source of
truth. The exported manifest makes prompts repo-owned, editable, and available
to future regeneration scripts without reading old image artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "visuals" / "prompts.json"
GENERATED_DIR = REPO_ROOT / "web" / "public" / "visuals" / "generated"
DOCS_VISUALS_DIR = REPO_ROOT / "docs" / "visuals"
WEB_VISUALS_DIR = REPO_ROOT / "web" / "public" / "visuals"


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _extract_json_object(raw: bytes) -> dict[str, Any] | None:
    marker = b'{"prompt":'
    start = raw.find(marker)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for offset, byte in enumerate(raw[start:], start=start):
        char = chr(byte)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                payload = raw[start : offset + 1].decode("utf-8", errors="replace")
                return json.loads(payload)
    return None


def _image_metadata(path: Path) -> dict[str, Any] | None:
    try:
        return _extract_json_object(path.read_bytes())
    except (OSError, json.JSONDecodeError):
        return None


def _record_for(path: Path, collection: str) -> dict[str, Any]:
    metadata = _image_metadata(path) or {}
    prompt = str(metadata.get("originalPrompt") or metadata.get("prompt") or "").strip()
    record: dict[str, Any] = {
        "id": path.stem,
        "path": _relative(path),
        "collection": collection,
        "prompt": prompt,
        "source": "embedded-metadata-migration" if prompt else "missing",
        "model": metadata.get("model"),
        "seed": metadata.get("seed"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "quality": metadata.get("quality"),
    }
    if collection == "docs-visuals":
        mirror = WEB_VISUALS_DIR / path.name
        if mirror.exists():
            record["mirror_paths"] = [_relative(mirror)]
    return record


def build_manifest() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in sorted(GENERATED_DIR.glob("*.jpg")):
        records.append(_record_for(path, "generated-concept-visuals"))
    for path in sorted(DOCS_VISUALS_DIR.glob("*.png")):
        records.append(_record_for(path, "docs-visuals"))

    missing = [record["path"] for record in records if not record["prompt"]]
    return {
        "schema_version": 1,
        "source_note": (
            "Prompts were migrated from embedded image metadata. After this "
            "manifest is committed, edit prompts here and treat image metadata "
            "as non-authoritative."
        ),
        "records": records,
        "summary": {
            "total": len(records),
            "with_prompt": len(records) - len(missing),
            "missing_prompt": len(missing),
            "missing_prompt_paths": missing,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export persistent vision image prompt manifest")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = build_manifest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = manifest["summary"]
    print(
        "Exported vision image prompts: "
        f"{summary['with_prompt']}/{summary['total']} with prompts -> {_relative(args.out)}"
    )
    if summary["missing_prompt"]:
        print("Missing prompt records:")
        for path in summary["missing_prompt_paths"]:
            print(f"  - {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
