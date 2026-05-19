"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { getApiBase } from "@/lib/api";

type AgentQuestion = {
  id: string;
  agent_id: string;
  question: string;
  task_id?: string | null;
  thread_id?: string | null;
  choices: string[];
  context: Record<string, unknown>;
  status: "open" | "answered";
  answer?: string | null;
  answered_by?: string | null;
  created_at: string;
  updated_at: string;
  answered_at?: string | null;
};

type QuestionEvent = {
  sequence?: number;
  event_type: string;
  question?: AgentQuestion;
};

function mergeQuestion(items: AgentQuestion[], incoming: AgentQuestion): AgentQuestion[] {
  const next = [incoming, ...items.filter((item) => item.id !== incoming.id)];
  return next.sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
}

export default function AgentQuestionsPage() {
  const api = useMemo(() => getApiBase(), []);
  const [questions, setQuestions] = useState<AgentQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [streamState, setStreamState] = useState("connecting");
  const [error, setError] = useState("");
  const lastSequence = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function loadQuestions() {
      try {
        const res = await fetch(`${api}/api/agent/questions?limit=100`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { questions: AgentQuestion[] };
        if (!cancelled) setQuestions(data.questions ?? []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load questions");
      }
    }

    void loadQuestions();
    return () => {
      cancelled = true;
    };
  }, [api]);

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;

    async function connect() {
      while (!cancelled) {
        controller = new AbortController();
        setStreamState("connected");
        try {
          const res = await fetch(
            `${api}/api/agent/questions/stream?after=${lastSequence.current}&max_events=100&timeout_seconds=30`,
            {
              headers: { Accept: "text/event-stream" },
              signal: controller.signal,
            },
          );
          if (!res.ok || !res.body) throw new Error(`stream HTTP ${res.status}`);

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (!cancelled) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split("\n\n");
            buffer = frames.pop() ?? "";

            for (const frame of frames) {
              const line = frame.split("\n").find((part) => part.startsWith("data: "));
              if (!line) continue;
              const event = JSON.parse(line.slice(6)) as QuestionEvent;
              if (typeof event.sequence === "number") {
                lastSequence.current = Math.max(lastSequence.current, event.sequence);
              }
              if (event.question) {
                setQuestions((current) => mergeQuestion(current, event.question as AgentQuestion));
              }
            }
          }
        } catch (err) {
          if (!cancelled && !(err instanceof DOMException && err.name === "AbortError")) {
            setStreamState("reconnecting");
            setError(err instanceof Error ? err.message : "Question stream interrupted");
            await new Promise((resolve) => setTimeout(resolve, 1500));
          }
        }
      }
    }

    void connect();
    return () => {
      cancelled = true;
      controller?.abort();
    };
  }, [api]);

  async function submitAnswer(event: FormEvent<HTMLFormElement>, question: AgentQuestion) {
    event.preventDefault();
    const answer = (answers[question.id] ?? "").trim();
    if (!answer) return;

    const res = await fetch(`${api}/api/agent/questions/${encodeURIComponent(question.id)}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer, answered_by: "web" }),
    });
    if (!res.ok) {
      setError(`answer HTTP ${res.status}`);
      return;
    }
    const updated = (await res.json()) as AgentQuestion;
    setQuestions((current) => mergeQuestion(current, updated));
    setAnswers((current) => ({ ...current, [question.id]: "" }));
  }

  const openQuestions = questions.filter((question) => question.status === "open");
  const answeredQuestions = questions.filter((question) => question.status === "answered");

  return (
    <main className="min-h-screen max-w-6xl mx-auto p-6 md:p-8 space-y-6">
      <nav className="flex flex-wrap gap-3 text-sm">
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/substrate/form" className="text-muted-foreground hover:text-foreground">
          Form
        </Link>
      </nav>

      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Agent Questions</h1>
          <p className="text-sm text-muted-foreground">
            Live questions from sub-agents, carried over SSE for human answers.
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="rounded-md border border-border px-2 py-1 text-muted-foreground">
            stream {streamState}
          </span>
          <span className="rounded-md border border-border px-2 py-1">
            {openQuestions.length} open
          </span>
        </div>
      </header>

      {error && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
          {error}
        </p>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Open</h2>
        {openQuestions.length === 0 && (
          <p className="rounded-lg border border-border px-3 py-3 text-sm text-muted-foreground">
            No open questions.
          </p>
        )}
        {openQuestions.map((question) => (
          <article key={question.id} className="rounded-lg border border-border bg-card/40 p-4 space-y-3">
            <div className="flex flex-col gap-1 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium">{question.question}</p>
                <p className="text-xs text-muted-foreground">
                  {question.agent_id}
                  {question.task_id ? ` · ${question.task_id}` : ""}
                  {question.thread_id ? ` · ${question.thread_id}` : ""}
                </p>
              </div>
              <time className="text-xs text-muted-foreground" dateTime={question.created_at}>
                {new Date(question.created_at).toLocaleString()}
              </time>
            </div>

            {question.choices.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {question.choices.map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    onClick={() => setAnswers((current) => ({ ...current, [question.id]: choice }))}
                    className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
                  >
                    {choice}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={(event) => void submitAnswer(event, question)} className="flex flex-col gap-2 md:flex-row">
              <input
                value={answers[question.id] ?? ""}
                onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
                className="min-h-10 flex-1 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                placeholder="Answer"
              />
              <button
                type="submit"
                className="min-h-10 rounded-md bg-foreground px-4 text-sm font-medium text-background hover:opacity-90"
              >
                Send answer
              </button>
            </form>
          </article>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Answered</h2>
        {answeredQuestions.slice(0, 20).map((question) => (
          <article key={question.id} className="rounded-lg border border-border p-4 text-sm">
            <div className="flex flex-col gap-2 md:flex-row md:justify-between">
              <div>
                <p className="font-medium">{question.question}</p>
                <p className="text-muted-foreground">{question.answer}</p>
              </div>
              <span className="text-xs text-muted-foreground">{question.answered_by ?? "web"}</span>
            </div>
          </article>
        ))}
        {answeredQuestions.length === 0 && (
          <p className="rounded-lg border border-border px-3 py-3 text-sm text-muted-foreground">
            No answered questions yet.
          </p>
        )}
      </section>
    </main>
  );
}
