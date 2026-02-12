"use client";

import { useEffect, useState } from "react";

export default function ApiHealthPage() {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${apiUrl}/api/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        setData(json);
        setStatus("ok");
      })
      .catch((e) => {
        setError(String(e));
        setStatus("error");
      });
  }, [apiUrl]);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <h1 className="text-2xl font-bold mb-4">API Health</h1>
      {status === "loading" && <p>Checking {apiUrl}/api/health...</p>}
      {status === "ok" && data && (
        <pre className="bg-gray-100 p-4 rounded text-left">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
      {status === "error" && (
        <p className="text-red-600">
          API not reachable: {error}. Is the API running?
        </p>
      )}
    </main>
  );
}
