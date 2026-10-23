import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Reproduce from web/, with each server in its own terminal:
 * form-run node -e 'require("node:http").createServer((req,res)=>{res.writeHead(200,{"content-type":"application/json"});res.end(JSON.stringify({items:[],total:0}));}).listen(3218,"127.0.0.1")'
 * form-run env API_URL=http://127.0.0.1:3218 NEXT_PUBLIC_API_URL=http://127.0.0.1:3218 npm run dev -- --port 3217 --hostname 127.0.0.1 --webpack
 * form-run env PLAYWRIGHT_BASE_URL=http://127.0.0.1:3217 ./node_modules/.bin/playwright test tests/e2e/people-search.spec.ts --project=chromium --workers=1 --reporter=list
 * The synthetic API supplies server-rendered directory data; browser routes
 * below supply search outcomes and keep other browser API requests local.
 */

const emptyResult = (query: string) => ({ query, concepts: [], presences: [], existing_edges: [] });
const conceptResult = (query: string) => ({
  ...emptyResult(query),
  concepts: [{ id: "synthetic-rhythm", name: "Shared rhythms", type: "concept", hz: null, score: 1, shared_tokens: ["music", "movement"] }],
});
const searchInput = (page: Page) => page.getByPlaceholder(/Type what's alive|Explore a shared interest/);
const emptyMessage = (page: Page) => page.getByText("Try another phrase or explore the directory below. This search returned no matches.");
const searchError = (page: Page) => page.getByRole("alert").filter({ hasText: "Search is temporarily unavailable. Try again." });

test.beforeEach(async ({ page, baseURL }) => {
  test.skip(!baseURL || !["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL).hostname), "Run with PLAYWRIGHT_BASE_URL pointing to a local web server backed by synthetic directory data.");
  await page.route("**/api/**", (route) => route.fulfill({ json: { items: [], total: 0 } }));
});

async function openSearch(page: Page) {
  await page.goto("/presences?kind=humans", { waitUntil: "networkidle" });
  await expect(searchInput(page)).toBeVisible();
}

test("waiting and short input stay distinct from a completed empty search", async ({ page }) => {
  let pending: Route | undefined;
  await page.route("**/api/resolve/query", (route) => { pending = route; });
  await openSearch(page);
  await searchInput(page).fill("mu");
  await expect(emptyMessage(page)).toBeHidden();
  await searchInput(page).fill("music movement");
  await expect(page.getByText("Searching…", { exact: true })).toBeVisible();
  await expect(emptyMessage(page)).toBeHidden();
  await expect.poll(() => Boolean(pending)).toBe(true);
  await pending!.fulfill({ json: emptyResult("music movement") });
  await expect(emptyMessage(page)).toBeVisible();
  await expect(searchError(page)).toBeHidden();
  await expect(searchInput(page)).toHaveAccessibleName("Search concepts and presences");
});

for (const failure of ["http", "network", "invalid JSON", "invalid payload"] as const) {
  test(`${failure} failure offers retry and preserves a successful concept result`, async ({ page }) => {
    let attempts = 0;
    await page.route("**/api/resolve/query", async (route) => {
      attempts += 1;
      if (attempts === 1) {
        if (failure === "network") await route.abort();
        else if (failure === "invalid JSON") await route.fulfill({ contentType: "application/json", body: "{" });
        else if (failure === "invalid payload") await route.fulfill({ json: { query: "music movement", concepts: [null], presences: [], existing_edges: [] } });
        else await route.fulfill({ status: 503, json: { detail: "Synthetic outage" } });
        return;
      }
      await route.fulfill({ json: conceptResult(route.request().postDataJSON().query) });
    });
    await openSearch(page);
    await searchInput(page).fill("music movement");
    await expect(searchError(page)).toBeVisible();
    await expect(emptyMessage(page)).toBeHidden();
    await page.getByRole("button", { name: "Retry search" }).click();
    await expect(page.getByRole("link", { name: "Shared rhythms" })).toHaveAttribute("href", "/vision/synthetic-rhythm");
    await expect(searchError(page)).toBeHidden();
    await expect(page.getByText("Concepts", { exact: true })).toBeVisible();
    expect(attempts).toBe(2);
    await page.screenshot({ path: test.info().outputPath(`search-${failure}-recovered.png`), fullPage: true });
  });
}

for (const outcome of ["empty", "failure"] as const) {
test(`a superseded ${outcome} response cannot replace the latest results or end its loading state`, async ({ page }) => {
  // Let the older fetch finish despite cancellation, as can happen after a
  // response has arrived while its body is still being read.
  await page.addInitScript(() => {
    const fetch = window.fetch.bind(window);
    window.fetch = (input, init) => String(input).includes("/api/resolve/query")
      ? fetch(input, { ...init, signal: undefined })
      : fetch(input, init);
  });
  const pending = new Map<string, Route>();
  await page.route("**/api/resolve/query", (route) => {
    pending.set(route.request().postDataJSON().query, route);
  });
  await openSearch(page);
  await searchInput(page).fill("old phrase");
  await expect.poll(() => pending.has("old phrase")).toBe(true);
  await searchInput(page).fill("music movement");
  await pending.get("old phrase")!.fulfill({ status: outcome === "failure" ? 503 : 200, json: emptyResult("old phrase") });
  await expect(page.getByText("Searching…", { exact: true })).toBeVisible();
  await expect(emptyMessage(page)).toBeHidden();
  await expect(searchError(page)).toBeHidden();
  await expect.poll(() => pending.has("music movement")).toBe(true);
  await searchInput(page).fill("latest phrase");
  await expect.poll(() => pending.has("latest phrase")).toBe(true);
  await pending.get("latest phrase")!.fulfill({ json: conceptResult("latest phrase") });
  await expect(page.getByRole("link", { name: "Shared rhythms" })).toBeVisible();
  const olderResponse = page.waitForResponse((response) => response.url().endsWith("/api/resolve/query") && response.request().postDataJSON().query === "music movement");
  await pending.get("music movement")!.fulfill({ status: outcome === "failure" ? 503 : 200, json: emptyResult("music movement") });
  await olderResponse;
  await expect(page.getByRole("link", { name: "Shared rhythms" })).toBeVisible();
  await searchInput(page).fill("new phrase");
  await expect(page.getByRole("link", { name: "Shared rhythms" })).toBeHidden();
  await expect(page.getByText("Searching…", { exact: true })).toBeVisible();
  await searchInput(page).clear();
  await expect(page.getByText("Searching…", { exact: true })).toBeHidden();
  await expect(emptyMessage(page)).toBeHidden();
});
}

test("a late response stays absent after the input is cleared", async ({ page }) => {
  await page.addInitScript(() => {
    const fetch = window.fetch.bind(window);
    window.fetch = (input, init) => String(input).includes("/api/resolve/query")
      ? fetch(input, { ...init, signal: undefined })
      : fetch(input, init);
  });
  let pending: Route | undefined;
  await page.route("**/api/resolve/query", (route) => { pending = route; });
  await openSearch(page);
  await searchInput(page).fill("music movement");
  await expect.poll(() => Boolean(pending)).toBe(true);
  await searchInput(page).clear();
  const response = page.waitForResponse("**/api/resolve/query");
  await pending!.fulfill({ json: conceptResult("music movement") });
  await response;
  await expect(page.getByRole("link", { name: "Shared rhythms" })).toBeHidden();
  await expect(page.getByText("Searching…", { exact: true })).toBeHidden();
  await expect(emptyMessage(page)).toBeHidden();
});

test("a matching presence keeps its own directory detail link", async ({ page }) => {
  await page.route("**/api/resolve/query", (route) => route.fulfill({ json: {
    ...emptyResult(route.request().postDataJSON().query),
    presences: [{ id: "community:synthetic", name: "Garden circle", type: "community", image_url: null, canonical_url: null, score: 1, shared_tokens: ["garden", "circle"] }],
  } }));
  await openSearch(page);
  await searchInput(page).fill("garden circle");
  await expect(page.getByRole("link", { name: "Garden circle community" })).toHaveAttribute("href", "/people/community%3Asynthetic");
});

