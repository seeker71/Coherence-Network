#!/usr/bin/env python3
"""Pre-generate all Pollinations images and save as static assets.

Reads visuals from the DB (via API), generates the same deterministic
Pollinations URL the frontend would use, downloads each image, and
saves to web/public/visuals/generated/{concept-id}-{index}.jpg.

After running, the concept page serves local files — zero runtime
dependency on Pollinations.

Usage:
    python scripts/generate_visuals.py                              # production
    python scripts/generate_visuals.py --api-url http://localhost:8000
    python scripts/generate_visuals.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "visuals" / "generated"
DEFAULT_API = "https://api.coherencycoin.com"


def concept_seed(concept_id: str) -> int:
    """Same seed logic as the frontend: sum of char codes."""
    return sum(ord(c) for c in concept_id)


def pollinations_url(prompt: str, seed: int = 42, width: int = 1024, height: int = 576) -> str:
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"


def fetch_concepts(api_url: str) -> list[dict]:
    """Fetch all living-collective concepts with visuals."""
    url = f"{api_url}/api/concepts/domain/living-collective?limit=200"
    if httpx:
        resp = httpx.get(url, timeout=30)
        data = resp.json()
    else:
        with urllib.request.urlopen(url, timeout=30) as resp:
            import json
            data = json.loads(resp.read())
    items = data.get("items", [])
    return [c for c in items if c.get("visuals")]


def download_image(url: str, dest: Path, retries: int = 3) -> bool:
    """Download an image with retries."""
    for attempt in range(retries):
        try:
            if httpx:
                resp = httpx.get(url, timeout=60, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    dest.write_bytes(resp.content)
                    return True
                if resp.status_code == 503:
                    wait = 5 * (attempt + 1)
                    print(f"    503, waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"    HTTP {resp.status_code}, {len(resp.content)} bytes", file=sys.stderr)
            else:
                urllib.request.urlretrieve(url, str(dest))
                if dest.stat().st_size > 1000:
                    return True
        except Exception as e:
            print(f"    Error: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return False


def main():
    parser = argparse.ArgumentParser(description="Pre-generate Pollinations images as static assets")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    concepts = fetch_concepts(args.api_url)
    print(f"Concepts with visuals: {len(concepts)}")

    total = 0
    downloaded = 0
    skipped = 0
    failed = 0

    for c in concepts:
        cid = c["id"]
        base_seed = concept_seed(cid)
        visuals = c.get("visuals", [])

        for i, v in enumerate(visuals):
            total += 1
            prompt = v.get("prompt", "")
            if not prompt:
                continue

            seed = base_seed + i * 17
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

            # Small delay between requests to be nice to Pollinations
            time.sleep(1)

    print(f"\nDone: {downloaded} downloaded, {skipped} already exist, {failed} failed (of {total} total)")


if __name__ == "__main__":
    main()
