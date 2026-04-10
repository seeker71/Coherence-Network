import { test, expect } from '@playwright/test';

// Terms that non-technical users won't understand without explanation
const TECHNICAL_JARGON = [
  'api', 'endpoint', 'payload', 'schema', 'http', 'json', 'sdk',
  'oauth', 'uuid', 'mcp', 'stdio', 'sse', 'cdn', 'ssr',
  'sqlite', 'postgres', 'neo4j', 'graphql',
  'idempotency', 'deduplication', 'fingerprint', 'hash',
  'gini coefficient', 'jaccard', 'cosine similarity', 'shannon entropy',
  'harmonic kernel', 'optimal transport', 'crk', 'ot-phi',
  'proprioception',
];

const PUBLIC_PAGES = [
  { path: '/', name: 'Home' },
  { path: '/ideas', name: 'Ideas' },
  { path: '/discover', name: 'Discover' },
  { path: '/vitality', name: 'Vitality' },
  { path: '/teams', name: 'Teams' },
  { path: '/contribute', name: 'Contribute' },
];

// Pages may be slow under parallel test load — give them extra headroom.
test.describe.configure({ timeout: 90_000 });

for (const { path, name } of PUBLIC_PAGES) {
  test(`${name} - jargon audit`, async ({ page }) => {
    await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    const text = (await page.locator('body').innerText()).toLowerCase();

    const foundJargon: string[] = [];
    for (const term of TECHNICAL_JARGON) {
      const regex = new RegExp(`\\b${term}\\b`, 'i');
      if (regex.test(text)) {
        foundJargon.push(term);
      }
    }

    if (foundJargon.length > 0) {
      console.warn(`[jargon] ${path}: ${foundJargon.join(', ')}`);
    }

    expect(
      foundJargon.length,
      `${path} has too much jargon for non-technical users: ${foundJargon.join(', ')}`
    ).toBeLessThanOrEqual(5);
  });
}
