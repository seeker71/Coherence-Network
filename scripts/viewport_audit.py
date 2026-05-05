#!/usr/bin/env python3
"""Audit a list of URLs at desktop (1440x900) and mobile (390x844) widths.

Saves screenshots to output/viewport-audit/{path-slug}-{width}.png so a
human (or another agent) can scan both viewport renderings side-by-side.
Uses Playwright (already a dev dep) so no network setup needed.

Usage:
    python3 scripts/viewport_audit.py [path1] [path2] ...
    python3 scripts/viewport_audit.py --base https://coherencycoin.com /come-in /silence

Default base is http://localhost:3002. With no paths, audits the
welcoming-flow surfaces.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

DEFAULT_PATHS = [
    "/",
    "/come-in",
    "/one-sheet",
    "/silence",
    "/silence/built",
    "/silence/breath",
    "/with-us",
    "/begin",
    "/share",
    "/me/work",
    "/practice",
    "/people/contributor%3Aactualize-earth-4d812a0238eb",
]
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "viewport-audit"


def slugify(path: str) -> str:
    return path.strip("/").replace("/", "-").replace("%", "_") or "home"


async def shoot(base: str, paths: list[str]) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Playwright not available. Install with `pip install playwright` "
            "and `playwright install chromium`.",
            file=sys.stderr,
        )
        sys.exit(2)

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for label, viewport in [
            ("desktop", {"width": 1440, "height": 900}),
            ("mobile", {"width": 390, "height": 844}),
        ]:
            ctx = await browser.new_context(viewport=viewport)
            page = await ctx.new_page()
            for path in paths:
                url = f"{base.rstrip('/')}{path}"
                slug = slugify(path)
                out = OUT / f"{slug}-{label}.png"
                try:
                    await page.goto(url, wait_until="networkidle", timeout=20000)
                    await page.screenshot(path=str(out), full_page=False)
                    print(f"  ✓ {label:7s} {path}  → {out.relative_to(ROOT)}")
                except Exception as e:
                    print(f"  ✗ {label:7s} {path}  {e}")
            await ctx.close()
        await browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3002")
    ap.add_argument("paths", nargs="*", default=DEFAULT_PATHS)
    args = ap.parse_args()
    print(f"Auditing {len(args.paths)} paths at {args.base}")
    asyncio.run(shoot(args.base, args.paths))
    print(f"\nScreenshots saved to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
