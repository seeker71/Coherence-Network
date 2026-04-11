/**
 * Shared loading-state skeletons.
 *
 * Next.js App Router mounts a `loading.tsx` at any route-segment boundary
 * as a React Suspense fallback while the server component fetches its
 * data. Historically all 71 pages shared a single root-level skeleton
 * (`app/loading.tsx`), so users saw the same generic placeholder
 * regardless of whether they were on a list, a detail view, or a
 * multi-panel dashboard.
 *
 * This module exports three tailored variants. Segment-level
 * `loading.tsx` files import and render the appropriate one.
 */

import type { ReactNode } from "react";

function Bar({ className }: { className?: string }) {
  return <div className={`rounded bg-muted ${className || ""}`} />;
}

function ShellWrap({ children, label }: { children: ReactNode; label: string }) {
  return (
    <main
      className="mx-auto max-w-6xl px-4 md:px-8 py-12 animate-pulse"
      aria-busy="true"
      aria-label={label}
    >
      {children}
    </main>
  );
}

/** Row-based skeleton for list pages (/ideas, /specs, /contributors, /tasks). */
export function ListSkeleton({ label = "Loading list" }: { label?: string }) {
  return (
    <ShellWrap label={label}>
      <div className="space-y-6">
        <Bar className="h-8 w-48" />
        <Bar className="h-5 w-72" />
        <div className="space-y-3 mt-8">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Bar className="h-10 w-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <Bar className="h-5 w-3/4" />
                <Bar className="h-4 w-1/2" />
              </div>
              <Bar className="h-8 w-20" />
            </div>
          ))}
        </div>
      </div>
    </ShellWrap>
  );
}

/** Detail skeleton for `[id]` pages (/ideas/[id], /specs/[id], /contributors/[id]). */
export function DetailSkeleton({ label = "Loading details" }: { label?: string }) {
  return (
    <ShellWrap label={label}>
      <div className="space-y-8">
        <div className="space-y-3">
          <Bar className="h-4 w-32" />
          <Bar className="h-10 w-3/4" />
          <Bar className="h-5 w-1/2" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2 p-4 rounded-lg border border-border/40">
              <Bar className="h-4 w-20" />
              <Bar className="h-8 w-24" />
            </div>
          ))}
        </div>
        <div className="space-y-3">
          <Bar className="h-6 w-40" />
          <Bar className="h-24 w-full" />
          <Bar className="h-24 w-full" />
        </div>
      </div>
    </ShellWrap>
  );
}

/** Dashboard skeleton for multi-panel pages (/dashboard, /pipeline, /today, /marketplace). */
export function DashboardSkeleton({ label = "Loading dashboard" }: { label?: string }) {
  return (
    <ShellWrap label={label}>
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <Bar className="h-9 w-64" />
          <Bar className="h-8 w-32" />
        </div>
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-2 p-4 rounded-lg border border-border/40">
              <Bar className="h-4 w-16" />
              <Bar className="h-10 w-20" />
              <Bar className="h-3 w-24" />
            </div>
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3 p-4 rounded-lg border border-border/40">
            <Bar className="h-5 w-40" />
            <Bar className="h-48 w-full" />
          </div>
          <div className="space-y-3 p-4 rounded-lg border border-border/40">
            <Bar className="h-5 w-40" />
            <Bar className="h-48 w-full" />
          </div>
        </div>
      </div>
    </ShellWrap>
  );
}
