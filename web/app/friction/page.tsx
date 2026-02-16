"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

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
  stage: string;
  block_type: string;
  severity: string;
  owner: string;
  status: string;
  energy_loss_estimate: number;
  cost_of_delay: number;
}

export default function FrictionPage() {
  const [report, setReport] = useState<FrictionReport | null>(null);
  const [events, setEvents] = useState<FrictionEvent[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [reportRes, eventsRes] = await Promise.all([
          fetch(`${API_URL}/api/friction/report?window_days=7`),
          fetch(`${API_URL}/api/friction/events?limit=20`),
        ]);
        if (!reportRes.ok || !eventsRes.ok) {
          throw new Error(`HTTP ${reportRes.status}/${eventsRes.status}`);
        }
        const reportJson = (await reportRes.json()) as FrictionReport;
        const eventsJson = (await eventsRes.json()) as FrictionEvent[];
        if (cancelled) return;
        setReport(reportJson);
        setEvents(eventsJson);
        setStatus("ok");
      } catch (e) {
        if (!cancelled) {
          setError(String(e));
          setStatus("error");
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
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
                    {event.stage} | {event.owner} | energy {event.energy_loss_estimate} | delay{" "}
                    {event.cost_of_delay}
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
