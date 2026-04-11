import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";
import {
  buildFlowSearchParams,
  UI_RUNTIME_SUMMARY_WINDOW,
} from "@/lib/egress";
import {
  explainIdeaPriority,
  formatConfidence,
  formatUsd,
  humanizeIdeaPriority,
  humanizeManifestationStatus,
} from "@/lib/humanize";
import IdeaDsssSpecBuilder from "@/components/ideas/IdeaDsssSpecBuilder";
import IdeaProgressEditor from "@/components/ideas/IdeaProgressEditor";
import IdeaTaskQuickCreate from "@/components/ideas/IdeaTaskQuickCreate";
import IdeaShare from "@/components/idea_share";
import { IdeaStakeForm } from "@/components/idea_stake_form";
import IdeaLensPanel from "@/components/ideas/IdeaLensPanel";
import IdeaDetailTabs from "@/components/ideas/IdeaDetailTabs";
import { loadPublicWebConfig } from "@/lib/app-config";
import type { IdeaQuestion, IdeaWithScore } from "@/lib/types";

const { fetchDefaults: FETCH_DEFAULTS, webUiBaseUrl: BASE_URL } = loadPublicWebConfig();
const FETCH_TIMEOUT_MS = FETCH_DEFAULTS.timeoutMs;
const FETCH_RETRY_DELAY_MS = 250;
const FETCH_RETRY_ATTEMPTS = FETCH_DEFAULTS.retryAttempts;
export const revalidate = 90;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ idea_id: string }>;
}): Promise<Metadata> {
  const resolved = await params;
  const ideaId = decodeURIComponent(resolved.idea_id);
  const result = await loadIdea(ideaId);
  if (result.kind !== "ok") {
    return { title: "Idea" };
  }
  const idea = result.idea;
  const ideaUrl = `${BASE_URL}/ideas/${encodeURIComponent(idea.id)}`;
  return {
    title: idea.name,
    description: idea.description.slice(0, 300),
    openGraph: {
      title: idea.name,
      description: idea.description.slice(0, 300),
      url: ideaUrl,
      type: "article",
    },
    twitter: {
      card: "summary",
      title: idea.name,
      description: idea.description.slice(0, 200),
    },
  };
}

type FlowItem = {
  idea_id: string;
  spec: { spec_ids: string[] };
  process: {
    task_ids: string[];
    thread_branches: string[];
    source_files: string[];
  };
  implementation: {
    lineage_ids: string[];
    implementation_refs: string[];
    runtime_events_count: number;
    runtime_total_ms: number;
    runtime_cost_estimate: number;
  };
  contributors: {
    all: string[];
    by_role: Record<string, string[]>;
  };
  contributions: {
    usage_events_count: number;
    measured_value_total: number;
  };
};

type FlowResponse = {
  items: FlowItem[];
};

type LoadIdeaResult =
  | { kind: "ok"; idea: IdeaWithScore }
  | { kind: "not_found" }
  | { kind: "error"; details: string };

type StakeRecord = {
  contributor_id: string;
  amount_cc: number;
  contribution_type: string;
  idea_id?: string;
  timestamp?: string;
};

type InvestmentData = {
  contributor_id: string;
  ideas: Record<string, StakeRecord[]>;
};

type ActivityEvent = {
  type: string;
  timestamp: string;
  summary: string;
  contributor_id?: string | null;
};

type LoadFlowResult = {
  flow: FlowItem | null;
  details: string | null;
};

type IdeaListPayload =
  | {
      ideas?: IdeaWithScore[];
    }
  | IdeaWithScore[];

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJsonWithRetries<T>(
  url: string,
  attempts = FETCH_RETRY_ATTEMPTS,
): Promise<{ status: number | null; data: T | null; details: string | null }> {
  let lastStatus: number | null = null;
  let lastDetails: string | null = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(new DOMException("Request timed out", "TimeoutError")),
      FETCH_TIMEOUT_MS,
    );
    try {
      const res = await fetch(url, { cache: "no-store", signal: controller.signal });
      lastStatus = res.status;
      if (res.ok) {
        return { status: res.status, data: (await res.json()) as T, details: null };
      }
      lastDetails = `HTTP ${res.status}`;
      if (res.status < 500 && res.status !== 429) {
        return { status: res.status, data: null, details: lastDetails };
      }
    } catch (error) {
      lastDetails = String(error);
    } finally {
      clearTimeout(timeoutId);
    }
    if (attempt < attempts) {
      await wait(FETCH_RETRY_DELAY_MS * attempt);
    }
  }

  return { status: lastStatus, data: null, details: lastDetails };
}

async function loadIdea(ideaId: string): Promise<LoadIdeaResult> {
  const API = getApiBase();
  const detailUrl = `${API}/api/ideas/${encodeURIComponent(ideaId)}`;
  const detailResult = await fetchJsonWithRetries<IdeaWithScore>(detailUrl);
  if (detailResult.data) return { kind: "ok", idea: detailResult.data };
  if (detailResult.status === 404) return { kind: "not_found" };

  // Fallback to idea list lookup when detail route is intermittently unavailable.
  const listUrl = `${API}/api/ideas?limit=60`;
  const listResult = await fetchJsonWithRetries<IdeaListPayload>(listUrl);
  const listPayload = listResult.data;
  const ideaRows = Array.isArray(listPayload)
    ? listPayload
    : Array.isArray(listPayload?.ideas)
      ? listPayload.ideas
      : [];
  const fromList = ideaRows.find((idea) => idea.id === ideaId);
  if (fromList) return { kind: "ok", idea: fromList };

  const detailReason = detailResult.details || "detail endpoint unavailable";
  const listReason = listResult.details || "ideas fallback unavailable";
  return { kind: "error", details: `${detailReason}; fallback ${listReason}` };
}

async function loadFlowForIdea(ideaId: string): Promise<LoadFlowResult> {
  const API = getApiBase();
  const params = buildFlowSearchParams({ ideaId });
  const url = `${API}/api/inventory/flow?${params.toString()}`;
  const result = await fetchJsonWithRetries<FlowResponse>(url);
  if (!result.data || !Array.isArray(result.data.items)) {
    return { flow: null, details: result.details || "Flow payload unavailable" };
  }
  return {
    flow: result.data.items.find((item) => item.idea_id === ideaId) ?? null,
    details: null,
  };
}

async function loadIdeaStakes(ideaId: string): Promise<StakeRecord[]> {
  // Aggregate stakes from all contributors by scanning the flow contributors
  // and checking their ledger entries for this idea.
  // For now, try to get stakes from flow contributors' ledger data.
  try {
    const API = getApiBase();
    // Use a broad search — check known contributors' idea investments
    // The /contributions endpoint lists all contributions; filter for stakes on this idea.
    const res = await fetch(`${API}/api/contributions?limit=500`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    const items: StakeRecord[] = (data?.items ?? (Array.isArray(data) ? data : []))
      .filter((r: StakeRecord) => r.idea_id === ideaId && r.contribution_type === "stake");
    return items;
  } catch {
    return [];
  }
}

async function loadIdeaActivity(ideaId: string): Promise<ActivityEvent[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}/activity?limit=20`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.events ?? [];
  } catch {
    return [];
  }
}

type RegistrySpec = {
  spec_id: string;
  title: string;
  summary?: string;
  idea_id?: string | null;
};

type ChildIdea = {
  id: string;
  name: string;
  description: string;
  manifestation_status: string;
  free_energy_score: number;
};

async function loadRegistrySpecs(ideaId: string): Promise<RegistrySpec[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}/specs`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function loadChildIdeas(ideaId: string): Promise<ChildIdea[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}/children`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export default async function IdeaDetailPage({ params }: { params: Promise<{ idea_id: string }> }) {
  const resolved = await params;
  const ideaId = decodeURIComponent(resolved.idea_id);
  const ideaResult = await loadIdea(ideaId);
  if (ideaResult.kind === "not_found") {
    notFound();
  }
  if (ideaResult.kind === "error") {
    return (
      <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-8">
        <h1 className="text-3xl font-bold tracking-tight">Idea Details Unavailable</h1>
        <p className="text-muted-foreground">
          Could not load this idea from upstream right now.
        </p>
        <p className="text-sm text-muted-foreground">
          details <code>{ideaResult.details}</code>
        </p>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href="/ideas" className="underline hover:text-foreground">
            Back to ideas
          </Link>
          <a
            href={`${getApiBase()}/api/ideas/${encodeURIComponent(ideaId)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-foreground"
          >
            Open upstream API
          </a>
        </div>
      </main>
    );
  }

  const idea = ideaResult.idea;
  const [flowResult, stakes, activity, registrySpecs, childIdeas] = await Promise.all([
    loadFlowForIdea(ideaId),
    loadIdeaStakes(ideaId),
    loadIdeaActivity(ideaId),
    loadRegistrySpecs(ideaId),
    loadChildIdeas(ideaId),
  ]);
  const flow = flowResult.flow;
  const apiBase = getApiBase();
  const linkedPlanIds = flow?.spec.spec_ids ?? [];
  const linkedTaskIds = flow?.process.task_ids ?? [];
  const linkedRefs = flow?.implementation.implementation_refs ?? [];
  const contributorCount = flow?.contributors.all.length ?? 0;
  const usageEventsCount = flow?.contributions.usage_events_count ?? 0;
  const measuredValueTotal = flow?.contributions.measured_value_total ?? 0;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">
          Ideas
        </Link>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-muted-foreground">{idea.name}</span>
      </div>

      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{idea.name}</h1>
        <p className="max-w-3xl text-muted-foreground">{idea.description}</p>
        <p className="text-sm text-muted-foreground">
          Current proof level: {humanizeManifestationStatus(idea.manifestation_status)}
        </p>
        <IdeaShare
          ideaId={idea.id}
          name={idea.name}
          description={idea.description}
          valueGap={idea.value_gap}
          status={humanizeManifestationStatus(idea.manifestation_status)}
          url={`${BASE_URL}/ideas/${encodeURIComponent(idea.id)}`}
        />
      </div>

      {/* Tabbed content */}
      <IdeaDetailTabs
        idea={idea}
        flow={flow}
        stakes={stakes}
        activity={activity}
        apiBase={apiBase}
        flowDetails={flowResult.details}
        display={{
          manifestationLabel: humanizeManifestationStatus(idea.manifestation_status),
          priorityLabel: humanizeIdeaPriority(idea.free_energy_score),
          priorityExplain: explainIdeaPriority(idea.free_energy_score),
          valueGap: formatUsd(idea.value_gap),
          confidence: formatConfidence(idea.confidence),
          measuredValueTotal: formatUsd(measuredValueTotal),
        }}
        linkedPlanIds={linkedPlanIds}
        linkedTaskIds={linkedTaskIds}
        linkedRefs={linkedRefs}
        flowSearchParams={buildFlowSearchParams({ ideaId: idea.id }).toString()}
        registrySpecs={registrySpecs}
        childIdeas={childIdeas}
      >
        {/* Interactive server-rendered client components placed as Overview tab children */}
        <IdeaLensPanel ideaId={idea.id} defaultLens="libertarian" />

        <IdeaProgressEditor
          ideaId={idea.id}
          initialActualValue={idea.actual_value}
          initialActualCost={idea.actual_cost}
          initialConfidence={idea.confidence}
          initialManifestationStatus={idea.manifestation_status as "none" | "partial" | "validated"}
        />

        <IdeaTaskQuickCreate
          ideaId={idea.id}
          ideaName={idea.name}
          unansweredQuestions={idea.open_questions.filter((q) => !q.answer).map((q) => q.question)}
        />

        <IdeaDsssSpecBuilder
          ideaId={idea.id}
          ideaName={idea.name}
          description={idea.description}
          potentialValue={idea.potential_value}
          estimatedCost={idea.estimated_cost}
          openQuestions={idea.open_questions.filter((q) => !q.answer).map((q) => q.question)}
          existingSpecIds={flow?.spec.spec_ids ?? []}
        />

        <div className="border-t border-amber-200/40 dark:border-amber-800/20 pt-4">
          <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200 mb-3">Back this idea</h3>
          <IdeaStakeForm ideaId={idea.id} ideaName={idea.name} />
        </div>
      </IdeaDetailTabs>

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">All Ideas</Link>
          <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="text-amber-600 dark:text-amber-400 hover:underline">Progress</Link>
          <Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">Contribute</Link>
        </div>
      </nav>
    </main>
  );
}
