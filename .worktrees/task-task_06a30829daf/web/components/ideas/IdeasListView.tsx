"use client";

import Link from "next/link";
import { useState } from "react";
import { useExpertMode } from "@/components/expert-mode-context";
import { IdeaCopyLink } from "@/components/idea_share";

type IdeaQuestion = {
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer?: string | null;
};

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  resistance_risk: number;
  manifestation_status: string;
  stage?: string;
  interfaces: string[];
  open_questions: IdeaQuestion[];
  free_energy_score: number;
  value_gap: number;
  idea_type?: string;
  parent_idea_id?: string | null;
  child_idea_ids?: string[];
};

type ViewMode = "cards" | "table";

function formatUsd(val: number): string {
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(0)}k`;
  return `$${val.toFixed(0)}`;
}

function formatConfidence(val: number): string {
  return `${Math.round(val * 100)}%`;
}

function humanizeStatus(status: string): string {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "Validated";
  if (s === "partial") return "In progress";
  return "Not started";
}

function stageEmoji(status: string): string {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "✅";
  if (s === "partial") return "🔨";
  return "📋";
}

function whatItNeeds(idea: IdeaWithScore): string {
  const s = idea.manifestation_status.trim().toLowerCase();
  if (s === "validated") return "Proven — ready to scale";
  if (s === "partial") return "Needs more validation";
  if (idea.open_questions?.some((q) => !q.answer)) return "Has open questions";
  return "Needs a spec";
}

function IdeaCard({ idea, isExpert }: { idea: IdeaWithScore; isExpert: boolean }) {
  const valueGapPct =
    idea.potential_value > 0
      ? Math.min(((idea.potential_value - idea.actual_value) / idea.potential_value) * 100, 100)
      : 0;

  return (
    <article className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <Link
          href={`/ideas/${encodeURIComponent(idea.id)}`}
          className="text-lg font-medium hover:text-primary transition-colors duration-300 flex-1 min-w-0"
        >
          {idea.name}
        </Link>
        <div className="flex items-center gap-2 flex-wrap justify-end shrink-0">
          <span
            className="text-sm"
            title={humanizeStatus(idea.manifestation_status)}
            aria-label={humanizeStatus(idea.manifestation_status)}
            role="img"
          >
            {stageEmoji(idea.manifestation_status)}
          </span>
          <span className="text-xs rounded-full border border-border/40 px-3 py-1 bg-muted/30 text-muted-foreground">
            {humanizeStatus(idea.manifestation_status)}
          </span>
        </div>
      </div>

      <p className="text-sm text-foreground/80 leading-relaxed">{idea.description}</p>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-foreground/70">
          <span>Value realized</span>
          <span>
            {formatUsd(idea.actual_value)} / {formatUsd(idea.potential_value)}
          </span>
        </div>
        <div className="h-2 rounded-full bg-muted/40 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary/40 to-primary/80 transition-all duration-500"
            style={{ width: `${Math.max(100 - valueGapPct, 2)}%` }}
          />
        </div>
      </div>

      <p className="text-xs text-primary/80">{whatItNeeds(idea)}</p>

      <div className="flex items-center gap-3">
        <div className="flex-1 h-1.5 rounded-full bg-muted/40 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary/60"
            style={{ width: `${Math.min(idea.confidence * 100, 100)}%` }}
          />
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          {formatConfidence(idea.confidence)} confidence
        </span>
      </div>

      {isExpert && (
        <p className="text-xs font-mono text-muted-foreground">
          id={idea.id} | fes={idea.free_energy_score.toFixed(3)}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-4 text-sm">
        <Link
          href={`/ideas/${encodeURIComponent(idea.id)}`}
          className="text-primary hover:text-foreground transition-colors duration-300"
        >
          Open idea &rarr;
        </Link>
        <Link
          href={`/flow?idea_id=${encodeURIComponent(idea.id)}`}
          className="text-muted-foreground hover:text-foreground transition-colors duration-300"
        >
          View progress
        </Link>
        <IdeaCopyLink url={`https://coherencycoin.com/ideas/${encodeURIComponent(idea.id)}`} />
      </div>
    </article>
  );
}

function IdeaTableRow({ idea, isExpert }: { idea: IdeaWithScore; isExpert: boolean }) {
  return (
    <tr className="border-b border-border/30 hover:bg-muted/20 transition-colors">
      <td className="py-3 px-4">
        <Link
          href={`/ideas/${encodeURIComponent(idea.id)}`}
          className="font-medium hover:text-primary transition-colors"
        >
          {idea.name}
        </Link>
        {isExpert && (
          <p className="text-xs font-mono text-muted-foreground">{idea.id}</p>
        )}
      </td>
      <td className="py-3 px-4 text-sm text-muted-foreground hidden md:table-cell">
        {stageEmoji(idea.manifestation_status)} {humanizeStatus(idea.manifestation_status)}
      </td>
      <td className="py-3 px-4 text-sm text-right hidden sm:table-cell">
        {formatUsd(idea.value_gap)}
      </td>
      <td className="py-3 px-4 text-sm text-right hidden lg:table-cell">
        {formatConfidence(idea.confidence)}
      </td>
      {isExpert && (
        <td className="py-3 px-4 text-xs font-mono text-muted-foreground text-right hidden xl:table-cell">
          {idea.free_energy_score.toFixed(3)}
        </td>
      )}
      <td className="py-3 px-4 text-right">
        <Link
          href={`/ideas/${encodeURIComponent(idea.id)}`}
          className="text-primary text-sm hover:underline"
        >
          Open &rarr;
        </Link>
      </td>
    </tr>
  );
}

export default function IdeasListView({ ideas }: { ideas: IdeaWithScore[] }) {
  const { isExpert } = useExpertMode();
  const [viewMode, setViewMode] = useState<ViewMode>("cards");

  return (
    <div className="space-y-4">
      {/* View mode switcher */}
      <div className="flex items-center gap-2" role="group" aria-label="View mode">
        <span className="text-xs text-muted-foreground">View:</span>
        {(["cards", "table"] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => setViewMode(mode)}
            className={[
              "rounded-lg border px-3 py-1.5 text-xs font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring",
              viewMode === mode
                ? "border-primary/60 bg-primary/10 text-primary"
                : "border-border/40 text-muted-foreground hover:text-foreground hover:border-border",
            ].join(" ")}
            aria-pressed={viewMode === mode}
          >
            {mode === "cards" ? "Cards" : "Table"}
          </button>
        ))}
        <span className="text-xs text-muted-foreground ml-auto">{ideas.length} ideas</span>
      </div>

      {/* Cards view */}
      {viewMode === "cards" && (
        <div className="space-y-3">
          {ideas.map((idea) => (
            <IdeaCard key={idea.id} idea={idea} isExpert={isExpert} />
          ))}
        </div>
      )}

      {/* Table view */}
      {viewMode === "table" && (
        <div className="overflow-x-auto rounded-2xl border border-border/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/40 bg-muted/20">
                <th className="py-3 px-4 text-left font-medium text-muted-foreground">Idea</th>
                <th className="py-3 px-4 text-left font-medium text-muted-foreground hidden md:table-cell">Status</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground hidden sm:table-cell">Value gap</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground hidden lg:table-cell">Confidence</th>
                {isExpert && (
                  <th className="py-3 px-4 text-right font-medium text-muted-foreground hidden xl:table-cell">FE Score</th>
                )}
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">Link</th>
              </tr>
            </thead>
            <tbody>
              {ideas.map((idea) => (
                <IdeaTableRow key={idea.id} idea={idea} isExpert={isExpert} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
