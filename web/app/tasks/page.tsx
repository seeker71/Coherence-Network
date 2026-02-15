"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type TaskRow = {
  id: string;
  direction: string;
  task_type: string;
  status: string;
  model: string;
  created_at: string;
  updated_at?: string | null;
};

export default function TasksPage() {
  const [rows, setRows] = useState<TaskRow[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/agent/tasks?limit=100`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(json));
        if (cancelled) return;
        setRows(Array.isArray(json.tasks) ? json.tasks : []);
        setStatus("ok");
      } catch (e) {
        if (cancelled) return;
        setError(String(e));
        setStatus("error");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-4">
      <Link href="/" className="text-muted-foreground hover:text-foreground">
        ← Coherence Network
      </Link>
      <h1 className="text-2xl font-bold">Tasks</h1>
      <p className="text-sm text-muted-foreground">
        Human interface for `/api/agent/tasks`.
      </p>
      {status === "loading" && <p className="text-muted-foreground">Loading tasks…</p>}
      {status === "error" && <p className="text-destructive">{error}</p>}
      {status === "ok" && (
        <ul className="space-y-2 text-sm">
          {rows.map((row) => (
            <li key={row.id} className="rounded border p-3">
              <p className="font-medium">{row.id}</p>
              <p className="text-muted-foreground">{row.direction}</p>
              <p className="text-muted-foreground">
                {row.task_type} | {row.status} | {row.model}
              </p>
            </li>
          ))}
          {rows.length === 0 && <li className="text-muted-foreground">No tasks found.</li>}
        </ul>
      )}
    </main>
  );
}
