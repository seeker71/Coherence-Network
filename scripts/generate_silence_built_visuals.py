#!/usr/bin/env python3
"""Generate the compound-vision images for /silence/built via Pollinations.

Renders six views of the Brahmavihara mandala compound — aerial, entry,
sea-side, council interior, commons interior, dawn nest — using the same
deterministic Pollinations URL pattern the rest of the KB uses.

Usage:
    python3 scripts/generate_silence_built_visuals.py [--force]
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
        "slug": "aerial",
        "seed": 4204,
        "width": 1280,
        "height": 1280,
        "prompt": (
            "aerial top-down view of a tropical Balinese sacred compound, "
            "eight-petal mandala layout, central round pavilion with conical alang-alang thatched roof, "
            "eight small bamboo bales at cardinal points around it, long open pavilion on the south side, "
            "lush tropical gardens between the buildings, lotus pond, frangipani trees, banana, "
            "stone path arcs forming six garden rooms, parcel near a beach, deep green jungle around, "
            "soft afternoon sunlight, photorealistic architectural photography, drone view, no text"
        ),
    },
    {
        "slug": "entry",
        "seed": 4205,
        "width": 1280,
        "height": 768,
        "prompt": (
            "ground level view walking up to a traditional Balinese compound gate, "
            "carved paras stone gate with white and yellow striped umbrella, padmasana lotus shrine, "
            "frangipani trees lining the path, alang-alang thatched roofs visible beyond, "
            "tropical north Bali, late afternoon golden light, photorealistic, no text"
        ),
    },
    {
        "slug": "sea-side",
        "seed": 4206,
        "width": 1280,
        "height": 768,
        "prompt": (
            "view from a grass lawn looking north toward an open Balinese pavilion, "
            "long low bamboo and alang-alang thatched bale stretching across the frame, "
            "deep eaves, polished coconut wood floor, conical roof of a council pavilion rising behind, "
            "single old tamarind tree, ocean breeze, tropical garden, north Bali coast, "
            "soft sea light, photorealistic architectural photography, no text"
        ),
    },
    {
        "slug": "council-interior",
        "seed": 4207,
        "width": 1280,
        "height": 1280,
        "prompt": (
            "interior of a round Balinese council pavilion, looking up into a high conical "
            "alang-alang thatched roof, eight giant bamboo posts around the perimeter, "
            "small oculus at the apex letting in natural light, ring of carved paras stone seats, "
            "central black lava stone fire pit with low embers, woven bamboo, "
            "soft incense smoke, photorealistic architectural photography, no text"
        ),
    },
    {
        "slug": "commons-interior",
        "seed": 4208,
        "width": 1280,
        "height": 768,
        "prompt": (
            "long open Balinese pavilion interior at evening, polished coconut wood floor, "
            "alang-alang thatched roof on tabah bamboo trusses overhead, woven gedeg bamboo screens, "
            "stone hearth and earth oven at one end, hanging baskets of garlic and herbs, "
            "scattered woven mats and cushions, low oil lamps, jasmine vines climbing posts, "
            "warm golden interior light, garden visible through open south side, "
            "photorealistic architectural photography, no text"
        ),
    },
    {
        "slug": "nest-dawn",
        "seed": 4209,
        "width": 1024,
        "height": 1280,
        "prompt": (
            "small private Balinese sleeping bale at dawn, raised one foot off the earth on ironwood feet, "
            "sliding woven bamboo gedeg screens, sleeping platform with thick kapok mattress, "
            "white mosquito netting hanging like a soft cloud, frangipani branches above, "
            "jasmine vines on the threshold, alang-alang thatched roof, tropical garden, "
            "first light coming through, photorealistic architectural photography, no text"
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
