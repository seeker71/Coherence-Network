import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { buildFlowSearchParams } from "@/lib/egress";
import { fetchJsonOrNull } from "@/lib/fetch";
import {
  formatConfidence,
  formatCount,
  humanizeManifestationStatus,
} from "@/lib/humanize";

const DEMO_IDEA_ID = "community-project-funder-match";

const ACTIVE_STATUSES = new Set(["pending", "queued", "in_progress", "running", "claimed"]);

const STEPS = [
  {
    title: "Open the sample idea",
    summary: "Start on the idea page and make sure a first-time reader can explain the goal, who benefits, and what is still unknown.",
    label: "Open sample idea",
  },
  {
    title: "Turn it into a small plan",
    summary: "On that same page, create one simple plan or a short set of steps so the work is not stuck at the idea stage.",
    label: "Open idea page tools",
  },
  {
    title: "Start one work card",
    summary: "Create the next small piece of work and keep its update note readable by another person, not just by the system.",
    label: "Open work board",
  },
  {
    title: "Check the visible trail",
    summary: "Open the progress view and confirm the path from idea to plan to work is visible without hunting through internal records.",
    label: "Open progress",
  },
] as const;

type IdeaQuestion = {
  question: string;
};

type Idea = {
  id: string;
  name: string;
  description: string;
  confidence: number;
  manifestation_status: string;
  open_questions: IdeaQuestion[];
};

type IdeasResponse = {
  ideas: Idea[];
  summary?: {
    total_ideas: number;
  };
};

type FlowItem = {
  idea_id: string;
  spec: {
    spec_ids: string[];
  };
  process: {
    task_ids: string[];
  };
  implementation: {
    implementation_refs: string[];
  };
};

type FlowResponse = {
  summary?: {
    ideas: number;
    with_spec: number;
    with_process: number;
  };
  items?: FlowItem[];
};

type AgentTask = {
  id: string;
  status: string;
};

type TaskListPayload =
  | AgentTask[]
  | {
      tasks?: AgentTask[];
      items?: AgentTask[];
    };

export const metadata: Metadata = {
  title: "Guided Demo | Coherence Network",
  description: "Walk one real-world idea through the MVP in plain language.",
};

export const dynamic = "force-dynamic";

function extractTasks(payload: TaskListPayload | null): AgentTask[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.tasks)) return payload.tasks;
  if (Array.isArray(payload.items)) return payload.items;
  return [];
}

function storyStage(flow: FlowItem | null): string {
  if (!flow) return "Ready for a first plan";
  if (flow.implementation.implementation_refs.length > 0) return "Visible proof has started";
  if (flow.process.task_ids.length > 0) return "Work has started";
  if (flow.spec.spec_ids.length > 0) return "A short plan exists";
  return "Ready for a first plan";
}

function nextMove(flow: FlowItem | null): string {
  if (!flow || flow.spec.spec_ids.length === 0) {
    return "Write a short plan so the idea becomes a real next step.";
  }
  if (flow.process.task_ids.length === 0) {
    return "Create the first work card so someone can start moving it forward.";
  }
  if (flow.implementation.implementation_refs.length === 0) {
    return "Add the first visible result or proof note so progress is not just a promise.";
  }
  return "Review what is already proven, then create the next follow-up step.";
}

export default async function DemoMvpPage() {
  const apiBase = getApiBase();
  const ideasData = await fetchJsonOrNull<IdeasResponse>(
    `${apiBase}/api/ideas?include_internal=false&limit=120`,
    { cache: "no-store" },
    5000,
  );

  const ideas = [...(ideasData?.ideas ?? [])];
  const demoIdea = ideas.find((idea) => idea.id === DEMO_IDEA_ID) ?? ideas[0] ?? null;

  const [flowData, demoFlowData, taskData] = await Promise.all([
    fetchJsonOrNull<FlowResponse>(
      `${apiBase}/api/inventory/flow?${buildFlowSearchParams().toString()}`,
      { cache: "no-store" },
      5000,
    ),
    demoIdea
      ? fetchJsonOrNull<FlowResponse>(
          `${apiBase}/api/inventory/flow?${buildFlowSearchParams({ ideaId: demoIdea.id }).toString()}`,
          { cache: "no-store" },
          5000,
        )
      : Promise.resolve(null),
    fetchJsonOrNull<TaskListPayload>(`${apiBase}/api/agent/tasks?limit=100`, { cache: "no-store" }, 5000),
  ]);

  const tasks = extractTasks(taskData);
  const movingTaskCount = tasks.filter((task) => ACTIVE_STATUSES.has(task.status)).length;
  const flowSummary = flowData?.summary;
  const visibleStories = flowSummary ? Math.min(flowSummary.with_spec ?? 0, flowSummary.with_process ?? 0) : 0;
  const demoFlow = demoIdea
    ? (demoFlowData?.items ?? []).find((item) => item.idea_id === demoIdea.id) ?? null
    : null;
  const ideaHref = demoIdea ? `/ideas/${encodeURIComponent(demoIdea.id)}` : "/ideas";
  const progressHref = demoIdea ? `/flow?idea_id=${encodeURIComponent(demoIdea.id)}` : "/flow";
  const taskHref = "/tasks";
  const planCount = demoFlow?.spec.spec_ids.length ?? 0;
  const workCount = demoFlow?.process.task_ids.length ?? 0;
  const proofCount = demoFlow?.implementation.implementation_refs.length ?? 0;
  const questionCount = demoIdea?.open_questions.length ?? 0;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-6xl mx-auto space-y-8">
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-8 space-y-4">
          <p className="text-sm text-muted-foreground">Guided walkthrough</p>
          <h1 className="text-3xl md:text-4xl font-light tracking-tight">See one real-world idea move through the MVP</h1>
          <p className="max-w-3xl text-muted-foreground">
            This example is not a software feature. It is a community project that needs a clear goal, a small next
            step, and visible proof that progress is real.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href={ideaHref} className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Open sample idea
            </Link>
            <Link href="/today" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Open today view
            </Link>
            <Link href={taskHref} className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Open work board
            </Link>
            <Link href={progressHref} className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Open progress
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr,0.9fr]">
          <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Sample story</p>
              <h2 className="text-xl font-medium">
                {demoIdea?.name || "Sample idea unavailable right now"}
              </h2>
              <p className="text-muted-foreground">
                {demoIdea?.description || "Open Ideas to choose a sample story from this local copy."}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground">How sure we are today</p>
                <p className="mt-1 text-lg font-semibold">{demoIdea ? formatConfidence(demoIdea.confidence) : "-"}</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground">Proof today</p>
                <p className="mt-1 text-lg font-semibold">
                  {demoIdea ? humanizeManifestationStatus(demoIdea.manifestation_status) : "Not visible yet"}
                </p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground">Questions still open</p>
                <p className="mt-1 text-lg font-semibold">{formatCount(questionCount)}</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground">Best next move</p>
                <p className="mt-1 text-sm font-medium">{nextMove(demoFlow)}</p>
              </div>
            </div>

            {demoIdea && questionCount > 0 ? (
              <div className="space-y-2">
                <p className="font-medium">Questions people still need answered</p>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {demoIdea.open_questions.slice(0, 3).map((question) => (
                    <li key={question.question} className="rounded-xl border border-border/20 bg-background/40 p-3">
                      {question.question}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>

          <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Follow the path</p>
              <h2 className="text-xl font-medium">What to click, in order</h2>
              <p className="text-muted-foreground">
                A first-time viewer should understand the project, the next step, and the proof trail without learning internal terms.
              </p>
            </div>

            <div className="space-y-3">
              {STEPS.map((step, index) => {
                const href = index === 0 || index === 1 ? ideaHref : index === 2 ? taskHref : progressHref;
                return (
                  <div key={step.title} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                    <p className="text-sm text-muted-foreground">Step {index + 1}</p>
                    <h3 className="font-medium">{step.title}</h3>
                    <p className="text-sm text-muted-foreground">{step.summary}</p>
                    <Link href={href} className="inline-flex rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
                      {step.label}
                    </Link>
                  </div>
                );
              })}
            </div>
          </article>
        </section>

        <section className="grid grid-cols-2 gap-3 text-sm lg:grid-cols-4">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-muted-foreground">Story stage</p>
            <p className="mt-1 text-lg font-semibold">{storyStage(demoFlow)}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-muted-foreground">Short plans linked</p>
            <p className="mt-1 text-xl font-semibold">{formatCount(planCount)}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-muted-foreground">Work cards linked</p>
            <p className="mt-1 text-xl font-semibold">{formatCount(workCount)}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-muted-foreground">Visible proof items</p>
            <p className="mt-1 text-xl font-semibold">{formatCount(proofCount)}</p>
          </div>
        </section>

        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-4">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Live snapshot from this local copy</p>
            <h2 className="text-xl font-medium">What is already moving here</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground">Ideas people can explore</p>
              <p className="mt-1 text-xl font-semibold">{formatCount(ideasData?.summary?.total_ideas ?? ideas.length)}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground">Work cards moving now</p>
              <p className="mt-1 text-xl font-semibold">{formatCount(movingTaskCount)}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground">Stories with plan and work visible</p>
              <p className="mt-1 text-xl font-semibold">{formatCount(visibleStories)}</p>
            </div>
          </div>
        </section>
    </main>
  );
}
