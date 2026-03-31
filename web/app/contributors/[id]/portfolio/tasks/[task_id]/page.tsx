"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface TaskDetail {
  id: string; direction: string; task_type: string;
  status: string; provider: string | null; outcome: string | null;
  result: string | null; created_at: string | null; updated_at: string | null;
  idea_id: string | null; metadata: Record<string, unknown>;
}

export default function TaskDrilldownPage() {
  const params = useParams<{ id: string; task_id: string }>();
  const { id, task_id } = params ?? {};
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!task_id) return;
    setStatus("loading");
    try {
      const res = await fetch(`${API}/api/tasks/${task_id}`);
      if (!res.ok) throw new Error((await res.json()).detail ?? "Task not found");
      setTask(await res.json());
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [task_id]);

  useEffect(() => { void load(); }, [load]);

  const back = `/contributors/${id}/portfolio`;

  if (status === "loading") return <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading…</p></main>;
  if (status === "error" || !task) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-4">
        <Link href={back} className="text-sm text-primary underline">← Portfolio</Link>
        <p className="text-destructive">{error}</p>
      </main>
    );
  }

  const outcomeClass = task.outcome === "passed" ? "text-green-400" : task.outcome === "failed" ? "text-red-400" : "text-yellow-400";

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <Link href={back} className="text-sm text-muted-foreground hover:text-foreground transition-colors">← Portfolio</Link>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-2">
        <p className="text-sm text-muted-foreground">Task detail</p>
        <h1 className="text-2xl font-light leading-snug">{task.direction.slice(0, 120)}{task.direction.length > 120 ? "…" : ""}</h1>
        <div className="flex flex-wrap gap-2 pt-1">
          {task.task_type && <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/30 text-zinc-300">{task.task_type}</span>}
          {task.provider && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-700/20 text-blue-300">{task.provider}</span>}
          {task.outcome && <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${outcomeClass}`}>{task.outcome}</span>}
        </div>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground">Status</p>
          <p className="font-medium capitalize">{task.status}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground">Created</p>
          <p>{task.created_at ? new Date(task.created_at).toLocaleDateString() : "—"}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground">Updated</p>
          <p>{task.updated_at ? new Date(task.updated_at).toLocaleDateString() : "—"}</p>
        </div>
      </section>

      {task.result && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2">
          <h2 className="text-lg font-medium">Result / Output</h2>
          <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
            {task.result}
          </pre>
        </section>
      )}
    </main>
  );
}
