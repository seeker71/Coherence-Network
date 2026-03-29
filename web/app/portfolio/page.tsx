"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { buildSystemLineageSearchParams } from "@/lib/egress";
import { useLiveRefresh } from "@/lib/live_refresh";

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
  specs: {
    count: number;
    source: string;
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
  tracking: {
    tracked_idea_ids_count: number;
    runtime_events_count: number;
    spec_discovery_source: string;
  };
}

interface IdeaStorageInfo {
  backend: string;
  database_url: string;
  idea_count: number;
  question_count: number;
  bootstrap_source: string;
}

export default function PortfolioPage() {
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [storage, setStorage] = useState<IdeaStorageInfo | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [draftAnswers, setDraftAnswers] = useState<Record<string, string>>({});
  const [draftDeltas, setDraftDeltas] = useState<Record<string, string>>({});
  const [submittingKey, setSubmittingKey] = useState<string | null>(null);

  const loadInventory = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const lineageParams = buildSystemLineageSearchParams();
      const [inventoryRes, storageRes] = await Promise.all([
        fetch(`/api/inventory/system-lineage?${lineageParams.toString()}`),
        fetch("/api/ideas/storage"),
      ]);
      const inventoryJson = await inventoryRes.json();
      const storageJson = await storageRes.json();
      if (!inventoryRes.ok) throw new Error(JSON.stringify(inventoryJson));
      if (!storageRes.ok) throw new Error(JSON.stringify(storageJson));
      setInventory(inventoryJson);
      setStorage(storageJson);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(loadInventory);

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
      const res = await fetch(`/api/ideas/${encodeURIComponent(question.idea_id)}/questions/answer`, {
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
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Portfolio</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">Portfolio Overview</h1>
        <p className="max-w-3xl text-muted-foreground">
          Track idea governance at a glance: unanswered questions, runtime cost, and value gaps across the portfolio.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link href="/contributors" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Contributors
          </Link>
          <Link href="/contributions" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Contributions
          </Link>
          <Link href="/assets" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Assets
          </Link>
          <Link href="/tasks" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Tasks
          </Link>
          <Link href="/ideas" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Ideas
          </Link>
          <Link href="/specs" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Specs
          </Link>
          <Link href="/pipeline" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
            Pipeline
          </Link>
        </div>
      </section>

      {status === "loading" && <p className="text-muted-foreground">Loading portfolio data…</p>}
      {status === "error" && error && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && inventory && (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
              <p className="text-muted-foreground">Ideas in portfolio</p>
              <p className="text-2xl font-light text-primary">{inventory.ideas.summary.total_ideas}</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
              <p className="text-muted-foreground">Tracked ideas</p>
              <p className="text-2xl font-light text-primary">{inventory.tracking.tracked_idea_ids_count}</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
              <p className="text-muted-foreground">Specs discovered</p>
              <p className="text-2xl font-light text-primary">{inventory.specs.count}</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
              <p className="text-muted-foreground">Usage events</p>
              <p className="text-2xl font-light text-primary">{inventory.implementation_usage.usage_events_count}</p>
            </div>
          </section>

          {storage && (
            <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 text-sm space-y-1">
              <p className="text-xl font-medium">Tracking Backend</p>
              <p className="text-muted-foreground">
                {storage.backend} | {storage.idea_count} ideas | {storage.question_count} questions | bootstrap{" "}
                {storage.bootstrap_source}
              </p>
              <p className="text-xs text-muted-foreground break-all">source {storage.database_url}</p>
            </section>
          )}

          <p className="text-xs text-muted-foreground">
            Spec source: {inventory.specs.source} | Runtime events: {inventory.tracking.runtime_events_count} | Unanswered questions:{" "}
            {inventory.questions.unanswered_count} | Value gap: {inventory.ideas.summary.total_value_gap}
          </p>

          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
            <h2 className="text-xl font-medium">Top Unanswered Questions</h2>
            {inventory.questions.unanswered.length === 0 && (
              <p className="text-sm text-muted-foreground">No open questions yet. Add new high-value questions to get started.</p>
            )}
            <ul className="space-y-3">
              {inventory.questions.unanswered.map((q) => {
                const key = `${q.idea_id}::${q.question}`;
                const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
                return (
                  <li key={key} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                    <p className="font-medium">{q.question}</p>
                    <p className="text-sm text-muted-foreground">
                      idea:{" "}
                      <Link href={`/ideas/${encodeURIComponent(q.idea_id)}`} className="underline hover:text-foreground">
                        {q.idea_id}
                      </Link>{" "}
                      | value: {q.value_to_whole} | cost: {q.estimated_cost} | ROI:{" "}
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

          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2">
            <h2 className="text-xl font-medium">Runtime Cost by Idea (24h)</h2>
            <ul className="space-y-2 text-sm">
              {topRuntime.map((row) => (
                <li key={row.idea_id} className="flex justify-between rounded-xl border border-border/20 bg-background/40 p-4">
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
