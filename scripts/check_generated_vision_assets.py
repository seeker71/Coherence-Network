#!/usr/bin/env python3
"""Validate generated vision assets referenced by concepts and web pages.

Checks two classes of references:
1. Inline `![caption](visuals:prompt)` entries in concept markdown, which map to
   `/visuals/generated/{concept_id}-story-{index}.jpg`
2. Explicit `/visuals/generated/...` references in the vision web app.

By default the checker also requires each referenced asset to be git-tracked so
deploys cannot silently depend on local-only generated files.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from kb_common import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[1]
CONCEPT_DIR = REPO_ROOT / "docs" / "vision-kb" / "concepts"
VISION_WEB_DIR = REPO_ROOT / "web" / "app" / "vision"
GENERATED_DIR = REPO_ROOT / "web" / "public" / "visuals" / "generated"
DOCS_VISUALS_DIR = REPO_ROOT / "docs" / "visuals"
WEB_VISUALS_DIR = REPO_ROOT / "web" / "public" / "visuals"
PROMPT_MANIFEST = DOCS_VISUALS_DIR / "prompts.json"

INLINE_VISUAL_RE = re.compile(r"!\[[^\]]*\]\(visuals:[^)]+\)")
GENERATED_REF_RE = re.compile(r'["\'](/visuals/generated/([^"\']+))["\']')


def is_git_tracked(path: Path) -> bool:
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_prompt_manifest() -> dict[str, dict[str, Any]]:
    if not PROMPT_MANIFEST.exists():
        raise FileNotFoundError(f"missing prompt manifest: {display_path(PROMPT_MANIFEST)}")
    data = json.loads(PROMPT_MANIFEST.read_text(encoding="utf-8"))
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError(f"prompt manifest has no records list: {display_path(PROMPT_MANIFEST)}")

    by_path: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        path = record.get("path")
        if isinstance(path, str):
            by_path[path] = record
        for mirror in record.get("mirror_paths") or []:
            if isinstance(mirror, str):
                by_path[mirror] = record
    return by_path


def all_manifest_required_assets() -> list[tuple[str, Path, Path]]:
    requirements: list[tuple[str, Path, Path]] = []
    for asset_path in sorted(GENERATED_DIR.glob("*.jpg")):
        requirements.append(("generated visual file", asset_path, PROMPT_MANIFEST))
    for asset_path in sorted(DOCS_VISUALS_DIR.glob("*.png")):
        requirements.append(("docs visual file", asset_path, PROMPT_MANIFEST))
    for asset_path in sorted(WEB_VISUALS_DIR.glob("*.png")):
        if asset_path.parent == WEB_VISUALS_DIR:
            requirements.append(("web visual mirror file", asset_path, PROMPT_MANIFEST))
    return requirements


def concept_story_requirements() -> list[tuple[str, Path, Path]]:
    requirements: list[tuple[str, Path, Path]] = []
    for concept_path in sorted(CONCEPT_DIR.glob("lc-*.md")):
        content = concept_path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(content)
        concept_id = frontmatter.get("id") or concept_path.stem.split(".")[0]
        count = len(INLINE_VISUAL_RE.findall(content))
        for index in range(count):
            asset_path = GENERATED_DIR / f"{concept_id}-story-{index}.jpg"
            requirements.append(
                (
                    f"{display_path(concept_path)} inline visual {index}",
                    asset_path,
                    concept_path,
                )
            )
    return requirements


def explicit_generated_requirements() -> list[tuple[str, Path, Path]]:
    requirements: list[tuple[str, Path, Path]] = []
    seen: set[tuple[str, str]] = set()
    for file_path in sorted(VISION_WEB_DIR.rglob("*.tsx")):
        text = file_path.read_text(encoding="utf-8")
        for match in GENERATED_REF_RE.finditer(text):
            asset_name = match.group(2)
            key = (str(file_path), asset_name)
            if key in seen:
                continue
            seen.add(key)
            asset_path = GENERATED_DIR / asset_name
            requirements.append(
                (
                    f"{display_path(file_path)} reference {asset_name}",
                    asset_path,
                    file_path,
                )
            )
    return requirements


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated vision assets")
    parser.add_argument(
        "--allow-untracked",
        action="store_true",
        help="Only require files to exist locally; skip git-tracked enforcement.",
    )
    args = parser.parse_args()

    requirements = concept_story_requirements() + explicit_generated_requirements()
    manifest_requirements = all_manifest_required_assets()

    missing: list[str] = []
    untracked: list[str] = []
    missing_prompt_records: list[str] = []
    empty_prompt_records: list[str] = []

    try:
        prompt_records = load_prompt_manifest()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"Generated vision prompt manifest check failed: {exc}")
        return 1

    for source_label, asset_path, _source_path in requirements:
        if not asset_path.exists():
            missing.append(f"{source_label}: missing {asset_path.relative_to(REPO_ROOT)}")
            continue
        if not args.allow_untracked and not is_git_tracked(asset_path):
            untracked.append(f"{source_label}: untracked {asset_path.relative_to(REPO_ROOT)}")

    for source_label, asset_path, _source_path in manifest_requirements:
        rel_path = str(asset_path.relative_to(REPO_ROOT))
        record = prompt_records.get(rel_path)
        if record is None:
            missing_prompt_records.append(f"{source_label}: missing prompt record for {rel_path}")
            continue
        if not str(record.get("prompt") or "").strip():
            empty_prompt_records.append(f"{source_label}: empty prompt for {rel_path}")

    if missing or untracked or missing_prompt_records or empty_prompt_records:
        if missing:
            print("Missing generated vision assets:")
            for item in missing:
                print(f"  - {item}")
        if untracked:
            print("Generated vision assets must be git-tracked before verification:")
            for item in untracked:
                print(f"  - {item}")
        if missing_prompt_records:
            print("Generated vision assets must have persistent prompt records:")
            for item in missing_prompt_records:
                print(f"  - {item}")
        if empty_prompt_records:
            print("Generated vision prompt records must not be empty:")
            for item in empty_prompt_records:
                print(f"  - {item}")
        return 1

    tracked_mode = "exist + tracked" if not args.allow_untracked else "exist"
    print(
        "Generated vision asset check passed "
        f"({len(requirements)} references checked, "
        f"{len(manifest_requirements)} prompt records checked, mode={tracked_mode})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
