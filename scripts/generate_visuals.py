#!/usr/bin/env python3
"""Pre-generate all Pollinations images and save as static assets.

Fetches concepts from the DB (via API), generates deterministic
Pollinations URLs for BOTH gallery visuals and inline story visuals,
downloads each image, and saves to web/public/visuals/generated/.

Naming convention:
  Gallery visuals:  {concept-id}-{index}.jpg
  Story visuals:    {concept-id}-story-{index}.jpg

After running, the concept page serves local files — zero runtime
dependency on Pollinations.

Usage:
    python scripts/generate_visuals.py                              # production
    python scripts/generate_visuals.py --api-url http://localhost:8000
    python scripts/generate_visuals.py --dry-run
    python scripts/generate_visuals.py --force                      # re-download all
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

from kb_common import (
    OUTPUT_DIR, DEFAULT_API,
    concept_seed, SEED_STRIDE, STORY_SEED_STRIDE,
    pollinations_url, api_get, download_image,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_MANIFEST = REPO_ROOT / "docs" / "visuals" / "prompts.json"


def fetch_concepts(api_url: str) -> list[dict]:
    """Fetch all living-collective concepts."""
    url = f"{api_url}/api/concepts/domain/living-collective?limit=200"
    data = api_get(url)
    return data.get("items", [])


def extract_story_visuals(story_content: str) -> list[dict]:
    """Extract inline visuals from story_content markdown."""
    visuals = []
    for m in re.finditer(r"!\[([^\]]*)\]\(visuals:([^)]+)\)", story_content):
        visuals.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
    return visuals


def manifest_pollinations_url(record: dict[str, Any]) -> str:
    """Build a Pollinations URL from a persistent prompt manifest record."""
    prompt = str(record.get("prompt") or "").strip()
    encoded = urllib.parse.quote(prompt)
    width = int(record.get("width") or 1024)
    height = int(record.get("height") or 576)
    seed = int(record.get("seed") or 42)
    model = urllib.parse.quote(str(record.get("model") or "flux"))
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&model={model}&nologo=true&seed={seed}"
    )


def generate_from_manifest(manifest_path: Path, only_path: str | None, dry_run: bool, force: bool) -> int:
    """Generate images from committed prompt records.

    This path is the durable regeneration contract: edit the manifest prompt,
    then regenerate by stable repo path without reading metadata from the old
    image artifact.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list):
        print(f"Manifest has no records list: {manifest_path}", file=sys.stderr)
        return 1

    selected = []
    for record in records:
        if not isinstance(record, dict):
            continue
        path = str(record.get("path") or "")
        mirrors = [str(p) for p in record.get("mirror_paths") or []]
        if only_path and only_path not in [path, *mirrors, record.get("id")]:
            continue
        selected.append(record)

    if only_path and not selected:
        print(f"No manifest record matched: {only_path}", file=sys.stderr)
        return 1

    total = len(selected)
    downloaded = 0
    skipped = 0
    failed = 0

    for record in selected:
        prompt = str(record.get("prompt") or "").strip()
        rel_path = str(record.get("path") or "")
        if not prompt or not rel_path:
            failed += 1
            print(f"  SKIP invalid record: {record.get('id')}", file=sys.stderr)
            continue

        dest = REPO_ROOT / rel_path
        mirror_paths = [REPO_ROOT / str(path) for path in record.get("mirror_paths") or []]
        if dest.exists() and not force:
            skipped += 1
            for mirror in mirror_paths:
                if not mirror.exists():
                    mirror.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, mirror)
            continue

        url = manifest_pollinations_url(record)
        if dry_run:
            print(f"  [DRY RUN] {rel_path}: {prompt[:80]}...")
            downloaded += 1
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {rel_path}...", end=" ", flush=True)
        if download_image(url, dest):
            for mirror in mirror_paths:
                mirror.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, mirror)
            size_kb = dest.stat().st_size // 1024
            print(f"OK ({size_kb}KB)")
            downloaded += 1
        else:
            print("FAILED")
            failed += 1
        time.sleep(1)

    print(f"\nDone: {downloaded} generated, {skipped} already exist, {failed} failed (of {total} total)")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description="Pre-generate Pollinations images as static assets")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument(
        "--from-manifest",
        action="store_true",
        help="Generate from docs/visuals/prompts.json instead of API concept data.",
    )
    parser.add_argument("--manifest", type=Path, default=PROMPT_MANIFEST)
    parser.add_argument(
        "--only-path",
        help="When using --from-manifest, regenerate one repo path or record id.",
    )
    args = parser.parse_args()

    if args.from_manifest:
        return generate_from_manifest(args.manifest, args.only_path, args.dry_run, args.force)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    concepts = fetch_concepts(args.api_url)
    print(f"Total concepts: {len(concepts)}")

    total = 0
    downloaded = 0
    skipped = 0
    failed = 0

    for c in concepts:
        cid = c["id"]
        base_seed = concept_seed(cid)

        # ── Gallery visuals (from `visuals` property) ──
        gallery_visuals = c.get("visuals", [])
        for i, v in enumerate(gallery_visuals):
            prompt = v.get("prompt", "")
            if not prompt:
                continue
            total += 1
            seed = base_seed + i * SEED_STRIDE
            filename = f"{cid}-{i}.jpg"
            dest = OUTPUT_DIR / filename

            if dest.exists() and not args.force:
                skipped += 1
                continue

            url = pollinations_url(prompt, seed)
            if args.dry_run:
                print(f"  [DRY RUN] {filename}: {prompt[:60]}...")
                downloaded += 1
                continue

            print(f"  {filename}...", end=" ", flush=True)
            if download_image(url, dest):
                size_kb = dest.stat().st_size // 1024
                print(f"OK ({size_kb}KB)")
                downloaded += 1
            else:
                print("FAILED")
                failed += 1
            time.sleep(1)

        # ── Story visuals (from `story_content` inline ![](visuals:...) ) ──
        story_content = c.get("story_content", "")
        if story_content:
            story_visuals = extract_story_visuals(story_content)
            for i, v in enumerate(story_visuals):
                prompt = v.get("prompt", "")
                if not prompt:
                    continue
                total += 1
                seed = base_seed + i * STORY_SEED_STRIDE
                filename = f"{cid}-story-{i}.jpg"
                dest = OUTPUT_DIR / filename

                if dest.exists() and not args.force:
                    skipped += 1
                    continue

                url = pollinations_url(prompt, seed)
                if args.dry_run:
                    print(f"  [DRY RUN] {filename}: {prompt[:60]}...")
                    downloaded += 1
                    continue

                print(f"  {filename}...", end=" ", flush=True)
                if download_image(url, dest):
                    size_kb = dest.stat().st_size // 1024
                    print(f"OK ({size_kb}KB)")
                    downloaded += 1
                else:
                    print("FAILED")
                    failed += 1
                time.sleep(1)

    print(f"\nDone: {downloaded} downloaded, {skipped} already exist, {failed} failed (of {total} total)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
