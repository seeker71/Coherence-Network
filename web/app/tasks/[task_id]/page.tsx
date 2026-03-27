"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";

import { getApiBase } from "@/lib/api";
import TaskLiveStream from "../TaskLiveStream";

type ActivityEvent = {
  id?: string;
  task_id: string;
  node_id: string;
  node_name: string;
  provider: string;
  event_type: string;
  data: Record<string, unknown>;
  timestamp: string;
};

type TaskInfo = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  model?: string;
  output?: string | null;
  current_step?: string | null;
  context?: Record<string, unknown> | null;
  claimed_by?: string | null;
  created_at?: string;
  updated_at?: string;
};

function eventIcon(eventType: string): string {
  switch (eventType) {
    case "claimed":
      return "Claimed";
    case "executing":
      return "Executing";
    case "progress":
      return "Progress";
    case "output":
      return "Output";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "timeout":
      return "Timed out";
    case "end":
      return "Stream ended";
    default:
      return eventType;
  }
}

function eventColor(eventType: string): string {
  switch (eventType) {
    case "completed":
      return "bg-green-400";
    case "failed":
    case "timeout":
      return "bg-red-400";
    case "executing":
    case "progress":
      return "bg-amber-400";
    case "claimed":
      return "bg-blue-400";
    default:
      return "bg-muted-foreground/40";
  }
}

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = typeof params.task_id === "string" ? params.task_id : "";
  const apiBase = getApiBase();

  const [task, setTask] = useState<TaskInfo | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [sseStatus, setSseStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [taskLoading, setTaskLoading] = useState(true);

  // Fetch task info
  const loadTask = useCallback(async () => {
    if (!taskId) return;
    setTaskLoading(true);
    try {
      const res = await fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}`);
      if (res.ok) {
        const data = (await res.json()) as TaskInfo;
        setTask(data);
      }
    } catch {
      // ignore
    } finally {
      setTaskLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    void loadTask();
  }, [loadTask]);

  // Fetch existing stream events
  useEffect(() => {
    if (!taskId) return;
    fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}/stream`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) setEvents(data as ActivityEvent[]);
      })
      .catch(() => {});
  }, [taskId]);

  // SSE live stream
  useEffect(() => {
    if (!taskId) return;
    setSseStatus("connecting");

    const source = new EventSource(
      `${apiBase}/api/agent/tasks/${encodeURIComponent(taskId)}/events`
    );

    source.onopen = () => {
      setSseStatus("open");
    };

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ActivityEvent;
        if (data.event_type === "end") {
          setSseStatus("closed");
          source.close();
          void loadTask();
          return;
        }
        setEvents((prev) => [...prev, data]);
      } catch {
        // ignore parse errors
      }
    };

    source.onerror = () => {
      setSseStatus("closed");
      source.close();
    };

    return () => {
      source.close();
    };
  }, [taskId, apiBase, loadTask]);

  const context = task?.context && typeof task.context === "object" ? task.context : {};
  const provider = String(context.provider || task?.model || "unknown");
  const nodeInfo = task?.claimed_by || "unknown";

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-4xl space-y-4">
        <div className="flex items-center gap-3">
          <Link
            href="/tasks"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Back to Tasks
          </Link>
        </div>

        {/* Task info */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
          {taskLoading && !task ? (
            <p className="text-muted-foreground">Loading task...</p>
          ) : task ? (
            <>
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex h-2.5 w-2.5 rounded-full ${
                    task.status === "running" || task.status === "in_progress" || task.status === "claimed"
                      ? "bg-amber-400"
                      : task.status === "completed"
                        ? "bg-green-400"
                        : task.status === "failed"
                          ? "bg-red-400"
                          : "bg-muted-foreground/40"
                  }`}
                />
                <h1 className="text-2xl font-light tracking-tight">{task.task_type} task</h1>
                <span className="rounded-md border border-border/30 px-2 py-0.5 text-xs text-muted-foreground">
                  {task.status}
                </span>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-3">{task.direction}</p>
              <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                <span>ID: <code className="font-mono">{task.id}</code></span>
                <span>Node: {nodeInfo}</span>
                <span>Provider: {provider}</span>
                {task.created_at && <span>Created: {new Date(task.created_at).toLocaleString()}</span>}
              </div>
            </>
          ) : (
            <p className="text-muted-foreground">Task not found.</p>
          )}
        </section>

        {/* Live Stream */}
        {task && (task.status === "running" || task.status === "in_progress" || task.status === "claimed") && (
          <section className="space-y-2">
            <h2 className="text-lg font-medium">Live Stream</h2>
            <TaskLiveStream taskId={taskId} />
          </section>
        )}

        {/* Event timeline */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
          <h2 className="text-lg font-medium">Event Timeline</h2>
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No activity events yet. Events will appear here as the task progresses.
            </p>
          ) : (
            <div className="space-y-2">
              {events.map((event, i) => (
                <div
                  key={event.id || `${event.timestamp}-${i}`}
                  className="flex items-start gap-3 rounded-lg border border-border/20 bg-card/40 p-3"
                >
                  <div className="flex flex-col items-center gap-1 pt-0.5">
                    <span className={`inline-flex h-2.5 w-2.5 rounded-full ${eventColor(event.event_type)}`} />
                    {i < events.length - 1 && (
                      <div className="w-px flex-1 bg-border/30" />
                    )}
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{eventIcon(event.event_type)}</span>
                      {event.node_name && (
                        <span className="text-xs text-muted-foreground">by {event.node_name}</span>
                      )}
                      {event.provider && (
                        <span className="text-xs text-muted-foreground">with {event.provider}</span>
                      )}
                      <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    {event.data && Object.keys(event.data).length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        {Object.entries(event.data)
                          .filter(([k]) => k !== "node_id" && k !== "node_name" && k !== "provider")
                          .map(([key, value]) => (
                            <span key={key} className="mr-3">
                              {key}: {typeof value === "string" ? value : JSON.stringify(value)}
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Task output */}
        {task?.output && (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
            <h2 className="text-lg font-medium">Output</h2>
            <pre className="max-h-96 overflow-auto rounded-lg bg-background/50 p-3 text-xs font-mono whitespace-pre-wrap">
              {task.output}
            </pre>
          </section>
        )}
      </div>
    </main>
  );
}
