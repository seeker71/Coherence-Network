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
        Human view of blocking points and energy-loss hotspots from the machine ledger.
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading friction data…</p>}
      {status === "error" && (
        <p className="text-destructive">Failed to load friction data: {error}</p>
      )}

      {status === "ok" && report && (
        <section className="space-y-6">
          {entryPoints && (
            <div className="rounded border p-4">
              <h2 className="font-semibold mb-3">Friction entry points</h2>
              <p className="text-muted-foreground text-sm mb-3">
                total {entryPoints.total_entry_points} | open {entryPoints.open_entry_points}
              </p>
              <ul className="space-y-3 text-sm">
                {entryPoints.entry_points.length === 0 && (
                  <li className="text-muted-foreground">No friction entry points detected.</li>
                )}
                {entryPoints.entry_points.map((entry) => (
                  <li key={entry.key} className="rounded border p-3">
                    <p className="font-medium">
                      {entry.title} | severity {entry.severity} | status {entry.status}
                    </p>
                    <p className="text-muted-foreground">
                      events {entry.event_count} | wasted_minutes {entry.wasted_minutes} | energy_loss {entry.energy_loss} | cost_of_delay{" "}
                      {entry.cost_of_delay}
                    </p>
                    <p className="text-muted-foreground">{entry.recommended_action}</p>
                    {entry.evidence_links.length > 0 && (
                      <p className="text-muted-foreground">
                        evidence:{" "}
                        {entry.evidence_links.slice(0, 3).map((link, idx) => (
                          <span key={`${entry.key}-${link}`}>
                            {idx > 0 ? " | " : ""}
                            <a href={link} target={link.startsWith("http") ? "_blank" : "_self"} rel="noreferrer" className="underline">
                              {link}
                            </a>
                          </span>
                        ))}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Events (7d)</p>
              <p className="text-lg font-semibold">{report.total_events}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Open</p>
              <p className="text-lg font-semibold">{report.open_events}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Energy loss</p>
              <p className="text-lg font-semibold">{report.total_energy_loss}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Cost of delay</p>
              <p className="text-lg font-semibold">{report.total_cost_of_delay}</p>
            </div>
          </div>

          <div className="rounded border p-4">
            <h2 className="font-semibold mb-3">Top block types by energy loss</h2>
            <ul className="space-y-2 text-sm">
              {report.top_block_types.length === 0 && (
                <li className="text-muted-foreground">No events in the selected window.</li>
              )}
              {report.top_block_types.map((row) => (
                <li key={row.key} className="flex items-center justify-between">
                  <span>{row.key}</span>
                  <span className="text-muted-foreground">
                    count {row.count} | energy {row.energy_loss}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded border p-4">
            <h2 className="font-semibold mb-3">Recent events</h2>
            <ul className="space-y-2 text-sm">
              {events.length === 0 && (
                <li className="text-muted-foreground">No logged friction events yet.</li>
              )}
              {events.map((event) => (
                <li key={event.id} className="rounded border p-3">
                  <div className="flex items-center justify-between">
                    <strong>{event.block_type}</strong>
                    <span className="text-muted-foreground">{event.status}</span>
                  </div>
                  <p className="text-muted-foreground">
                    {event.stage} |{" "}
                    <Link
                      href={`/contributors?contributor_id=${encodeURIComponent(event.owner)}`}
                      className="underline hover:text-foreground"
                    >
                      {event.owner}
                    </Link>{" "}
                    | energy {event.energy_loss_estimate} | delay {event.cost_of_delay}
                  </p>
                  <p className="text-muted-foreground">
                    task {event.task_id || "-"} | tool {event.tool || "-"} | provider{" "}
                    {event.provider || "-"}/{event.billing_provider || "-"} | model {event.model || "-"}
                  </p>
                  <p className="text-muted-foreground">
                    resolution_action {event.resolution_action || "-"}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </main>
  );
}
