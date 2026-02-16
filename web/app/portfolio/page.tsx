"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

interface IdeaQuestionRow {
  idea_id: string;
  idea_name: string;
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer: string | null;
  measured_delta: number | null;
}

interface RuntimeIdeaRow {
  idea_id: string;
  event_count: number;
  total_runtime_ms: number;
  runtime_cost_estimate: number;
}

interface InventoryResponse {
  ideas: {
    summary: {
      total_ideas: number;
      total_potential_value: number;
      total_actual_value: number;
      total_value_gap: number;
    };
  };
  questions: {
    answered_count: number;
    unanswered_count: number;
    unanswered: IdeaQuestionRow[];
  };
  runtime: {
    ideas: RuntimeIdeaRow[];
  };
  implementation_usage: {
    lineage_links_count: number;
    usage_events_count: number;
  };
}

export default function PortfolioPage() {
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [draftAnswers, setDraftAnswers] = useState<Record<string, string>>({});
  const [draftDeltas, setDraftDeltas] = useState<Record<string, string>>({});
  const [submittingKey, setSubmittingKey] = useState<string | null>(null);

  async function loadInventory() {
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/inventory/system-lineage?runtime_window_seconds=86400`, {
        cache: "no-store",
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setInventory(json);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  useEffect(() => {
    void loadInventory();
  }, []);

  const topRuntime = useMemo(() => {
    if (!inventory) return [];
    return [...inventory.runtime.ideas]
      .sort((a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate)
      .slice(0, 5);
  }, [inventory]);

  async function submitAnswer(question: IdeaQuestionRow) {
    const key = `${question.idea_id}::${question.question}`;
    const answer = (draftAnswers[key] || "").trim();
    if (!answer) return;
    const deltaRaw = (draftDeltas[key] || "").trim();
    const measuredDelta = deltaRaw ? Number(deltaRaw) : undefined;
    setSubmittingKey(key);
    try {
      const res = await fetch(`${API_URL}/api/ideas/${encodeURIComponent(question.idea_id)}/questions/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.question,
          answer,
          measured_delta: Number.isFinite(measuredDelta) ? measuredDelta : undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setDraftAnswers((prev) => ({ ...prev, [key]: "" }));
      setDraftDeltas((prev) => ({ ...prev, [key]: "" }));
      await loadInventory();
    } catch (e) {
      setStatus("error");
      setError(String(e));
    } finally {
      setSubmittingKey(null);
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div>
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Portfolio Cockpit</h1>
      <p className="text-muted-foreground">
        Human interface for ROI-first idea governance: unanswered questions, runtime cost, and value gap.
      </p>
      <div className="flex flex-wrap gap-2 text-sm">
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground underline">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground underline">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground underline">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground underline">
          Tasks
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground underline">
          Ideas
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground underline">
          Specs
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground underline">
          Usage
        </Link>
      </div>

      {status === "loading" && <p className="text-muted-foreground">Loading portfolio data…</p>}
      {status === "error" && error && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && inventory && (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Ideas</p>
              <p className="text-lg font-semibold">{inventory.ideas.summary.total_ideas}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Value gap</p>
              <p className="text-lg font-semibold">{inventory.ideas.summary.total_value_gap}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Questions unanswered</p>
              <p className="text-lg font-semibold">{inventory.questions.unanswered_count}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Lineage links</p>
              <p className="text-lg font-semibold">{inventory.implementation_usage.lineage_links_count}</p>
            </div>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Top Unanswered Questions (ROI-ordered)</h2>
            {inventory.questions.unanswered.length === 0 && (
              <p className="text-sm text-muted-foreground">No open questions. Add new high-value questions.</p>
            )}
            <ul className="space-y-3">
              {inventory.questions.unanswered.map((q) => {
                const key = `${q.idea_id}::${q.question}`;
                const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
                return (
                  <li key={key} className="rounded border p-3 space-y-2">
                    <p className="font-medium">{q.question}</p>
                    <p className="text-sm text-muted-foreground">
                      idea: {q.idea_id} | value: {q.value_to_whole} | cost: {q.estimated_cost} | ROI:{" "}
                      {roi.toFixed(2)}
                    </p>
                    <div className="flex flex-col md:flex-row gap-2">
                      <Input
                        placeholder="Answer"
                        value={draftAnswers[key] || ""}
                        onChange={(e) => setDraftAnswers((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Input
                        placeholder="Measured delta (optional)"
                        value={draftDeltas[key] || ""}
                        onChange={(e) => setDraftDeltas((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Button
                        disabled={submittingKey === key || !(draftAnswers[key] || "").trim()}
                        onClick={() => void submitAnswer(q)}
                      >
                        {submittingKey === key ? "Saving…" : "Answer"}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="rounded border p-4 space-y-2">
            <h2 className="font-semibold">Runtime Cost by Idea (24h)</h2>
            <ul className="space-y-2 text-sm">
              {topRuntime.map((row) => (
                <li key={row.idea_id} className="flex justify-between rounded border p-2">
                  <span>{row.idea_id}</span>
                  <span className="text-muted-foreground">
                    events {row.event_count} | runtime {row.total_runtime_ms.toFixed(2)}ms | cost $
                    {row.runtime_cost_estimate.toFixed(6)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
