/**
 * Capture mobile screenshots for the part-two chapters of
 * /blog/ana-walks, straight from coherencycoin.com.
 *
 *   npx playwright test --config=web/playwright.config.ts web/scripts/capture-ana-walk-part2.ts
 *
 * Or standalone (preferred — doesn't depend on test runner):
 *
 *   npx ts-node web/scripts/capture-ana-walk-part2.ts
 *
 * Writes to web/public/stories/ana-walk/*.png.
 */

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import * as fs from "fs";
import * as path from "path";

const BASE = process.env.ANA_WALK_BASE_URL || "https://coherencycoin.com";
const OUT_DIR = path.resolve(__dirname, "..", "public", "stories", "ana-walk");

const VIEWPORT = { width: 390, height: 844 };
const DEVICE_SCALE = 2; // retina

interface Shot {
  name: string;
  url: string;
  /** Optional JS to run after load (simulate state that only exists locally,
   *  e.g. seed localStorage before rendering). */
  preMount?: string;
  /** Wait ms after page ready before snapshotting. */
  settleMs?: number;
  /** Optional scroll position. */
  scrollY?: number;
}

/**
 * For chapters that depend on localStorage state (the invite pre-register,
 * morning nudge, returning-visitor banner), we navigate to a seed URL first,
 * write the right values into localStorage, then reload.
 */
const SHOTS: Shot[] = [
  {
    // Chapter 10: /feed/you showing the new InviteFriend card (name + language selector)
    name: "11-invite-mobile.png",
    url: "/feed/you",
    // Pretend there is a soft identity so the invite card is enabled.
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Patrick");
      localStorage.setItem("cc-contributor-id", "patrick-local");
    `,
    settleMs: 2500,
    scrollY: 600, // scroll down to reveal the InviteFriend card
  },
  {
    // Chapter 11: first arrival as Mama, invited by Patrick, in German
    name: "12-meet-nourishing-welcome-mobile.png",
    url: "/meet/concept/lc-nourishing?from=Patrick&name=Mama&invited_by=patrick-local&lang=de",
    // Clear any prior identity so we hit the first-time branch.
    preMount: `
      localStorage.clear();
    `,
    settleMs: 2500,
  },
  {
    // Chapter 12: after tapping the amber heart, say-something panel unfolds.
    // We can't easily click on a server-rendered page here without Playwright,
    // so we'll capture the same page scrolled to where the gestures and the
    // voice panel would both be visible. Click + wait for the panel.
    name: "13-meeting-gesture-mobile.png",
    url: "/meet/concept/lc-nourishing?from=Patrick&name=Mama&invited_by=patrick-local&lang=de",
    preMount: `
      localStorage.clear();
    `,
    settleMs: 2500,
    // We'll augment the capture flow below to click the amber heart.
  },
  {
    // Chapter 13: the next morning — seed cc-last-visit-at to yesterday
    // so the morning nudge gate passes. Also seed a contributor name.
    name: "14-home-morning-mobile.png",
    url: "/",
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Mama");
      const yesterday = new Date(Date.now() - 18 * 3600 * 1000).toISOString();
      localStorage.setItem("cc-last-visit-at", yesterday);
    `,
    settleMs: 3500, // nudge fetches three endpoints — give it time
  },
];

async function runShot(context: BrowserContext, shot: Shot): Promise<void> {
  const page: Page = await context.newPage();
  const url = BASE + shot.url;
  try {
    // First, navigate to the site origin so we can set localStorage for it.
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
    if (shot.preMount) {
      await page.evaluate(shot.preMount);
    }
    await page.goto(url, { waitUntil: "networkidle", timeout: 45000 });
    if (shot.name === "13-meeting-gesture-mobile.png") {
      // Try to click the amber heart to open the say-something panel.
      // The selector is emoji-text; match the button that contains "💛".
      try {
        const heart = page.locator('button:has-text("💛")').first();
        await heart.waitFor({ state: "visible", timeout: 5000 });
        await heart.click();
        await page.waitForTimeout(1200);
      } catch {
        /* if it fails, we still capture the meeting surface */
      }
    }
    if (shot.scrollY) {
      await page.evaluate((y) => window.scrollTo(0, y), shot.scrollY);
    }
    await page.waitForTimeout(shot.settleMs ?? 1500);
    const outPath = path.join(OUT_DIR, shot.name);
    await page.screenshot({
      path: outPath,
      fullPage: false,
    });
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
