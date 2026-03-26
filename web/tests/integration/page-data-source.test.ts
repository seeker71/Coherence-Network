import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = path.resolve(__dirname, "../..");

type PageAssertion = {
  route: string;
  file: string;
  apiHints: string[];
  dynamicHints: RegExp[];
};

const PAGE_ASSERTIONS: PageAssertion[] = [
  {
    route: "/",
    file: "app/page.tsx",
    apiHints: ["/api/ideas", "/api/coherence/score", "getApiBase()"],
    dynamicHints: [/summary\?\.total_ideas/, /coherenceScore\.score/, /nodeCount/],
  },
  {
    route: "/ideas",
    file: "app/ideas/page.tsx",
    apiHints: ["/api/ideas", "/api/ideas/progress", "getApiBase()"],
    dynamicHints: [/data\.summary\.total_ideas/, /idea\.name/, /completionPct/],
  },
  {
    route: "/specs",
    file: "app/specs/page.tsx",
    apiHints: ["/api/inventory/system-lineage", "/api/spec-registry", "getApiBase()"],
    dynamicHints: [/filteredSpecs\.length/, /s\.title/, /filteredRegistry\.length/],
  },
  {
    route: "/usage",
    file: "app/usage/page.tsx",
    apiHints: ["/api/providers/stats", "getApiBase()", "loadRuntimeSlice"],
    dynamicHints: [/providerStats\.summary/, /warnings\.length/, /runtimeSlice\.hasMore/],
  },
  {
    route: "/automation",
    file: "app/automation/page.tsx",
    apiHints: ["/api/automation/usage", "/api/providers/stats", "getApiBase()"],
    dynamicHints: [/usage\.tracked_providers/, /readiness/, /validation/],
  },
  {
    route: "/flow",
    file: "app/flow/page.tsx",
    apiHints: ["/api/providers/stats", "getApiBase()", "loadData("],
    dynamicHints: [/filteredItems\.map/, /pipelineHealth\.summary/, /topContributorsRowsList/],
  },
  {
    route: "/contribute",
    file: "app/contribute/page.tsx",
    apiHints: ["/api/contributors", "/api/ideas", "/api/spec-registry", "getApiBase()"],
    dynamicHints: [/contributors\.map/, /changeRequests\.map/, /status === "loading"/],
  },
];

function readWebFile(relativePath: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");
}

describe("each page renders dynamic API content", () => {
  it("confirms all audited pages consume API data and dynamic bindings", () => {
    for (const page of PAGE_ASSERTIONS) {
      const source = readWebFile(page.file);
      for (const apiHint of page.apiHints) {
        expect(
          source.includes(apiHint),
          `${page.route} should include API hint: ${apiHint}`,
        ).toBe(true);
      }
      for (const dynamicHint of page.dynamicHints) {
        expect(
          dynamicHint.test(source),
          `${page.route} should bind dynamic value: ${dynamicHint.source}`,
        ).toBe(true);
      }
    }
  });
});

describe("fallback messages carry data-placeholder attribute", () => {
  it("annotates fallback/empty/loading/error states in scoped pages", () => {
    const requiredAnnotations: Array<{ file: string; textHint: string }> = [
      { file: "app/page.tsx", textHint: "No recent activity yet. Be the first to share an idea." },
      { file: "app/specs/page.tsx", textHint: "No data available yet. Once the API is running, results will appear here." },
      { file: "app/usage/page.tsx", textHint: "Provider stats are not available right now. Check back once the API is connected." },
      { file: "app/flow/page.tsx", textHint: "Run some tasks to see pipeline activity." },
      { file: "app/contribute/page.tsx", textHint: 'status === "loading"' },
    ];

    for (const entry of requiredAnnotations) {
      const source = readWebFile(entry.file);
      expect(
        source.includes('data-placeholder="true"'),
        `${entry.file} should include data-placeholder`,
      ).toBe(true);
      expect(source.includes(entry.textHint), `${entry.file} should include fallback hint text`).toBe(
        true,
      );
    }
  });
});

describe("no page contains hardcoded mock data arrays", () => {
  it("guards against mock array placeholders in audited routes", () => {
    const bannedPatterns = [/mockData/, /placeholder.*=.*\[/];
    for (const page of PAGE_ASSERTIONS) {
      const source = readWebFile(page.file);
      for (const pattern of bannedPatterns) {
        expect(
          pattern.test(source),
          `${page.file} should not match banned pattern ${pattern.source}`,
        ).toBe(false);
      }
    }
  });
});
