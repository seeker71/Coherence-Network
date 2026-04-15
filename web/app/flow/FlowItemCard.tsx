import Link from "next/link";

import { formatConfidence, formatUsd, humanizeStatus } from "@/lib/humanize";

import type { FlowItem } from "./types";

type Props = { item: FlowItem };

function stageLabel(value: string | null): string {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "spec") return "planning";
  if (normalized === "process") return "work setup";
  if (normalized === "implementation") return "visible result";
  if (normalized === "validation") return "proof";
  if (normalized === "contributors") return "people handoff";
  if (normalized === "contributions") return "measured impact";
  if (!normalized) return "nothing major";
  return humanizeStatus(normalized);
}

function humanIdeaName(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "Untitled idea";
  if (/[_-]/.test(trimmed) && !trimmed.includes(" ")) {
    return trimmed
      .split(/[_-]+/)
      .filter(Boolean)
      .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
      .join(" ");
  }
  return trimmed;
}

function statusBadge(item: FlowItem): { label: string; color: string } {
  if (item.interdependencies.blocked) {
    return { label: "Stuck", color: "bg-red-500/10 text-red-500" };
  }
  if (item.validation.sensed && (item.validation.local.pass > 0 || item.validation.ci.pass > 0 || item.validation.e2e.pass > 0)) {
    return { label: "Has proof", color: "bg-green-500/10 text-green-500" };
  }
  if (item.process.sensed && item.process.task_ids.length > 0) {
    return { label: "In progress", color: "bg-blue-500/10 text-blue-500" };
  }
  if (item.spec.sensed) {
    return { label: "Planned", color: "bg-amber-500/10 text-amber-500" };
  }
  return { label: "Early", color: "bg-muted text-muted-foreground" };
}

function attentionLine(item: FlowItem): string | null {
  const parts: string[] = [];
  if (item.interdependencies.blocked) {
    parts.push(`Blocked at ${stageLabel(item.interdependencies.blocking_stage)}`);
  }
  if (item.interdependencies.estimated_unblock_cost > 0) {
    parts.push(`${formatUsd(item.interdependencies.estimated_unblock_cost)} effort`);
  }
  if (item.contributors.total_unique === 0) {
    parts.push("0 people assigned");
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function hasMeaningfulSignals(item: FlowItem): boolean {
  return item.idea_signals.confidence > 0 || item.idea_signals.value_gap > 0;
}

export function FlowItemCard({ item }: Props) {
  const firstTaskId = item.process.task_ids[0] || "";
  const displayName = humanIdeaName(item.idea_name || item.idea_id);
  const badge = statusBadge(item);
  const attention = attentionLine(item);
  const hasPeople = item.contributors.total_unique > 0;
  const hasResults = item.implementation.runtime_events_count > 0 || item.contributions.usage_events_count > 0;

  const pills: Array<{ label: string; sensed: boolean }> = [
    { label: "Plan", sensed: item.spec.sensed },
    { label: "Work", sensed: item.process.sensed },
    { label: "Results", sensed: item.implementation.sensed },
    { label: "Checks", sensed: item.validation.sensed },
  ];

  return (
    <article className="rounded-xl border border-border/20 bg-background/40 px-4 py-3 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold text-sm">
          <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="hover:underline">
            {displayName}
          </Link>
        </h2>
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-tight ${badge.color}`}>
          {badge.label}
        </span>
        {hasMeaningfulSignals(item) && (
          <span className="text-[11px] text-muted-foreground ml-auto">
            {item.idea_signals.confidence > 0 && <>{formatConfidence(item.idea_signals.confidence)} conf</>}
            {item.idea_signals.confidence > 0 && item.idea_signals.value_gap > 0 && " · "}
            {item.idea_signals.value_gap > 0 && <>{formatUsd(item.idea_signals.value_gap)} gap</>}
          </span>
        )}
        <div className="flex gap-1.5 ml-auto text-xs">
          <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="rounded-lg border border-border/30 px-2 py-0.5 hover:bg-accent transition-colors">
            Open
          </Link>
          {firstTaskId ? (
            <Link href={`/tasks?task_id=${encodeURIComponent(firstTaskId)}`} className="rounded-lg border border-border/30 px-2 py-0.5 hover:bg-accent transition-colors">
              Work
            </Link>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {pills.map((pill) => (
          <span
            key={pill.label}
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] leading-tight ${
              pill.sensed ? "bg-green-500/10 text-green-600" : "bg-muted/50 text-muted-foreground"
            }`}
          >
            <span>{pill.sensed ? "\u2713" : "\u2717"}</span>
            {pill.label}
          </span>
        ))}
        {hasPeople && (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] leading-tight bg-green-500/10 text-green-600">
            <span>{"\u2713"}</span>
            {item.contributors.total_unique} people
          </span>
        )}
        {hasResults && (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] leading-tight bg-green-500/10 text-green-600">
            {item.implementation.runtime_events_count} events
          </span>
        )}
      </div>

      {attention && (
        <p className="text-xs text-muted-foreground">{attention}</p>
      )}
    </article>
  );
}
