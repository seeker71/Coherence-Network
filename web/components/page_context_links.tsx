"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { getApiBase } from "@/lib/api";

type LinkItem = {
  href: string;
  label: string;
};

type ContextDef = {
  ideaId: string;
  related: LinkItem[];
  machinePaths: LinkItem[];
};

const SHARED_RELATED: LinkItem[] = [
  { href: "/today", label: "Today" },
  { href: "/demo", label: "Demo" },
  { href: "/search", label: "Search" },
  { href: "/ideas", label: "Ideas" },
  { href: "/flow", label: "Progress" },
  { href: "/contribute", label: "Contribute" },
  { href: "/tasks", label: "Work" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/specs", label: "Plans" },
];

const CONTEXTS: Record<string, ContextDef> = {
  "/": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/inventory/system-lineage", label: "System lineage" },
      { href: "/api/inventory/page-lineage", label: "Page lineage" },
      { href: "/api/ideas", label: "Ideas API" },
    ],
  },
  "/portfolio": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/inventory/system-lineage", label: "System lineage" },
      { href: "/api/inventory/page-lineage", label: "Page lineage" },
      { href: "/api/ideas", label: "Ideas API" },
    ],
  },
  "/flow": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/inventory/flow", label: "Flow inventory" },
      { href: "/api/inventory/system-lineage", label: "System lineage" },
      { href: "/api/contributors", label: "Contributors API" },
      { href: "/api/contributions", label: "Contributions API" },
    ],
  },
  "/ideas": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/ideas", label: "Ideas API" },
      { href: "/api/inventory/system-lineage", label: "System lineage" },
    ],
  },
  "/demo": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/ideas", label: "Ideas API" },
      { href: "/api/inventory/flow?runtime_window_seconds=86400", label: "Flow inventory API" },
      { href: "/api/agent/tasks?limit=100", label: "Tasks API" },
    ],
  },
  "/today": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/ideas", label: "Ideas API" },
      { href: "/api/agent/tasks?limit=100", label: "Tasks API" },
      { href: "/api/inventory/flow?runtime_window_seconds=86400", label: "Flow inventory API" },
    ],
  },
  "/ideas/[idea_id]": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/ideas", label: "Ideas API" },
      { href: "/api/inventory/system-lineage", label: "System lineage" },
    ],
  },
  "/specs": {
    ideaId: "coherence-network-api-runtime",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/spec-registry", label: "Spec registry API" },
      { href: "/api/inventory/routes/canonical", label: "Canonical routes" },
    ],
  },
  "/specs/[spec_id]": {
    ideaId: "coherence-network-api-runtime",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/spec-registry", label: "Spec registry API" },
      { href: "/api/inventory/flow", label: "Flow inventory" },
      { href: "/api/inventory/system-lineage", label: "System lineage" },
    ],
  },
  "/usage": {
    ideaId: "coherence-network-value-attribution",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/runtime/ideas/summary?seconds=21600", label: "Runtime summary" },
      { href: "/api/runtime/web/views/summary?seconds=21600", label: "Full-view runtime + cost" },
      { href: "/api/friction/report?window_days=7", label: "Friction report" },
    ],
  },
  "/automation": {
    ideaId: "coherence-network-agent-pipeline",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/automation/usage", label: "Automation usage API" },
      { href: "/api/automation/usage/alerts", label: "Automation alerts API" },
      { href: "/api/automation/usage/snapshots", label: "Automation snapshots API" },
      { href: "/api/automation/usage/readiness", label: "Automation readiness API" },
      { href: "/api/automation/usage/provider-validation", label: "Provider validation API" },
      { href: "/api/automation/usage/provider-validation/run", label: "Provider validation run API" },
    ],
  },
  "/contributors": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/contributors", label: "Contributors API" },
      { href: "/api/contributions", label: "Contributions API" },
    ],
  },
  "/contribute": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/contributors", label: "Contributors API" },
      { href: "/api/governance/change-requests", label: "Change requests API" },
      { href: "/api/spec-registry", label: "Spec registry API" },
      { href: "/api/ideas", label: "Ideas API" },
    ],
  },
  "/contributions": {
    ideaId: "coherence-network-value-attribution",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/contributions", label: "Contributions API" },
      { href: "/api/distributions", label: "Distributions API" },
    ],
  },
  "/assets": {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/assets", label: "Assets API" },
      { href: "/api/contributions", label: "Contributions API" },
    ],
  },
  "/tasks": {
    ideaId: "coherence-network-agent-pipeline",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/agent/tasks", label: "Tasks API" },
      { href: "/api/agent/pipeline-status", label: "Pipeline status" },
      { href: "/api/agent/effectiveness", label: "Effectiveness" },
    ],
  },
  "/agent": {
    ideaId: "coherence-network-agent-pipeline",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/agent/visibility", label: "Agent visibility" },
      { href: "/api/agent/usage", label: "Agent usage" },
      { href: "/api/agent/pipeline-status", label: "Pipeline status" },
      { href: "/api/agent/effectiveness", label: "Effectiveness" },
    ],
  },
  "/remote-ops": {
    ideaId: "coherence-network-agent-pipeline",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/gates/public-deploy-contract", label: "Public deploy contract" },
      { href: "/api/agent/pipeline-status", label: "Pipeline status" },
      { href: "/api/agent/tasks?status=pending&limit=20", label: "Pending tasks" },
      { href: "/api/health", label: "Health check" },
    ],
  },
  "/gates": {
    ideaId: "deployment-gate-reliability",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/gates/main-contract", label: "Main contract" },
      { href: "/api/gates/public-deploy-contract", label: "Public deploy contract" },
      { href: "/api/gates/commit-traceability", label: "Commit traceability" },
    ],
  },
  "/friction": {
    ideaId: "coherence-network-agent-pipeline",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/friction/report?window_days=7", label: "Friction report" },
      { href: "/api/friction/events?limit=20", label: "Friction events" },
    ],
  },
  "/search": {
    ideaId: "coherence-network-web-interface",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/search?q=react", label: "Search API example" },
      { href: "/api/inventory/routes/canonical", label: "Canonical routes" },
    ],
  },
  "/project/[ecosystem]/[name]": {
    ideaId: "coherence-network-web-interface",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/search?q=react", label: "Search API example" },
      { href: "/api/inventory/page-lineage", label: "Page lineage" },
    ],
  },
  "/import": {
    ideaId: "coherence-signal-depth",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/import/stack", label: "Import API" },
      { href: "/api/health", label: "API health" },
    ],
  },
  "/api-health": {
    ideaId: "coherence-network-api-runtime",
    related: SHARED_RELATED,
    machinePaths: [
      { href: "/api/health", label: "Health" },
      { href: "/api/ready", label: "Readiness" },
      { href: "/api/version", label: "Version" },
    ],
  },
};

function normalizePath(pathname: string): string {
  if (pathname.startsWith("/ideas/")) return "/ideas/[idea_id]";
  if (pathname.startsWith("/specs/")) return "/specs/[spec_id]";
  if (pathname.startsWith("/project/")) return "/project/[ecosystem]/[name]";
  return pathname;
}

function dedupe(items: LinkItem[]): LinkItem[] {
  const seen = new Set<string>();
  const out: LinkItem[] = [];
  for (const item of items) {
    if (seen.has(item.href)) continue;
    seen.add(item.href);
    out.push(item);
  }
  return out;
}

function toBreadcrumb(pathname: string): string {
  if (pathname === "/") return "Home";
  return pathname
    .split("/")
    .filter(Boolean)
    .map((part) => decodeURIComponent(part).replace(/[-_]/g, " "))
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" / ");
}

export default function PageContextLinks() {
  const pathname = usePathname() || "/";
  const apiBase = getApiBase();
  const key = normalizePath(pathname);

  const dynamicIdeaId =
    key === "/ideas/[idea_id]" ? decodeURIComponent(pathname.split("/")[2] || "") : "";
  const dynamicSpecId =
    key === "/specs/[spec_id]" ? decodeURIComponent(pathname.split("/")[2] || "") : "";
  const dynamicProjectEcosystem =
    key === "/project/[ecosystem]/[name]" ? decodeURIComponent(pathname.split("/")[2] || "") : "";
  const dynamicProjectName =
    key === "/project/[ecosystem]/[name]" ? decodeURIComponent(pathname.split("/")[3] || "") : "";

  const fallback: ContextDef = {
    ideaId: "portfolio-governance",
    related: SHARED_RELATED,
    machinePaths: [{ href: "/api/inventory/system-lineage", label: "System lineage" }],
  };
  const base = CONTEXTS[key] ?? fallback;

  const ideaId = dynamicIdeaId || base.ideaId;
  const related = dedupe(
    [...base.related, { href: `/ideas/${encodeURIComponent(ideaId)}`, label: "Idea root" }].filter(
      (item) => item.href !== pathname
    )
  );
  const relatedMobile = related.slice(0, 6);

  const machine = [...base.machinePaths];
  if (key === "/ideas/[idea_id]" && dynamicIdeaId) {
    machine.unshift({
      href: `/api/ideas/${encodeURIComponent(dynamicIdeaId)}`,
      label: "Idea detail API",
    });
  }
  if (key === "/specs/[spec_id]" && dynamicSpecId) {
    machine.unshift({
      href: `/api/spec-registry/${encodeURIComponent(dynamicSpecId)}`,
      label: "Spec detail API",
    });
  }
  if (key === "/project/[ecosystem]/[name]" && dynamicProjectEcosystem && dynamicProjectName) {
    machine.unshift({
      href: `/api/projects/${encodeURIComponent(dynamicProjectEcosystem)}/${encodeURIComponent(dynamicProjectName)}`,
      label: "Project API",
    });
  }

  const machineLinks = dedupe(machine);
  const focusLabel = ideaId.replace(/[-_]/g, " ");

  return (
    <section className="border-b border-border/70 bg-background/55">
      <div className="mx-auto max-w-6xl px-4 md:px-8 py-1.5">
        <div className="flex items-center gap-2 text-xs">
          <p className="truncate text-muted-foreground">
            <span className="hidden sm:inline">Page </span>
            <span className="font-medium text-foreground">{toBreadcrumb(pathname)}</span>
          </p>
          <span className="hidden lg:inline text-muted-foreground/90">Current focus {focusLabel}</span>
          <div className="flex-1" />
          <details className="relative">
            <summary className="list-none cursor-pointer rounded-full border border-border/80 px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground">
              <span className="sm:hidden">Quick links</span>
              <span className="hidden sm:inline">Related pages</span>
            </summary>
            <div className="absolute right-0 mt-2 w-56 rounded-xl border border-border/80 bg-popover/95 p-2 shadow-lg backdrop-blur">
              {related.map((item, idx) => (
                <Link
                  key={`rel-${item.href}`}
                  href={item.href}
                  className={`block rounded px-2 py-1.5 text-sm hover:bg-accent ${idx < relatedMobile.length ? "" : "hidden sm:block"}`}
                >
                  {item.label}
                </Link>
              ))}
              <p className="mt-1 px-2 text-[11px] text-muted-foreground sm:hidden">
                Open the full menu in the header for all pages.
              </p>
            </div>
          </details>
          <details className="relative hidden sm:block">
            <summary className="list-none cursor-pointer rounded-full border border-border/80 px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground">
              Behind the scenes
            </summary>
            <div className="absolute right-0 mt-2 w-64 rounded-xl border border-border/80 bg-popover/95 p-2 shadow-lg backdrop-blur">
              {machineLinks.map((item) => (
                <a
                  key={`api-${item.href}`}
                  href={`${apiBase}${item.href}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  {item.label}
                </a>
              ))}
            </div>
          </details>
        </div>
      </div>
    </section>
  );
}
