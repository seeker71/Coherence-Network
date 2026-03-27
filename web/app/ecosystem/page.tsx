import { ECOSYSTEM_LINKS } from "@/lib/ecosystem-links";

export default function EcosystemPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10 md:px-8">
      <header className="mb-8 space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">Ecosystem</h1>
        <p className="max-w-3xl text-sm text-muted-foreground md:text-base">
          Use these links to build (packages + docs), integrate (API), contribute (source), and run agents
          (runtime/tooling) without leaving the Coherence workflow.
        </p>
      </header>

      <div className="overflow-hidden rounded-xl border border-border/50">
        <table className="w-full border-collapse text-left">
          <thead className="bg-muted/35 text-sm">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Purpose</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Open</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {ECOSYSTEM_LINKS.map((entry) => (
              <tr key={entry.id} className="border-t border-border/40 align-top">
                <td className="px-4 py-3 font-medium text-foreground">{entry.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{entry.purpose}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex rounded-full border border-border/60 px-2 py-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                    {entry.type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      entry.status === "available"
                        ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                        : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                    }`}
                  >
                    {entry.status === "available" ? "Available" : "Unavailable"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {entry.url ? (
                    <a
                      href={entry.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex rounded-md border border-border/60 px-2.5 py-1 text-xs font-medium text-foreground transition hover:bg-accent/60"
                    >
                      Open link
                    </a>
                  ) : (
                    <span
                      className="inline-flex cursor-not-allowed rounded-md border border-border/40 px-2.5 py-1 text-xs text-muted-foreground/80"
                      aria-disabled="true"
                    >
                      Link not configured yet
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
