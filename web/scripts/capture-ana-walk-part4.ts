/**
 * Capture mobile screenshots for Part 4 of /blog/ana-walks ("What
 * the door now hears back") covering cycles V (push toggle on by
 * default) and W (the /me identity page).
 *
 *   ANA_WALK_BASE_URL=https://coherencycoin.com npx ts-node web/scripts/capture-ana-walk-part4.ts
 *
 * Writes to web/public/stories/ana-walk/19-*.png and 20-*.png.
 */

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE = process.env.ANA_WALK_BASE_URL || "https://coherencycoin.com";
const OUT_DIR = path.resolve(__dirname, "..", "public", "stories", "ana-walk");

const VIEWPORT = { width: 390, height: 844 };
const DEVICE_SCALE = 2;

interface Shot {
  name: string;
  url: string;
  preMount?: string;
  initScript?: string;
  settleMs?: number;
  scrollY?: number;
}

const SHOTS: Shot[] = [
  {
    // Chapter 19: /feed/you with the EnablePush toggle visible.
    // Seed a soft identity so the toggle and surrounding warmth
    // affordances render — and fake "yesterday's last visit" so the
    // SinceLastVisit panel above also shows something.
    name: "19-feed-you-push-toggle-mobile.png",
    url: "/feed/you",
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Mama");
      localStorage.setItem("cc-contributor-id", "mama-local");
      localStorage.setItem("cc-presence-fingerprint", "mama-fp-demo");
      const yesterday = new Date(Date.now() - 18 * 3600 * 1000).toISOString();
      localStorage.setItem("cc-last-visit-at", yesterday);
      document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";
    `,
    initScript: `
      // Force the morning gate (06:00–11:00) so MorningNudge fires too.
      (function() {
        Date.prototype.getHours = function() { return 7; };
        Date.prototype.getMinutes = function() { return 42; };
      })();
    `,
    settleMs: 4500,
    // Scroll just past the FeedTabs so the EnablePush card sits in
    // the upper third of the viewport.
    scrollY: 280,
  },
  {
    // Chapter 20: the /me identity page itself — the new presence
    // surface. Show it for an unnamed visitor first (the empty case
    // is more informative than a populated one for first viewers).
    name: "20-me-unnamed-mobile.png",
    url: "/me",
    preMount: `
      localStorage.clear();
      document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";
    `,
    settleMs: 2500,
  },
  {
    // Chapter 21: the /me page with a graduated identity, showing
    // the footprint prose. Seed fake personal-feed data via cache
    // bypass + use a real contributor id from prod that has activity.
    // We pick "mama-local" — exists from earlier captures.
    name: "21-me-footprint-mobile.png",
    url: "/me",
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Mama");
      localStorage.setItem("cc-contributor-id", "mama-local");
      localStorage.setItem("cc-presence-fingerprint", "mama-fp-demo");
      localStorage.setItem("cc-invited-by", "patrick-local");
      document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";
    `,
    settleMs: 3500,
  },
];

async function runShot(context: BrowserContext, shot: Shot): Promise<void> {
  const page: Page = await context.newPage();
  const url = BASE + shot.url;
  try {
    if (shot.initScript) {
      await page.addInitScript({ content: shot.initScript });
    }
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (shot.preMount) {
      await page.evaluate(shot.preMount);
    }
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
