import Link from "next/link";

import { getApiBase } from "@/lib/api";

const REPO_BLOB_MAIN = "https://github.com/seeker71/Coherence-Network/blob/main";

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

function toRepoHref(pathOrUrl: string): string {
  if (/^https?:\/\//.test(pathOrUrl)) return pathOrUrl;
  return `${REPO_BLOB_MAIN}/${pathOrUrl.replace(/^\/+/, "")}`;
}

async function loadIdea(ideaId: string): Promise<IdeaWithScore> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}`, { cache: "no-store" });
  if (res.status === 404) throw new Error("Idea not found");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeaWithScore;
}

async function loadFlowForIdea(ideaId: string): Promise<FlowItem | null> {
  const API = getApiBase();
  const params = new URLSearchParams({
    runtime_window_seconds: "86400",
    idea_id: ideaId,
  });
  const res = await fetch(`${API}/api/inventory/flow?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`flow HTTP ${res.status}`);
  const payload = (await res.json()) as FlowResponse;
  if (!Array.isArray(payload.items)) return null;
  return payload.items.find((item) => item.idea_id === ideaId) ?? null;
}

export default async function IdeaDetailPage({ params }: { params: Promise<{ idea_id: string }> }) {
  const resolved = await params;
  const ideaId = decodeURIComponent(resolved.idea_id);
  const [idea, flow] = await Promise.all([loadIdea(ideaId), loadFlowForIdea(ideaId)]);
  const apiBase = getApiBase();

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <div className="space-y-1">
        <h1 className="text-2xl font-bold">{idea.name}</h1>
        <p className="text-muted-foreground">{idea.id}</p>
      </div>

      <p>{idea.description}</p>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Manifestation</p>
          <p className="text-lg font-semibold">{idea.manifestation_status}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Free energy</p>
          <p className="text-lg font-semibold">{idea.free_energy_score.toFixed(2)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Value gap</p>
          <p className="text-lg font-semibold">{idea.value_gap.toFixed(2)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Confidence</p>
          <p className="text-lg font-semibold">{idea.confidence.toFixed(2)}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Linked Spec → Process → Implementation → Contributors</h2>
        <p className="text-muted-foreground">
          specs{" "}
          {flow && flow.spec.spec_ids.length > 0
            ? flow.spec.spec_ids.map((specId, idx) => (
                <span key={specId}>
                  {idx > 0 ? ", " : ""}
                  <Link href={`/specs/${encodeURIComponent(specId)}`} className="underline hover:text-foreground">
                    {specId}
                  </Link>
                </span>
              ))
            : (
              <Link href="/specs" className="underline hover:text-foreground">
                missing
              </Link>
            )}{" "}
          |{" "}
          <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground">
            process
          </Link>{" "}
          |{" "}
          <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground">
            implementation
          </Link>
        </p>
        <p className="text-muted-foreground">
          task_ids{" "}
          {flow && flow.process.task_ids.length > 0
            ? flow.process.task_ids.map((taskId, idx) => (
                <span key={taskId}>
                  {idx > 0 ? ", " : ""}
                  <Link href={`/tasks?task_id=${encodeURIComponent(taskId)}`} className="underline hover:text-foreground">
                    {taskId}
                  </Link>
                </span>
              ))
            : "-"}
        </p>
        <p className="text-muted-foreground">
          implementation_refs{" "}
          {flow && flow.implementation.implementation_refs.length > 0
            ? flow.implementation.implementation_refs.slice(0, 8).map((ref, idx) => (
                <span key={ref}>
                  {idx > 0 ? ", " : ""}
                  <a href={toRepoHref(ref)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                    {ref}
                  </a>
                </span>
              ))
            : "-"}
        </p>
        <p className="text-muted-foreground">
          contributors{" "}
          {flow && flow.contributors.all.length > 0
            ? flow.contributors.all.slice(0, 10).map((contributorId, idx) => (
                <span key={contributorId}>
                  {idx > 0 ? ", " : ""}
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
                    className="underline hover:text-foreground"
                  >
                    {contributorId}
                  </Link>
                </span>
              ))
            : (
              <Link href="/contributors" className="underline hover:text-foreground">
                missing
              </Link>
            )}
        </p>
        <p className="text-muted-foreground">
          usage_events {flow?.contributions.usage_events_count ?? 0} | measured_value {flow?.contributions.measured_value_total.toFixed(2) ?? "0.00"} |
          runtime_events {flow?.implementation.runtime_events_count ?? 0} | runtime_ms {flow?.implementation.runtime_total_ms.toFixed(2) ?? "0.00"}
        </p>
      </section>

      <section className="rounded border p-4 space-y-3">
        <h2 className="font-semibold">Open Questions</h2>
        {idea.open_questions.length === 0 && <p className="text-sm text-muted-foreground">None</p>}
        <ul className="space-y-2 text-sm">
          {idea.open_questions.map((q) => {
            const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
            return (
              <li key={q.question} className="rounded border p-3 space-y-1">
                <p className="font-medium">{q.question}</p>
                <p className="text-muted-foreground">
                  value {q.value_to_whole} | cost {q.estimated_cost} | ROI {roi.toFixed(2)}
                </p>
                {q.answer ? (
                  <p className="text-muted-foreground">answer: {q.answer}</p>
                ) : (
                  <p className="text-muted-foreground">answer: (unanswered)</p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">API Links</h2>
        <p className="text-muted-foreground">Use these for machine inspection and automation.</p>
        <ul className="space-y-1">
          <li>
            <a href={`${apiBase}/api/ideas/${encodeURIComponent(idea.id)}`} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              /api/ideas/{idea.id}
            </a>
          </li>
          <li>
            <a
              href={`${apiBase}/api/inventory/flow?runtime_window_seconds=86400&idea_id=${encodeURIComponent(idea.id)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              /api/inventory/flow?idea_id={idea.id}
            </a>
          </li>
          <li>
            <a href={`${apiBase}/api/runtime/ideas/summary?seconds=86400`} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              /api/runtime/ideas/summary
            </a>
          </li>
          <li>
            <a href={`${apiBase}/api/inventory/system-lineage`} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              /api/inventory/system-lineage
            </a>
          </li>
        </ul>
      </section>
    </main>
  );
}
