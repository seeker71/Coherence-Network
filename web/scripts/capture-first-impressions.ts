/**
 * Capture mobile screenshots of the first five pages a cold visitor
 * walks through. No logged-in state, no localStorage seeded, no
 * cookies — exactly what a brand-new phone meets.
 *
 *   ANA_WALK_BASE_URL=https://coherencycoin.com npx ts-node web/scripts/capture-first-impressions.ts
 *
 * Writes to web/public/stories/first-impressions/*.png.
 */

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE = process.env.ANA_WALK_BASE_URL || "https://coherencycoin.com";
const OUT_DIR = path.resolve(__dirname, "..", "public", "stories", "first-impressions");

const VIEWPORT = { width: 390, height: 844 };
const DEVICE_SCALE = 2;

interface Shot {
  name: string;
  url: string;
  settleMs?: number;
  scrollY?: number;
}

const SHOTS: Shot[] = [
  // 1. Home — the landing. Top of fold.
  { name: "01-home-top.png", url: "/", settleMs: 3500 },
  // 2. Home — second screen (scroll past hero)
  { name: "02-home-scroll.png", url: "/", settleMs: 3500, scrollY: 800 },
  // 3. Vision — when they tap "Vision" in the nav
  { name: "03-vision.png", url: "/vision", settleMs: 4000 },
  // 4. Walk a concept — the concept page they'd land on
  { name: "04-meet-concept.png", url: "/vision/lc-pulse", settleMs: 4000 },
  // 5. Feed — the felt pulse
  { name: "05-feed.png", url: "/feed", settleMs: 3500 },
  // 6. Here — the attention map
  { name: "06-here.png", url: "/here", settleMs: 3500 },
  // 7. Explore — the walk
  { name: "07-explore.png", url: "/explore/concept", settleMs: 4000 },
];

async function runShot(context: BrowserContext, shot: Shot): Promise<void> {
  const page: Page = await context.newPage();
  const url = BASE + shot.url;
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    try {
      await page.waitForLoadState("networkidle", { timeout: 20000 });
    } catch {
      /* settleMs is enough */
    }
    if (shot.scrollY) {
      await page.evaluate((y) => window.scrollTo(0, y), shot.scrollY);
    }
    await page.waitForTimeout(shot.settleMs ?? 1500);
    const outPath = path.join(OUT_DIR, shot.name);
    await page.screenshot({ path: outPath, fullPage: false });
    console.log(`  captured ${shot.name} <- ${url}`);
  } finally {
    await page.close();
  }
}

async function main(): Promise<void> {
  if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  }
  const browser: Browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      viewport: VIEWPORT,
      deviceScaleFactor: DEVICE_SCALE,
      userAgent:
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
      ignoreHTTPSErrors: true,
      locale: "en-US",
    });
    for (const shot of SHOTS) {
      await runShot(context, shot);
    }
    await context.close();
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
