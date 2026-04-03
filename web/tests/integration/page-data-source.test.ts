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
    route: "/api-coverage",
    file: "app/api-coverage/page.tsx",
    apiHints: ["useApiCoverage", "probeSummary", "topTraceabilityGaps", "allEndpoints"],
    dynamicHints: [/topTraceabilityGaps\.map/, /probes\.map/, /allEndpoints\.map/],
  },
  {
    route: "/ideas",
    file: "app/ideas/page.tsx",
    apiHints: ["/api/ideas", "/api/ideas/progress", "getApiBase()"],
    dynamicHints: [/data\.summary\.total_ideas/, /data\.ideas/, /completionPct/],
  },
  {
    route: "/specs",
    file: "app/specs/page.tsx",
    apiHints: ["/api/inventory/system-lineage", "/api/spec-registry", "getApiBase()"],
    dynamicHints: [/filteredSpecs\.length/, /spec\.title/, /filteredRegistry\.length/],
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
    apiHints: ["/api/automation/usage", "/api/providers/stats", "getApiBase()", "loadAutomationData"],
    dynamicHints: [/GardenMap/, /usage\.providers/, /readiness=\{readiness\}/],
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
  {
    route: "/marketplace",
    file: "app/marketplace/page.tsx",
    apiHints: ["/api/marketplace/browse", "getApiBase()"],
    dynamicHints: [/listing\.idea_title/, /listing\.fork_count/, /setListings/],
  },
  {
    route: "/graphs",
    file: "app/graphs/page.tsx",
    apiHints: ["/api/graph/nodes", "/api/edges", "getApiBase()"],
    dynamicHints: [/filteredNodes\.slice/, /neighbors\.map/, /selectedNodeId/],
  },
  {
    route: "/dashboard",
    file: "app/dashboard/page.tsx",
    apiHints: ["/api/federation/nodes", "/api/agent/tasks?status=running&limit=20", "/api/pipeline/pulse", "getApiBase()"],
    dynamicHints: [/setNodes/, /setTasks/, /bottleneckTitle/, /bottleneckDetail/],
  },
  {
    route: "/nodes",
    file: "app/nodes/page.tsx",
    apiHints: ["/api/federation/nodes", "/api/providers/stats", "/api/automation/usage/readiness", "getApiBase()"],
    dynamicHints: [/nodes\.length/, /fleetRate/, /readiness/],
  },
  {
    route: "/pipeline",
    file: "app/pipeline/page.tsx",
    apiHints: ["/api/federation/nodes", "/api/agent/tasks/active", "/api/providers/stats"],
    dynamicHints: [/setProviderStats/, /taskSummary/, /recentActivity/],
  },
  {
    route: "/friction",
    file: "app/friction/page.tsx",
    apiHints: ["/api/friction/report", "/api/friction/events", "/api/friction/entry-points", "getApiBase()"],
    dynamicHints: [/entryPoints\.entry_points/, /report\.total_events/, /events\.map/],
  },
  {
    route: "/contributions",
    file: "app/contributions/page.tsx",
    apiHints: ["/api/contributions", "/api/coherence/score", "/api/assets", "getApiBase()"],
    dynamicHints: [/filteredRows\.slice/, /liveCoherenceScore/, /contributorNames/],
  },
  {
    route: "/assets",
    file: "app/assets/page.tsx",
    apiHints: ["/api/assets", "getApiBase()"],
    dynamicHints: [/filteredRows\.slice/, /status === "ok"/, /`\/assets\/\$\{encodeURIComponent\(a\.id\)\}`/],
  },
  {
    route: "/assets/[asset_id]",
    file: "app/assets/[asset_id]/page.tsx",
    apiHints: [
      "/api/assets/${encodeURIComponent(assetId)}",
      "/api/assets/${encodeURIComponent(assetId)}/contributions",
      "/api/contributors",
      "getApiBase()",
    ],
    dynamicHints: [/contributions\.length/, /contributorsById\.get/, /asset\.description/],
  },
  {
    route: "/identity",
    file: "app/identity/page.tsx",
    apiHints: ["/api/identity/providers", "/api/identity/link", "getApiBase()"],
    dynamicHints: [/Object\.entries\(providers\)/, /setProviders/, /setIdentities/],
  },
  {
    route: "/resonance",
    file: "app/resonance/page.tsx",
    apiHints: ["/api/ideas/resonance", "/api/news/feed", "/api/ideas?limit=60", "getApiBase()"],
    dynamicHints: [/itemsWithActivity/, /newsItems/, /loadActivity/],
  },
  {
    route: "/invest",
    file: "app/invest/page.tsx",
    apiHints: ["/api/ideas?limit=60", "getApiBase()"],
    dynamicHints: [/gardenStage/, /idea\.manifestation_status/, /sorted\.map/],
  },
  {
    route: "/today",
    file: "app/today/page.tsx",
    apiHints: ["/api/ideas", "/api/agent/tasks?limit=100", "getApiBase()"],
    dynamicHints: [/topIdea/, /deriveTaskIdea/, /ideasById/],
  },
  {
    route: "/tasks",
    file: "app/tasks/page.tsx",
    apiHints: ["/api/agent/tasks?", "/api/ideas?limit=500", "/api/agent/tasks/active", "/api/agent/tasks/activity?limit=30"],
    dynamicHints: [/setRows/, /setRecentActivity/, /selectedTaskEvents/, /taskIdFilter/],
  },
  {
    route: "/contributors/[id]/portfolio",
    file: "app/contributors/[id]/portfolio/page.tsx",
    apiHints: [
      "/api/contributors/${encodeURIComponent(contributorId)}",
      "fetch(`${base}/portfolio`)",
      "/cc-history?window=90d&bucket=7d",
      "/idea-contributions?sort=cc_attributed_desc&limit=20",
      "/stakes?sort=roi_desc&limit=20",
      "/tasks?status=completed&limit=20",
      "getApiBase()",
    ],
    dynamicHints: [/summary\.cc_balance/, /ideas && ideas\.items\.length > 0/, /stakes && stakes\.items\.length > 0/, /tasks && tasks\.items\.length > 0/, /contributors\?contributor_id=/],
  },
  {
    route: "/contributors/[id]/portfolio/tasks/[task_id]",
    file: "app/contributors/[id]/portfolio/tasks/[task_id]/page.tsx",
    apiHints: ["/api/contributors/${encodeURIComponent(id ?? \"\")}/tasks/${encodeURIComponent(task_id)}", "getApiBase()"],
    dynamicHints: [/task\.description/, /task\.cc_earned/, /task\.completed_at/],
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
  it("keeps explicit fallback or loading messages in scoped pages", () => {
    const requiredAnnotations: Array<{ file: string; textHint: string }> = [
      { file: "app/page.tsx", textHint: "No recent activity yet. Be the first to share an idea." },
      { file: "app/specs/page.tsx", textHint: "No specs are visible yet. Once lineage or registry data lands, this page will show the linked ideas, contributors, and implementation proof automatically." },
      { file: "app/usage/page.tsx", textHint: "Provider stats are not available right now. Check back once the API is connected." },
      { file: "app/flow/page.tsx", textHint: "Run some tasks to see pipeline activity." },
      { file: "app/contribute/page.tsx", textHint: 'status === "loading"' },
    ];

    for (const entry of requiredAnnotations) {
      const source = readWebFile(entry.file);
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
