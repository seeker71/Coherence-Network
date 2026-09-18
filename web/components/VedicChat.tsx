"use client";

// VedicChat — the conversation surface for /vedic: a question in plain words,
// the native jyotisha reading back. Every answer is computed by
// form-stdlib/vedic-chat.fk on the fkwu runtime behind /api/vedic/ask; this
// component carries words both ways and computes nothing of the chart.

import { useEffect, useRef, useState } from "react";

import { getApiBase } from "@/lib/api";

type VedicAnswer = {
  question: string;
  answer: string;
  ground: string;
  year: number;
  runtime: string;
  body: string;
  lane: string;
};

type Turn =
  | { kind: "question"; text: string }
  | { kind: "answer"; text: string; runtime: string }
  | { kind: "silence"; text: string };

const STARTERS = [
  "show me my chart",
  "where is my moon?",
  "what is my nakshatra?",
  "which dasha is running now?",
  "what is my lagna?",
  "houses",
];

export function VedicChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);
  const [ground, setGround] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setTurns((t) => [...t, { kind: "question", text: q }]);
    setDraft("");
    try {
      const res = await fetch(
        `${getApiBase()}/api/vedic/ask?q=${encodeURIComponent(q)}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        let detail = `${res.status}`;
        try {
          const err = (await res.json()) as { detail?: string };
          if (err.detail) detail = err.detail;
        } catch {
          // the body was not JSON; the status is the whole message
        }
        setTurns((t) => [
          ...t,
          {
            kind: "silence",
            text: `The native body did not answer (${detail}). The chart is computed on the fkwu kernel; when it is not reachable from this host, this door stays honest and quiet.`,
          },
        ]);
        return;
      }
      const data = (await res.json()) as VedicAnswer;
      setGround(data.ground);
      setTurns((t) => [...t, { kind: "answer", text: data.answer, runtime: data.runtime }]);
    } catch (e) {
      setTurns((t) => [
        ...t,
        { kind: "silence", text: `The door could not be reached: ${e instanceof Error ? e.message : String(e)}` },
      ]);
    } finally {
      setAsking(false);
    }
  }

  useEffect(() => {
    // the door opens by naming what it can answer, from the body itself
    void ask("help");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  return (
    <section className="flex flex-col gap-4">
      {ground ? (
        <p className="text-xs text-muted-foreground">
          Cast from: <span className="text-foreground">{ground}</span>
        </p>
      ) : null}

      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-3 md:p-4">
        {turns.length === 0 ? (
          <p className="text-sm text-muted-foreground">Opening the door…</p>
        ) : null}
        {turns.map((turn, i) => {
          if (turn.kind === "question") {
            return (
              <div key={i} className="self-end max-w-[85%] rounded-lg bg-primary/15 px-3 py-2 text-sm text-foreground">
                {turn.text}
              </div>
            );
          }
          if (turn.kind === "silence") {
            return (
              <div key={i} className="self-start max-w-[95%] rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                {turn.text}
              </div>
            );
          }
          return (
            <div key={i} className="self-start max-w-[95%] rounded-lg bg-muted px-3 py-2">
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
                {turn.text}
              </pre>
              <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                computed on {turn.runtime}
              </p>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <div className="flex flex-wrap gap-2">
        {STARTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => void ask(s)}
            disabled={asking}
            className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:border-primary hover:text-foreground disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(draft);
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about a graha, the lagna, a dasha year…"
          aria-label="Your question"
          maxLength={400}
          className="flex-1 min-w-0 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
        />
        <button
          type="submit"
          disabled={asking || draft.trim().length === 0}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {asking ? "…" : "Ask"}
        </button>
      </form>
    </section>
  );
}
