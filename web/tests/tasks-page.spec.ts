/**
 * Spec 156 acceptance tests: Tasks page renders dynamic API data,
 * shows error+retry on failure, and avoids misleading zero-state.
 *
 * These are static-analysis tests that verify the page source contains
 * the required patterns (same approach as page-data-source.test.ts).
 */
import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = path.resolve(__dirname, "..");

function readWebFile(relativePath: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");
}

describe("spec 156: tasks page renders counts and items from API success", () => {
  const pageSource = readWebFile("app/tasks/page.tsx");
  const utilsSource = readWebFile("app/tasks/utils.ts");
  const apiSource = readWebFile("lib/api.ts");

  it("fetches from the same-origin proxy path /api/agent/tasks", () => {
    // Page must use the proxied path, not a cross-origin URL
    expect(pageSource).toContain("/api/agent/tasks");
  });

  it("does NOT hardcode a cross-origin API base in the fetch call", () => {
    // The fetch call should use a relative path, not http://... or an env var directly
    expect(pageSource).not.toMatch(/fetch\s*\(\s*["']https?:\/\//);
  });

  it("getApiBase returns empty string in browser context for proxy usage", () => {
    // Browser path must return "" so fetches are same-origin
    expect(apiSource).toContain('return ""');
    expect(apiSource).toContain("typeof window");
  });

  it("reads tasks array from the API response", () => {
    // Must handle json.tasks (primary) and json.items (backward compat)
    expect(pageSource).toMatch(/json\.tasks/);
  });

  it("reads total from the API response", () => {
    expect(pageSource).toMatch(/json\.total/);
  });

  it("computes counter values from task rows", () => {
    // Spec requires counters for pending/running/completed/failed states
    expect(pageSource).toContain("readyCount");
    expect(pageSource).toContain("activeCount");
    expect(pageSource).toContain("blockedCount");
    expect(pageSource).toContain("finishedCount");
  });

  it("renders counter cards in the UI", () => {
    expect(pageSource).toContain("{readyCount}");
    expect(pageSource).toContain("{activeCount}");
    expect(pageSource).toContain("{blockedCount}");
    expect(pageSource).toContain("{finishedCount}");
  });

  it("renders the task list only on success status", () => {
    // TasksListSection should only render when status === "ok"
    expect(pageSource).toContain('status === "ok"');
    expect(pageSource).toContain("TasksListSection");
  });
});

describe("spec 156: tasks page shows fetch error and retry on network failure", () => {
  const pageSource = readWebFile("app/tasks/page.tsx");

  it("tracks a three-state fetch status: loading | ok | error", () => {
    expect(pageSource).toMatch(/useState.*"loading"\s*\|\s*"ok"\s*\|\s*"error"/);
  });

  it("captures error detail on fetch failure", () => {
    // catch block must set error state
    expect(pageSource).toContain('setStatus("error")');
    expect(pageSource).toContain("setError(");
  });

  it("renders an error indicator when status is error", () => {
    expect(pageSource).toMatch(/status\s*===\s*"error"/);
    // Must display the error message to user
    expect(pageSource).toContain("{error}");
  });
});

describe("spec 156: tasks page does not render zero-state when fetch failed", () => {
  const pageSource = readWebFile("app/tasks/page.tsx");

  it("gates task list rendering behind success status, not just row count", () => {
    // The list section is inside a status === "ok" conditional, so a fetch
    // failure with zero rows won't show the list as if successful
    expect(pageSource).toContain('status === "ok"');
  });

  it("shows loading state before data arrives", () => {
    expect(pageSource).toMatch(/status\s*===\s*"loading"/);
  });

  it("does not show task list when status is loading or error", () => {
    // The <TasksListSection JSX usage (not the import) must be inside
    // the status === "ok" guard block.
    const okBlock = pageSource.indexOf('status === "ok"');
    // Find the JSX usage: <TasksListSection (not the import statement)
    const jsxUsage = pageSource.indexOf("<TasksListSection");
    expect(okBlock).toBeGreaterThan(-1);
    expect(jsxUsage).toBeGreaterThan(-1);
    // JSX rendering of TasksListSection must appear after the ok guard
    expect(jsxUsage).toBeGreaterThan(okBlock);
  });
});

describe("spec 156: tasks page utility functions", () => {
  const utilsSource = readWebFile("app/tasks/utils.ts");

  it("exports fetchWithTimeout with configurable timeout", () => {
    expect(utilsSource).toContain("export async function fetchWithTimeout");
    expect(utilsSource).toContain("REQUEST_TIMEOUT_MS");
  });

  it("aborts on timeout to prevent hanging requests", () => {
    expect(utilsSource).toContain("AbortController");
    expect(utilsSource).toContain("controller.abort");
  });

  it("exports pagination constants", () => {
    expect(utilsSource).toContain("DEFAULT_PAGE_SIZE");
    expect(utilsSource).toContain("MAX_PAGE_SIZE");
  });
});
