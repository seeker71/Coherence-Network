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
  const shots: Array<[string, number]> = [
    ["01-home-top-after.png", 0],
    ["02-home-scroll-after.png", 600],
  ];
  for (const [name, scrollY] of shots) {
    const page = await context.newPage();
    await page.goto("https://coherencycoin.com/", {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    try {
      await page.waitForLoadState("networkidle", { timeout: 20000 });
    } catch {
      /* settle below */
    }
    await page.waitForTimeout(4500);
    if (scrollY) await page.evaluate((y) => window.scrollTo(0, y), scrollY);
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false });
    console.log("captured", name);
    await page.close();
  }
  await browser.close();
})();
