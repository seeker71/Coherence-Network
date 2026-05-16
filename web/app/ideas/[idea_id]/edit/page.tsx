// Idea edit surface — mirrors the asymmetry-closing for /vision/{id}/edit.
// Ideas were view-only from the web until now; this brings authoring inside
// the visiting body.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
import type { IdeaWithScore } from "@/lib/types";
import { IdeaEditor } from "./_components/IdeaEditor";

export const dynamic = "force-dynamic";

async function fetchIdea(id: string): Promise<IdeaWithScore | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/ideas/${encodeURIComponent(id)}`, {
      next: { revalidate: 0 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ idea_id: string }>;
}): Promise<Metadata> {
  const { idea_id } = await params;
  const idea = await fetchIdea(decodeURIComponent(idea_id));
  return {
    title: idea ? `Edit ${idea.name} — Coherence Network` : "Edit Idea",
  };
}

export default async function EditIdeaPage({
  params,
}: {
  params: Promise<{ idea_id: string }>;
}) {
  const { idea_id } = await params;
  const ideaId = decodeURIComponent(idea_id);
  const idea = await fetchIdea(ideaId);
  if (!idea) notFound();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <nav className="mb-8 flex items-center gap-2 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/ideas" className="hover:text-amber-400/80 transition-colors">
          Ideas
        </Link>
        <span className="text-stone-700">/</span>
        <Link
          href={`/ideas/${encodeURIComponent(idea.id)}`}
          className="hover:text-amber-400/80 transition-colors"
        >
          {idea.name}
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Edit</span>
      </nav>

      <h1 className="mb-8 text-3xl font-extralight text-white">{idea.name}</h1>

      <IdeaEditor idea={idea} />
    </main>
  );
}
