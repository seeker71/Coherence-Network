import type { BreathStatus, OngoingSilence, PulseHistoryOverall } from "./types";
import { STATUS_BANNER, STATUS_DOT, STATUS_LABEL, formatDuration } from "./status-tokens";

const HEADLINE: Record<BreathStatus, string> = {
  breathing: "All organs breathing",
  strained: "Something is strained",
  silent: "Something has gone silent",
  unknown: "The witness has nothing to say",
};

const SUBTITLE: Record<BreathStatus, string> = {
  breathing:
    "Every organ responded within the last probe window. The body is whole.",
  strained:
    "At least one organ is returning intermittent failures. Listening more closely.",
  silent:
    "At least one organ has stopped responding. The body is not whole right now.",
  unknown:
    "The witness has no samples yet — it may have just started, or it may be quiet itself.",
};

export function OverallBanner({
  overall,
  checkedAt,
  ongoing,
  historyOverall,
  windowDays,
}: {
  overall: BreathStatus;
  checkedAt: string;
  ongoing: OngoingSilence[];
  historyOverall: PulseHistoryOverall | null;
  windowDays: number;
}) {
  const tokens = STATUS_BANNER[overall];
  const checked = new Date(checkedAt);
  const uptimeAvailable =
    historyOverall !== null && historyOverall.uptime_pct > 0;

  return (
    <section
      className={`rounded-3xl border ${tokens.border} bg-gradient-to-b ${tokens.bg} p-8 shadow-lg ${tokens.glow}`}
      aria-label="Overall pulse"
    >
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span
              className={`relative inline-flex h-3 w-3 rounded-full ${STATUS_DOT[overall]}`}
              aria-hidden="true"
            >
              {overall === "breathing" && (
                <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/40" />
              )}
            </span>
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              {STATUS_LABEL[overall]}
            </p>
          </div>
          <h2 className={`mt-3 text-3xl font-light tracking-tight ${tokens.text}`}>
            {HEADLINE[overall]}
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground leading-relaxed">
            {SUBTITLE[overall]}
          </p>
          <p className="mt-4 text-[11px] uppercase tracking-wider text-muted-foreground/70">
            Listened at {checked.toLocaleString()}
          </p>
        </div>
        {uptimeAvailable && historyOverall && (
          <div className="text-right flex-shrink-0">
            <p className={`text-5xl font-extralight ${tokens.text}`}>
              {historyOverall.uptime_pct.toFixed(
                historyOverall.uptime_pct === 100 ? 0 : 2,
              )}
              <span className="text-2xl">%</span>
            </p>
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground/70 mt-1">
              steady breath · {windowDays}d
            </p>
            {historyOverall.worst_organ && (
              <p className="text-[11px] text-muted-foreground mt-1">
                weakest organ:{" "}
                <span className="font-mono">{historyOverall.worst_organ}</span>{" "}
                ({historyOverall.worst_uptime_pct.toFixed(2)}%)
              </p>
            )}
          </div>
        )}
      </div>

      {ongoing.length > 0 && (
        <div className="mt-6 rounded-xl border border-border/40 bg-background/40 p-4 space-y-2">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Ongoing silence{ongoing.length > 1 ? "s" : ""}
          </p>
          <ul className="space-y-1.5 text-sm">
            {ongoing.map((s) => (
              <li key={s.id} className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    s.severity === "silent" ? "bg-rose-500" : "bg-amber-500"
                  }`}
                  aria-hidden="true"
                />
                <span className="font-medium">{s.organ}</span>
                <span className="text-muted-foreground">
                  — quiet for {formatDuration(s.duration_seconds)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
