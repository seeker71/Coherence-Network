import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Idea Resonance",
  description: "See what ideas resonate structurally with this one.",
};

export const revalidate = 120;

type ResonanceMatch = {
  idea_id: string;
  name: string;
  coherence: number;
  cross_domain: boolean;
  domain: string[];
};

type IdeaBrief = {
  id: string;
  name: string;
};

async function loadResonance(ideaId: string): Promise<ResonanceMatch[]> {
  try {
    const API = getApiBase();
    const res = await fetch(
      `${API}/api/ideas/${encodeURIComponent(ideaId)}/resonance?limit=10`,
      { cache: "no-store" },
    );
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function loadIdea(ideaId: string): Promise<IdeaBrief | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function coherenceColor(score: number): string {
  if (score >= 0.35) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 0.12) return "text-amber-600 dark:text-amber-400";
  return "text-muted-foreground";
}

export default async function IdeaResonancePage({
  params,
}: {
  params: Promise<{ idea_id: string }>;
}) {
  const resolved = await params;
  const ideaId = decodeURIComponent(resolved.idea_id);
  const [matches, idea] = await Promise.all([
    loadResonance(ideaId),
    loadIdea(ideaId),
  ]);

  const ideaName = idea?.name ?? ideaId;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href="/ideas"
          className="text-amber-600 dark:text-amber-400 hover:underline"
        >
          Ideas
        </Link>
        <span className="text-muted-foreground/40">/</span>
        <Link
          href={`/ideas/${encodeURIComponent(ideaId)}`}
          className="text-amber-600 dark:text-amber-400 hover:underline"
        >
          {ideaName}
        </Link>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-muted-foreground">Resonance</span>
      </div>

      <h1 className="text-3xl font-bold tracking-tight">
        What resonates with {ideaName}
      </h1>
      <p className="text-muted-foreground max-w-2xl">
        Ideas that share structural similarity through the Concept Resonance
        Kernel, even across different domains.
      </p>

      {matches.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          No resonant ideas found yet. As the portfolio grows, structural
          connections will emerge.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {matches.map((m) => (
            <Link
              key={m.idea_id}
              href={`/ideas/${encodeURIComponent(m.idea_id)}`}
              className="block rounded-lg border border-border/40 p-4 hover:border-amber-500/40 transition-colors space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-semibold text-sm leading-tight truncate">
                  {m.name}
                </h2>
                <span
                  className={`text-xs font-mono tabular-nums ${coherenceColor(m.coherence)}`}
                >
                  {(m.coherence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {m.cross_domain && (
                  <span className="inline-block rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs px-1.5 py-0.5">
                    cross-domain
                  </span>
                )}
                {m.domain?.map((d) => (
                  <span
                    key={d}
                    className="inline-block rounded bg-muted text-muted-foreground text-xs px-1.5 py-0.5"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      )}

      <nav className="pt-8 text-center border-t border-border/20">
        <Link
          href={`/ideas/${encodeURIComponent(ideaId)}`}
          className="text-sm text-amber-600 dark:text-amber-400 hover:underline"
        >
          Back to {ideaName}
        </Link>
      </nav>
    </main>
  );
}
