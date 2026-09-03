/** Public, source-attributed stewardship documents inside the shared Hati shell. */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MarkdownProse } from "@/components/markdown-prose";
import { loadStewardshipPage } from "@/lib/stewardship-documents";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ path?: string[] }>;
};

async function readPage(params: PageProps["params"]) {
  const { path = [] } = await params;
  return loadStewardshipPage(path);
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const page = await readPage(params);
  return {
    title: page ? `${page.title} — Coherence Network` : "Stewardship not found",
    description: "Public, category-level records of what the network holds and tends.",
  };
}

export default async function StewardshipPage({ params }: PageProps) {
  const page = await readPage(params);
  if (!page) notFound();

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="border-b border-border/60 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
            Stewardship
          </p>
          <h1 className="text-3xl font-light tracking-tight md:text-5xl">
            {page.title}
          </h1>
          <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
            Public records carry categories, consent, and stewardship status.
            Sensitive specifics remain outside this surface.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {page.kind === "document" ? (
          <article className="space-y-5 text-sm leading-7 text-muted-foreground md:text-base [&_h2]:pt-5 [&_h2]:text-xl [&_h2]:text-foreground [&_h3]:pt-3 [&_h3]:text-base [&_h3]:text-foreground [&_li]:ml-5 [&_li]:list-disc [&_ul]:space-y-2">
            <MarkdownProse text={page.body} />
            <p className="border-t border-border/50 pt-6 text-xs">
              <a
                className="text-primary underline-offset-4 hover:underline"
                href={`https://github.com/seeker71/Coherence-Network/blob/main/docs/stewardship/${page.sourcePath}`}
                rel="noopener noreferrer"
                target="_blank"
              >
                Read the source record
              </a>
            </p>
          </article>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {page.entries.map((entry) => (
              <Link
                className="rounded-xl border border-border/60 bg-card/40 p-4 text-sm transition-colors hover:border-primary/40 hover:bg-card/70"
                href={entry.href}
                key={entry.href}
              >
                {entry.title} <span aria-hidden>→</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
