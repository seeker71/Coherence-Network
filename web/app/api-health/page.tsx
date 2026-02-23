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

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
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
      <p className="mb-3 text-sm text-gray-600">
        Auto-refresh every 60s. {lastUpdated ? `Last updated: ${lastUpdated}` : "Waiting for first response..."}
      </p>
      {status === "loading" && <p>Checking API health via {proxyUrl} (upstream: {apiUrl}/api/health)...</p>}
      {status === "ok" && data && (
        <pre className="bg-gray-100 p-4 rounded text-left">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
      {status === "error" && (
        <p className="text-red-600">
          API not reachable: {error}. Check NEXT_PUBLIC_API_URL and Railway availability.
        </p>
      )}
    </main>
  );
}
