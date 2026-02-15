"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AgentTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  created_at?: string;
  updated_at?: string;
};

export default function TasksPage() {
  const [rows, setRows] = useState<AgentTask[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setStatus("loading");
      setError(null);
      try {
        const res = await fetch(`${API_URL}/api/agent/tasks`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(json));
        setRows(Array.isArray(json.tasks) ? json.tasks : []);
        setStatus("ok");
      } catch (e) {
        setStatus("error");
        setError(String(e));
      }
    })();
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex gap-3">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Tasks</h1>
      <p className="text-muted-foreground">Human interface for `GET /api/agent/tasks`.</p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">Total: {rows.length}</p>
          <ul className="space-y-2 text-sm">
            {rows.slice(0, 50).map((t) => (
              <li key={t.id} className="rounded border p-2 space-y-1">
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{t.id}</span>
                  <span className="text-muted-foreground">
                    {t.task_type} | {t.status}
                  </span>
                </div>
                <div className="text-muted-foreground">{t.direction}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

