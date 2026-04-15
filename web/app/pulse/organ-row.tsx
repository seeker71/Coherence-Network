import type { OrganHistory, OrganNow, Silence } from "./types";
import { STATUS_BAR, STATUS_DOT, STATUS_TEXT } from "./status-tokens";
import { DayBar } from "./day-tooltip";
import { LatencySparkline } from "./latency-sparkline";
import { silencesOnDay } from "./silences-on-day";

/**
 * One organ, one row. Current status dot on the left, label, uptime %, and
 * a N-day daily bar chart on the right. Each bar is a rich-tooltip DayBar
 * that shows the samples/failures/latency of that day plus any silences
 * that overlapped it. A small latency sparkline sits under the bar chart
 * so you can see the body's tempo, not just its aliveness.
 */
export function OrganRow({
  now,
  history,
  silences,
}: {
  now: OrganNow | undefined;
  history: OrganHistory;
  silences: Silence[];
}) {
  const currentStatus = now?.status ?? "unknown";
  const uptime = history.uptime_pct;
  const uptimeLabel =
    history.daily.every((d) => d.samples === 0)
      ? "—"
      : `${uptime.toFixed(uptime === 100 ? 0 : 2)}%`;

  // Pre-compute silences per day once rather than per-bar.
  const byDate: Record<string, Silence[]> = {};
  for (const d of history.daily) {
    byDate[d.date] = silencesOnDay(silences, d.date);
  }

  return (
    <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${STATUS_DOT[currentStatus]}`}
            aria-hidden="true"
          />
          <div className="min-w-0">
            <h3 className="text-base font-medium truncate">{history.label}</h3>
            <p className="text-xs text-muted-foreground truncate">
              {history.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-right flex-shrink-0">
          <div>
            <p className={`text-2xl font-light ${STATUS_TEXT[currentStatus]}`}>
              {uptimeLabel}
            </p>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              steady breath · {history.daily.length}d
            </p>
          </div>
        </div>
      </div>

      {/* Daily bars */}
      <div>
        <div
          className="flex items-end gap-[2px] h-8"
          role="img"
          aria-label={`${history.label} daily breath over ${history.daily.length} days`}
        >
          {history.daily.map((d) => (
            <DayBar
              key={d.date}
              day={d}
              silencesForDay={byDate[d.date] ?? []}
              organLabel={history.label}
              barClass={STATUS_BAR[d.status]}
            />
          ))}
        </div>
        <div className="flex items-center justify-between mt-1 text-[10px] text-muted-foreground/60">
          <span>{formatDateLabel(history.daily[0]?.date)}</span>
          <span>today</span>
        </div>
      </div>

      {/* Latency sparkline — collected all along, finally visible */}
      {history.latency_p50_ms !== null && (
        <div className="flex items-center justify-between gap-3 pt-1">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            tempo
          </p>
          <div className={STATUS_TEXT[currentStatus]}>
            <LatencySparkline daily={history.daily} />
          </div>
        </div>
      )}

      {/* Detail line when not breathing */}
      {now && now.detail && currentStatus !== "breathing" && (
        <p className="text-xs text-rose-300/90 font-mono bg-rose-500/5 rounded-lg px-3 py-2">
          {now.detail}
        </p>
      )}
    </div>
  );
}

function formatDateLabel(dateStr: string | undefined): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}
