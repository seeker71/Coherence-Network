/**
 * Spec 156 — tasks page structural tests.
 *
 * These verify the /tasks page source meets the requirements:
 * 1. Fetches via same-origin proxy path (not cross-origin)
 * 2. Renders counters from API status counts
 * 3. Shows explicit error state with retry on fetch failure
 * 4. Does not show zero-state counters when fetch failed
 */
import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = path.resolve(__dirname, "..");
const TASKS_PAGE = fs.readFileSync(path.join(WEB_ROOT, "app/tasks/page.tsx"), "utf8");
const API_LIB = fs.readFileSync(path.join(WEB_ROOT, "lib/api.ts"), "utf8");

describe("renders_counts_and_items_from_api_success", () => {
  it("page uses statusCounts from API for pending/running/completed", () => {
    expect(TASKS_PAGE).toContain("statusCounts?.pending");
    expect(TASKS_PAGE).toContain("statusCounts?.running");
    expect(TASKS_PAGE).toContain("statusCounts?.completed");
  });

  it("page parses counts from API response payload", () => {
    expect(TASKS_PAGE).toContain("parseStatusCountsFromPayload");
    expect(TASKS_PAGE).toContain("normalizeStatusCounts");
  });

  it("page falls back to deriving counts from task rows", () => {
    expect(TASKS_PAGE).toContain("deriveStatusCountsFromRows");
  });

  it("page fetches /api/agent/tasks/count for status totals", () => {
    expect(TASKS_PAGE).toContain('"/api/agent/tasks/count"');
  });
});

describe("shows_fetch_error_and_retry_on_network_failure", () => {
  it("page includes error state section with data-testid", () => {
    expect(TASKS_PAGE).toContain('data-testid="fetch-error"');
  });

  it("page includes retry button with data-testid", () => {
    expect(TASKS_PAGE).toContain('data-testid="retry-button"');
  });

  it("error section displays the error message string", () => {
    // Error text is rendered from the `error` state variable
    expect(TASKS_PAGE).toMatch(/\{error\}/);
  });

  it("error section shows a descriptive title", () => {
    expect(TASKS_PAGE).toContain("Could not load task data");
  });

  it("retry button calls loadRows without page reload", () => {
    expect(TASKS_PAGE).toContain("onClick={() => void loadRows()}");
  });
});

describe("does_not_render_zero_state_when_fetch_failed", () => {
  it("counters show unavailable placeholder in error state", () => {
    // When status === "error", counters render "—" instead of numeric zero
    expect(TASKS_PAGE).toContain('title="Unavailable"');
    // All counter cells use the error-guard pattern
    const unavailableCount = (TASKS_PAGE.match(/status === "error"/g) || []).length;
    expect(unavailableCount).toBeGreaterThanOrEqual(5);
  });

  it("counter elements have data-testid attributes", () => {
    expect(TASKS_PAGE).toContain('data-testid="counter-pending"');
    expect(TASKS_PAGE).toContain('data-testid="counter-running"');
    expect(TASKS_PAGE).toContain('data-testid="counter-completed"');
    expect(TASKS_PAGE).toContain('data-testid="counter-total"');
  });
});

describe("same-origin proxy route", () => {
  it("tasks page fetches via relative /api path (same-origin)", () => {
    // Must use relative "/api/agent/tasks" not an absolute cross-origin URL
    expect(TASKS_PAGE).toContain('fetchWithTimeout(`/api/agent/tasks?');
    expect(TASKS_PAGE).not.toMatch(/fetchWithTimeout\([`"']https?:\/\//);
  });

  it("api.ts returns empty string for browser (proxy mode)", () => {
    expect(API_LIB).toContain('if (isBrowser) return ""');
  });
});

describe("race condition handling", () => {
  it("uses request ID to prevent stale responses from overwriting state", () => {
    expect(TASKS_PAGE).toContain("loadRowsRequestId");
    expect(TASKS_PAGE).toContain("requestId !== loadRowsRequestId.current");
  });
});
