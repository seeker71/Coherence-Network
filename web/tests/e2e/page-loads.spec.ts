import { test, expect } from '@playwright/test';

const PAGES = [
  { path: '/', name: 'Home' },
  { path: '/ideas', name: 'Ideas' },
  { path: '/specs', name: 'Specs' },
  { path: '/tasks', name: 'Tasks' },
  { path: '/contributors', name: 'Contributors' },
  { path: '/concepts', name: 'Concepts' },
  { path: '/teams', name: 'Teams' },
  { path: '/messages', name: 'Messages' },
  { path: '/activity', name: 'Activity' },
  { path: '/projects', name: 'Projects' },
  { path: '/discover', name: 'Discover' },
  { path: '/constellation', name: 'Constellation' },
  { path: '/vitality', name: 'Vitality' },
  { path: '/governance', name: 'Governance' },
  { path: '/news', name: 'News' },
  { path: '/federation', name: 'Federation' },
  { path: '/beliefs', name: 'Beliefs' },
  { path: '/peers', name: 'Peers' },
  { path: '/coherence', name: 'Coherence' },
  { path: '/cc', name: 'CC Economics' },
  { path: '/breath', name: 'Breath' },
  { path: '/identity', name: 'Identity' },
  { path: '/contribute', name: 'Contribute' },
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/resonance', name: 'Resonance' },
  { path: '/pipeline', name: 'Pipeline' },
];

// Extra headroom for pages that are slow under parallel test load.
test.describe.configure({ timeout: 90_000 });

for (const { path, name } of PAGES) {
  test(`${name} page loads`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    const response = await page.goto(path, {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
    expect(response?.status(), `HTTP status for ${path}`).toBeLessThan(400);

    // Wait for body to have content
    await expect(page.locator('body')).not.toBeEmpty();

    // No JavaScript errors
    expect(errors, `JS errors on ${path}: ${errors.join(', ')}`).toHaveLength(0);

    // Page has a title
    const title = await page.title();
    expect(title.length, `Empty title on ${path}`).toBeGreaterThan(0);
  });
}
