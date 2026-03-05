"use client";

import Link from "next/link";
import type { AgentTask } from "./types";

type TasksListSectionProps = {
  filteredRows: AgentTask[];
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
        {filteredRows.map((t) => (
          <li key={t.id} className="rounded-lg border border-border/70 bg-background/45 p-2 space-y-1">
            <div className="flex justify-between gap-3">
              <span className="font-medium">
                <Link href={`/tasks?task_id=${encodeURIComponent(t.id)}`} className="underline hover:text-foreground">
                  {t.id}
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
          </li>
        ))}
      </ul>
    </section>
  );
}
