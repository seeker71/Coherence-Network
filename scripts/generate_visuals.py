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
import re
import sys
import time

from kb_common import (
    OUTPUT_DIR, DEFAULT_API,
    concept_seed, SEED_STRIDE, STORY_SEED_STRIDE,
    pollinations_url, api_get, download_image,
)


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


def main():
    parser = argparse.ArgumentParser(description="Pre-generate Pollinations images as static assets")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
