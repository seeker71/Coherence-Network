"use client";

import { useEffect, useState } from "react";

export default function ApiHealthPage() {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const proxyUrl = "/api/health-proxy";
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      fetch(proxyUrl, { cache: "no-store" })
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
        });
    };

    poll();
    const id = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [proxyUrl]);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <h1 className="text-2xl font-bold mb-4">API Health</h1>
      <p className="mb-3 text-sm text-gray-600">
        Auto-refresh every 15s. {lastUpdated ? `Last updated: ${lastUpdated}` : "Waiting for first response..."}
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
