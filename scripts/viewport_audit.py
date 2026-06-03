#!/usr/bin/env python3
"""Audit a list of URLs at desktop (1440x900) and mobile (390x844) widths.

Saves screenshots to output/viewport-audit/{path-slug}-{width}.png AND reports
responsive-health signals per page+width so the looking isn't left entirely to
a human opening 16 PNGs:
  - horizontal overflow: the widest element extending past the viewport (the
    mobile-cutoff failure mode). "NONE" when nothing overflows.
  - content width: how much horizontal space `main` uses (the "wasted 1000px
    narrow column on desktop" failure mode CLAUDE.md names — content_w far
    below the viewport on desktop is the smell).
A small overflow on desktop is often an intentional full-bleed hero image, not
a bug — the screenshot is still captured so the eye can judge benign-vs-broken.

Wait strategy: `domcontentloaded` + a short settle, NOT `networkidle`. A live
organism page (witness polling, live metrics, streaming counts) never reaches
network-idle, so `networkidle` times out on every page even though it renders
fine. domcontentloaded+settle is the correct wait for a live-data surface.

Uses Playwright. If not importable in a PEP-668 externally-managed env, install
into a venv: `python3 -m venv .venv-audit && .venv-audit/bin/pip install
playwright && .venv-audit/bin/python -m playwright install chromium`, then run
with that interpreter.

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
    "/vision",   # the concept list — where the living KB reaches visitors
    "/people",   # the presences / contributors index
    "/ideas",    # the ideas index
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
    "/substrate",
    "/portfolio/investments",
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
    findings: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for label, viewport in [
            ("desktop", {"width": 1440, "height": 900}),
            ("mobile", {"width": 390, "height": 844}),
        ]:
            w = viewport["width"]
            ctx = await browser.new_context(viewport=viewport)
            page = await ctx.new_page()
            for path in paths:
                url = f"{base.rstrip('/')}{path}"
                slug = slugify(path)
                out = OUT / f"{slug}-{label}.png"
                try:
                    # domcontentloaded + settle, NOT networkidle: a live-data page
                    # (witness polling, live metrics) never reaches network-idle.
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2500)
                    # widest element extending past the viewport (mobile-cutoff smell)
                    overflow = await page.evaluate(
                        "(w) => { let m = 0; for (const el of document.querySelectorAll('*')) {"
                        " const r = el.getBoundingClientRect();"
                        " if (r.right > w + 2 && r.width > 0 && getComputedStyle(el).overflow !== 'hidden')"
                        " m = Math.max(m, Math.round(r.right)); } return m; }",
                        w,
                    )
                    # horizontal space `main` actually uses (wasted-narrow-column smell on desktop)
                    content_w = await page.evaluate(
                        "() => { const m = document.querySelector('main') || document.body;"
                        " return Math.round(m.getBoundingClientRect().width); }"
                    )
                    await page.screenshot(path=str(out), full_page=False)
                    ov = "NONE" if overflow <= w + 2 else f"{overflow}px"
                    print(f"  ✓ {label:7s} {path:32s} overflow={ov:8s} content_w={content_w}  → {out.relative_to(ROOT)}")
                    if overflow > w + 2:
                        findings.append(f"{label} {path}: element overflows to {overflow}px (viewport {w}) — check {out.name} (often an intentional full-bleed image)")
                    if label == "desktop" and content_w < w * 0.7:
                        findings.append(f"desktop {path}: main content only {content_w}px of {w} — possible wasted desktop width")
                except Exception as e:
                    print(f"  ✗ {label:7s} {path}  {str(e)[:70]}")
                    findings.append(f"{label} {path}: FAILED to load/render — {str(e)[:60]}")
            await ctx.close()
        await browser.close()

    print()
    if findings:
        print("Responsive-health signals worth a look (open the screenshot to judge benign-vs-bug):")
        for f in findings:
            print(f"  · {f}")
    else:
        print("Responsive-health: no overflow or wasted-width signals — pages whole at both widths.")


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
