"use client";

import Link from "next/link";
import { useState } from "react";
import { useExpertMode } from "@/components/expert-mode-context";
import { ClientTabs } from "@/components/ui/client-tabs";
// Client components cannot import app-config (fs/os), but the server injects
// the resolved PublicWebConfig into window.__COHERENCE_PUBLIC_CONFIG__ from
// layout.tsx, so we read it back via readPublicWebConfig().
import { readPublicWebConfig } from "@/lib/public-config";
import type { IdeaQuestion, IdeaWithScore } from "@/lib/types";

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

type StakeRecord = {
  contributor_id: string;
  amount_cc: number;
  contribution_type: string;
  idea_id?: string;
  timestamp?: string;
};

type ActivityEvent = {
  type: string;
  timestamp: string;
  summary: string;
  contributor_id?: string | null;
};

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

interface IdeaDetailTabsProps {
  idea: IdeaWithScore;
  flow: FlowItem | null;
  stakes: StakeRecord[];
  activity: ActivityEvent[];
  apiBase: string;
  flowDetails: string | null;
  /** Preformatted display values */
  display: {
    manifestationLabel: string;
    priorityLabel: string;
    priorityExplain: string;
    valueGap: string;
    confidence: string;
    measuredValueTotal: string;
  };
  linkedPlanIds: string[];
  linkedTaskIds: string[];
  linkedRefs: string[];
  flowSearchParams: string;
  /** Specs registered directly against this idea via frontmatter idea_id. */
  registrySpecs?: RegistrySpec[];
  /** Child ideas whose parent_idea_id equals this idea (absorbed under the super-idea). */
  childIdeas?: ChildIdea[];
  /** Child slot: interactive forms (IdeaLensPanel, IdeaProgressEditor, etc.) */
  children?: React.ReactNode;
}

function toRepoHref(pathOrUrl: string): string {
  if (/^https?:\/\//.test(pathOrUrl)) return pathOrUrl;
  const repoBlob = readPublicWebConfig().repoUrl;
  return `${repoBlob}/${pathOrUrl.replace(/^\/+/, "")}`;
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

function activityIcon(type: string): string {
  if (type === "change_request") return "📝";
  if (type === "question_answered") return "💡";
  if (type === "question_added") return "❓";
  if (type === "stage_advanced") return "🚀";
  if (type === "value_recorded") return "📊";
  if (type === "lineage_link") return "🔗";
  return "•";
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function IdeaDetailTabs({
  idea,
  flow,
  stakes,
  activity,
  apiBase,
  flowDetails,
  display,
  linkedPlanIds,
  linkedTaskIds,
  linkedRefs,
  flowSearchParams,
  registrySpecs,
  childIdeas,
  children,
}: IdeaDetailTabsProps) {
  const { isExpert } = useExpertMode();
  const [rawJsonOpen, setRawJsonOpen] = useState(false);

  const contributorCount = flow?.contributors.all.length ?? 0;
  const usageEventsCount = flow?.contributions.usage_events_count ?? 0;

  const specCount = (registrySpecs && registrySpecs.length) || linkedPlanIds.length;
  const childCount = childIdeas?.length ?? 0;

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "specs", label: "Specs", count: specCount },
    ...(childCount > 0 ? [{ id: "absorbed", label: "Absorbed", count: childCount }] : []),
    { id: "tasks", label: "Tasks", count: linkedTaskIds.length },
    { id: "contributors", label: "Contributors", count: contributorCount },
    { id: "edges", label: "Edges", count: linkedRefs.length },
    { id: "history", label: "History", count: activity.length },
  ];

  return (
    <ClientTabs tabs={tabs} defaultTab="overview">
      {(activeTab) => (
        <>
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Metrics grid */}
              <section className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5">
                  <p className="text-muted-foreground text-xs">
                    {isExpert ? "Manifestation status" : "How real it is"}
                  </p>
                  <p className="text-lg font-semibold mt-1">{display.manifestationLabel}</p>
                  {isExpert && (
                    <p className="text-xs text-muted-foreground mt-1 font-mono">{idea.manifestation_status}</p>
                  )}
                </div>
                <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5">
                  <p className="text-muted-foreground text-xs">
                    {isExpert ? "Free energy score" : "Best time to work on this"}
                  </p>
                  <p className="text-lg font-semibold mt-1">{display.priorityLabel}</p>
                  <p className="text-xs text-muted-foreground mt-1">{display.priorityExplain}</p>
                  {isExpert && (
                    <p className="text-xs text-muted-foreground font-mono">{idea.free_energy_score.toFixed(4)}</p>
                  )}
                </div>
                <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5">
                  <p className="text-muted-foreground text-xs">
                    {isExpert ? "Value gap" : "Value still available"}
                  </p>
                  <p className="text-lg font-semibold mt-1">{display.valueGap}</p>
                </div>
                <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5">
                  <p className="text-muted-foreground text-xs">
                    {isExpert ? "Confidence score" : "How sure we are"}
                  </p>
                  <p className="text-lg font-semibold mt-1">{display.confidence}</p>
                  {isExpert && (
                    <p className="text-xs text-muted-foreground font-mono">{idea.confidence.toFixed(4)}</p>
                  )}
                </div>
              </section>

              {/* Interactive children (lens panel, progress editor, stake form, etc.) */}
              {children}

              {/* Open questions */}
              <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
                <h2 className="text-lg font-semibold">
                  {isExpert ? "Open questions" : "Questions still to answer"}
                </h2>
                {idea.open_questions.length === 0 && (
                  <p className="text-sm text-muted-foreground">Nothing open right now.</p>
                )}
                <ul className="space-y-2 text-sm">
                  {idea.open_questions.map((q) => (
                    <li key={q.question} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                      <p className="font-medium">{q.question}</p>
                      {!isExpert ? (
                        <p className="text-muted-foreground">
                          {q.answer ? `Current answer: ${q.answer}` : "No answer yet."}
                        </p>
                      ) : (
                        <>
                          <p className="text-muted-foreground">
                            Value to whole: {q.value_to_whole} | Estimated cost: {q.estimated_cost}
                          </p>
                          {q.answer ? (
                            <p className="text-muted-foreground">Answer: {q.answer}</p>
                          ) : (
                            <p className="text-muted-foreground">No answer yet.</p>
                          )}
                          {q.measured_delta != null && (
                            <p className="text-xs font-mono text-muted-foreground">
                              Measured delta: {q.measured_delta}
                            </p>
                          )}
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              {/* Investment summary */}
              <section className="rounded-2xl border border-amber-200 bg-amber-50/30 p-6 space-y-3 text-sm dark:border-amber-800/40 dark:bg-amber-950/10">
                <h2 className="font-semibold text-amber-900 dark:text-amber-200">Investment</h2>
                <p className="text-amber-800/70 dark:text-amber-300/70">
                  {isExpert ? "CC staked and contribution metrics." : "CC staked on this idea and what it produced."}
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
                          <span className="text-amber-900 dark:text-amber-200">{s.contributor_id}</span>
                          <span className="font-medium text-amber-700 dark:text-amber-400">
                            {(s.amount_cc || 0).toFixed(1)} CC
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="text-amber-700/60 dark:text-amber-400/60">No CC staked on this idea yet.</p>
                )}
                <div className="flex items-center gap-2 pt-1">
                  <p className="text-xs text-amber-700/60 dark:text-amber-400/60">
                    Work cards: {flow?.process.task_ids.length ?? 0} created
                  </p>
                  {isExpert && (
                    <p className="text-xs font-mono text-amber-700/50 dark:text-amber-400/40">
                      usage_events={usageEventsCount} measured={display.measuredValueTotal}
                    </p>
                  )}
                </div>
              </section>

              {/* Expert: raw JSON toggle */}
              {isExpert && (
                <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Raw JSON</h2>
                    <button
                      type="button"
                      onClick={() => setRawJsonOpen((v) => !v)}
                      className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted/60"
                    >
                      {rawJsonOpen ? "Hide" : "Show"}
                    </button>
                  </div>
                  {rawJsonOpen && (
                    <pre className="overflow-x-auto rounded-xl bg-muted/30 p-4 text-xs font-mono whitespace-pre-wrap">
                      {JSON.stringify(idea, null, 2)}
                    </pre>
                  )}
                </section>
              )}
            </div>
          )}

          {activeTab === "specs" && (
            <div className="space-y-4 text-sm">
              <h2 className="text-lg font-semibold">
                {isExpert ? "Linked specs (registry)" : "Specs for this idea"}
              </h2>
              {registrySpecs && registrySpecs.length > 0 ? (
                <ul className="space-y-2">
                  {registrySpecs.map((s) => (
                    <li key={s.spec_id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                      <Link
                        href={`/specs/${encodeURIComponent(s.spec_id)}`}
                        className="underline hover:text-foreground font-medium"
                      >
                        {s.title || s.spec_id}
                      </Link>
                      {s.summary && (
                        <p className="text-xs text-muted-foreground leading-relaxed">{s.summary}</p>
                      )}
                      {isExpert && (
                        <p className="text-xs font-mono text-muted-foreground">{s.spec_id}</p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : linkedPlanIds.length > 0 ? (
                <>
                  {flowDetails && (
                    <p className="text-muted-foreground text-xs">Flow data unavailable: <code>{flowDetails}</code></p>
                  )}
                  <ul className="space-y-2">
                    {linkedPlanIds.map((specId, idx) => (
                      <li key={specId} className="rounded-xl border border-border/20 bg-background/40 p-4">
                        <Link
                          href={`/specs/${encodeURIComponent(specId)}`}
                          className="underline hover:text-foreground font-medium"
                        >
                          {isExpert ? specId : `Plan ${idx + 1}`}
                        </Link>
                        {isExpert && (
                          <p className="text-xs font-mono text-muted-foreground mt-1">{specId}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-muted-foreground">No specs linked yet.</p>
              )}
            </div>
          )}

          {activeTab === "absorbed" && childIdeas && (
            <div className="space-y-4 text-sm">
              <h2 className="text-lg font-semibold">
                {isExpert ? "Child ideas (parent_idea_id match)" : "Ideas absorbed into this one"}
              </h2>
              <p className="text-muted-foreground text-xs">
                These ideas were wired under this super-idea during the fractal restructure.
              </p>
              {childIdeas.length === 0 ? (
                <p className="text-muted-foreground">No absorbed ideas yet.</p>
              ) : (
                <ul className="space-y-2">
                  {childIdeas.map((c) => (
                    <li key={c.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                      <Link
                        href={`/ideas/${encodeURIComponent(c.id)}`}
                        className="underline hover:text-foreground font-medium"
                      >
                        {c.name}
                      </Link>
                      {c.description && (
                        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                          {c.description}
                        </p>
                      )}
                      {isExpert && (
                        <p className="text-xs font-mono text-muted-foreground">
                          {c.id} · fes={c.free_energy_score.toFixed(3)}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {activeTab === "tasks" && (
            <div className="space-y-4 text-sm">
              <h2 className="text-lg font-semibold">
                {isExpert ? "Linked task IDs" : "Work cards for this idea"}
              </h2>
              {linkedTaskIds.length === 0 ? (
                <p className="text-muted-foreground">No work cards yet.</p>
              ) : (
                <ul className="space-y-2">
                  {linkedTaskIds.map((taskId, idx) => (
                    <li key={taskId} className="rounded-xl border border-border/20 bg-background/40 p-4">
                      <Link
                        href={`/tasks?task_id=${encodeURIComponent(taskId)}`}
                        className="underline hover:text-foreground font-medium"
                      >
                        {isExpert ? taskId : `Work card ${idx + 1}`}
                      </Link>
                      {isExpert && (
                        <p className="text-xs font-mono text-muted-foreground mt-1">{taskId}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <Link
                href={`/flow?idea_id=${encodeURIComponent(idea.id)}`}
                className="text-primary hover:underline text-sm"
              >
                Open full progress view &rarr;
              </Link>
            </div>
          )}

          {activeTab === "contributors" && (
            <div className="space-y-4 text-sm">
              <h2 className="text-lg font-semibold">
                {isExpert ? "Contributors and metrics" : "People who worked on this"}
              </h2>
              {!flow ? (
                <p className="text-muted-foreground">Contributor data not available.</p>
              ) : (
                <>
                  <p className="text-muted-foreground">
                    {contributorCount} {contributorCount === 1 ? "person" : "people"} or agents touched this idea.
                  </p>
                  {flow.contributors.all.length > 0 && (
                    <ul className="space-y-2">
                      {flow.contributors.all.map((cId) => (
                        <li key={cId} className="rounded-xl border border-border/20 bg-background/40 p-4 flex items-center justify-between">
                          <span>{cId}</span>
                          {isExpert && (
                            <span className="text-xs font-mono text-muted-foreground">
                              {Object.entries(flow.contributors.by_role)
                                .filter(([, ids]) => ids.includes(cId))
                                .map(([role]) => role)
                                .join(", ") || "contributor"}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {isExpert && (
                    <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                      <p className="font-medium">Metrics</p>
                      <p className="text-muted-foreground font-mono text-xs">
                        usage_events: {usageEventsCount}<br />
                        measured_value: {display.measuredValueTotal}
                      </p>
                    </div>
                  )}
                  <Link href="/contributors" className="text-primary hover:underline">
                    Open people view &rarr;
                  </Link>
                </>
              )}
            </div>
          )}

          {activeTab === "edges" && (
            <div className="space-y-4 text-sm">
              <h2 className="text-lg font-semibold">
                {isExpert ? "Implementation references" : "Files and saved results"}
              </h2>
              {linkedRefs.length === 0 ? (
                <p className="text-muted-foreground">No linked files or saved results yet.</p>
              ) : (
                <ul className="space-y-2">
                  {linkedRefs.map((ref, idx) => (
                    <li key={ref} className="rounded-xl border border-border/20 bg-background/40 p-4">
                      <a
                        href={toRepoHref(ref)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline hover:text-foreground font-medium"
                        title={ref}
                      >
                        {referenceLabel(ref, idx)}
                      </a>
                      {isExpert && (
                        <p className="text-xs font-mono text-muted-foreground mt-1 break-all">{ref}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {isExpert && flow && (
                <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                  <p className="font-medium">API Links</p>
                  <ul className="space-y-1 text-xs font-mono">
                    <li>
                      <a href={`${apiBase}/api/ideas/${encodeURIComponent(idea.id)}`} target="_blank" rel="noopener noreferrer" className="underline text-primary">
                        /api/ideas/{idea.id}
                      </a>
                    </li>
                    <li>
                      <a href={`${apiBase}/api/inventory/flow?${flowSearchParams}`} target="_blank" rel="noopener noreferrer" className="underline text-primary">
                        /api/inventory/flow
                      </a>
                    </li>
                  </ul>
                </div>
              )}
            </div>
          )}

          {activeTab === "history" && (
            <div className="space-y-4 text-sm">
              <h2 className="text-lg font-semibold">
                {isExpert ? "Activity events" : "Recent activity"}
              </h2>
              {activity.length === 0 ? (
                <p className="text-muted-foreground">No activity recorded yet.</p>
              ) : (
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
                          {isExpert && (
                            <>
                              <span>&middot;</span>
                              <span className="font-mono">{event.type}</span>
                              <span className="font-mono">{event.timestamp}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </ClientTabs>
  );
}
