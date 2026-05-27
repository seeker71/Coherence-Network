// DeployLogViewer — client component that streams the deploy log over SSE
// (primary path) and falls back to /api/deploy/log/tail polling if the
// browser or proxy chain blocks EventSource. Highlights TIMING:, errors,
// and the final "Deploy complete" line. Mobile-first: tested at 390px.
//
// API contract (api/app/routers/deploy.py, public no-auth):
//   GET /api/deploy/log/tail?lines=N
//     → {lines: string[], total: number, exists: boolean, path: string}
//   GET /api/deploy/log/stream  (SSE)
//     → events of shape `data: {"line": string, "at": iso8601}\n\n`
//   GET /api/deploy/status
//     → {current_sha, deployed_sha, in_progress, started_at, log_exists}
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";

const POLL_INTERVAL_MS = 5000;
const STATUS_POLL_INTERVAL_MS = 10000;
const LINE_LIMITS = [200, 500, 2000] as const;
type LineLimit = (typeof LINE_LIMITS)[number];

type DeployStatus = {
  current_sha?: string | null;
  deployed_sha?: string | null;
  in_progress?: boolean;
  started_at?: string | null;
  log_exists?: boolean;
};

type LogTailResponse = {
  lines?: string[];
  total?: number;
  exists?: boolean;
  path?: string;
};

type SseLineEvent = { line?: string; at?: string };

type Transport = "sse" | "polling" | "connecting" | "error";

type Classification = "timing" | "error" | "complete" | "info";

function classifyLine(line: string): Classification {
  if (/Deploy complete|DEPLOY COMPLETE|deploy finished/i.test(line)) return "complete";
  if (/\bTIMING:/i.test(line)) return "timing";
  if (/\bFAIL\b|Traceback|\bERROR\b|\bFATAL\b/.test(line)) return "error";
  return "info";
}

function classClassesFor(c: Classification): string {
  switch (c) {
    case "complete":
      return "text-emerald-300";
    case "timing":
      return "text-amber-300/90";
    case "error":
      return "text-rose-300";
    default:
      return "text-stone-300/90";
  }
}

function formatSince(ts: number | null): string {
  if (!ts) return "—";
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s ago`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m ago`;
}

function shortSha(sha: string | null | undefined): string {
  if (!sha) return "—";
  return sha.length > 8 ? sha.slice(0, 8) : sha;
}

// Append `incoming` to `prev`, deduping lines that are already at the tail.
// Both the SSE stream and polling fallback emit the recent tail on each
// connect / poll; we trust line content + ordering to recognise overlap.
function appendDedupedTail(prev: string[], incoming: string[]): string[] {
  if (incoming.length === 0) return prev;
  if (prev.length === 0) return [...incoming];

  // Find the longest suffix of prev that is a prefix of incoming.
  const maxOverlap = Math.min(prev.length, incoming.length);
  let overlap = 0;
  for (let k = maxOverlap; k > 0; k--) {
    let match = true;
    for (let i = 0; i < k; i++) {
      if (prev[prev.length - k + i] !== incoming[i]) {
        match = false;
        break;
      }
    }
    if (match) {
      overlap = k;
      break;
    }
  }
  const fresh = incoming.slice(overlap);
  if (fresh.length === 0) return prev;
  const merged = [...prev, ...fresh];
  // Cap memory at ~5000 lines so the page stays light on phone RAM.
  if (merged.length > 5000) return merged.slice(merged.length - 5000);
  return merged;
}

export function DeployLogViewer() {
  const apiBase = useMemo(() => getApiBase(), []);
  const [lines, setLines] = useState<string[]>([]);
  const [limit, setLimit] = useState<LineLimit>(500);
  const [status, setStatus] = useState<DeployStatus>({});
  const [totalLines, setTotalLines] = useState<number | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [transport, setTransport] = useState<Transport>("connecting");
  const [autoScroll, setAutoScroll] = useState(true);
  const [, setTickTock] = useState(0); // forces "time since" re-render
  const logBodyRef = useRef<HTMLDivElement | null>(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    autoScrollRef.current = autoScroll;
  }, [autoScroll]);

  const appendLines = useCallback((incoming: string[]) => {
    if (!incoming.length) return;
    setLines((prev) => appendDedupedTail(prev, incoming));
    setLastUpdate(Date.now());
  }, []);

  // Status poll — gives us SHA + in_progress.
  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const r = await fetch(`${apiBase}/api/deploy/status`, { cache: "no-store" });
        if (!r.ok) return;
        const data = (await r.json()) as DeployStatus;
        if (!cancelled) setStatus(data);
      } catch {
        // silent — the log itself is the louder signal
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, STATUS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiBase]);

  // Stream / poll loop. SSE primary; polling fallback on error.
  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (cancelled) return;
      setTransport("polling");
      const poll = async () => {
        try {
          const url = `${apiBase}/api/deploy/log/tail?lines=${limit}`;
          const r = await fetch(url, { cache: "no-store" });
          if (!r.ok) return;
          const data = (await r.json()) as LogTailResponse;
          if (typeof data.total === "number") setTotalLines(data.total);
          if (data.lines && data.lines.length) appendLines(data.lines);
        } catch {
          // try again next interval
        }
      };
      poll();
      pollTimer = setInterval(poll, POLL_INTERVAL_MS);
    };

    const startSse = () => {
      if (typeof window === "undefined" || typeof EventSource === "undefined") {
        startPolling();
        return;
      }
      try {
        const streamUrl = `${apiBase}/api/deploy/log/stream`;
        es = new EventSource(streamUrl);
        setTransport("connecting");
        let gotOpen = false;
        es.onopen = () => {
          gotOpen = true;
          setTransport("sse");
        };
        es.onmessage = (ev) => {
          if (!ev.data) return;
          const raw = ev.data as string;
          if (raw.startsWith("{")) {
            try {
              const obj = JSON.parse(raw) as SseLineEvent;
              if (typeof obj.line === "string") {
                appendLines([obj.line]);
                return;
              }
            } catch {
              /* fall through to raw */
            }
          }
          appendLines([raw]);
        };
        es.onerror = () => {
          if (cancelled) return;
          es?.close();
          es = null;
          if (!gotOpen) setTransport("error");
          startPolling();
        };
      } catch {
        startPolling();
      }
    };

    startSse();

    return () => {
      cancelled = true;
      if (es) es.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [apiBase, limit, appendLines]);

  // Tick-tock for "time since last update" — once per second.
  useEffect(() => {
    const id = setInterval(() => setTickTock((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll to bottom when new lines arrive, if user hasn't scrolled up.
  useEffect(() => {
    if (!autoScrollRef.current) return;
    const el = logBodyRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines]);

  // Detect when the user scrolls up — pause auto-scroll. If they return
  // to the bottom, re-engage.
  const onScroll = useCallback(() => {
    const el = logBodyRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }, []);

  // Slice to the current display limit (older lines stay in memory; the
  // limit selector is a viewport rather than a fetch arg).
  const visibleLines = useMemo(() => {
    if (lines.length <= limit) return lines;
    return lines.slice(lines.length - limit);
  }, [lines, limit]);

  const stateLabel = (() => {
    if (status.log_exists === false) {
      return { text: "no log yet", cls: "text-stone-400 border-stone-700/40 bg-stone-800/40" };
    }
    if (status.in_progress) {
      return { text: "in progress", cls: "text-amber-300 border-amber-500/30 bg-amber-500/10" };
    }
    // Otherwise: if current_sha matches deployed_sha, treat as complete.
    if (status.current_sha && status.deployed_sha && status.current_sha === status.deployed_sha) {
      return { text: "complete", cls: "text-emerald-300 border-emerald-500/30 bg-emerald-500/10" };
    }
    return { text: "idle", cls: "text-stone-400 border-stone-700/40 bg-stone-800/40" };
  })();

  const sinceText = formatSince(lastUpdate);
  const linesShownTotal = totalLines ?? lines.length;

  return (
    <div className="space-y-3 sm:space-y-4">
      {/* Header */}
      <header className="space-y-2">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h1 className="text-xl sm:text-2xl font-extralight text-white">Deploy Status</h1>
          <span
            className={`text-xs sm:text-sm font-mono px-2 py-0.5 rounded-full border ${stateLabel.cls}`}
            aria-live="polite"
          >
            {stateLabel.text}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-400">
          <span>
            sha: <code className="text-amber-300/80 font-mono">{shortSha(status.current_sha)}</code>
          </span>
          {status.deployed_sha && status.deployed_sha !== status.current_sha && (
            <>
              <span aria-hidden className="text-stone-700">·</span>
              <span>
                live: <code className="text-stone-400 font-mono">{shortSha(status.deployed_sha)}</code>
              </span>
            </>
          )}
          <span aria-hidden className="text-stone-700">·</span>
          <span>{linesShownTotal} lines</span>
          <span aria-hidden className="text-stone-700">·</span>
          <span>updated {sinceText}</span>
          <span aria-hidden className="text-stone-700">·</span>
          <span className="text-stone-500">
            transport:{" "}
            <span
              className={
                transport === "sse"
                  ? "text-emerald-400/80"
                  : transport === "polling"
                    ? "text-amber-400/80"
                    : "text-stone-500"
              }
            >
              {transport}
            </span>
          </span>
        </div>
      </header>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-stone-500">show last:</span>
        {LINE_LIMITS.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setLimit(n)}
            className={`px-3 py-1.5 rounded-lg border transition-colors min-h-[36px] ${
              limit === n
                ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
                : "border-stone-800/60 bg-stone-900/40 text-stone-400 hover:text-stone-200"
            }`}
            aria-pressed={limit === n}
          >
            {n}
          </button>
        ))}
        <label className="flex items-center gap-1.5 ml-auto text-stone-400 min-h-[36px] px-2 cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => {
              setAutoScroll(e.target.checked);
              if (e.target.checked) {
                const el = logBodyRef.current;
                if (el) el.scrollTop = el.scrollHeight;
              }
            }}
            className="accent-amber-500"
          />
          auto-scroll
        </label>
      </div>

      {/* Log body */}
      <div
        ref={logBodyRef}
        onScroll={onScroll}
        className="rounded-xl border border-stone-800/60 bg-black/60 px-2 sm:px-4 py-3 font-mono text-[11px] sm:text-xs leading-relaxed overflow-y-auto overflow-x-hidden h-[65vh] sm:h-[70vh]"
        role="log"
        aria-live="polite"
        aria-label="Deploy log output"
      >
        {visibleLines.length === 0 ? (
          <p className="text-stone-600 italic">
            {transport === "connecting"
              ? "connecting to log stream…"
              : transport === "error"
                ? "log stream unavailable. retrying via polling…"
                : status.log_exists === false
                  ? "no deploy log yet — nothing has been written."
                  : "waiting for log lines…"}
          </p>
        ) : (
          visibleLines.map((ln, i) => {
            const c = classifyLine(ln);
            return (
              <div
                key={`${i}-${ln.slice(0, 24)}`}
                className={`whitespace-pre-wrap break-words ${classClassesFor(c)}`}
              >
                {ln}
              </div>
            );
          })
        )}
      </div>

      {/* Tap-to-bottom (visible when auto-scroll is paused) */}
      {!autoScroll && (
        <button
          type="button"
          onClick={() => {
            const el = logBodyRef.current;
            if (el) el.scrollTop = el.scrollHeight;
            setAutoScroll(true);
          }}
          className="w-full sm:w-auto px-4 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 text-sm min-h-[44px]"
        >
          scroll to bottom · resume auto
        </button>
      )}

      <p className="text-[11px] text-stone-600 leading-relaxed pt-2">
        Public surface — same posture as <a href="/verify" className="underline decoration-stone-700 hover:text-stone-400">/verify</a>.
        SSE primary, polling fallback at {POLL_INTERVAL_MS / 1000}s.
      </p>
    </div>
  );
}
