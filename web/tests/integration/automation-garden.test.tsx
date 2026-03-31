import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { buildActivityBrookItems } from "@/lib/automation-page-data";
import type { AutomationPagePayload } from "@/lib/automation-page-data";

const WEB_ROOT = path.resolve(__dirname, "../..");

function read(rel: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, rel), "utf8");
}

const minimalPayload = (): AutomationPagePayload => ({
  usage: {
    generated_at: "2026-03-28T12:00:00.000Z",
    providers: [],
    unavailable_providers: [],
    tracked_providers: 0,
  },
  alerts: { generated_at: "2026-03-28T12:00:00.000Z", threshold_ratio: 0.2, alerts: [] },
  readiness: {
    generated_at: "2026-03-28T12:00:00.000Z",
    required_providers: [],
    all_required_ready: true,
    blocking_issues: [],
    recommendations: [],
    providers: [],
  },
  validation: {
    generated_at: "2026-03-28T12:00:00.000Z",
    required_providers: [],
    runtime_window_seconds: 86400,
    min_execution_events: 1,
    all_required_validated: true,
    blocking_issues: [],
    providers: [],
  },
  execStats: null,
  networkStats: null,
  federationNodes: [],
  fleetCapabilities: null,
});

describe("automation garden (spec 181)", () => {
  it("page imports garden experience and data loader", () => {
    const page = read("app/automation/page.tsx");
    expect(page).toContain('from "@/components/automation/automation_garden"');
    expect(page).toContain('from "@/lib/automation-page-data"');
    expect(page).toContain("<AutomationGarden");
    expect(page).toContain('data-testid="automation-technical-soil"');
  });

  it("automation_garden exposes required data-testid markers", () => {
    const g = read("components/automation/automation_garden.tsx");
    expect(g).toContain('data-testid="automation-garden"');
    expect(g).toContain('data-testid="garden-canopy"');
    expect(g).toContain('data-testid="garden-activity-brook"');
    expect(g).toContain('data-testid="garden-node-meadow"');
  });

  it("buildActivityBrookItems returns at least one pulse item", () => {
    const items = buildActivityBrookItems(minimalPayload());
    expect(items.length).toBeGreaterThan(0);
    expect(items.some((i) => i.title.includes("Meadow refreshed"))).toBe(true);
  });
});
