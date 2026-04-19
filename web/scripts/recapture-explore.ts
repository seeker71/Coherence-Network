import { chromium } from "playwright";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OUT_DIR = path.resolve(__dirname, "..", "public", "stories", "first-impressions");

(async () => {
  const browser = await chromium.launch({ headless: true });

  // Mobile
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    locale: "en-US",
  });
  const m = await mobile.newPage();
  await m.goto("https://coherencycoin.com/explore/concept", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await m.waitForLoadState("networkidle", { timeout: 20000 }); } catch {}
  await m.waitForTimeout(4500);
  await m.screenshot({ path: path.join(OUT_DIR, "07-explore-mobile-after.png"), fullPage: false });
  console.log("captured 07-explore-mobile-after.png");
  await m.close();
  await mobile.close();

  // Desktop
  const desktop = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    locale: "en-US",
  });
  const d = await desktop.newPage();
  await d.goto("https://coherencycoin.com/explore/concept", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await d.waitForLoadState("networkidle", { timeout: 20000 }); } catch {}
  await d.waitForTimeout(4500);
  await d.screenshot({ path: path.join(OUT_DIR, "07-explore-desktop-after.png"), fullPage: false });
  console.log("captured 07-explore-desktop-after.png");
  await d.close();
  await desktop.close();

  await browser.close();
})();
