import { chromium } from "playwright";
import * as path from "path";

const BASE = "https://coherencycoin.com";
const OUT = path.resolve("public/stories/ana-walk");

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ignoreHTTPSErrors: true,
  });
  for (const [theme, suffix] of [["dark", ""], ["light", "-light"]] as const) {
    for (const [name, url] of [
      ["17-people-mama", "/people/mama-test-fp-cycle-o?lang=de"],
      ["18-people-testsoul", "/people/testsoul-test-fp-cycle-o?lang=de"],
    ] as const) {
      const page = await context.newPage();
      if (theme === "light") {
        await page.addInitScript({ content: `document.documentElement.classList.remove("dark"); document.documentElement.classList.add("light");` });
      }
      await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.evaluate(`document.cookie = "NEXT_LOCALE=de; path=/; max-age=31536000";`);
      await page.goto(BASE + url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForLoadState("networkidle", { timeout: 20000 }); } catch {}
      await page.waitForTimeout(2500);
      await page.screenshot({ path: path.join(OUT, `${name}-mobile${suffix}.png`), fullPage: false });
      console.log(`captured ${name}-mobile${suffix}.png`);
      await page.close();
    }
  }
  await context.close();
  await browser.close();
}
main().catch(e => { console.error(e); process.exit(1); });
