#!/usr/bin/env python3
"""V2 iteration — push harder on the two weakest rounds (plan + aerial)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kb_common import download_image, pollinations_url

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "web" / "public" / "silence" / "2026-05-04-brahmavihara" / "design-log"

VIEWS = [
    {
        "slug": "02b-plan-refined-v2",
        "seed": 5202,
        "width": 1280,
        "height": 1280,
        "prompt": (
            "FLAT TOP-DOWN BLACK INK ARCHITECTURAL FLOOR PLAN on white drafting paper, "
            "no perspective, no color, NO illustration. Pure plan-view of a sacred Balinese mandala compound. "
            "Outer frame: thin black square border representing the parcel boundary. "
            "Inside the parcel, drawn ONLY as 2D top-down outlines: "
            "(1) FOUR identical large circles at the four corners (NW, NE, SW, SE) — these are corner bale dome roofs in plan, each circle has thin radial lines representing thatch ribs; "
            "(2) EIGHT identical small SQUARES placed at the eight cardinal points along the inner radius (N, NE, E, SE, S, SW, W, NW) — these are the small nest bales in plan, each square crossed by a small X; "
            "(3) at the EXACT center, ONE small filled black DOT surrounded by EIGHT tiny circles arranged in a perfect ring — the central beaded seat ring with the council fire at its heart; "
            "(4) curving thin lines forming a SIX-PETAL FLOWER pattern, the petals shaded with very light grey hatching to indicate gardens; "
            "(5) on the south edge, ONE long thin RECTANGLE — the long commons bale in plan; "
            "(6) compass rose with N pointing UP in upper right corner; "
            "(7) scale bar 0-10-20 meters lower left; "
            "(8) clean handwritten dimension lines marking 60m parcel width. "
            "BLACK ink on WHITE paper, drafting style, NO color, NO trees, NO illustration, NO perspective view, "
            "STRICT 2D top-down architectural plan only. Reference: Le Corbusier hand plan, Alvar Aalto plan drawing. "
            "--ar 1:1 --style raw --v 7"
        ),
    },
    {
        "slug": "08b-aerial-photoreal-v2",
        "seed": 5208,
        "width": 1280,
        "height": 1280,
        "prompt": (
            "Aerial drone photograph of a real built tropical Balinese sacred compound, photorealistic, golden hour. "
            "STRICT GEOMETRY visible from above: at the EXACT CENTER of the image, ONE round pavilion with a tall conical alang-alang grass thatched roof and a small dark oculus visible at the apex. "
            "Around it forming a perfect ring: EIGHT identical small bale-dauh sleeping pavilions with hipped alang-alang roofs at the eight cardinal points. "
            "At the four CORNERS of the compound square: FOUR larger round dome-bale pavilions with wide hipped alang-alang roofs. "
            "Curving stone path arcs between the structures form a SIX-PETAL flower pattern with garden rooms in each petal: lotus pond visible as a dark circle of water, fruit forest dense canopy, frangipani in pink-white bloom, low herb garden, fern shade garden, banana grove. "
            "On the SOUTH (BOTTOM of frame): a long rectangular bale-agung commons pavilion with low alang-alang roof, beyond it open lawn and white sand beach with the ocean. "
            "On the NORTH (TOP of frame): a road lined with frangipani trees. "
            "On the EAST (RIGHT of frame): four narrow rectangular existing villas. "
            "On the WEST (LEFT of frame): deep tropical jungle. "
            "Late afternoon, sun from west (left), long eastward shadows. "
            "Reference: Ibuku Green Village aerial drone photography, traditional Balinese pekarangan, Bambu Indah aerial. "
            "Photorealistic drone aerial photography, sharp focus, no text, no watermark, no people, no boats. "
            "--ar 1:1 --style raw --v 7"
        ),
    },
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for view in VIEWS:
        dest = OUT_DIR / f"{view['slug']}.jpg"
        url = pollinations_url(
            view["prompt"], seed=view["seed"],
            width=view["width"], height=view["height"],
        )
        print(f"  fetching   {view['slug']:30s}")
        ok = download_image(url, dest)
        if not ok:
            print(f"    FAILED: {view['slug']}", file=sys.stderr)
            return 1
        size_kb = dest.stat().st_size // 1024
        print(f"  saved      {dest.name:30s}  {size_kb}KB")
        time.sleep(2)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
