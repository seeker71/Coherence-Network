"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

type AgentTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  created_at?: string;
  updated_at?: string;
};

function TasksPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<AgentTask[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const statusFilter = useMemo(() => (searchParams.get("status") || "").trim(), [searchParams]);
  const typeFilter = useMemo(() => (searchParams.get("task_type") || "").trim(), [searchParams]);

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
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
  }, []);

  useLiveRefresh(loadRows);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (statusFilter && row.status !== statusFilter) return false;
      if (typeFilter && row.task_type !== typeFilter) return false;
      return true;
    });
  }, [rows, statusFilter, typeFilter]);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Tasks</h1>
      <p className="text-muted-foreground">
        Human interface for `GET /api/agent/tasks`.
        {statusFilter ? (
          <>
            {" "}
            status <code>{statusFilter}</code>.
          </>
        ) : null}
        {typeFilter ? (
          <>
            {" "}
            task type <code>{typeFilter}</code>.
          </>
        ) : null}
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">
            Total: {filteredRows.length}
            {(statusFilter || typeFilter) ? (
              <>
                {" "}
                | <Link href="/tasks" className="underline hover:text-foreground">Clear filters</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 50).map((t) => (
              <li key={t.id} className="rounded border p-2 space-y-1">
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{t.id}</span>
                  <span className="text-muted-foreground text-right">
                    <Link
                      href={`/tasks?task_type=${encodeURIComponent(t.task_type)}`}
                      className="underline hover:text-foreground"
                    >
                      {t.task_type}
                    </Link>{" "}
                    |{" "}
                    <Link
                      href={`/tasks?status=${encodeURIComponent(t.status)}`}
                      className="underline hover:text-foreground"
                    >
                      {t.status}
                    </Link>
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

export default function TasksPage() {
  return (
    <Suspense fallback={<main className="min-h-screen p-8 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading tasks…</p></main>}>
      <TasksPageContent />
    </Suspense>
  );
}
