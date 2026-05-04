import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { loadPublicWebConfig } from "@/lib/app-config";
import {
  NOTEBOOK_PAGES,
  SILENCE_RETREAT,
  getNotebookPage,
} from "../_data";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return NOTEBOOK_PAGES.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: RouteParams): Promise<Metadata> {
  const { slug } = await params;
  const page = getNotebookPage(slug);
  if (!page) return {};
  const title = `${page.shortTitle} — Silence, Brahmavihara`;
  return {
    title,
    description: page.blurb,
    openGraph: {
      title,
      description: page.blurb,
      url: `${_WEB_UI}/silence/${page.slug}`,
      images: [{ url: page.image }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description: page.blurb,
      images: [page.image],
    },
  };
}

export default async function NotebookSlugPage({ params }: RouteParams) {
  const { slug } = await params;
  const page = getNotebookPage(slug);
  if (!page) notFound();

  const idx = NOTEBOOK_PAGES.findIndex((p) => p.slug === page.slug);
  const prev = idx > 0 ? NOTEBOOK_PAGES[idx - 1] : null;
  const next =
    idx >= 0 && idx < NOTEBOOK_PAGES.length - 1
      ? NOTEBOOK_PAGES[idx + 1]
      : null;

  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <p className="not-prose text-xs uppercase tracking-widest text-muted-foreground">
        <Link
          href="/silence"
          className="text-muted-foreground/80 hover:text-amber-400"
        >
          ← Silence
        </Link>{" "}
        · {SILENCE_RETREAT.date} · Page {String(page.n).padStart(2, "0")} of{" "}
        {NOTEBOOK_PAGES.length}
      </p>

      <h1 className="text-3xl font-light tracking-tight">{page.title}</h1>

      <div className="not-prose my-8 mx-auto max-w-2xl rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
        <Image
          src={page.image}
          alt={page.alt}
          width={4000}
          height={2252}
          className="w-full h-auto"
          sizes="(max-width: 768px) 100vw, 768px"
          priority
        />
      </div>

      <div className="space-y-4 text-stone-300 leading-relaxed">
        {page.body()}
        <p className="rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
          {page.held}
        </p>
      </div>

      <hr className="border-border/30 my-10" />

      <nav className="not-prose flex items-stretch justify-between gap-4 text-sm">
        {prev ? (
          <Link
            href={`/silence/${prev.slug}`}
            className="flex-1 rounded-xl border border-border/30 bg-card/30 hover:bg-card/50 p-4 transition-colors"
          >
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">
              ← {String(prev.n).padStart(2, "0")} · previous breath
            </p>
            <p className="text-stone-300">{prev.shortTitle}</p>
          </Link>
        ) : (
          <span className="flex-1" />
        )}
        {next ? (
          <Link
            href={`/silence/${next.slug}`}
            className="flex-1 rounded-xl border border-border/30 bg-card/30 hover:bg-card/50 p-4 transition-colors text-right"
          >
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">
              {String(next.n).padStart(2, "0")} · next breath →
            </p>
            <p className="text-stone-300">{next.shortTitle}</p>
          </Link>
        ) : (
          <span className="flex-1" />
        )}
      </nav>

      <p className="not-prose mt-8 text-center text-xs">
        <Link
          href="/silence"
          className="text-amber-500/80 hover:text-amber-400"
        >
          ← Read the whole arc
        </Link>
      </p>
    </main>
  );
}
