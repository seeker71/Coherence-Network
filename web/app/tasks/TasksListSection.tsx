"use client";

import Link from "next/link";
import type { AgentTask } from "./types";
import { humanizeIdeaName, humanizeTaskStatus, humanizeTaskType } from "./utils";

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
      ideaName: humanizeIdeaName(fromContext || fromLookup || ideaId),
    };
  }

  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Showing {pageStart}-{pageEnd} of {totalTasks} work cards | page {page}
          {statusFilter || typeFilter || taskIdFilter ? (
            <>
              {" "}|{" "}
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
                Previous page
              </Link>
            ) : (
              <span className="opacity-50">Previous page</span>
            )}
            {hasNext ? (
              <Link href={nextHref} className="underline hover:text-foreground">
                Next page
              </Link>
            ) : (
              <span className="opacity-50">Next page</span>
            )}
          </div>
        ) : null}
      </div>
      <ul className="space-y-2 text-sm">
        {filteredRows.map((task, index) => {
          const linkedIdea = taskIdeaContext(task);
          return (
            <li key={task.id} className="rounded-lg border border-border/70 bg-background/45 p-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Link
                  href={`/tasks?task_id=${encodeURIComponent(task.id)}`}
                  className="font-medium underline hover:text-foreground"
                  title={`Task ID: ${task.id}`}
                >
                  Work card {pageStart + index}
                </Link>
                <span className="text-muted-foreground text-right">
                  {humanizeTaskType(task.task_type)} | {humanizeTaskStatus(task.status)}
                </span>
              </div>
              <div className="text-muted-foreground">{task.direction}</div>
              {linkedIdea ? (
                <div className="text-muted-foreground">
                  Linked idea{" "}
                  <Link
                    href={`/ideas/${encodeURIComponent(linkedIdea.ideaId)}`}
                    className="underline hover:text-foreground"
                    title={`Idea ID: ${linkedIdea.ideaId}`}
                  >
                    {linkedIdea.ideaName}
                  </Link>
                  {" "}|{" "}
                  <Link
                    href={`/flow?idea_id=${encodeURIComponent(linkedIdea.ideaId)}`}
                    className="underline hover:text-foreground"
                    title={`Idea ID: ${linkedIdea.ideaId}`}
                  >
                    Open progress
                  </Link>
                </div>
              ) : null}
            </li>
          );
        })}
        {filteredRows.length === 0 ? (
          <li className="rounded-lg border border-dashed border-border/70 bg-background/45 p-4 space-y-2">
            <p className="text-muted-foreground">No work cards are visible in this view yet.</p>
            <p className="text-muted-foreground">
              Start from Today or Ideas, create the next small step, then return here to keep the work current.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/today" className="underline hover:text-foreground">
                Open today view
              </Link>
              <Link href="/ideas" className="underline hover:text-foreground">
                Browse ideas
              </Link>
            </div>
          </li>
        ) : null}
      </ul>
    </section>
  );
}
