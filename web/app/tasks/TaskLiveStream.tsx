"use client";

import { useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";

type StreamEvent = {
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
  node_name?: string;
  provider?: string;
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

function EventIcon({ type }: { type: string }) {
  switch (type) {
    case "heartbeat":
      return <span className="text-yellow-500">♥</span>;
    case "progress":
      return <span className="text-cyan-500">→</span>;
    case "provider_done":
      return <span className="text-green-500">✓</span>;
    case "completed":
      return <span className="text-green-500">🏁</span>;
    case "failed":
    case "timeout":
      return <span className="text-red-500">✗</span>;
    case "stream_open":
      return <span className="text-cyan-500">◉</span>;
    case "claimed":
      return <span className="text-muted-foreground">○</span>;
    case "executing":
      return <span className="text-amber-500">▶</span>;
    default:
      return <span className="text-muted-foreground">·</span>;
  }
}

function EventMessage({ event }: { event: StreamEvent }) {
  const d = event.data;
  switch (event.event_type) {
    case "heartbeat": {
      const files = (d.files_changed as number) || 0;
      const summary = (d.git_summary as string) || "no changes";
      const elapsed = (d.elapsed_s as number) || 0;
      const diffStat = d.diff_stat as string | undefined;
      return (
        <span>
          <span className="text-muted-foreground">{elapsed}s</span>
          {" · "}
          <span>{files} file{files !== 1 ? "s" : ""}</span>
          {" · "}
          <span className="text-muted-foreground">{summary}</span>
          {diffStat && (
            <span className="block text-xs text-muted-foreground font-mono mt-0.5">
              {diffStat}
            </span>
          )}
        </span>
      );
    }
    case "progress": {
      const msg = (d.message as string) || (d.preview as string) || "";
      return <span>{msg}</span>;
    }
    case "provider_done": {
      const dur = (d.duration_s as number) || 0;
      const chars = (d.output_chars as number) || 0;
      const ok = d.success as boolean;
      return (
        <span>
          Done in {dur}s · {chars} chars
          {ok ? (
            <span className="text-green-500 ml-1">success</span>
          ) : (
            <span className="text-red-500 ml-1">failed</span>
          )}
        </span>
      );
    }
    case "completed":
      return <span className="font-medium">Task completed</span>;
    case "failed":
      return <span className="font-medium text-red-500">Task failed</span>;
    case "timeout":
      return <span className="font-medium text-yellow-500">Task timed out</span>;
    case "executing":
      return (
        <span>
          Executing via <span className="font-medium">{event.provider || (d.provider as string) || "?"}</span>
          {event.node_name && (
            <span className="text-muted-foreground"> on {event.node_name}</span>
          )}
        </span>
      );
    case "claimed":
      return <span className="text-muted-foreground">Claimed</span>;
    case "stream_open":
      return <span>Stream opened: {(d.label as string) || ""}</span>;
    default:
      return <span className="text-muted-foreground">[{event.event_type}]</span>;
  }
}

export default function TaskLiveStream({ taskId }: { taskId: string }) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [ended, setEnded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!taskId || ended) return;

    const apiBase = getApiBase();
    const controller = new AbortController();
    let buffer = "";

    async function connect() {
      try {
        const resp = await fetch(
          `${apiBase}/api/agent/tasks/${taskId}/events`,
          {
            headers: { Accept: "text/event-stream", "Cache-Control": "no-cache" },
            signal: controller.signal,
          },
        );
        if (!resp.ok || !resp.body) return;
        setConnected(true);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          while (buffer.includes("\n\n")) {
            const idx = buffer.indexOf("\n\n");
            const chunk = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);

            for (const line of chunk.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              try {
                const event = JSON.parse(line.slice(6)) as StreamEvent;
                if (event.event_type === "end") {
                  setEnded(true);
                  return;
                }
                setEvents((prev) => [...prev.slice(-99), event]);
              } catch {}
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setConnected(false);
        }
      }
    }

    connect();
    return () => controller.abort();
  }, [taskId, ended]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events]);

  if (events.length === 0 && !connected) {
    return (
      <div className="rounded-xl border border-border/20 bg-background/40 p-4 text-sm text-muted-foreground">
        Connecting to live stream...
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/20 bg-background/40 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border/10">
        <span className="text-xs font-medium">
          {connected && !ended ? (
            <span className="text-green-500">● Live</span>
          ) : ended ? (
            <span className="text-muted-foreground">Stream ended</span>
          ) : (
            <span className="text-yellow-500">● Connecting</span>
          )}
        </span>
        <span className="text-xs text-muted-foreground">{events.length} events</span>
      </div>
      <div ref={scrollRef} className="max-h-80 overflow-y-auto p-3 space-y-1.5 text-xs">
        {events.map((event, i) => (
          <div key={`${event.timestamp}-${i}`} className="flex items-start gap-2">
            <span className="text-muted-foreground whitespace-nowrap w-16 flex-shrink-0">
              {formatTime(event.timestamp)}
            </span>
            <span className="flex-shrink-0 w-4 text-center">
              <EventIcon type={event.event_type} />
            </span>
            <span className="min-w-0">
              <EventMessage event={event} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
