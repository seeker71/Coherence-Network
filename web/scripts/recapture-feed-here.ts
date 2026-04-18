import { chromium } from "playwright";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OUT_DIR = path.resolve(__dirname, "..", "public", "stories", "first-impressions");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    locale: "en-US",
  });
  const shots: Array<[string, string]> = [
    ["05-feed-after.png", "/feed"],
    ["06-here-after.png", "/here"],
  ];
  for (const [name, url] of shots) {
    const page = await context.newPage();
    await page.goto("https://coherencycoin.com" + url, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    try {
      await page.waitForLoadState("networkidle", { timeout: 20000 });
    } catch {
      /* settle time below */
    }
    await page.waitForTimeout(3500);
    await page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false });
    console.log("captured", name);
    await page.close();
  }
  await browser.close();
})();
