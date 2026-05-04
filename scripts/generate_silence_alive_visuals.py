#!/usr/bin/env python3
"""Generate the alive / growing-over-time views for /silence/built.

The compound is biological architecture — the seed pattern grows, the old
makes room for new organic growth. These views capture the timeline:
seedling, mature, elder.

Usage:
    python3 scripts/generate_silence_alive_visuals.py [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kb_common import download_image, pollinations_url

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "web" / "public" / "silence" / "2026-05-04-brahmavihara" / "built"

VIEWS = [
    {
        "slug": "year-1-seedling",
        "seed": 4310,
        "width": 1280,
        "height": 768,
        "prompt": (
            "freshly built tropical Balinese compound at year 1, golden new alang-alang thatched roofs, "
            "pale bamboo posts, young frangipani trees, fruit tree saplings, fresh stone paths, "
            "earth still bare in places, raked lines visible, the buildings looking new and clean, "
            "tropical north Bali landscape, soft morning light, photorealistic architectural photography, no text"
        ),
    },
    {
        "slug": "year-5-mature",
        "seed": 4311,
        "width": 1280,
        "height": 768,
        "prompt": (
            "tropical Balinese compound at year 5, alang-alang roofs slightly silvered with age, "
            "bamboo posts darkening to honey color, frangipani trees full and blossoming, "
            "fruit forest beginning to canopy, mosses filling cracks in stone paths, "
            "lotus pond with full leaves, ferns growing from roof corners, vines climbing posts, "
            "lush mature gardens between buildings, photorealistic architectural photography, no text"
        ),
    },
    {
        "slug": "year-15-elder",
        "seed": 4312,
        "width": 1280,
        "height": 768,
        "prompt": (
            "weathered elder tropical Balinese compound after 15 years of life, alang-alang roofs deep silver-grey, "
            "bamboo posts dark amber, thick moss covering stone paths and walls, mature fruit forest "
            "with full canopy embracing the buildings, jasmine and passion flower vines wrapping every post, "
            "small new bale extensions added organically, an old bale half composted back into garden, "
            "deep shade, soft humid air, the buildings indistinguishable from the forest, "
            "photorealistic architectural photography, no text"
        ),
    },
    {
        "slug": "growth-detail",
        "seed": 4313,
        "width": 1024,
        "height": 1024,
        "prompt": (
            "macro detail of bamboo post wrapped in jasmine vine and tillandsia air plants, "
            "alang-alang thatch above with bird's-nest ferns growing from the corners, "
            "bamboo gone honey-amber with age, gecko on the post, soft tropical light, "
            "the architecture and the living plants becoming one body, "
            "photorealistic close-up nature photography, no text"
        ),
    },
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="re-download even if files exist")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for view in VIEWS:
        dest = OUT_DIR / f"{view['slug']}.jpg"
        if dest.exists() and not args.force:
            print(f"  skip (exists)  {dest.name}")
            continue
        url = pollinations_url(
            view["prompt"], seed=view["seed"],
            width=view["width"], height=view["height"],
        )
        print(f"  fetching       {view['slug']:20s}  ({view['width']}x{view['height']})")
        ok = download_image(url, dest)
        if not ok:
            print(f"    FAILED: {view['slug']}", file=sys.stderr)
            return 1
        size_kb = dest.stat().st_size // 1024
        print(f"  saved          {dest.name:20s}  {size_kb}KB")
        time.sleep(2)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
