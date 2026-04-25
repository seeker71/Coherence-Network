"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

interface ReportRow {
  key: string;
  count: number;
  energy_loss: number;
  cost_of_delay?: number;
}

interface FrictionReport {
  window_days: number;
  total_events: number;
  open_events: number;
  total_energy_loss: number;
  total_cost_of_delay: number;
  top_block_types: ReportRow[];
  top_stages: ReportRow[];
}

interface FrictionEvent {
  id: string;
  timestamp: string;
  task_id?: string | null;
  run_id?: string | null;
  provider?: string | null;
  billing_provider?: string | null;
  tool?: string | null;
  model?: string | null;
  stage: string;
  block_type: string;
  severity: string;
  owner: string;
  status: string;
  energy_loss_estimate: number;
  cost_of_delay: number;
  resolution_action?: string | null;
  notes?: string | null;
}

interface FrictionEntryPoint {
  key: string;
  title: string;
  severity: string;
  status: string;
  event_count: number;
  energy_loss: number;
  cost_of_delay: number;
  wasted_minutes: number;
  recommended_action: string;
  evidence_links: string[];
  sources: string[];
}

interface FrictionEntryPointReport {
  generated_at: string;
  window_days: number;
  total_entry_points: number;
  open_entry_points: number;
  entry_points: FrictionEntryPoint[];
}

export default function FrictionPage() {
  const [report, setReport] = useState<FrictionReport | null>(null);
  const [events, setEvents] = useState<FrictionEvent[]>([]);
  const [entryPoints, setEntryPoints] = useState<FrictionEntryPointReport | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [reportRes, eventsRes, entryRes] = await Promise.all([
        fetch(`${API_URL}/api/friction/report?window_days=7`, { cache: "no-store" }),
        fetch(`${API_URL}/api/friction/events?limit=20`, { cache: "no-store" }),
        fetch(`${API_URL}/api/friction/entry-points?window_days=7&limit=25`, { cache: "no-store" }),
      ]);
      if (!reportRes.ok || !eventsRes.ok || !entryRes.ok) {
        throw new Error(`HTTP ${reportRes.status}/${eventsRes.status}/${entryRes.status}`);
      }
      const reportJson = (await reportRes.json()) as FrictionReport;
      const eventsJson = (await eventsRes.json()) as FrictionEvent[];
      const entryJson = (await entryRes.json()) as FrictionEntryPointReport;
      setReport(reportJson);
      setEvents(eventsJson);
      setEntryPoints(entryJson);
      setStatus("ok");
      setError(null);
    } catch (e) {
      setError(String(e));
      setStatus("error");
    }
  }, []);

  useLiveRefresh(load);

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto">
      <div className="mb-6 flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>
      <h1 className="text-2xl font-bold mb-3">Friction Ledger</h1>
      <p className="text-muted-foreground mb-6">
        Active blocking points and energy-loss hotspots across the system.
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading friction data…</p>}
      {status === "error" && (
        <p className="text-destructive">Failed to load friction data: {error}</p>
      )}

      {status === "ok" && report && (
        <section className="space-y-6">
          {entryPoints && (
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
              <h2 className="font-semibold mb-3">Friction Entry Points</h2>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                  <p className="text-muted-foreground text-xs">Total</p>
                  <p className="text-lg font-semibold">{entryPoints.total_entry_points}</p>
                </div>
                <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                  <p className="text-muted-foreground text-xs">Open</p>
                  <p className="text-lg font-semibold">{entryPoints.open_entry_points}</p>
                </div>
              </div>
              <ul className="space-y-3 text-sm">
                {entryPoints.entry_points.length === 0 && (
                  <li className="text-muted-foreground">No friction entry points detected.</li>
                )}
                {entryPoints.entry_points.map((entry) => (
                  <li key={entry.key} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-medium">{entry.title}</span>
                      <span className="flex gap-1.5">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          entry.severity === "critical" ? "bg-red-500/10 text-red-500"
                            : entry.severity === "warning" ? "bg-amber-500/10 text-amber-500"
                              : "bg-blue-500/10 text-blue-500"
                        }`}>
                          {entry.severity}
                        </span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          entry.status === "open" ? "bg-red-500/10 text-red-500"
                            : entry.status === "resolved" ? "bg-green-500/10 text-green-500"
                              : "bg-muted text-muted-foreground"
                        }`}>
                          {entry.status}
                        </span>
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {entry.event_count > 0 && (
                        <div>
                          <p className="text-muted-foreground text-xs">Events</p>
                          <p className="font-medium">{entry.event_count}</p>
                        </div>
                      )}
                      {entry.wasted_minutes > 0 && (
                        <div>
                          <p className="text-muted-foreground text-xs">Wasted minutes</p>
                          <p className="font-medium">{entry.wasted_minutes}</p>
                        </div>
                      )}
                      {entry.energy_loss > 0 && (
                        <div>
                          <p className="text-muted-foreground text-xs">Energy loss</p>
                          <p className="font-medium">{entry.energy_loss}</p>
                        </div>
                      )}
                      {entry.cost_of_delay > 0 && (
                        <div>
                          <p className="text-muted-foreground text-xs">Cost of delay</p>
                          <p className="font-medium">{entry.cost_of_delay}</p>
                        </div>
                      )}
                    </div>
                    <p className="text-muted-foreground">{entry.recommended_action}</p>
                    {entry.evidence_links.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {entry.evidence_links.slice(0, 3).map((link) => (
                          <a key={`${entry.key}-${link}`} href={link} target={link.startsWith("http") ? "_blank" : "_self"} rel="noreferrer" className="text-xs underline text-muted-foreground hover:text-foreground">
                            {link}
                          </a>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Events (7d)</p>
              <p className="text-lg font-semibold">{report.total_events}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Open</p>
              <p className="text-lg font-semibold">{report.open_events}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Energy loss</p>
              <p className="text-lg font-semibold">{report.total_energy_loss}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Cost of delay</p>
              <p className="text-lg font-semibold">{report.total_cost_of_delay}</p>
            </div>
          </div>

          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
            <h2 className="font-semibold mb-3">Top Block Types by Energy Loss</h2>
            <ul className="space-y-2 text-sm">
              {report.top_block_types.length === 0 && (
                <li className="text-muted-foreground">No events in the selected window.</li>
              )}
              {report.top_block_types.map((row) => (
                <li key={row.key} className="flex items-center justify-between rounded-xl border border-border/20 bg-background/40 p-3">
                  <span className="font-medium">{row.key}</span>
                  <span className="flex gap-3 text-xs">
                    <span className="text-muted-foreground">{row.count} events</span>
                    <span className="text-muted-foreground">{row.energy_loss} energy</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
            <h2 className="font-semibold mb-3">Recent Events</h2>
            <ul className="space-y-2 text-sm">
              {events.length === 0 && (
                <li className="text-muted-foreground">No logged friction events yet.</li>
              )}
              {events.map((event) => {
                const hasMetrics = event.energy_loss_estimate > 0 || event.cost_of_delay > 0;
                const hasToolInfo = !!(event.task_id || event.tool || event.provider || event.model);
                return (
                  <li key={event.id} className="rounded-xl border border-border/20 bg-background/40 px-4 py-3 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{event.block_type}</span>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        event.status === "open" ? "bg-red-500/10 text-red-500"
                          : event.status === "resolved" ? "bg-green-500/10 text-green-500"
                            : "bg-muted text-muted-foreground"
                      }`}>
                        {event.status}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                      <span>{event.stage}</span>
                      <span>&middot;</span>
                      <Link
                        href={`/contributors?contributor_id=${encodeURIComponent(event.owner)}`}
                        className="underline hover:text-foreground"
                      >
                        {event.owner}
                      </Link>
                      <span>&middot;</span>
                      <span>
                        {new Date(event.timestamp).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    {hasMetrics && (
                      <div className="flex gap-4 text-xs">
                        {event.energy_loss_estimate > 0 && (
                          <span><span className="text-muted-foreground">Energy: </span>{event.energy_loss_estimate}</span>
                        )}
                        {event.cost_of_delay > 0 && (
                          <span><span className="text-muted-foreground">Delay: </span>{event.cost_of_delay}</span>
                        )}
                      </div>
                    )}
                    {hasToolInfo && (
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                        {event.task_id && <span>task {event.task_id}</span>}
                        {event.tool && <span>tool {event.tool}</span>}
                        {event.provider && (
                          <span>{event.provider}{event.billing_provider && event.billing_provider !== event.provider ? ` / ${event.billing_provider}` : ""}</span>
                        )}
                        {event.model && <span>{event.model}</span>}
                      </div>
                    )}
                    {event.resolution_action && (
                      <p className="text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">Resolution: </span>
                        {event.resolution_action}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      )}
    </main>
  );
}
