import Link from "next/link";

/**
 * Three-button time-range selector. Pure server component — clicking any
 * option updates the URL (?days=N) and the async page re-renders against
 * that window. No client state, no re-fetch logic.
 */
export function RangeToggle({ active }: { active: number }) {
  const options = [7, 30, 90];
  return (
    <div
      className="inline-flex items-center rounded-full border border-border/40 bg-background/40 p-0.5 text-xs"
      role="group"
      aria-label="Time range"
    >
      {options.map((n) => {
        const isActive = n === active;
        return (
          <Link
            key={n}
            href={`/pulse?days=${n}`}
            scroll={false}
            className={`px-3 py-1 rounded-full transition-colors ${
              isActive
                ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
            }`}
            aria-current={isActive ? "page" : undefined}
          >
            {n}d
          </Link>
        );
      })}
    </div>
  );
}
