import type { Metadata } from "next";
import {
  ECOSYSTEM_LINKS,
  CATEGORY_GUIDANCE,
  type EcosystemLink,
} from "@/lib/ecosystem-links";

export const metadata: Metadata = {
  title: "Ecosystem",
  description: "Discover core Coherence Network entry points — source, packages, docs, runtime, and tooling.",
};

function LinkRow({ link }: { link: EcosystemLink }) {
  const isAvailable = link.status === "available" && link.url;

  return (
    <tr data-testid={`ecosystem-row-${link.id}`}>
      <td className="py-3 pr-4 font-medium text-foreground">{link.name}</td>
      <td className="py-3 pr-4 text-muted-foreground">{link.purpose}</td>
      <td className="py-3 pr-4">
        <span className="inline-block rounded-full border border-border/50 px-2 py-0.5 text-xs capitalize text-muted-foreground">
          {link.type}
        </span>
      </td>
      <td className="py-3">
        {isAvailable ? (
          <a
            href={link.url!}
            target="_blank"
            rel="noreferrer noopener"
            className="text-sm text-primary hover:underline"
            data-testid={`ecosystem-link-${link.id}`}
          >
            Open &rarr;
          </a>
        ) : (
          <span
            className="text-sm text-muted-foreground/60"
            data-testid={`ecosystem-unavailable-${link.id}`}
          >
            Unavailable &mdash; Link not configured yet
          </span>
        )}
      </td>
    </tr>
  );
}

export default function EcosystemPage() {
  let links: typeof ECOSYSTEM_LINKS;

  try {
    links = ECOSYSTEM_LINKS;
  } catch {
    return (
      <div className="mx-auto max-w-4xl px-4 md:px-8 py-16 text-center">
        <h1 className="text-2xl font-semibold mb-2">Ecosystem links temporarily unavailable</h1>
        <p className="text-muted-foreground">Refresh page or check again shortly.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 md:px-8 py-12">
      <h1 className="text-3xl font-bold tracking-tight mb-2">Ecosystem</h1>
      <p className="text-muted-foreground mb-8">
        Core entry points for the Coherence Network — build, integrate, contribute, and run agents.
      </p>

      <div className="overflow-x-auto rounded-lg border border-border/50">
        <table className="w-full text-sm" data-testid="ecosystem-table">
          <thead>
            <tr className="border-b border-border/40 bg-muted/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="py-3 px-4 pr-4 font-medium">Name</th>
              <th className="py-3 pr-4 font-medium">Purpose</th>
              <th className="py-3 pr-4 font-medium">Type</th>
              <th className="py-3 pr-4 font-medium">Link</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30 px-4">
            {links.map((link) => (
              <LinkRow key={link.id} link={link} />
            ))}
          </tbody>
        </table>
      </div>

      <section className="mt-12" aria-labelledby="guidance-heading">
        <h2 id="guidance-heading" className="text-xl font-semibold mb-4">Contributor Guidance</h2>
        <dl className="grid gap-4 sm:grid-cols-2">
          {(Object.entries(CATEGORY_GUIDANCE) as [string, string][]).map(([type, guidance]) => (
            <div key={type} className="rounded-lg border border-border/40 p-4">
              <dt className="text-sm font-medium capitalize text-foreground">{type}</dt>
              <dd className="mt-1 text-sm text-muted-foreground">{guidance}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
