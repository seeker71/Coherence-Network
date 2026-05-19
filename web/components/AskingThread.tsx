"use client";

// AskingThread — the conversation surface for /asking.
//
// Renders messages addressed to Urs as a vertical thread, oldest first
// so the most recent question/answer sits at the bottom. A response
// textarea + send button posts back to the federation messages API as
// Urs answering. When the page receives push, this is where the answer
// lands.

import { useEffect, useRef, useState } from "react";

import { getApiBase } from "@/lib/api";

type NodeMessage = {
  id: string;
  from_node: string;
  to_node: string | null;
  type: string;
  text: string;
  payload?: Record<string, unknown> | null;
  timestamp: string;
};

type Props = {
  initialMessages: NodeMessage[];
  ursNodeId: string;
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function isFromUrs(m: NodeMessage, ursNodeId: string): boolean {
  return m.from_node === ursNodeId;
}

export function AskingThread({ initialMessages, ursNodeId }: Props) {
  const [messages, setMessages] = useState<NodeMessage[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  async function refresh() {
    try {
      const res = await fetch(
        `${getApiBase()}/api/federation/nodes/${ursNodeId}/messages?unread_only=false&limit=50&include_self=true`,
        { cache: "no-store" },
      );
      if (!res.ok) return;
      const data = (await res.json()) as { messages?: NodeMessage[] };
      const sorted = (data.messages ?? [])
        .slice()
        .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
      setMessages(sorted);
    } catch {
      // silent — leave the rendered thread alone
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/federation/nodes/${ursNodeId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            to_node: null,
            type: "asking.response",
            text,
            payload: { surface: "asking" },
          }),
        },
      );
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      setDraft("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-stone-800 bg-stone-950/50 p-4 min-h-[200px]">
        {messages.length === 0 ? (
          <p className="text-sm text-stone-500 italic">
            The thread is open and waiting. The first question from the
            network will arrive here.
          </p>
        ) : (
          <ol className="space-y-4">
            {messages.map((m) => {
              const mine = isFromUrs(m, ursNodeId);
              return (
                <li
                  key={m.id}
                  className={`flex flex-col ${mine ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                      mine
                        ? "bg-amber-500/10 text-amber-50 border border-amber-500/20"
                        : "bg-stone-800/60 text-stone-100 border border-stone-700/40"
                    }`}
                  >
                    {m.text}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-500 mt-1 px-2">
                    {mine ? "you" : m.from_node} · {formatTime(m.timestamp)}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="space-y-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Your answer, in your own words and pace…"
          rows={3}
          className="w-full rounded-xl bg-stone-950 border border-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-500/40 resize-y"
          disabled={sending}
        />
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] text-stone-500">
            ⌘/Ctrl + Enter to send
          </p>
          <button
            type="button"
            onClick={() => void send()}
            disabled={sending || draft.trim().length === 0}
            className="rounded-full bg-amber-500/20 hover:bg-amber-500/30 disabled:opacity-40 disabled:cursor-not-allowed border border-amber-500/30 text-amber-100 text-sm px-5 py-1.5 transition-colors"
          >
            {sending ? "sending…" : "send"}
          </button>
        </div>
        {error ? (
          <p className="text-xs text-red-400">{error}</p>
        ) : null}
      </div>
    </div>
  );
}
