"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const HEALTH_POLL_INTERVAL_MS = 60000;
const HEALTH_REQUEST_TIMEOUT_MS = 10000;

export default function ApiHealthPage() {
  const apiUrl = getApiBase();
  const proxyUrl = "/api/health-proxy";
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let inFlight: AbortController | null = null;

    const poll = () => {
      const controller = new AbortController();
      inFlight?.abort();
      inFlight = controller;
      let timeoutId: ReturnType<typeof setTimeout> | null = null;
      const timeoutPromise = new Promise<Response>((_, reject) => {
        timeoutId = setTimeout(() => {
          controller.abort(new DOMException("Request timed out", "TimeoutError"));
          reject(new Error(`Request timed out after ${HEALTH_REQUEST_TIMEOUT_MS}ms`));
        }, HEALTH_REQUEST_TIMEOUT_MS);
      });

      Promise.race([
        fetch(proxyUrl, { cache: "no-store", signal: controller.signal }),
        timeoutPromise,
      ])
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((json) => {
          if (cancelled) return;
          setData(json);
          setError(null);
          setStatus("ok");
          setLastUpdated(new Date().toLocaleString());
        })
        .catch((e) => {
          if (cancelled) return;
          setError(String(e));
          setStatus("error");
          setLastUpdated(new Date().toLocaleString());
        })
        .finally(() => {
          if (timeoutId) clearTimeout(timeoutId);
          if (inFlight === controller) {
            inFlight = null;
          }
        });
    };

    poll();
    const id = setInterval(poll, HEALTH_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      inFlight?.abort();
      clearInterval(id);
    };
  }, [proxyUrl]);

  const isStatusValue = (v: unknown): boolean => {
    if (typeof v === "string") return ["ok", "healthy", "up", "error", "down", "degraded"].includes(v.toLowerCase());
    if (typeof v === "object" && v !== null && "status" in (v as Record<string, unknown>)) return true;
    return false;
  };
  const isOkValue = (v: unknown): boolean => {
    if (typeof v === "string") return ["ok", "healthy", "up"].includes(v.toLowerCase());
    if (typeof v === "object" && v !== null && "status" in (v as Record<string, unknown>)) {
      const s = (v as Record<string, unknown>).status;
      return typeof s === "string" && ["ok", "healthy", "up"].includes(s.toLowerCase());
    }
    return true;
  };
  const healthEntries = data ? Object.entries(data) : [];
  const statusEntries = healthEntries.filter(([, v]) => isStatusValue(v));
  const allOk = data && (statusEntries.length === 0 || statusEntries.every(([, v]) => isOkValue(v)));

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8 max-w-2xl mx-auto">
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
      </div>
      <h1 className="text-2xl font-bold mb-4">API Health</h1>
      <p className="mb-3 text-sm text-muted-foreground">
        Auto-refreshes every 60 seconds.{" "}
        {lastUpdated ? `Last checked: ${lastUpdated}` : "Waiting for first response..."}
      </p>

      {status === "loading" && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 w-full text-center">
          <p className="text-muted-foreground">Checking system health...</p>
        </section>
      )}

      {status === "ok" && data && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 w-full space-y-4">
          <div className="flex items-center gap-2">
            <span className={`inline-block w-3 h-3 rounded-full ${allOk ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-lg font-semibold">
              {allOk ? "All systems operational" : "Issues detected"}
            </span>
          </div>
          <div className="space-y-2">
            {healthEntries.map(([key, value]) => {
              const strValue = typeof value === "object" && value !== null
                ? (value as Record<string, unknown>).status as string ?? JSON.stringify(value)
                : String(value);
              const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
              // Format timestamps
              const isTimestamp = typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value);
              const displayValue = isTimestamp ? new Date(value as string).toLocaleString() : strValue;
              const isOk = isOkValue(value);
              const showBadge = isStatusValue(value);
              return (
                <div key={key} className="flex items-center justify-between rounded-xl border border-border/20 bg-background/40 p-3">
                  <span className="text-sm">{label}</span>
                  {showBadge ? (
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      isOk ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                    }`}>
                      {displayValue}
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground">{displayValue}</span>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {status === "error" && (
        <section className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 w-full space-y-2">
          <div className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-red-500" />
            <span className="text-lg font-semibold">API unreachable</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Could not connect to the backend service. Please verify the API server is running and accessible.
          </p>
          {error && <p className="text-xs text-muted-foreground">{error}</p>}
        </section>
      )}
    </main>
  );
}
