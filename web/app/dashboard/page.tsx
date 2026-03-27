"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

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
  bottleneck: { type: string; reason: string; recommendation: string };
  phase_stats: Record<string, { completed: number; failed: number; pending: number; success_rate: number | null }>;
  ideas: { total_in_portfolio: number; without_spec: number; full_cycle: unknown[]; advancing: unknown[]; stuck: unknown[] };
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
        <p className="text-muted-foreground">Connecting...</p>
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
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [tasks, setTasks] = useState<RunningTask[]>([]);
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [activeTab, setActiveTab] = useState<string>("");
  const [lastRefresh, setLastRefresh] = useState(Date.now());

  const refresh = useCallback(async () => {
    try {
      const [nodesRes, tasksRes, pulseRes] = await Promise.all([
        fetch(`${API}/api/federation/nodes`, { cache: "no-store" }),
        fetch(`${API}/api/agent/tasks?status=running&limit=20`, { cache: "no-store" }),
        fetch(`${API}/api/pipeline/pulse`, { cache: "no-store" }),
      ]);
      if (nodesRes.ok) setNodes(await nodesRes.json());
      if (tasksRes.ok) {
        const d = await tasksRes.json();
        setTasks(d.tasks || []);
      }
      if (pulseRes.ok) setPulse(await pulseRes.json());
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

  return (
    <main className="min-h-screen bg-background text-foreground p-4 space-y-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Pipeline Dashboard</h1>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Refreshed {relTime(new Date(lastRefresh).toISOString())}</span>
          <Link href="/" className="underline hover:text-foreground">Home</Link>
          <Link href="/nodes" className="underline hover:text-foreground">Nodes</Link>
          <Link href="/tasks" className="underline hover:text-foreground">Tasks</Link>
        </div>
      </div>

      {/* Fleet + Pulse Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Fleet Summary */}
        <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Fleet</p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-2xl font-bold">{nodes.length}</p>
              <p className="text-[10px] text-muted-foreground">nodes</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{totalRunning}</p>
              <p className="text-[10px] text-muted-foreground">running</p>
            </div>
            <div>
              <p className={`text-2xl font-bold ${fleetRate >= 70 ? "text-green-500" : fleetRate >= 40 ? "text-yellow-500" : "text-red-500"}`}>
                {fleetRate}%
              </p>
              <p className="text-[10px] text-muted-foreground">success</p>
            </div>
          </div>
        </div>

        {/* Bottleneck */}
        <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Bottleneck</p>
          {pulse ? (
            <>
              <p className="text-sm font-medium">{pulse.bottleneck.type.replace(/_/g, " ")}</p>
              <p className="text-xs text-muted-foreground line-clamp-2">{pulse.bottleneck.reason}</p>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">Loading...</p>
          )}
        </div>

        {/* Phase Stats */}
        <div className="rounded-xl border border-border/20 bg-card/40 p-4 space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">Phases</p>
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
            <p className="text-xs text-muted-foreground p-2">No running tasks</p>
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
