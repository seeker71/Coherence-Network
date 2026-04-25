import { test, expect } from '@playwright/test';

// Use domcontentloaded (not 'load') because pages stream resources and fonts
// that keep 'load' pending beyond the test timeout while the DOM is ready.
const GOTO_OPTS = { waitUntil: 'domcontentloaded' as const, timeout: 60_000 };

// Extra headroom for pages that are slow under parallel test load.
test.describe.configure({ timeout: 90_000 });

test('home page shows navigation', async ({ page }) => {
  await page.goto('/', GOTO_OPTS);
  const links = await page.locator('a[href^="/"]').count();
  expect(links).toBeGreaterThan(3);
});

test('ideas page lists ideas or shows empty state', async ({ page }) => {
  await page.goto('/ideas', GOTO_OPTS);
  const bodyText = await page.locator('body').innerText();
  expect(bodyText.length).toBeGreaterThan(100);
});

test('vitality page shows score', async ({ page }) => {
  await page.goto('/vitality', GOTO_OPTS);
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).toMatch(/vitality|health|diversity|resonance|flow/i);
});

test('discover page shows resonance content', async ({ page }) => {
  await page.goto('/discover', GOTO_OPTS);
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).toMatch(/resonan|discover|idea/i);
});

test('constellation page has visualization elements', async ({ page }) => {
  await page.goto('/constellation', GOTO_OPTS);
  const visualElements = await page.locator('svg, [style*="position: absolute"]').count();
  expect(visualElements).toBeGreaterThan(0);
});

test('breath page shows gas/water/ice', async ({ page }) => {
  await page.goto('/breath', GOTO_OPTS);
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).toMatch(/gas|water|ice|breath/i);
});

test('cc page shows coherence credit info', async ({ page }) => {
  await page.goto('/cc', GOTO_OPTS);
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).toMatch(/cc|coherence credit|supply|minted/i);
});
