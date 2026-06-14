"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { readActiveWorkspaceFromCookie, withWorkspaceScope } from "@/lib/workspace";
import { useT } from "@/components/MessagesProvider";

const API = getApiBase();

// ── Types ──────────────────────────────────────────────────────

type NodeInfo = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  last_seen_at: string;
  streak?: {
    completed?: number;
    failed?: number;
    timed_out?: number;
    executing?: number;
    total_resolved?: number;
    success_rate?: number | null;
    last_10?: string[];
    by_provider?: Record<string, { ok: number; fail: number; total: number; success_rate: number | null }>;
    attention?: string;
  };
  capabilities?: {
    system_metrics?: {
      cpu_percent?: number;
      memory_percent?: number;
      disk_percent?: number;
      process_count?: number;
      net_sent_mb?: number;
      net_recv_mb?: number;
      cpu_count?: number;
      memory_total_gb?: number;
    };
  };
};

type RunningTask = {
  id: string;
  task_type: string;
  status: string;
  model?: string;
  claimed_by?: string;
  direction?: string;
  context?: { idea_id?: string; idea_name?: string };
};

type PulseData = {
  bottleneck: {
    type: string | null;
    reason: string | null;
    recommendation: string | null;
  };
  phase_stats: Record<string, { completed: number; failed: number; pending: number; success_rate: number | null }>;
  ideas: { total_in_portfolio: number; without_spec: number; full_cycle: unknown[]; advancing: unknown[]; stuck: unknown[] };
};

type LearningDashboardData = {
  summary: {
    routed_model_count: number;
    proof_run_count: number;
    proof_pass_count: number;
    learning_surface_count: number;
    trained_native_model_count: number;
    proven_floor_count: number;
    blocked_or_pending_count: number;
  };
  north_star: string;
  floor: string;
  models: {
    executor: string;
    model_id: string;
    tiers: string[];
    fallback_rank?: number | null;
    task_types: string[];
    role: string;
  }[];
  native_training_artifacts: {
    artifact_id: string;
    artifact_kind: string;
    model_family: string;
    status: string;
    recipe_path: string;
    proof_band_path?: string | null;
    weights_hash: string;
    dataset_hash: string;
    eval_hash: string;
    sample_count: number;
    heldout_count: number;
    correct_count: number;
    wrong_count: number;
    native_accuracy_ppm: number;
    oracle_accuracy_ppm: number;
    continuous_cycle_count: number;
    proof_status: string;
    native_beats_oracle: boolean;
    observed_at?: string | null;
    receipt_path: string;
  }[];
  learning_surfaces: {
    surface_id: string;
    title: string;
    kind: string;
    state: string;
    proof_status: string;
    training_metadata: {
      commands?: string[];
      evidence_refs?: string[];
      trained_native_weights?: boolean;
      note?: string;
    };
    north_star_alignment: string;
    next_step?: string | null;
    evidence_path: string;
  }[];
  recent_proof_runs: {
    run_id: string;
    model_used: string;
    pass_fail: string;
    attempts: number;
    commands_run: string[];
    source_path?: string | null;
  }[];
  guidance: string[];
};

type SSEEvent = {
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
  node_name?: string;
  provider?: string;
};

// ── Helpers ────────────────────────────────────────────────────

function relTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h`;
}

function ppmToPercent(value: number): string {
  return `${(value / 10000).toFixed(value % 10000 === 0 ? 0 : 1)}%`;
}

function Gauge({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  const color = pct > 80 ? "bg-red-500" : pct > 60 ? "bg-yellow-500" : "bg-green-500";
  return (
    <div className="flex-1 min-w-[60px]">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{label}</span><span>{Math.round(value)}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StreakDots({ last10 }: { last10: string[] }) {
  return (
    <span className="font-mono text-xs">
      {last10.map((r, i) => (
        <span key={i} className={r === "ok" ? "text-green-500" : r === "fail" ? "text-red-500" : "text-yellow-500"}>
          {r === "ok" ? "✓" : r === "fail" ? "✗" : "T"}
        </span>
      ))}
    </span>
  );
}

function StatusPill({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const cls = normalized.includes("pass") || normalized.includes("proven") || normalized.includes("ready")
    ? "bg-green-500/15 text-green-600"
    : normalized.includes("pending") || normalized.includes("local")
      ? "bg-amber-500/15 text-amber-600"
      : normalized.includes("block") || normalized.includes("fail")
        ? "bg-red-500/15 text-red-600"
        : "bg-muted text-muted-foreground";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${cls}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}

// ── Task Live Tab ──────────────────────────────────────────────

function TaskTab({ task, isActive, onClick }: { task: RunningTask; isActive: boolean; onClick: () => void }) {
  const idea = task.context?.idea_id || "?";
  const shortIdea = idea.length > 20 ? idea.slice(0, 20) + "…" : idea;
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs rounded-t-lg border border-b-0 whitespace-nowrap transition-colors ${
        isActive
          ? "bg-background border-border/30 text-foreground font-medium"
          : "bg-muted/30 border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse" />
      {task.task_type} · {shortIdea}
    </button>
  );
}

function TaskStream({ taskId }: { taskId: string }) {
  const t = useT();
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    let buffer = "";
    (async () => {
      try {
        const resp = await fetch(`${API}/api/agent/tasks/${taskId}/events`, {
          headers: { Accept: "text/event-stream" },
          signal: ctrl.signal,
        });
        if (!resp.ok || !resp.body) return;
        setConnected(true);
        const reader = resp.body.getReader();
        const dec = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += dec.decode(value, { stream: true });
          while (buffer.includes("\n\n")) {
            const idx = buffer.indexOf("\n\n");
            const chunk = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            for (const line of chunk.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              try {
                const ev = JSON.parse(line.slice(6)) as SSEEvent;
                if (ev.event_type === "end") return;
                setEvents(prev => [...prev.slice(-49), ev]);
              } catch {}
            }
          }
        }
      } catch {}
    })();
    return () => ctrl.abort();
  }, [taskId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events]);

  return (
    <div ref={scrollRef} className="h-48 overflow-y-auto p-3 space-y-1 text-xs font-mono">
      {!connected && events.length === 0 && (
        <p className="text-muted-foreground">{t("dashboard.connecting")}</p>
      )}
      {events.map((ev, i) => {
        const ts = new Date(ev.timestamp).toLocaleTimeString();
        const d = ev.data;
        let icon = "·";
        let msg = ev.event_type;
        if (ev.event_type === "heartbeat") {
          icon = "♥";
          msg = `${d.elapsed_s}s | ${d.files_changed} files | ${d.git_summary}`;
        } else if (ev.event_type === "progress") {
          icon = "→";
          msg = (d.message as string) || (d.preview as string) || "";
        } else if (ev.event_type === "provider_done") {
          icon = "✓";
          msg = `Done ${d.duration_s}s | ${d.output_chars} chars`;
        } else if (ev.event_type === "completed") {
          icon = "🏁";
          msg = "Completed";
        } else if (ev.event_type === "failed") {
          icon = "✗";
          msg = "Failed";
        } else if (ev.event_type === "executing") {
          icon = "▶";
          msg = `via ${ev.provider || d.provider || "?"}`;
        }
        return (
          <div key={`${ev.timestamp}-${i}`} className="flex gap-2">
            <span className="text-muted-foreground w-16 flex-shrink-0">{ts}</span>
            <span className="w-3 text-center">{icon}</span>
            <span className="text-foreground/80">{msg}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────

export default function DashboardPage() {
  const t = useT();
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [tasks, setTasks] = useState<RunningTask[]>([]);
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [learning, setLearning] = useState<LearningDashboardData | null>(null);
  const [activeTab, setActiveTab] = useState<string>("");
  const [lastRefresh, setLastRefresh] = useState(Date.now());

  const refresh = useCallback(async () => {
    try {
      const workspaceId = readActiveWorkspaceFromCookie();
      const [nodesRes, tasksRes, pulseRes, learningRes] = await Promise.all([
        fetch(`${API}/api/federation/nodes`, { cache: "no-store" }),
        fetch(withWorkspaceScope(`${API}/api/agent/tasks?status=running&limit=20`, workspaceId), { cache: "no-store" }),
        fetch(`${API}/api/pipeline/pulse`, { cache: "no-store" }),
        fetch(`${API}/api/models/learning-dashboard`, { cache: "no-store" }),
      ]);
      if (nodesRes.ok) setNodes(await nodesRes.json());
      if (tasksRes.ok) {
        const d = await tasksRes.json();
        setTasks(d.tasks || []);
      }
      if (pulseRes.ok) setPulse(await pulseRes.json());
      if (learningRes.ok) setLearning(await learningRes.json());
      setLastRefresh(Date.now());
    } catch {}
  }, []);

  useEffect(() => { refresh(); const iv = setInterval(refresh, 10000); return () => clearInterval(iv); }, [refresh]);

  // Auto-select first task tab
  useEffect(() => {
    if (!activeTab && tasks.length > 0) setActiveTab(tasks[0].id);
  }, [tasks, activeTab]);

  const totalRunning = nodes.reduce((s, n) => s + (n.streak?.executing || 0), 0);
  const fleetOk = nodes.reduce((s, n) => s + (n.streak?.completed || 0), 0);
  const fleetTotal = nodes.reduce((s, n) => s + (n.streak?.total_resolved || 0), 0);
  const fleetRate = fleetTotal > 0 ? Math.round((fleetOk / fleetTotal) * 100) : 0;
  const bottleneckTitle = pulse?.bottleneck.type
    ? pulse.bottleneck.type.replace(/_/g, " ")
    : "Pipeline balanced";
  const bottleneckDetail =
    pulse?.bottleneck.reason ||
    pulse?.bottleneck.recommendation ||
    "No single phase is dominating the backlog right now.";

  return (
    <main className="min-h-screen bg-background text-foreground p-4 pb-24 md:pb-4 space-y-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("dashboard.title")}</h1>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Refreshed {relTime(new Date(lastRefresh).toISOString())}</span>
          <Link href="/" className="underline hover:text-foreground">{t("dashboard.home")}</Link>
          <Link href="/nodes" className="underline hover:text-foreground">{t("nav.nodes")}</Link>
          <Link href="/tasks" className="underline hover:text-foreground">{t("nav.workCards")}</Link>
        </div>
      </div>

      {/* Fleet + Pulse Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Fleet Summary */}
        <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">{t("dashboard.fleet")}</p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-2xl font-bold">{nodes.length}</p>
              <p className="text-[10px] text-muted-foreground">{t("dashboard.fleetNodes")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{totalRunning}</p>
              <p className="text-[10px] text-muted-foreground">{t("dashboard.fleetRunning")}</p>
            </div>
            <div>
              <p className={`text-2xl font-bold ${fleetRate >= 70 ? "text-green-500" : fleetRate >= 40 ? "text-yellow-500" : "text-red-500"}`}>
                {fleetRate}%
              </p>
              <p className="text-[10px] text-muted-foreground">{t("dashboard.fleetSuccess")}</p>
            </div>
          </div>
        </div>

        {/* Bottleneck */}
        <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">{t("dashboard.bottleneck")}</p>
          {pulse ? (
            <>
              <p className="text-sm font-medium">{bottleneckTitle}</p>
              <p className="text-xs text-muted-foreground line-clamp-2">{bottleneckDetail}</p>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">{t("common.loading")}</p>
          )}
        </div>

        {/* Phase Stats */}
        <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">{t("dashboard.phases")}</p>
          {pulse && (
            <div className="space-y-1">
              {Object.entries(pulse.phase_stats).map(([phase, s]) => {
                const rate = s.success_rate != null ? Math.round(s.success_rate * 100) : 0;
                const color = rate >= 70 ? "bg-green-500" : rate >= 40 ? "bg-yellow-500" : "bg-red-500";
                return (
                  <div key={phase} className="flex items-center gap-2 text-xs">
                    <span className="w-16 text-muted-foreground">{phase}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div className={`h-full rounded-full ${color}`} style={{ width: `${rate}%` }} />
                    </div>
                    <span className="w-8 text-right">{rate}%</span>
                    {s.pending > 0 && <span className="text-amber-500">+{s.pending}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Learning Direction */}
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Learning direction</h2>
            <p className="text-xs text-muted-foreground">
              Models, receipts, and next moves toward native learning.
            </p>
          </div>
          {learning && <StatusPill value={`${learning.summary.proven_floor_count} proven floors`} />}
        </div>

        {learning ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-center">
              <div className="rounded-xl border border-border/20 bg-card/40 p-3">
                <p className="text-2xl font-bold">{learning.summary.trained_native_model_count}</p>
                <p className="text-[10px] text-muted-foreground">native trained</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-card/40 p-3">
                <p className="text-2xl font-bold">{learning.summary.routed_model_count}</p>
                <p className="text-[10px] text-muted-foreground">routed models</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-card/40 p-3">
                <p className="text-2xl font-bold">{learning.summary.learning_surface_count}</p>
                <p className="text-[10px] text-muted-foreground">learning surfaces</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-card/40 p-3">
                <p className="text-2xl font-bold text-green-500">{learning.summary.proof_pass_count}</p>
                <p className="text-[10px] text-muted-foreground">recent proofs</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-card/40 p-3">
                <p className="text-2xl font-bold text-green-500">{learning.summary.proven_floor_count}</p>
                <p className="text-[10px] text-muted-foreground">proven floors</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-card/40 p-3">
                <p className="text-2xl font-bold text-amber-500">{learning.summary.blocked_or_pending_count}</p>
                <p className="text-[10px] text-muted-foreground">open gates</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-3 lg:col-span-2">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">North star</p>
                  <p className="text-sm leading-relaxed">{learning.north_star}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">Current floor</p>
                  <p className="text-sm leading-relaxed">{learning.floor}</p>
                </div>
              </div>
              <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Guidance</p>
                {learning.guidance.slice(0, 3).map(item => (
                  <p key={item} className="text-xs leading-relaxed text-muted-foreground">
                    {item}
                  </p>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              <div className="rounded-xl border border-border/20 bg-card/40 overflow-hidden xl:col-span-2">
                <div className="px-4 py-3 border-b border-border/10">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">Native training artifacts</p>
                </div>
                {learning.native_training_artifacts.length > 0 ? (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-border/10">
                    {learning.native_training_artifacts.slice(0, 4).map(artifact => (
                      <div key={artifact.artifact_id} className="bg-card p-4 space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium font-mono break-all">{artifact.artifact_id}</p>
                          <StatusPill value={artifact.proof_status} />
                          <StatusPill value={artifact.status} />
                          {artifact.native_beats_oracle && <StatusPill value="native beats oracle" />}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {artifact.model_family} · cycle {artifact.continuous_cycle_count} · samples {artifact.sample_count} · heldout {artifact.heldout_count}
                        </p>
                        <p className="text-xs">
                          <span className="text-muted-foreground">Eval: </span>
                          native {ppmToPercent(artifact.native_accuracy_ppm)} · oracle {ppmToPercent(artifact.oracle_accuracy_ppm)} · {artifact.correct_count}/{artifact.heldout_count} correct
                        </p>
                        <div className="space-y-1 text-[10px] text-muted-foreground font-mono">
                          <p className="break-all">weights {artifact.weights_hash}</p>
                          <p className="break-all">data {artifact.dataset_hash}</p>
                          <p className="break-all">eval {artifact.eval_hash}</p>
                          <p className="break-all">{artifact.receipt_path}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4">
                    <p className="text-xs text-muted-foreground">No committed native weight/data/eval receipt has passed yet.</p>
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-border/20 bg-card/40 overflow-hidden">
                <div className="px-4 py-3 border-b border-border/10">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">Proof surfaces</p>
                </div>
                <div className="divide-y divide-border/10">
                  {learning.learning_surfaces.slice(0, 6).map(surface => (
                    <div key={surface.surface_id} className="p-4 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium">{surface.title}</p>
                        <StatusPill value={surface.proof_status} />
                        <StatusPill value={surface.state} />
                      </div>
                      <p className="text-xs text-muted-foreground">{surface.kind} · {surface.north_star_alignment}</p>
                      <p className="text-xs text-muted-foreground">{surface.training_metadata.note}</p>
                      {surface.next_step && (
                        <p className="text-xs">
                          <span className="text-muted-foreground">Next: </span>
                          {surface.next_step}
                        </p>
                      )}
                      <p className="text-[10px] text-muted-foreground font-mono break-all">{surface.evidence_path}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-border/20 bg-card/40 overflow-hidden">
                <div className="px-4 py-3 border-b border-border/10">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">Routed models</p>
                </div>
                <div className="divide-y divide-border/10">
                  {learning.models.slice(0, 8).map(model => (
                    <div key={`${model.executor}-${model.model_id}`} className="p-4 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium font-mono break-all">{model.model_id}</p>
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                          {model.executor}
                        </span>
                        {model.fallback_rank && (
                          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                            fallback #{model.fallback_rank}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {model.role} · {model.tiers.length > 0 ? model.tiers.join(", ") : "no tier"} · {model.task_types.length > 0 ? model.task_types.join(", ") : "no task binding"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border/20 bg-card/40 overflow-hidden">
              <div className="px-4 py-3 border-b border-border/10">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Recent proof runs</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border/10">
                {learning.recent_proof_runs.slice(0, 6).map(run => (
                  <div key={run.run_id} className="bg-card p-4 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium">{run.run_id}</p>
                      <StatusPill value={run.pass_fail} />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {run.model_used} · attempts {run.attempts}
                    </p>
                    {run.commands_run[0] && (
                      <p className="text-[10px] text-muted-foreground font-mono break-all">
                        {run.commands_run[0]}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-border/20 bg-card/40 p-4">
            <p className="text-xs text-muted-foreground">{t("common.loading")}</p>
          </div>
        )}
      </section>

      {/* Node Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {nodes.map(node => {
          const sm = node.capabilities?.system_metrics;
          const color = (Date.now() - new Date(node.last_seen_at).getTime()) < 300000 ? "bg-green-500" : "bg-yellow-500";
          return (
            <div key={node.node_id} className="rounded-xl border border-border/20 bg-card/40 p-3 space-y-2">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${color}`} />
                <span className="font-medium text-sm">{node.hostname}</span>
                <span className="text-xs text-muted-foreground ml-auto">{relTime(node.last_seen_at)}</span>
              </div>
              {node.streak?.last_10 && node.streak.last_10.length > 0 && (
                <div className="flex items-center gap-2">
                  <StreakDots last10={node.streak.last_10} />
                  {node.streak.success_rate != null && (
                    <span className={`text-xs font-medium ${node.streak.success_rate >= 0.7 ? "text-green-500" : "text-yellow-500"}`}>
                      {Math.round(node.streak.success_rate * 100)}%
                    </span>
                  )}
                  {(node.streak.executing || 0) > 0 && (
                    <span className="text-xs text-amber-500">{node.streak.executing} running</span>
                  )}
                </div>
              )}
              {sm && (
                <div className="flex gap-3">
                  {sm.cpu_percent != null && <Gauge label="CPU" value={sm.cpu_percent} />}
                  {sm.memory_percent != null && <Gauge label="RAM" value={sm.memory_percent} />}
                  {sm.disk_percent != null && <Gauge label="Disk" value={sm.disk_percent} />}
                </div>
              )}
              {/* Provider heatmap */}
              <div className="flex flex-wrap gap-1">
                {node.providers.map(p => {
                  const ps = node.streak?.by_provider?.[p];
                  const rate = ps?.success_rate;
                  const cls = !ps || ps.total === 0
                    ? "bg-muted text-muted-foreground"
                    : (rate ?? 0) >= 0.8 ? "bg-green-500/15 text-green-500"
                    : (rate ?? 0) >= 0.5 ? "bg-yellow-500/15 text-yellow-500"
                    : "bg-red-500/15 text-red-500";
                  return (
                    <span key={p} className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${cls}`}>
                      {p}{ps && ps.total > 0 ? ` ${Math.round((rate ?? 0) * 100)}%` : ""}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Tasks with Live Streams */}
      <div className="rounded-xl border border-border/20 bg-card/40 overflow-hidden">
        <div className="flex items-center gap-1 px-3 pt-2 overflow-x-auto">
          {tasks.length === 0 ? (
            <p className="text-xs text-muted-foreground p-2">{t("dashboard.noRunning")}</p>
          ) : (
            tasks.map(t => (
              <TaskTab
                key={t.id}
                task={t}
                isActive={activeTab === t.id}
                onClick={() => setActiveTab(t.id)}
              />
            ))
          )}
        </div>
        {activeTab && (
          <div className="border-t border-border/10">
            <div className="px-3 py-1.5 flex items-center gap-2 text-xs text-muted-foreground border-b border-border/10">
              {(() => {
                const t = tasks.find(t => t.id === activeTab);
                if (!t) return <span>Task not found</span>;
                return (
                  <>
                    <span className="font-medium text-foreground">{t.task_type}</span>
                    <span>·</span>
                    <span>{t.context?.idea_id || "?"}</span>
                    <span>·</span>
                    <span>via {t.model || "?"}</span>
                    <span>·</span>
                    <span>on {t.claimed_by || "?"}</span>
                    <Link href={`/tasks/${t.id}`} className="ml-auto underline hover:text-foreground">
                      detail →
                    </Link>
                  </>
                );
              })()}
            </div>
            <TaskStream taskId={activeTab} />
          </div>
        )}
      </div>

      {/* Ideas Progress */}
      {pulse && (
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-xl border border-border/20 bg-card/40 p-3">
            <p className="text-2xl font-bold">{pulse.ideas.full_cycle.length}</p>
            <p className="text-[10px] text-muted-foreground">full cycle</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-card/40 p-3">
            <p className="text-2xl font-bold text-amber-500">{pulse.ideas.advancing.length}</p>
            <p className="text-[10px] text-muted-foreground">advancing</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-card/40 p-3">
            <p className="text-2xl font-bold text-red-500">{pulse.ideas.stuck.length}</p>
            <p className="text-[10px] text-muted-foreground">stuck</p>
          </div>
        </div>
      )}
    </main>
  );
}
