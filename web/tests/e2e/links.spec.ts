import { test, expect } from '@playwright/test';

const PAGES_TO_CHECK = [
  '/',
  '/ideas',
  '/specs',
  '/contributors',
  '/teams',
  '/discover',
  '/vitality',
  '/governance',
  '/cc',
];

// Allow generous time: each page may link to 20+ routes and the app is SSR,
// so each request can take several seconds to stream the full body.
test.describe.configure({ timeout: 300_000 });

// Limit how many link checks run in parallel so the SSR server isn't swamped.
async function mapLimit<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (true) {
      const i = next++;
      if (i >= items.length) return;
      results[i] = await fn(items[i]);
    }
  });
  await Promise.all(workers);
  return results;
}

type CheckResult = { link: string; status: number; error: string | null };

for (const path of PAGES_TO_CHECK) {
  test(`${path} - all internal links resolve`, async ({ page, request }) => {
    await page.goto(path, { waitUntil: 'domcontentloaded' });

    const hrefs = await page.locator('a[href]').evaluateAll((els) =>
      els.map((el) => (el as HTMLAnchorElement).getAttribute('href') || '')
    );

    const internalLinks = new Set<string>();
    for (const href of hrefs) {
      if (!href) continue;
      if (href.startsWith('http://') || href.startsWith('https://')) continue;
      if (href.startsWith('#') || href.startsWith('mailto:')) continue;
      if (href.startsWith('javascript:') || href.startsWith('tel:')) continue;
      if (href.startsWith('data:')) continue;
      const clean = href.split('#')[0].split('?')[0];
      if (!clean) continue;
      if (!clean.startsWith('/')) continue;
      internalLinks.add(clean);
    }

    const links = Array.from(internalLinks);

    // Try HEAD first (fast, no body); fall back to GET if HEAD is unsupported
    // or returns an unexpected status. SSR apps sometimes only answer GET.
    const check = async (link: string): Promise<CheckResult> => {
      try {
        const head = await request.fetch(link, {
          method: 'HEAD',
          timeout: 20_000,
        });
        if (head.status() < 400) {
          return { link, status: head.status(), error: null };
        }
        // HEAD said error — try GET as a fallback (some frameworks 405 on HEAD)
        if (head.status() === 405 || head.status() === 501) {
          const get = await request.get(link, { timeout: 30_000 });
          return { link, status: get.status(), error: null };
        }
        return { link, status: head.status(), error: null };
      } catch (e) {
        // On network error, retry once with GET
        try {
          const get = await request.get(link, { timeout: 30_000 });
          return { link, status: get.status(), error: null };
        } catch (e2) {
          return { link, status: 0, error: String(e2) };
        }
      }
    };

    const results = await mapLimit(links, 3, check);

    // Rate-limit responses (429) mean the server is alive and protecting
    // itself under our test burst, not that the link is broken. Only treat
    // true 4xx (excluding 429) and 5xx as broken.
    const isBroken = (r: CheckResult) => {
      if (r.error) return true;
      if (r.status === 429) return false;
      return r.status >= 400;
    };

    const broken = results
      .filter(isBroken)
      .map((r) => `${r.link} -> ${r.error ?? r.status}`);

    expect(
      broken,
      `Broken links on ${path} (${links.length} checked):\n  ${broken.join('\n  ')}`
    ).toHaveLength(0);
  });
}
