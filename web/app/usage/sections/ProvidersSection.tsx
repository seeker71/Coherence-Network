import type { DailySummaryProviderRow } from "../types";

type ProvidersSectionProps = {
  providerRows: DailySummaryProviderRow[];
};

export function ProvidersSection({ providerRows }: ProvidersSectionProps) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-2 text-sm">
      <h2 className="font-semibold">Providers + Limits</h2>
      <ul className="space-y-2">
        {providerRows.map((row) => (
          <li key={row.provider} className="rounded-lg border border-border/70 bg-background/45 p-2">
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-medium">
                {row.provider} ({row.status})
              </span>
              <span className="text-muted-foreground">{row.data_source}</span>
            </div>
            <p className="text-muted-foreground">
              {row.usage
                ? `${row.usage.label}: used ${row.usage.used} ${row.usage.unit}` +
                  (row.usage.limit != null ? ` | limit ${row.usage.limit}` : "") +
                  (row.usage.remaining != null ? ` | remaining ${row.usage.remaining}` : "") +
                  (row.usage.window ? ` | window ${row.usage.window}` : "") +
                  (row.usage.validation_state ? ` | validation ${row.usage.validation_state}` : "") +
                  (row.usage.evidence_source ? ` | evidence ${row.usage.evidence_source}` : "")
                : "No usage metric yet"}
            </p>
            {row.usage?.validation_detail ? (
              <p className="text-muted-foreground text-xs mt-1">{row.usage.validation_detail}</p>
            ) : null}
          </li>
        ))}
        {providerRows.length === 0 ? (
          <li className="text-muted-foreground">No provider summary rows available.</li>
        ) : null}
      </ul>
    </section>
  );
}
