import type { OrganHistory, OrganNow } from "./types";
import { STATUS_BAR, STATUS_DOT, STATUS_LABEL, STATUS_TEXT } from "./status-tokens";

/**
 * One organ, one row. Current status dot on the left, label and uptime %
 * in the middle, a 90-day bar chart on the right. The bars are plain
 * CSS grid divs — no charting library — so this component has zero JS cost.
 */
export function OrganRow({
  now,
  history,
}: {
  now: OrganNow | undefined;
  history: OrganHistory;
}) {
  const currentStatus = now?.status ?? "unknown";
  const uptime = history.uptime_pct;
  const uptimeLabel =
    history.daily.every((d) => d.samples === 0)
      ? "—"
      : `${uptime.toFixed(uptime === 100 ? 0 : 2)}%`;

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
            <div
              key={d.date}
              className={`flex-1 min-w-[3px] rounded-sm ${STATUS_BAR[d.status]} hover:opacity-100 opacity-90 transition-opacity`}
              style={{ height: d.samples === 0 ? "35%" : "100%" }}
              title={`${d.date} · ${STATUS_LABEL[d.status]}${
                d.samples > 0
                  ? ` · ${d.samples} sample${d.samples > 1 ? "s" : ""}, ${d.failures} failure${d.failures === 1 ? "" : "s"}`
                  : " · no samples"
              }`}
            />
          ))}
        </div>
        <div className="flex items-center justify-between mt-1 text-[10px] text-muted-foreground/60">
          <span>{formatDateLabel(history.daily[0]?.date)}</span>
          <span>today</span>
        </div>
      </div>

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
