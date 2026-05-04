#!/usr/bin/env python3
"""Generate the design-log iteration: sketch → plan → section → detail → axon → photoreal.

Eleven rounds tracing the architectural iteration, each prompt rebuilt from
careful reading of the page-8 sketch geometry: four corner dome-bales, six
intersecting petal arcs, eight cardinal nest points, central beaded ring with
council pavilion at the heart, three named axes, oriented with road on north,
ocean on south, deep jungle on west.

Usage:
    python3 scripts/generate_silence_design_log.py [--force] [--only N]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kb_common import download_image, pollinations_url

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "web" / "public" / "silence" / "2026-05-04-brahmavihara" / "design-log"


GEOMETRY_NOTE = (
    "Mandala geometry, render precisely: rectangular parcel; at TOP of frame a road "
    "(north, Vitality axis) lined with frangipani; at BOTTOM the ocean and white sand "
    "beach (south, Harmony axis); at LEFT deep jungle (west, Organic Intelligence axis); "
    "at RIGHT four existing rectangular villas. The mandala fills the western half. "
    "FOUR large round bale-agung pavilions at the four corners of the mandala square (NW, NE, SW, SE), "
    "each with wide hipped alang-alang thatched roof. Between them, SIX curving stone path arcs "
    "intersect to form a six-petal flower pattern; each petal is one garden room (lotus pond, "
    "fruit forest, kitchen herbs, medicine garden, frangipani offering garden, fern stillness garden). "
    "EIGHT small identical Balinese bale-dauh sleeping pavilions at the eight cardinal points "
    "(N, NE, E, SE, S, SW, W, NW) along the inner radius. AT THE EXACT CENTER a circular ring of "
    "eight low cylindrical paras-stone seats like a beaded necklace, and inside that ring at the "
    "very center one round council pavilion with a tall conical alang-alang thatched roof and a "
    "small oculus at the apex. Along the southern edge between mandala and lawn, ONE long "
    "rectangular bale-agung commons pavilion running east-west."
)


ROUNDS = [
    {
        "n": 1,
        "slug": "01-plan-sketch",
        "seed": 5101,
        "width": 1280,
        "height": 1280,
        "intent": "Architectural plan drawing — first sketch pass, faithful to the notebook geometry",
        "prompt": (
            "Hand-drawn architectural plan drawing of a sacred Balinese compound, ink on cream paper, "
            "delicate line work, careful crosshatching. Top-down plan view. "
            + GEOMETRY_NOTE +
            " Show the structures as outlined plan footprints, label each with elegant handwritten "
            "annotations: 'council pavilion', 'nest 1', 'nest 2'... 'corner bale NW'... 'commons', "
            "'lotus pond', 'frangipani garden', 'Vitality', 'Harmony', 'Organic Intelligence'. "
            "Compass rose in the upper right corner with N pointing up. "
            "Style: architect Geoffrey Bawa hand-drawn site plan + Ibuku design notebook page. "
            "Sharp ink, no color, no photographs, no people. --ar 1:1 --style raw --v 7"
        ),
    },
    {
        "n": 2,
        "slug": "02-plan-refined",
        "seed": 5102,
        "width": 1280,
        "height": 1280,
        "intent": "Refined plan with material labels and dimensions",
        "prompt": (
            "Hand-drawn architectural plan drawing on cream paper, second iteration with material "
            "annotations. Top-down view of the same Balinese sacred compound. "
            + GEOMETRY_NOTE +
            " This time add to the existing line drawing: dimension lines with measurements in meters "
            "(council pavilion 8m diameter, nests 4m square, corner domes 6m diameter, commons "
            "30m x 8m), and material call-outs in elegant handwriting: 'alang-alang thatch', "
            "'tabah bamboo posts', 'paras stone seats', 'coconut wood floor', 'lava stone fire pit', "
            "'lotus pond - black liner + reed bed', 'paras path arcs'. Compass rose, scale bar at "
            "1:200, north arrow. Light pencil shading on building roofs. Style: detailed architectural "
            "site plan, Geoffrey Bawa working drawing, Ibuku Green Village construction documents. "
            "Cream paper, brown ink, no color, no photographs, no people. --ar 1:1 --style raw --v 7"
        ),
    },
    {
        "n": 3,
        "slug": "03-section-EW",
        "seed": 5103,
        "width": 1600,
        "height": 768,
        "intent": "East–West cross-section through the council pavilion and two flanking nests",
        "prompt": (
            "Hand-drawn architectural building section drawing, east-west cut through a Balinese "
            "sacred compound, ink on cream paper, careful hatching. From left to right the section "
            "shows: (1) a corner dome-bale at far west, (2) a small bale-dauh nest, (3) the central "
            "ring of paras stone seats with the round council pavilion rising above (conical "
            "alang-alang roof, 9 meters tall, oculus at apex with light rays drawn descending), "
            "(4) another small bale-dauh nest east, (5) a corner dome-bale at far east. Below "
            "ground line, show ironwood footings and reed-bed greywater under one petal. Above each "
            "structure show roof construction layers labeled: 'alang-alang grass thatch 100mm', "
            "'bamboo battens', 'tabah bamboo trusses lashed with rattan', 'petung bamboo king post'. "
            "Tropical canopy of coconut palms drawn in light ink at edges. Human figures for scale "
            "(simple silhouettes). Compass orientation indicator E-W. Style: architectural "
            "construction section, ink on paper, Auroville Earth Institute drawing style + "
            "Geoffrey Bawa pencil section. Sharp ink, no color, no photographs. "
            "--ar 16:9 --style raw --v 7"
        ),
    },
    {
        "n": 4,
        "slug": "04-section-NS",
        "seed": 5104,
        "width": 1600,
        "height": 768,
        "intent": "North–South section showing the parcel slope and the long commons bale",
        "prompt": (
            "Hand-drawn architectural building section drawing, north-south cut through a Balinese "
            "sacred compound, ink on cream paper. From left (north) to right (south) the section "
            "shows: (1) frangipani trees on the road edge (Vitality axis), (2) the carved paras "
            "stone candi bentar split-gate, (3) a small bale-dauh nest, (4) the central ring of "
            "paras stone seats with the round council pavilion above (conical alang-alang roof, "
            "oculus at apex), (5) another small bale-dauh nest, (6) the long commons bale-agung "
            "running east-west cutting across the section, (7) open lawn falling gently toward "
            "the south, (8) the white sand beach and ocean (Harmony axis). Show subtle ground "
            "slope falling 2 meters from north to south across 60 meters. Label structures and "
            "axes. Roof material layers labeled. Style: architectural section drawing, "
            "Auroville + Geoffrey Bawa style, ink hatching, no color, no photographs. "
            "--ar 16:9 --style raw --v 7"
        ),
    },
    {
        "n": 5,
        "slug": "05-detail-bamboo-joint",
        "seed": 5105,
        "width": 1024,
        "height": 1280,
        "intent": "Material detail — bamboo + alang-alang structural joint",
        "prompt": (
            "Hand-drawn architectural detail drawing, ink on cream paper, close-up study of a "
            "structural joint in a traditional Balinese alang-alang thatched roof. Show the joint "
            "where a tabah bamboo king-post meets the rafter trusses: bamboo lashed together "
            "with split rattan in a traditional ikatan pattern, with carved hardwood pegs through "
            "the bamboo nodes. Above the joint: layered alang-alang grass thatch shown in cross "
            "section, individual blades drawn carefully, multiple thin layers totaling 100mm, the "
            "outer surface weathered silver-grey, inner surface honey-brown. Below the joint: a "
            "bird's-nest fern (Asplenium nidus) growing from the corner of the bamboo. Annotations "
            "in elegant handwriting label each material: 'tabah bamboo king post 150mm dia', "
            "'rattan split-binding wrapped 8 turns', 'hardwood peg 12mm dia', 'alang-alang grass "
            "thatch in 5 layers', 'bird's-nest fern (Asplenium nidus) — encouraged to grow'. "
            "Scale bar in centimeters. Style: detailed architectural construction drawing, "
            "Christopher Alexander A Pattern Language detail + Bambu Indah construction notes. "
            "Cream paper, brown ink, light pencil, no photographs, no people. "
            "--ar 4:5 --style raw --v 7"
        ),
    },
    {
        "n": 6,
        "slug": "06-detail-paras-stone",
        "seed": 5106,
        "width": 1024,
        "height": 1280,
        "intent": "Material detail — paras stone seat carving",
        "prompt": (
            "Hand-drawn architectural detail drawing, ink on cream paper, study of a single "
            "carved paras-yogya volcanic limestone seat from the central council ring. Show the "
            "seat in three views: (1) plan view from above showing a circular top with a carved "
            "lotus relief in low bas-relief, (2) elevation showing a cylindrical base 450mm high, "
            "350mm diameter, with carved frangipani and curving lines wrapping around, "
            "(3) section showing the stone is solid, with annotations on quarrying and finishing. "
            "Annotations in elegant handwriting: 'paras-yogya stone (volcanic limestone)', "
            "'carved by local Bali stone-carver from Tulamben', '400 kg', 'eight identical seats "
            "form the central ring', 'lotus carving on top', 'frangipani relief on side'. "
            "Light pencil shading on the stone surfaces. Scale bar. Style: heritage architectural "
            "documentation, Pura Beji carving studies, Christopher Alexander pattern detail. "
            "Cream paper, brown ink, no photographs, no people. --ar 4:5 --style raw --v 7"
        ),
    },
    {
        "n": 7,
        "slug": "07-axonometric",
        "seed": 5107,
        "width": 1280,
        "height": 1280,
        "intent": "Axonometric three-quarter view — show massing and arrangement",
        "prompt": (
            "Hand-drawn architectural axonometric drawing, three-quarter aerial view from the "
            "northeast looking southwest, ink on cream paper. " + GEOMETRY_NOTE + " "
            "Show all the structures in 30-degree axonometric projection with no perspective "
            "distortion. Each roof rendered with its alang-alang grass texture cross-hatched. "
            "Bamboo posts visible under the roofs as parallel verticals. The lotus pond shown "
            "with rippled hatching. Stone path arcs visible. Trees rendered as stylized canopy "
            "blobs with a few trunk lines. Compass rose in upper right. Style: Geoffrey Bawa "
            "axonometric site drawing + Ibuku presentation drawing + Lebbeus Woods technical "
            "ink work. Sharp ink, light pencil shading, no color, no photographs, no people. "
            "--ar 1:1 --style raw --v 7"
        ),
    },
    {
        "n": 8,
        "slug": "08-aerial-photoreal",
        "seed": 5108,
        "width": 1280,
        "height": 1280,
        "intent": "Photoreal aerial — translate the design back into a photograph",
        "prompt": (
            "Top-down aerial drone photograph of a real built sacred Balinese compound at golden "
            "hour, photorealistic. " + GEOMETRY_NOTE + " "
            "Late afternoon, sun from the west (left edge of frame), long eastward shadows from "
            "every roof. Late tropical light, warm. Reference: traditional Balinese pekarangan + "
            "Ibuku Green Village + Bambu Indah aerial photography. Photorealistic architectural "
            "drone photography, sharp focus, no text, no watermark, no people. "
            "--ar 1:1 --style raw --v 7"
        ),
    },
    {
        "n": 9,
        "slug": "09-council-photoreal",
        "seed": 5109,
        "width": 1280,
        "height": 1280,
        "intent": "Photoreal interior of the council pavilion with the oculus visible",
        "prompt": (
            "Photorealistic ultra-wide-angle photograph from inside a round Balinese council "
            "pavilion looking up. The conical alang-alang grass thatched roof rises overhead, "
            "supported by eight massive tabah bamboo posts gone honey-amber, lashed at every "
            "node with split rattan. At the apex of the cone, a small circular oculus is open "
            "to bright blue sky, with a clear shaft of warm sunlight descending through it onto "
            "the floor below. Bamboo trusses radiate from the apex outward. At ground level: a "
            "perfect ring of eight low cylindrical paras-stone seats carved with lotus reliefs. "
            "In the exact center: a circular fire pit cut from one block of black lava stone, "
            "low embers glowing red. Open-walled — beyond the eight bamboo posts, a tropical "
            "garden of bamboo grove and palms is visible. Soft ambient light from the sides plus "
            "the strong shaft from the oculus. Reference: Ibuku Mepantigan + traditional joglo "
            "pendopo. Photorealistic architectural interior, sharp focus, 14mm ultra-wide-angle, "
            "no text, no watermark, no people. --ar 1:1 --style raw --v 7"
        ),
    },
    {
        "n": 10,
        "slug": "10-nest-photoreal",
        "seed": 5110,
        "width": 1024,
        "height": 1280,
        "intent": "Photoreal nest exterior at dawn — empty bed, mosquito net cloud, jasmine threshold",
        "prompt": (
            "Photorealistic architectural exterior photograph of a small traditional Balinese "
            "sleeping bale at dawn. The bale is raised exactly one foot off the earth on four "
            "short ironwood pillar feet. Roughly 4 meters by 3 meters, with an open south face, "
            "three sides of sliding gedeg woven-bamboo screens partly open. INSIDE on a low "
            "platform, EMPTY: a thick kapok mattress dressed in unbleached white cotton, NO PERSON "
            "in or near the bed, four pillows of natural linen. Hanging from the central bamboo "
            "ridge beam: a single white mosquito net falling in a soft elliptical cloud-shape over "
            "the platform, gathered loosely at the corners, nearly translucent. The roof is hipped "
            "alang-alang grass, deep eaves, golden-brown. Bamboo posts at the corners are wrapped "
            "in flowering jasmine vines. A frangipani tree above drops white-and-yellow flowers "
            "onto the bale's roof. Threshold: two paras stone steps with white frangipani flowers "
            "scattered. Soft pink-gold dawn light from the right. Garden visible: bird's-nest "
            "ferns, alocasia, dewy grass. Reference: Bambu Indah Bali + traditional Balinese "
            "gladag bale. Photorealistic architectural photography, sharp focus, dawn lighting, "
            "EMPTY BED, no text, no watermark, NO PEOPLE in the entire image. "
            "--ar 4:5 --style raw --v 7"
        ),
    },
    {
        "n": 11,
        "slug": "11-commons-photoreal",
        "seed": 5111,
        "width": 1600,
        "height": 768,
        "intent": "Photoreal long commons bale — show the full 30m length with deep perspective",
        "prompt": (
            "Photorealistic architectural interior photograph of a long open Balinese bale-agung "
            "pavilion at evening, camera positioned at the eastern end on the floor at human-eye "
            "level looking west through the entire 30-meter length, deep one-point perspective "
            "with strong vanishing point at the far end. Polished coconut wood floor extends into "
            "the distance. Above: alang-alang grass thatched ceiling on twelve visible tabah "
            "bamboo trusses lashed with rattan, ceiling 5 meters high. South side: open, twelve "
            "bamboo posts spaced evenly, dark tropical garden beyond with fireflies and lotus "
            "pond hints. North side: half-closed gedeg sliding bamboo screens. Halfway down: "
            "three woven pandanus mats laid out, low cushions, a small pile of frame drums and "
            "one bamboo flute. At the far western end small in the distance: a stone hearth with "
            "earth oven built into a low wall, hanging baskets of garlic and chilies and dried "
            "medicinal herbs. Hanging Balinese woven-rattan lamp shades cast warm pools of golden "
            "light. Jasmine vines climb several south-side posts. Reference: Ibuku Heart of School "
            "Green School + traditional Balinese wantilan. Photorealistic architectural interior, "
            "deep one-point perspective, sharp focus, no text, no watermark, no people. "
            "--ar 16:9 --style raw --v 7"
        ),
    },
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="re-download even if files exist")
    p.add_argument("--only", type=int, default=None, help="generate only round N")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rounds = ROUNDS if args.only is None else [r for r in ROUNDS if r["n"] == args.only]

    for view in rounds:
        dest = OUT_DIR / f"{view['slug']}.jpg"
        if dest.exists() and not args.force:
            print(f"  skip (exists)  {dest.name}")
            continue
        url = pollinations_url(
            view["prompt"], seed=view["seed"],
            width=view["width"], height=view["height"],
        )
        print(f"  R{view['n']:02d} fetching   {view['slug']:30s}  ({view['width']}x{view['height']})")
        ok = download_image(url, dest)
        if not ok:
            print(f"    FAILED: {view['slug']}", file=sys.stderr)
            return 1
        size_kb = dest.stat().st_size // 1024
        print(f"  R{view['n']:02d} saved      {dest.name:30s}  {size_kb}KB")
        time.sleep(2)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
