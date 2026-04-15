import type { Silence } from "./types";
import { formatDuration } from "./status-tokens";

/**
 * Past silences — the body remembers when it stopped breathing.
 * Ongoing silences are shown in the overall banner, not here.
 */
export function SilenceList({ silences }: { silences: Silence[] }) {
  const past = silences.filter((s) => s.ended_at !== null).slice(0, 30);

  if (past.length === 0) {
    return (
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-6">
        <h2 className="text-sm uppercase tracking-wider text-muted-foreground mb-3">
          Past silences
        </h2>
        <p className="text-sm text-muted-foreground">
          The body has not gone silent within the window. Every organ has
          responded when listened to.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-6 space-y-3">
      <h2 className="text-sm uppercase tracking-wider text-muted-foreground">
        Past silences
      </h2>
      <ul className="divide-y divide-border/30">
        {past.map((s) => {
          const start = new Date(s.started_at);
          const end = s.ended_at ? new Date(s.ended_at) : null;
          return (
            <li
              key={s.id}
              className="grid grid-cols-1 sm:grid-cols-[auto_1fr_auto] gap-2 sm:gap-4 py-3 items-center"
            >
              <span
                className={`inline-flex items-center gap-2 text-xs font-medium uppercase tracking-wider ${
                  s.severity === "silent" ? "text-rose-400" : "text-amber-400"
                }`}
              >
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    s.severity === "silent" ? "bg-rose-500" : "bg-amber-500"
                  }`}
                  aria-hidden="true"
                />
                {s.severity}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{s.organ_label}</p>
                <p className="text-xs text-muted-foreground">
                  {start.toLocaleString()}
                  {end && ` → ${end.toLocaleString()}`}
                </p>
              </div>
              <p className="text-xs text-muted-foreground font-mono text-right">
                {formatDuration(s.duration_seconds)}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
