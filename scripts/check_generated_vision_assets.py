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
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONCEPT_DIR = REPO_ROOT / "docs" / "vision-kb" / "concepts"
VISION_WEB_DIR = REPO_ROOT / "web" / "app" / "vision"
GENERATED_DIR = REPO_ROOT / "web" / "public" / "visuals" / "generated"

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


def concept_story_requirements() -> list[tuple[str, Path, Path]]:
    requirements: list[tuple[str, Path, Path]] = []
    for concept_path in sorted(CONCEPT_DIR.glob("lc-*.md")):
        content = concept_path.read_text(encoding="utf-8")
        concept_id = concept_path.stem
        count = len(INLINE_VISUAL_RE.findall(content))
        for index in range(count):
            asset_path = GENERATED_DIR / f"{concept_id}-story-{index}.jpg"
            requirements.append(
                (
                    f"{concept_path.relative_to(REPO_ROOT)} inline visual {index}",
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
                    f"{file_path.relative_to(REPO_ROOT)} reference {asset_name}",
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

    missing: list[str] = []
    untracked: list[str] = []

    for source_label, asset_path, _source_path in requirements:
        if not asset_path.exists():
            missing.append(f"{source_label}: missing {asset_path.relative_to(REPO_ROOT)}")
            continue
        if not args.allow_untracked and not is_git_tracked(asset_path):
            untracked.append(f"{source_label}: untracked {asset_path.relative_to(REPO_ROOT)}")

    if missing or untracked:
        if missing:
            print("Missing generated vision assets:")
            for item in missing:
                print(f"  - {item}")
        if untracked:
            print("Generated vision assets must be git-tracked before verification:")
            for item in untracked:
                print(f"  - {item}")
        return 1

    tracked_mode = "exist + tracked" if not args.allow_untracked else "exist"
    print(f"Generated vision asset check passed ({len(requirements)} references checked, mode={tracked_mode}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
