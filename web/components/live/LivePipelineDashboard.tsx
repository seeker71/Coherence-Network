"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type RunnerRow = {
  runner_id?: string;
  status?: string;
  host?: string;
  version?: string;
  active_task_id?: string;
  online?: boolean;
  last_seen_at?: string | null;
};

type TaskSlice = {
  id?: string;
  task_type?: string;
  model?: string;
  direction?: string;
  claimed_by?: string;
  running_seconds?: number | null;
  wait_seconds?: number | null;
  duration_seconds?: number | null;
};

type IdeaMotion = {
  idea_id?: string;
  idea_name?: string;
  manifestation_status?: string;
  event_count?: number;
  by_source?: Record<string, number>;
  runtime_cost_estimate?: number;
};

type LivePayload = {
  generated_at: string;
  summary: {
    runners_online: number;
    tasks_running: number;
    tasks_pending: number;
    queue_depth: number;
    recent_completions_visible: number;
    pipeline_healthy?: boolean;
  };
  runners: { online_count: number; items: RunnerRow[] };
  execution: {
    running: TaskSlice[];
    pending: TaskSlice[];
    recent_completed: TaskSlice[];
    diagnostics?: Record<string, unknown>;
  };
  providers: {
    success_rate?: { rate?: number; completed?: number; failed?: number; total?: number };
    by_model?: Record<string, { successes?: number; failures?: number; rate?: number }> | Record<string, unknown>;
  };
  effectiveness: Record<string, unknown>;
  prompt_ab: {
    variants?: Record<string, { selection_probability?: number; sample_count?: number; roi?: number }>;
    total_measurements?: number;
  };
  ideas_in_motion: IdeaMotion[];
  partial_errors?: string[];
};

const POLL_MS = 15000;

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function LivePipelineDashboard({ initial }: { initial: Record<string, unknown> | null }) {
  const [data, setData] = useState<LivePayload | null>(initial as LivePayload | null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchLive = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/agent/live-pipeline", { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const json = (await res.json()) as LivePayload;
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchLive();
    const t = window.setInterval(() => {
      void fetchLive();
    }, POLL_MS);
    return () => window.clearInterval(t);
  }, [fetchLive]);

  if (error && !data) {
    return (
      <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-6 space-y-3">
        <p className="text-destructive font-medium">Could not load live pipeline</p>
        <p className="text-sm text-muted-foreground">{error}</p>
        <button
          type="button"
          onClick={() => void fetchLive()}
          className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent"
        >
          Retry
        </button>
      </div>
    );
  }

  const snap = data;
  const summary = snap?.summary;
  const variants = snap?.prompt_ab?.variants || {};
  const variantKeys = Object.keys(variants);
  const byModel = snap?.providers?.by_model as
    | Record<string, { count?: number; avg_duration?: number }>
    | undefined;
  const modelKeys = byModel && typeof byModel === "object" ? Object.keys(byModel) : [];
  const eff = snap?.effectiveness || {};
  const throughput = (eff.throughput as { tasks_per_day?: number; completed_7d?: number } | undefined) || {};

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Updated {snap ? formatTime(snap.generated_at) : "—"}</p>
          {loading ? <p className="text-xs text-muted-foreground mt-1">Refreshing…</p> : null}
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link href="/tasks" className="rounded-lg border border-border/30 px-3 py-1.5 hover:bg-accent/60">
            Work queue
          </Link>
          <Link href="/today" className="rounded-lg border border-border/30 px-3 py-1.5 hover:bg-accent/60">
            Today
          </Link>
          <button
            type="button"
            onClick={() => void fetchLive()}
            className="rounded-lg border border-border/30 px-3 py-1.5 hover:bg-accent/60"
          >
            Refresh now
          </button>
        </div>
      </div>

      {snap?.partial_errors && snap.partial_errors.length > 0 ? (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Partial data: missing {snap.partial_errors.join(", ")}
        </p>
      ) : null}

      {/* Pulse strip — newcomers */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Nodes online</p>
          <p className="text-3xl font-light text-primary">{summary?.runners_online ?? "—"}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Running now</p>
          <p className="text-3xl font-light text-primary">{summary?.tasks_running ?? "—"}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Queued</p>
          <p className="text-3xl font-light text-primary">{summary?.queue_depth ?? "—"}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Recent finishes</p>
          <p className="text-3xl font-light text-primary">{summary?.recent_completions_visible ?? "—"}</p>
        </div>
      </section>

      <div className="grid lg:grid-cols-2 gap-8">
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Nodes</h2>
          <div className="rounded-2xl border border-border/30 divide-y divide-border/20">
            {(snap?.runners.items || []).length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No active runner heartbeats in lease window.</p>
            ) : (
              snap!.runners.items.map((r, idx) => (
                <div key={r.runner_id || `runner-${idx}`} className="p-4 flex flex-col gap-1 text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="font-mono text-xs">{r.runner_id || "runner"}</span>
                    <span className="text-muted-foreground">{r.status}</span>
                  </div>
                  <p className="text-muted-foreground text-xs">
                    {r.host} · v{r.version || "?"}
                    {r.active_task_id ? (
                      <>
                        {" "}
                        · task{" "}
                        <Link href={`/tasks?task_id=${encodeURIComponent(r.active_task_id)}`} className="underline">
                          {r.active_task_id}
                        </Link>
                      </>
                    ) : null}
                  </p>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-lg font-medium">Executing</h2>
          <div className="rounded-2xl border border-border/30 divide-y divide-border/20">
            {(snap?.execution.running || []).length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">Nothing running right now.</p>
            ) : (
              snap!.execution.running.map((t) => (
                <div key={t.id || t.direction} className="p-4 space-y-1 text-sm">
                  <div className="flex justify-between gap-2">
                    <Link href={`/tasks?task_id=${encodeURIComponent(t.id || "")}`} className="font-mono text-xs underline">
                      {t.id}
                    </Link>
                    <span className="text-muted-foreground">{t.task_type}</span>
                  </div>
                  <p className="text-foreground/90">{t.direction}</p>
                  <p className="text-xs text-muted-foreground">
                    {t.model ? `${t.model} · ` : ""}
                    {t.claimed_by ? `claimed ${t.claimed_by} · ` : ""}
                    {t.running_seconds != null ? `${t.running_seconds}s` : ""}
                  </p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {snap?.execution.pending && snap.execution.pending.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Waiting</h2>
          <div className="rounded-2xl border border-border/30 divide-y divide-border/20">
            {snap.execution.pending.slice(0, 12).map((t) => (
              <div key={t.id} className="p-4 space-y-1 text-sm">
                <div className="flex justify-between gap-2">
                  <Link href={`/tasks?task_id=${encodeURIComponent(t.id || "")}`} className="font-mono text-xs underline">
                    {t.id}
                  </Link>
                  <span className="text-muted-foreground">wait {t.wait_seconds ?? "?"}s</span>
                </div>
                <p className="text-foreground/90">{t.direction}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {snap?.execution.recent_completed && snap.execution.recent_completed.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Just completed</h2>
          <div className="rounded-2xl border border-border/30 divide-y divide-border/20">
            {snap.execution.recent_completed.slice(0, 8).map((t) => (
              <div key={t.id} className="p-4 space-y-1 text-sm">
                <div className="flex justify-between gap-2">
                  <Link href={`/tasks?task_id=${encodeURIComponent(t.id || "")}`} className="font-mono text-xs underline">
                    {t.id}
                  </Link>
                  <span className="text-muted-foreground">{(t.duration_seconds ?? "?") + "s"}</span>
                </div>
                <p className="text-foreground/90">{t.direction}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {/* Expert */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Expert view</h2>
        <div className="grid md:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-border/30 p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">7d throughput</p>
            <p className="text-2xl font-light mt-1">{throughput.completed_7d ?? "—"}</p>
            <p className="text-xs text-muted-foreground mt-1">{throughput.tasks_per_day ?? "?"} / day</p>
          </div>
          <div className="rounded-2xl border border-border/30 p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Success rate</p>
            <p className="text-2xl font-light mt-1">
              {snap?.providers?.success_rate?.rate != null
                ? `${Math.round((snap.providers.success_rate.rate as number) * 1000) / 10}%`
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {snap?.providers?.success_rate?.completed ?? 0} ok / {snap?.providers?.success_rate?.total ?? 0} total
            </p>
          </div>
          <div className="rounded-2xl border border-border/30 p-4 md:col-span-2">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Queue mix</p>
            <p className="text-sm mt-2 text-foreground/90">
              {String(
                (snap?.execution.diagnostics as { dominant_pending_task_type?: string })?.dominant_pending_task_type ||
                  "—",
              )}
              <span className="text-muted-foreground">
                {" "}
                (
                {Math.round(
                  ((snap?.execution.diagnostics as { dominant_pending_share?: number })?.dominant_pending_share || 0) *
                    100,
                )}
                % of pending)
              </span>
            </p>
            {(snap?.execution.diagnostics as { queue_mix_warning?: boolean })?.queue_mix_warning ? (
              <p className="text-xs text-amber-600 mt-2">Queue mix warning: one type dominates.</p>
            ) : null}
          </div>
        </div>
      </section>

      {modelKeys.length > 0 ? (
        <section className="space-y-4">
          <h3 className="text-md font-medium">Providers (model)</h3>
          <div className="rounded-2xl border border-border/30 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 text-left text-muted-foreground">
                  <th className="p-3 font-medium">Model</th>
                  <th className="p-3 font-medium">Tasks</th>
                  <th className="p-3 font-medium">Avg duration</th>
                </tr>
              </thead>
              <tbody>
                {modelKeys.slice(0, 12).map((mk) => {
                  const row = byModel?.[mk];
                  return (
                    <tr key={mk} className="border-b border-border/10">
                      <td className="p-3 font-mono text-xs">{mk}</td>
                      <td className="p-3">{row?.count ?? "—"}</td>
                      <td className="p-3 text-muted-foreground">{row?.avg_duration != null ? `${row.avg_duration}s` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {variantKeys.length > 0 ? (
        <section className="space-y-4">
          <h3 className="text-md font-medium">Prompt A/B (Thompson selection probability)</h3>
          <p className="text-xs text-muted-foreground">Measurements: {snap?.prompt_ab?.total_measurements ?? 0}</p>
          <div className="rounded-2xl border border-border/30 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 text-left text-muted-foreground">
                  <th className="p-3 font-medium">Variant</th>
                  <th className="p-3 font-medium">P(select)</th>
                  <th className="p-3 font-medium">n</th>
                  <th className="p-3 font-medium">ROI</th>
                </tr>
              </thead>
              <tbody>
                {variantKeys.map((vk) => {
                  const v = variants[vk];
                  return (
                    <tr key={vk} className="border-b border-border/10">
                      <td className="p-3 font-mono text-xs">{vk}</td>
                      <td className="p-3">{v?.selection_probability ?? "—"}</td>
                      <td className="p-3">{v?.sample_count ?? "—"}</td>
                      <td className="p-3">{v?.roi ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="space-y-4">
        <h3 className="text-md font-medium">Ideas in motion (runtime window)</h3>
        <div className="rounded-2xl border border-border/30 divide-y divide-border/20">
          {(snap?.ideas_in_motion || []).length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No idea-linked runtime events in the last hour.</p>
          ) : (
            snap!.ideas_in_motion.map((row) => (
              <div key={row.idea_id} className="p-4 flex flex-col gap-1 text-sm">
                <div className="flex justify-between gap-2">
                  <Link href={`/ideas/${encodeURIComponent(row.idea_id || "")}`} className="font-medium hover:underline">
                    {row.idea_name || row.idea_id}
                  </Link>
                  <span className="text-xs text-muted-foreground">{row.manifestation_status || ""}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {row.event_count ?? 0} events · cost est. {row.runtime_cost_estimate?.toFixed?.(4) ?? row.runtime_cost_estimate}
                </p>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
