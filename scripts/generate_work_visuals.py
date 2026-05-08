#!/usr/bin/env python3
"""Generate hero images for works (asset nodes with creation_kind).

Mirrors the concept-visuals pipeline at scripts/generate_visuals.py but
for assets. For each asset with `creation_kind` and `slug` set, builds
a Pollinations prompt from the asset's fields (name + era +
creation_kind + substrate when present), downloads a square emblem,
and saves to web/public/works/generated/{slug}.jpg.

The web tile then resolves via convention — fetchCreations falls back
to /works/generated/{slug}.jpg when the asset has no explicit
image_url. No graph PATCH required; the image lives where the file
lands.

Per-work prompt overrides live inline in PROMPT_OVERRIDES. The default
prompt template is generic enough that new works get a reasonable
emblem on first generation; specific works can be tuned by adding an
override entry.

Usage:
    python3 scripts/generate_work_visuals.py                    # production API
    python3 scripts/generate_work_visuals.py --api-url http://localhost:8000
    python3 scripts/generate_work_visuals.py --dry-run          # print prompts only
    python3 scripts/generate_work_visuals.py --force            # regenerate all
    python3 scripts/generate_work_visuals.py --slug c64-midi-interface  # one work
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "web" / "public" / "works" / "generated"
DEFAULT_API = "https://api.coherencycoin.com"

# A square thumbnail size — large enough that web/CSS can downscale
# cleanly to the 200×200 tile and the 600×600 detail-page hero.
WIDTH = 768
HEIGHT = 768

# Default style suffix appended to every prompt. Steers Pollinations
# toward an emblem that reads at thumbnail scale: single focal point,
# dark background, glowing accent, no text. The era-tinted gradient
# already lives behind the image, so the image itself wants to feel
# emblematic rather than scenic.
STYLE_SUFFIX = (
    "minimal symbolic emblem, single focal point, deep dark background "
    "with subtle glow, abstract geometric, no text, no words, no labels, "
    "square composition, technical illustration, retro-futurist palette"
)

# Per-slug prompt overrides. Empty by default — when a work's
# auto-generated prompt yields a poor emblem, paste a tuned prompt
# here keyed by slug. The override completely replaces the auto
# prompt (style suffix is still appended).
PROMPT_OVERRIDES: dict[str, str] = {
    "c64-midi-interface": (
        "five-pin DIN MIDI connector glowing on a vintage 8-bit "
        "circuit board, retro-futurist illustration"
    ),
    "schindler-hc11-protocol": (
        "elevator silhouette with luminous binary protocol lines "
        "flowing between floors, technical schematic"
    ),
    "bmf-grammar": (
        "three concentric geometric ring symbols floating in dark "
        "space — BMF, BMA, BMO trio — golden glow"
    ),
    "bml-language": (
        "self-referential infinity loop made of glowing source code "
        "tokens, abstract emblem"
    ),
    "bmcpu-vm": (
        "abstract CPU schematic with bidirectional DO and UNDO arrows "
        "showing speculation cycle, technical illustration in deep blue"
    ),
    "jbmf-java": (
        "two parallel concentric lattices sharing a single central "
        "source — C++ and Java substrates — symmetric emblem"
    ),
    "backtracking-model-languages": (
        "decision tree with one branch walking backward, the path "
        "luminous against dark academic background"
    ),
    "quark-mono-corba": (
        "two columns linked by a glowing bridge — one labeled Java, "
        "one labeled C++ — abstract software-systems emblem"
    ),
    "quark-multi-undo-redo": (
        "stacked horizontal layers depicting an undo history, each "
        "layer translucent and glowing, time arrow on the side"
    ),
    "quark-virtual-dom": (
        "two nested tree diagrams with a diff-arrow between them, "
        "abstract data-structure emblem"
    ),
    "mindtouch-wiki-in-a-box": (
        "interconnected document nodes forming a luminous web inside "
        "a glowing box, knowledge-graph emblem"
    ),
    "trimble-glue-layer": (
        "two arrows of independent cadence aligning at a wire-optimal "
        "junction, surveying-instrument aesthetic"
    ),
    "qualcomm-hdmi-hdcp": (
        "padlock fused with a display panel, encrypted-data streams "
        "glowing through hardware, kernel-driver aesthetic"
    ),
    "qualcomm-test-automation": (
        "automated checklist with luminous gears spinning behind it, "
        "industrial test-rig aesthetic"
    ),
    "living-resonance-codex": (
        "eight-stage spiral arc unfolding from EMERGENT to DIVINE, "
        "consciousness-architecture emblem, deep amber and indigo"
    ),
    "living-codex-csharp": (
        "central hub with radiating spokes — Everything is a Node — "
        "U-CORE primitive emblem, network-topology illustration"
    ),
    "coherence-network": (
        "five-tier architecture stack with luminous edges connecting "
        "every layer, living-network emblem, mature green and gold"
    ),
}


def http_get_json(url: str) -> Any:
    # The Cloudflare layer in front of api.coherencycoin.com 403s the
    # default urllib UA; set a real-looking one. Same trick the other
    # KB-sync scripts use.
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "coherence-network-works-visuals/1.0 (script)",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        import json
        return json.loads(resp.read().decode("utf-8"))


def fetch_works(api_url: str) -> list[dict[str, Any]]:
    """Pull all assets that look like works (have creation_kind + slug).

    The /api/assets endpoint returns paginated lists. We walk pages
    until empty; in practice the seeker71 cohort is ~17 works, so one
    page covers it. Future contributors expand this naturally.
    """
    works: list[dict[str, Any]] = []
    offset = 0
    page = 100
    while True:
        url = f"{api_url}/api/assets?limit={page}&offset={offset}"
        data = http_get_json(url)
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        for item in items:
            slug = item.get("slug")
            kind = item.get("creation_kind")
            if slug and kind:
                works.append(item)
        if len(items) < page:
            break
        offset += page
    return works


def build_prompt(work: dict[str, Any]) -> str:
    """Compose a Pollinations prompt for a single work.

    Override-first: if PROMPT_OVERRIDES carries a tuned prompt for this
    slug, use it. Otherwise fall through to a template that pulls the
    asset's own self-description from name + creation_kind + era.
    """
    slug = work.get("slug", "")
    if slug in PROMPT_OVERRIDES:
        return f"{PROMPT_OVERRIDES[slug]}, {STYLE_SUFFIX}"

    name = (work.get("name") or "").split("—")[0].strip()
    kind = (work.get("creation_kind") or "work").replace("-", " ")
    era = work.get("era") or ""
    parts = [
        f"emblem for {name}",
        f"a {kind}",
    ]
    if era:
        parts.append(f"era: {era[:60]}")
    parts.append(STYLE_SUFFIX)
    return ", ".join(parts)


def pollinations_url(prompt: str, seed: int) -> str:
    encoded = urllib.parse.quote(prompt)
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={WIDTH}&height={HEIGHT}&model=flux&nologo=true&seed={seed}"
    )


def slug_seed(slug: str) -> int:
    """Deterministic seed from slug — same image every regeneration."""
    return sum(ord(c) for c in slug)


def download(url: str, dest: Path, retries: int = 4, min_bytes: int = 5000) -> bool:
    """Fetch a Pollinations image with simple retry/backoff.

    Pollinations occasionally serves a sub-1KB error page or times out
    while warming flux; the retry loop survives both. min_bytes guards
    against empty/error responses being committed as real images.
    """
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "coherence-network-works-visuals/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                blob = resp.read()
            if len(blob) < min_bytes:
                raise ValueError(f"response too small ({len(blob)}b)")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            return True
        except Exception as exc:
            wait = 3 * attempt
            print(f"    attempt {attempt}/{retries} failed ({exc}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default=DEFAULT_API)
    p.add_argument("--dry-run", action="store_true",
                   help="print prompts and target paths; download nothing")
    p.add_argument("--force", action="store_true",
                   help="regenerate even if the file already exists")
    p.add_argument("--slug", action="append", default=[],
                   help="restrict to one or more slugs (repeatable)")
    p.add_argument("--all-works", action="store_true",
                   help="generate for every asset with creation_kind, not just the "
                        "hand-tuned PROMPT_OVERRIDES set (default: overrides only)")
    args = p.parse_args()

    print(f"Fetching works from {args.api_url} ...")
    works = fetch_works(args.api_url)
    if args.slug:
        wanted = set(args.slug)
        works = [w for w in works if w.get("slug") in wanted]
    elif not args.all_works:
        # Default: only the hand-tuned set. Other works fall back to
        # the era-tinted gradient until someone hand-tunes a prompt.
        works = [w for w in works if w.get("slug") in PROMPT_OVERRIDES]
    print(f"  {len(works)} work(s) to consider")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0
    skipped = 0
    failed: list[str] = []

    for work in works:
        slug = work["slug"]
        dest = OUTPUT_DIR / f"{slug}.jpg"
        if dest.exists() and not args.force:
            skipped += 1
            continue

        prompt = build_prompt(work)
        seed = slug_seed(slug)
        url = pollinations_url(prompt, seed)
        rel = dest.relative_to(REPO_ROOT)

        if args.dry_run:
            print(f"  [{slug}]")
            print(f"    prompt: {prompt[:120]}{'...' if len(prompt) > 120 else ''}")
            print(f"    → {rel}")
            continue

        print(f"  [{slug}] generating ...")
        ok = download(url, dest)
        if ok:
            print(f"    → {rel} ({dest.stat().st_size // 1024} KB)")
            generated += 1
        else:
            print(f"    × failed after retries")
            failed.append(slug)

    print()
    print(f"Generated: {generated}  Skipped (already present): {skipped}  Failed: {len(failed)}")
    if failed:
        print("  failed slugs:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
