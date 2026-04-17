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
   *  e.g. seed localStorage before rendering). Evaluated on the origin
   *  BEFORE the test URL is loaded — so reads survive the navigation. */
  preMount?: string;
  /** Optional script to inject via Playwright's addInitScript — runs in
   *  every new document, surviving navigations. Use for Date overrides
   *  etc. that must be in place when the page first executes JS. */
  initScript?: string;
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
    scrollY: 1200, // scroll down to reveal the InviteFriend card
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
    // so the morning nudge gate passes. Also pretend the local time
    // is 07:42 so the 06:00–11:00 window matches.
    name: "14-home-morning-mobile.png",
    url: "/",
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Mama");
      localStorage.removeItem("cc-morning-nudge-dismissed");
      const yesterday = new Date(Date.now() - 18 * 3600 * 1000).toISOString();
      localStorage.setItem("cc-last-visit-at", yesterday);
      document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";
    `,
    initScript: `
      // Force Date#getHours to report 07:42 so the morning window gate
      // (06:00–11:00 local) passes regardless of when this script runs.
      // Survives the page navigation because it's an addInitScript.
      (function() {
        const _orig = Date.prototype.getHours;
        Date.prototype.getHours = function() { return 7; };
        const _origMin = Date.prototype.getMinutes;
        Date.prototype.getMinutes = function() { return 42; };
      })();
    `,
    settleMs: 5500,
  },
  {
    // Chapter 14: her personal corner /feed/you next morning. The
    // SinceLastVisit panel + MorningNudge + KinActivity all fire because
    // she has an identity, a prior visit timestamp, and has been gone
    // long enough. She also has a real voice on lc-nourishing from
    // yesterday so PersonalFeed below the fold has something to show.
    name: "15-corner-morning-mobile.png",
    url: "/feed/you",
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Mama");
      localStorage.removeItem("cc-morning-nudge-dismissed");
      const yesterday = new Date(Date.now() - 18 * 3600 * 1000).toISOString();
      localStorage.setItem("cc-last-visit-at", yesterday);
      document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";
    `,
    initScript: `
      (function() {
        Date.prototype.getHours = function() { return 7; };
        Date.prototype.getMinutes = function() { return 42; };
      })();
    `,
    settleMs: 5500,
  },
  {
    // Chapter 15: the concept page returned-visitor view with her own
    // voice now visible among "Stimmen aus dem Feld" — proof that her
    // contribution is seen. We scroll deep enough to land in the voices
    // section. The URL uses ?scroll=voices so a client-side effect
    // can position us there; otherwise we eyeball scrollY.
    name: "16-concept-voices-mobile.png",
    url: "/vision/lc-nourishing?lang=de",
    preMount: `
      localStorage.setItem("cc-reaction-author-name", "Mama");
      document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";
    `,
    settleMs: 4500,
    // scrollY omitted — handled in runShot by locating the voices heading.
  },
];

async function runShot(context: BrowserContext, shot: Shot): Promise<void> {
  const page: Page = await context.newPage();
  const url = BASE + shot.url;
  try {
    if (shot.initScript) {
      await page.addInitScript({ content: shot.initScript });
    }
    // First, navigate to the site origin so we can set localStorage for it.
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (shot.preMount) {
      await page.evaluate(shot.preMount);
    }
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    // Give client hydration + localStorage-gated components time to render
    try {
      await page.waitForLoadState("networkidle", { timeout: 20000 });
    } catch {
      /* some endpoints keep-alive; domcontentloaded + settleMs is enough */
    }
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
    } else if (shot.name === "16-concept-voices-mobile.png") {
      // Scroll to the "Stimmen aus dem Feld" heading if it exists, otherwise
      // the bottom of the page where voices live.
      await page.evaluate(() => {
        const headings = Array.from(document.querySelectorAll("h2, h3"));
        const voices = headings.find((h) =>
          /Stimmen|Voices from the field/i.test(h.textContent || ""),
        );
        if (voices) {
          voices.scrollIntoView({ block: "start" });
        } else {
          window.scrollTo(0, document.body.scrollHeight);
        }
      });
      await page.waitForTimeout(800);
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
    // Dark-mode captures (the current default theme).
    for (const shot of SHOTS) {
      await runShot(context, shot);
    }
    // Light-mode captures of the same scenes so we can verify both
    // themes carry the same quality of contrast + polish. Output names
    // get a "-light" suffix and land in the same directory.
    for (const shot of SHOTS) {
      const lightShot: Shot = {
        ...shot,
        name: shot.name.replace(/\.png$/, "-light.png"),
        preMount: (shot.preMount || "") + `
          document.documentElement.classList.remove("dark");
          document.documentElement.classList.add("light");
          try { localStorage.setItem("cc-theme", "light"); } catch {}
        `,
      };
      await runShot(context, lightShot);
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
