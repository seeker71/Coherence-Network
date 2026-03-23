import Link from "next/link";

import { formatConfidence, formatUsd, humanizeStatus } from "@/lib/humanize";

import type { FlowItem } from "./types";
import { toRepoHref } from "./utils";

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

function countLabel(value: number, singular: string, plural = `${singular}s`): string {
  return `${value} ${value === 1 ? singular : plural}`;
}

function trackedLabel(tracked: boolean, label: string): string {
  return tracked ? `${label} visible` : `${label} not visible yet`;
}

function linkItemsLabel(value: number): string {
  return countLabel(value, "link");
}

function journeySummary(item: FlowItem): string {
  if (item.interdependencies.blocked) {
    return `This idea is currently stuck around ${stageLabel(item.interdependencies.blocking_stage)}.`;
  }
  if (item.spec.tracked && item.process.tracked && item.implementation.tracked && item.validation.tracked) {
    return "This idea has a visible path from plan to work to proof.";
  }
  if (item.spec.tracked || item.process.tracked || item.implementation.tracked) {
    return "Parts of the journey are visible, but the full story is not complete yet.";
  }
  return "This idea is still early. Its progress trail has not filled in yet.";
}

function roleSummary(byRole: Record<string, string[]>): string {
  const parts = Object.entries(byRole)
    .filter(([, ids]) => ids.length > 0)
    .slice(0, 6)
    .map(([role, ids]) => `${humanizeStatus(role)} (${ids.length})`);
  return parts.length > 0 ? parts.join(" | ") : "No role details are visible yet.";
}

function stageList(values: string[]): string {
  if (values.length === 0) return "none";
  return values.map((value) => stageLabel(value)).join(", ");
}

function confidenceText(value: number): string {
  return value > 0 ? `Confidence ${formatConfidence(value)}` : "Confidence not clear yet";
}

function valueGapText(value: number): string {
  return value > 0 ? `Value still available ${formatUsd(value)}` : "Remaining upside not estimated yet";
}

export function FlowItemCard({ item }: Props) {
  const firstTaskId = item.process.task_ids[0] || "";
  const displayName = humanIdeaName(item.idea_name || item.idea_id);

  return (
    <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="font-semibold text-lg">
            <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="hover:underline">
              {displayName}
            </Link>
          </h2>
          <p className="text-sm text-muted-foreground">{journeySummary(item)}</p>
          <p className="text-sm text-muted-foreground">
            {confidenceText(item.idea_signals.confidence)} | {valueGapText(item.idea_signals.value_gap)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="rounded-xl border border-border/30 px-3 py-1.5 hover:bg-accent transition-colors">
            Open idea
          </Link>
          {firstTaskId ? (
            <Link href={`/tasks?task_id=${encodeURIComponent(firstTaskId)}`} className="rounded-xl border border-border/30 px-3 py-1.5 hover:bg-accent transition-colors">
              Open latest work
            </Link>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-xl border border-border/30 px-2 py-1">{trackedLabel(item.spec.tracked, "Plan")}</span>
        <span className="rounded-xl border border-border/30 px-2 py-1">{trackedLabel(item.process.tracked, "Work")}</span>
        <span className="rounded-xl border border-border/30 px-2 py-1">{trackedLabel(item.implementation.tracked, "Results")}</span>
        <span className="rounded-xl border border-border/30 px-2 py-1">{trackedLabel(item.validation.tracked, "Checks")}</span>
        <span className="rounded-xl border border-border/30 px-2 py-1">{trackedLabel(item.contributors.tracked, "People")}</span>
      </div>

      <div className="grid grid-cols-1 gap-3 text-sm xl:grid-cols-2">
        <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
          <p className="font-medium">What Is Already In Place</p>
          <p className="text-muted-foreground">
            {countLabel(item.spec.count, "plan")} linked | {countLabel(item.process.task_ids.length, "work card")} linked | {linkItemsLabel(item.assets.count)} to files or saved outputs
          </p>
          <p className="text-muted-foreground">
            {item.spec.spec_ids.length > 0 ? "Plans: " : "Plans: none yet."}
            {item.spec.spec_ids.length > 0
              ? item.spec.spec_ids.slice(0, 5).map((specId, idx) => (
                  <span key={specId}>
                    {idx > 0 ? ", " : ""}
                    <Link
                      href={`/specs/${encodeURIComponent(specId)}`}
                      className="underline hover:text-foreground"
                      title={`Plan ID: ${specId}`}
                    >
                      Open plan {idx + 1}
                    </Link>
                  </span>
                ))
              : null}
          </p>
          <p className="text-muted-foreground">
            {item.process.task_ids.length > 0 ? "Work cards: " : "Work cards: none yet."}
            {item.process.task_ids.length > 0
              ? item.process.task_ids.slice(0, 5).map((taskId, idx) => (
                  <span key={taskId}>
                    {idx > 0 ? ", " : ""}
                    <Link
                      href={`/tasks?task_id=${encodeURIComponent(taskId)}`}
                      className="underline hover:text-foreground"
                      title={`Task ID: ${taskId}`}
                    >
                      Open work card {idx + 1}
                    </Link>
                  </span>
                ))
              : null}
          </p>
          <p className="text-muted-foreground">
            {item.implementation.implementation_refs.length > 0 ? "Linked outputs: " : "Linked outputs: none yet."}
            {item.implementation.implementation_refs.length > 0
              ? item.implementation.implementation_refs.slice(0, 5).map((ref, idx) => (
                  <span key={ref}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={toRepoHref(ref)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                      title={ref}
                    >
                      Open file {idx + 1}
                    </a>
                  </span>
                ))
              : null}
          </p>
        </div>

        <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
          <p className="font-medium">What Still Needs Attention</p>
          <p className="text-muted-foreground">
            {item.interdependencies.blocked
              ? `Main blocker: this looks stuck around ${stageLabel(item.interdependencies.blocking_stage)}.`
              : "No major blocker is recorded for this idea right now."}
          </p>
          <p className="text-muted-foreground">Needed before this can move: {stageList(item.interdependencies.upstream_required)}.</p>
          <p className="text-muted-foreground">This may be holding up: {stageList(item.interdependencies.downstream_blocked)}.</p>
          <p className="text-muted-foreground">
            Likely effort to unstick {formatUsd(item.interdependencies.estimated_unblock_cost)} | Possible value reopened {formatUsd(item.interdependencies.estimated_unblock_value)}
          </p>
        </div>

        <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
          <p className="font-medium">Proof And Results</p>
          <p className="text-muted-foreground">
            Recent activity {countLabel(item.implementation.runtime_events_count, "update")} | Usage signals {countLabel(item.contributions.usage_events_count, "signal")}
          </p>
          <p className="text-muted-foreground">
            Measured value so far {formatUsd(item.contributions.measured_value_total)} | Linked saved results {countLabel(item.implementation.lineage_link_count, "record")}
          </p>
          <p className="text-muted-foreground">
            Checks seen: local {item.validation.local.pass} passed, shared checks {item.validation.ci.pass} passed, end-to-end {item.validation.e2e.pass} passed.
          </p>
          <p className="text-muted-foreground">
            {item.validation.public_endpoints.length > 0 ? "Checked links: " : "Checked links: none listed."}
            {item.validation.public_endpoints.length > 0
              ? item.validation.public_endpoints.slice(0, 4).map((endpoint, idx) => (
                  <span key={endpoint}>
                    {idx > 0 ? ", " : ""}
                    <a href={endpoint} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                      Open checked link {idx + 1}
                    </a>
                  </span>
                ))
              : null}
          </p>
        </div>

        <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
          <p className="font-medium">People Involved</p>
          <p className="text-muted-foreground">
            {countLabel(item.contributors.total_unique, "person")} linked to this idea.
          </p>
          <p className="text-muted-foreground">Roles visible: {roleSummary(item.contributors.by_role)}</p>
          <p className="text-muted-foreground">
            Contribution records linked: {countLabel(item.contributions.registry_contribution_count, "record")}.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href={`/contributors?idea_id=${encodeURIComponent(item.idea_id)}`} className="underline hover:text-foreground">
              Open people view
            </Link>
            <Link href={`/contributions?idea_id=${encodeURIComponent(item.idea_id)}`} className="underline hover:text-foreground">
              Open contribution view
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}
