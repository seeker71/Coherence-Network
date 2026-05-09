"use client";

/**
 * PeopleFilters — structural sort/filter axes for /people.
 *
 * The directory previously offered only one knob (`?kind=`) plus a
 * resonance search. A visitor wanting to see "the most recent
 * presences" or "only entries with real descriptions" or "any name
 * containing 'mose'" had no surface for it. This component renders
 * a thin row of structural axes: sort dropdown, two filter toggles,
 * and a substring search. All state lives in the URL so any view
 * is shareable.
 *
 * Server-side filtering happens in /people/page.tsx — this component
 * just writes URL params; the page reads them and shapes the rendered
 * directory.
 */

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useState, useTransition, useEffect } from "react";

export type PeopleSort = "lineage" | "recent" | "alpha";

const SORT_LABELS: Record<PeopleSort, string> = {
  lineage: "Lineage rank",
  recent: "Most recent first",
  alpha: "Alphabetical",
};

export function PeopleFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  const sort = (searchParams.get("sort") || "lineage") as PeopleSort;
  const withDesc = searchParams.get("with") === "description";
  const withImage = searchParams.get("with") === "image";
  const initialFind = searchParams.get("find") || "";
  const [find, setFind] = useState(initialFind);

  // Keep input in sync if URL changes from elsewhere (e.g. back/forward).
  useEffect(() => {
    setFind(searchParams.get("find") || "");
  }, [searchParams]);

  function update(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === null || v === "") params.delete(k);
      else params.set(k, v);
    }
    const qs = params.toString();
    startTransition(() => {
      router.replace(qs ? `${pathname}?${qs}` : pathname);
    });
  }

  function submitFind(e: React.FormEvent) {
    e.preventDefault();
    update({ find: find.trim() || null });
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {/* Sort dropdown */}
      <label className="flex items-center gap-1.5 rounded-full border border-border/40 bg-card/40 px-3 py-1.5 hover:border-border transition-colors">
        <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          Sort
        </span>
        <select
          value={sort}
          onChange={(e) => update({ sort: e.target.value === "lineage" ? null : e.target.value })}
          className="bg-transparent text-foreground text-xs cursor-pointer focus:outline-none"
        >
          {(Object.keys(SORT_LABELS) as PeopleSort[]).map((s) => (
            <option key={s} value={s} className="bg-background">
              {SORT_LABELS[s]}
            </option>
          ))}
        </select>
      </label>

      {/* Filter chips */}
      <button
        type="button"
        onClick={() => update({ with: withDesc ? null : "description" })}
        className={`rounded-full border px-3 py-1.5 transition-colors ${
          withDesc
            ? "border-[hsl(var(--primary))]/60 bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]"
            : "border-border/40 bg-card/40 text-muted-foreground hover:text-foreground hover:border-border"
        }`}
        aria-pressed={withDesc}
      >
        With description
      </button>

      <button
        type="button"
        onClick={() => update({ with: withImage ? null : "image" })}
        className={`rounded-full border px-3 py-1.5 transition-colors ${
          withImage
            ? "border-[hsl(var(--primary))]/60 bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]"
            : "border-border/40 bg-card/40 text-muted-foreground hover:text-foreground hover:border-border"
        }`}
        aria-pressed={withImage}
      >
        With image
      </button>

      {/* Substring search */}
      <form onSubmit={submitFind} className="flex items-center gap-1.5 rounded-full border border-border/40 bg-card/40 hover:border-border transition-colors px-3 py-1.5 ml-auto">
        <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground" aria-hidden="true">
          Find
        </span>
        <input
          type="text"
          value={find}
          onChange={(e) => setFind(e.target.value)}
          placeholder="name contains…"
          className="bg-transparent text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none w-32 sm:w-44"
          aria-label="Filter by substring in name"
        />
        {find && (
          <button
            type="button"
            onClick={() => {
              setFind("");
              update({ find: null });
            }}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Clear filter"
          >
            ×
          </button>
        )}
      </form>
    </div>
  );
}
