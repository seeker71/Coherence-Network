import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";
import {
  buildFlowSearchParams,
  UI_RUNTIME_SUMMARY_WINDOW,
} from "@/lib/egress";
import { formatConfidence, formatDecimal, formatUsd, humanizeStatus } from "@/lib/humanize";
import IdeaDsssSpecBuilder from "@/components/ideas/IdeaDsssSpecBuilder";
import IdeaProgressEditor from "@/components/ideas/IdeaProgressEditor";
import IdeaTaskQuickCreate from "@/components/ideas/IdeaTaskQuickCreate";

const REPO_BLOB_MAIN = "https://github.com/seeker71/Coherence-Network/blob/main";
const FETCH_TIMEOUT_MS = 6000;
const FETCH_RETRY_DELAY_MS = 250;
const FETCH_RETRY_ATTEMPTS = 3;
export const revalidate = 90;

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

function proofLabel(status: string): string {
  if (status === "none") return "Not proven yet";
  if (status === "partial") return "Partly proven";
  if (status === "validated") return "Proven in real use";
  return humanizeStatus(status);
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

export default async function IdeaDetailPage({ params }: { params: Promise<{ idea_id: string }> }) {
  const resolved = await params;
  const ideaId = decodeURIComponent(resolved.idea_id);
  const ideaResult = await loadIdea(ideaId);
  if (ideaResult.kind === "not_found") {
    notFound();
  }
  if (ideaResult.kind === "error") {
    return (
      <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-4">
        <h1 className="text-2xl font-bold">Idea Details Unavailable</h1>
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
  const flowResult = await loadFlowForIdea(ideaId);
  const flow = flowResult.flow;
  const apiBase = getApiBase();
  const linkedPlanIds = flow?.spec.spec_ids ?? [];
  const linkedTaskIds = flow?.process.task_ids ?? [];
  const linkedRefs = flow?.implementation.implementation_refs ?? [];
  const contributorCount = flow?.contributors.all.length ?? 0;
  const usageEventsCount = flow?.contributions.usage_events_count ?? 0;
  const measuredValueTotal = flow?.contributions.measured_value_total ?? 0;

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/today" className="text-muted-foreground hover:text-foreground">
          Today
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Plans
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Work
        </Link>
        <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="text-muted-foreground hover:text-foreground">
          Progress
        </Link>
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold">{idea.name}</h1>
        <p className="max-w-3xl text-muted-foreground">{idea.description}</p>
        <p className="text-sm text-muted-foreground">
          Current proof level: {proofLabel(idea.manifestation_status)}
        </p>
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

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">How real it is</p>
          <p className="text-lg font-semibold">{proofLabel(idea.manifestation_status)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Priority right now</p>
          <p className="text-lg font-semibold">{formatDecimal(idea.free_energy_score)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Value still available</p>
          <p className="text-lg font-semibold">{formatUsd(idea.value_gap)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">How sure we are</p>
          <p className="text-lg font-semibold">{formatConfidence(idea.confidence)}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Where This Idea Already Shows Up</h2>
        <p className="text-muted-foreground">
          Use this as a quick sense of what is already planned, moving, or producing proof.
        </p>
        {flow ? (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded border p-3 space-y-2">
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
            <div className="rounded border p-3 space-y-2">
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
            <div className="rounded border p-3 space-y-2">
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
            <div className="rounded border p-3 space-y-2">
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

      <section className="rounded border p-4 space-y-3">
        <h2 className="font-semibold">Questions Still To Answer</h2>
        {idea.open_questions.length === 0 && <p className="text-sm text-muted-foreground">Nothing open right now.</p>}
        <ul className="space-y-2 text-sm">
          {idea.open_questions.map((q) => {
            const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
            return (
              <li key={q.question} className="rounded border p-3 space-y-1">
                <p className="font-medium">{q.question}</p>
                <p className="text-muted-foreground">
                  Possible value {formatUsd(q.value_to_whole)} | Estimated effort {formatUsd(q.estimated_cost)} | Value for effort {formatDecimal(roi)}
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

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Raw Records</h2>
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
    </main>
  );
}
