"use client";

import Link from "next/link";
import type { AgentTask } from "./types";

type TasksListSectionProps = {
  filteredRows: AgentTask[];
  ideaNamesById: Record<string, string>;
  pageStart: number;
  pageEnd: number;
  totalTasks: number;
  page: number;
  statusFilter: string;
  typeFilter: string;
  taskIdFilter: string;
  hasPrevious: boolean;
  hasNext: boolean;
  previousHref: string;
  nextHref: string;
};

export function TasksListSection({
  filteredRows,
  ideaNamesById,
  pageStart,
  pageEnd,
  totalTasks,
  page,
  statusFilter,
  typeFilter,
  taskIdFilter,
  hasPrevious,
  hasNext,
  previousHref,
  nextHref,
}: TasksListSectionProps) {
  function taskIdeaContext(task: AgentTask): { ideaId: string; ideaName: string } | null {
    const ctx = task.context && typeof task.context === "object" && !Array.isArray(task.context)
      ? task.context
      : null;
    if (!ctx) return null;
    const ideaId = String(ctx.idea_id || "").trim();
    if (!ideaId) return null;
    const fromContext = String(ctx.idea_name || "").trim();
    const fromLookup = ideaNamesById[ideaId] || "";
    return {
      ideaId,
      ideaName: fromContext || fromLookup || "Linked idea",
    };
  }

  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-3">
      <p className="text-sm text-muted-foreground">
        Showing {pageStart}-{pageEnd} of {totalTasks} | page {page}
        {(statusFilter || typeFilter || taskIdFilter) ? (
          <>
            {" "}
            |{" "}
            <Link href="/tasks" className="underline hover:text-foreground">
              Clear filters
            </Link>
          </>
        ) : null}
      </p>
      {!taskIdFilter ? (
        <div className="flex gap-3 text-sm text-muted-foreground">
          {hasPrevious ? (
            <Link href={previousHref} className="underline hover:text-foreground">
              Previous
            </Link>
          ) : (
            <span className="opacity-50">Previous</span>
          )}
          {hasNext ? (
            <Link href={nextHref} className="underline hover:text-foreground">
              Next
            </Link>
          ) : (
            <span className="opacity-50">Next</span>
          )}
        </div>
      ) : null}
      <ul className="space-y-2 text-sm">
        {filteredRows.map((t, index) => {
          const linkedIdea = taskIdeaContext(t);
          return (
            <li key={t.id} className="rounded-lg border border-border/70 bg-background/45 p-2 space-y-2">
              <div className="flex justify-between gap-3">
                <span className="font-medium">
                  <Link
                    href={`/tasks?task_id=${encodeURIComponent(t.id)}`}
                    className="underline hover:text-foreground"
                    title={`Task ID: ${t.id}`}
                  >
                    Task {pageStart + index}
                  </Link>
                </span>
                <span className="text-muted-foreground text-right">
                  <Link href={`/tasks?task_type=${encodeURIComponent(t.task_type)}`} className="underline hover:text-foreground">
                    {t.task_type}
                  </Link>{" "}
                  |{" "}
                  <Link href={`/tasks?status=${encodeURIComponent(t.status)}`} className="underline hover:text-foreground">
                    {t.status}
                  </Link>
                </span>
              </div>
              <div className="text-muted-foreground">{t.direction}</div>
              {linkedIdea ? (
                <div className="text-muted-foreground">
                  Idea{" "}
                  <Link
                    href={`/ideas/${encodeURIComponent(linkedIdea.ideaId)}`}
                    className="underline hover:text-foreground"
                    title={`Idea ID: ${linkedIdea.ideaId}`}
                  >
                    {linkedIdea.ideaName}
                  </Link>{" "}
                  |{" "}
                  <Link
                    href={`/flow?idea_id=${encodeURIComponent(linkedIdea.ideaId)}`}
                    className="underline hover:text-foreground"
                    title={`Idea ID: ${linkedIdea.ideaId}`}
                  >
                    Open flow
                  </Link>
                </div>
              ) : null}
            </li>
          );
        })}
        {filteredRows.length === 0 ? (
          <li className="rounded-lg border border-dashed border-border/70 bg-background/45 p-4 space-y-2">
            <p className="text-muted-foreground">No tasks yet in this view.</p>
            <p className="text-muted-foreground">
              Start from an idea and create execution work, then return here to track progress.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/ideas" className="underline hover:text-foreground">
                Browse ideas
              </Link>
              <Link href="/contribute" className="underline hover:text-foreground">
                Open contribution console
              </Link>
            </div>
          </li>
        ) : null}
      </ul>
    </section>
  );
}
