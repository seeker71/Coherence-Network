"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function toWsOrigin(httpOrigin: string): string {
  try {
    const u = new URL(httpOrigin);
    const proto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${u.host}`;
  } catch {
    return "";
  }
}

export default function LiveEventsPage() {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "error">("idle");
  const wsRef = useRef<WebSocket | null>(null);

  const append = useCallback((text: string) => {
    setLines((prev) => {
      const next = [...prev, text];
      return next.slice(-200);
    });
  }, []);

  useEffect(() => {
    const envBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
    const origin =
      envBase ||
      (typeof window !== "undefined" ? window.location.origin : "");
    const token =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("token") || ""
        : "";
    const wsHost = envBase ? toWsOrigin(envBase) : toWsOrigin(origin);
    const q = token ? `?token=${encodeURIComponent(token)}` : "";
    const wsUrl = `${wsHost}/api/events/stream${q}`;

    setStatus("connecting");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => {
      setStatus("live");
      append("[socket] open");
    };
    ws.onmessage = (ev) => {
      try {
        const j = JSON.parse(ev.data as string);
        append(`${j.event_type ?? "?"} ${JSON.stringify(j.data ?? {}).slice(0, 200)}`);
      } catch {
        append(String(ev.data));
      }
    };
    ws.onerror = () => {
      setStatus("error");
      append("[socket] error");
    };
    ws.onclose = () => {
      setStatus("idle");
      append("[socket] closed");
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [append]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Live event stream</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        WebSocket <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/events/stream</code>
        — cross-service pub/sub. Set{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">NEXT_PUBLIC_API_URL</code> to your API
        origin (e.g. <code className="rounded bg-muted px-1 py-0.5 text-xs">http://localhost:8000</code>
        ). Optional <code className="rounded bg-muted px-1 py-0.5 text-xs">?token=</code> when{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">COHERENCE_EVENT_STREAM_TOKEN</code> is
        configured.
      </p>
      <div className="mb-4 text-sm">
        Status:{" "}
        <span className="font-medium">
          {status === "live" ? "connected" : status}
        </span>
      </div>
      <pre className="max-h-[480px] overflow-auto rounded-md border bg-card p-4 text-xs leading-relaxed">
        {lines.length === 0 ? "Waiting for events…" : lines.join("\n")}
      </pre>
    </main>
  );
}
