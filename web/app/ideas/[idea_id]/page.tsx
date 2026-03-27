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
import { TimeCommitmentForm } from "@/components/time_commitment_form";

const REPO_BLOB_MAIN = "https://github.com/seeker71/Coherence-Network/blob/main";
const FETCH_TIMEOUT_MS = 6000;
const FETCH_RETRY_DELAY_MS = 250;
const FETCH_RETRY_ATTEMPTS = 3;
export const revalidate = 90;

const BASE_URL = "https://coherencycoin.com";

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

type IdeaQuestion = {
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer?: string | null;
  measured_delta?: number | null;
};

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  resistance_risk: number;
  manifestation_status: string;
  interfaces: string[];
  open_questions: IdeaQuestion[];
  free_energy_score: number;
  value_gap: number;
};

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

function toRepoHref(pathOrUrl: string): string {
  if (/^https?:\/\//.test(pathOrUrl)) return pathOrUrl;
  return `${REPO_BLOB_MAIN}/${pathOrUrl.replace(/^\/+/, "")}`;
}

function fileLabel(pathOrUrl: string): string {
  const normalized = pathOrUrl.split("?")[0].split("#")[0];
  const pieces = normalized.split("/");
  return pieces[pieces.length - 1] || "Implementation file";
}

function referenceLabel(pathOrUrl: string, index: number): string {
  if (!pathOrUrl.includes("/") && pathOrUrl.includes(":")) {
    return `Saved record ${index + 1}`;
  }
  return fileLabel(pathOrUrl);
}

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

function activityIcon(type: string): string {
  if (type === "change_request") return "\uD83D\uDCDD";
  if (type === "question_answered") return "\uD83D\uDCA1";
  if (type === "question_added") return "\u2753";
  if (type === "stage_advanced") return "\uD83D\uDE80";
  if (type === "value_recorded") return "\uD83D\uDCCA";
  if (type === "lineage_link") return "\uD83D\uDD17";
  return "\u2022";
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
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
  const [flowResult, stakes, activity] = await Promise.all([
    loadFlowForIdea(ideaId),
    loadIdeaStakes(ideaId),
    loadIdeaActivity(ideaId),
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
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">
          Ideas
        </Link>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-muted-foreground">{idea.name}</span>
      </div>

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
        unansweredQuestions={idea.open_questions.filter((question) => !question.answer).map((question) => question.question)}
      />

      <IdeaDsssSpecBuilder
        ideaId={idea.id}
        ideaName={idea.name}
        description={idea.description}
        potentialValue={idea.potential_value}
        estimatedCost={idea.estimated_cost}
        openQuestions={idea.open_questions.filter((question) => !question.answer).map((question) => question.question)}
        existingSpecIds={flow?.spec.spec_ids ?? []}
      />

      {flowResult.details ? (
        <p className="text-sm text-muted-foreground">
          Flow data unavailable: <code>{flowResult.details}</code>
        </p>
      ) : null}

      <section className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
          <p className="text-muted-foreground">How real it is</p>
          <p className="text-lg font-semibold">{humanizeManifestationStatus(idea.manifestation_status)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
          <p className="text-muted-foreground">Best time to work on this</p>
          <p className="text-lg font-semibold">{humanizeIdeaPriority(idea.free_energy_score)}</p>
          <p className="text-xs text-muted-foreground">{explainIdeaPriority(idea.free_energy_score)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
          <p className="text-muted-foreground">Value still available</p>
          <p className="text-lg font-semibold">{formatUsd(idea.value_gap)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
          <p className="text-muted-foreground">How sure we are</p>
          <p className="text-lg font-semibold">{formatConfidence(idea.confidence)}</p>
        </div>
      </section>

      <section className="rounded-2xl border border-amber-200 bg-amber-50/30 p-6 space-y-3 text-sm dark:border-amber-800/40 dark:bg-amber-950/10">
        <h2 className="font-semibold text-amber-900 dark:text-amber-200">Investment</h2>
        <p className="text-amber-800/70 dark:text-amber-300/70">
          CC staked on this idea and what it produced.
        </p>
        {stakes.length > 0 ? (
          <>
            <div className="rounded-lg border border-amber-200/60 bg-white/60 p-3 dark:border-amber-800/30 dark:bg-stone-800/40">
              <p className="text-xs text-amber-700/70 dark:text-amber-400/70">Total CC Staked</p>
              <p className="text-lg font-semibold text-amber-900 dark:text-amber-100">
                {stakes.reduce((sum, s) => sum + (s.amount_cc || 0), 0).toFixed(1)} CC
              </p>
            </div>
            <ul className="space-y-1.5">
              {stakes.map((s, i) => (
                <li
                  key={`${s.contributor_id}-${i}`}
                  className="flex items-center justify-between rounded-lg border border-amber-200/40 bg-white/40 px-3 py-2 dark:border-amber-800/20 dark:bg-stone-800/30"
                >
                  <span className="text-amber-900 dark:text-amber-200">
                    {s.contributor_id}
                  </span>
                  <span className="font-medium text-amber-700 dark:text-amber-400">
                    {(s.amount_cc || 0).toFixed(1)} CC
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-amber-700/60 dark:text-amber-400/60">
            No CC staked on this idea yet.
          </p>
        )}
        <div className="flex items-center gap-2 pt-1">
          <p className="text-xs text-amber-700/60 dark:text-amber-400/60">
            Work cards: {flow?.process.task_ids.length ?? 0} created
          </p>
        </div>

        <div className="border-t border-amber-200/40 dark:border-amber-800/20 pt-4 mt-4">
          <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200 mb-3">Back this idea</h3>
          <IdeaStakeForm ideaId={idea.id} ideaName={idea.name} />
        </div>
        <div className="border-t border-amber-200/40 dark:border-amber-800/20 pt-4 mt-4">
          <TimeCommitmentForm ideaId={idea.id} ideaName={idea.name} />
        </div>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="font-semibold">Activity</h2>
        {activity.length > 0 ? (
          <div className="relative space-y-0">
            {activity.map((event, i) => (
              <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
                <div className="flex flex-col items-center">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted/60 text-xs">
                    {activityIcon(event.type)}
                  </span>
                  {i < activity.length - 1 && (
                    <div className="mt-1 w-px flex-1 bg-border/40" />
                  )}
                </div>
                <div className="min-w-0 flex-1 pt-0.5">
                  <p className="text-foreground">{event.summary}</p>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{timeAgo(event.timestamp)}</span>
                    {event.contributor_id && (
                      <>
                        <span>&middot;</span>
                        <span>{event.contributor_id}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground">No activity recorded yet.</p>
        )}
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
        <h2 className="text-xl font-semibold">Where This Idea Already Shows Up</h2>
        <p className="text-muted-foreground">
          Use this as a quick sense of what is already planned, moving, or producing proof.
        </p>
        {flow ? (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
              <p className="font-medium">Plans</p>
              <p className="text-muted-foreground">
                {linkedPlanIds.length > 0
                  ? `${linkedPlanIds.length} plan${linkedPlanIds.length === 1 ? "" : "s"} linked to this idea.`
                  : "No plans linked yet."}
              </p>
              {linkedPlanIds.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {linkedPlanIds.slice(0, 3).map((specId, idx) => (
                    <Link
                      key={specId}
                      href={`/specs/${encodeURIComponent(specId)}`}
                      className="underline hover:text-foreground"
                      title={`Plan ID: ${specId}`}
                    >
                      Open plan {idx + 1}
                    </Link>
                  ))}
                  {linkedPlanIds.length > 3 ? (
                    <Link href="/specs" className="underline hover:text-foreground">
                      See all plans
                    </Link>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
              <p className="font-medium">Work cards</p>
              <p className="text-muted-foreground">
                {linkedTaskIds.length > 0
                  ? `${linkedTaskIds.length} work card${linkedTaskIds.length === 1 ? "" : "s"} created so far.`
                  : "No work cards yet."}
              </p>
              {linkedTaskIds.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {linkedTaskIds.slice(0, 3).map((taskId, idx) => (
                    <Link
                      key={taskId}
                      href={`/tasks?task_id=${encodeURIComponent(taskId)}`}
                      className="underline hover:text-foreground"
                      title={`Task ID: ${taskId}`}
                    >
                      Open work card {idx + 1}
                    </Link>
                  ))}
                  {linkedTaskIds.length > 3 ? (
                    <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground">
                      See all work
                    </Link>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
              <p className="font-medium">Files and saved results</p>
              <p className="text-muted-foreground">
                {linkedRefs.length > 0
                  ? `${linkedRefs.length} linked file${linkedRefs.length === 1 ? "" : "s"} or saved result${linkedRefs.length === 1 ? "" : "s"}.`
                  : "No linked files or saved results yet."}
              </p>
              {linkedRefs.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {linkedRefs.slice(0, 3).map((ref, idx) => (
                    <a
                      key={ref}
                      href={toRepoHref(ref)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                      title={ref}
                    >
                      {referenceLabel(ref, idx)}
                    </a>
                  ))}
                  {linkedRefs.length > 3 ? (
                    <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground">
                      See more links
                    </Link>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
              <p className="font-medium">People and proof</p>
              <p className="text-muted-foreground">
                {contributorCount} people or agents touched this idea. {usageEventsCount} usage
                signal{usageEventsCount === 1 ? "" : "s"} recorded. Measured value so far: {formatUsd(measuredValueTotal)}.
              </p>
              <div className="flex flex-wrap gap-2">
                <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground">
                  Open progress view
                </Link>
                <Link href="/contributors" className="underline hover:text-foreground">
                  Open people view
                </Link>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground">The linked progress summary is not available right now.</p>
        )}
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-xl font-semibold">Questions Still To Answer</h2>
        {idea.open_questions.length === 0 && <p className="text-sm text-muted-foreground">Nothing open right now.</p>}
        <ul className="space-y-2 text-sm">
          {idea.open_questions.map((q) => {
            return (
              <li key={q.question} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                <p className="font-medium">{q.question}</p>
                <p className="text-muted-foreground">
                  Why this matters {formatUsd(q.value_to_whole)} | Expected work {formatUsd(q.estimated_cost)}
                </p>
                {q.answer ? (
                  <p className="text-muted-foreground">Current answer: {q.answer}</p>
                ) : (
                  <p className="text-muted-foreground">No answer yet.</p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
        <h2 className="text-xl font-semibold">Raw Records</h2>
        <p className="text-muted-foreground">Most people can ignore this section. Use it only when you need the underlying records.</p>
        <ul className="space-y-1">
          <li>
            <a href={`${apiBase}/api/ideas/${encodeURIComponent(idea.id)}`} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              Open idea API record
            </a>
          </li>
          <li>
            <a
              href={`${apiBase}/api/inventory/flow?${buildFlowSearchParams({ ideaId: idea.id }).toString()}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              Open flow API record
            </a>
          </li>
          <li>
            <a
              href={`${apiBase}/api/runtime/ideas/summary?seconds=${UI_RUNTIME_SUMMARY_WINDOW}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              Open runtime summary API
            </a>
          </li>
          <li>
            <a href={`${apiBase}/api/inventory/system-lineage`} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              Open system lineage API
            </a>
          </li>
        </ul>
      </section>

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
