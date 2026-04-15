import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
import type { Concept } from "@/lib/types/vision";
import { StoryEditor } from "./_components/StoryEditor";

export const dynamic = "force-dynamic";

async function fetchConcept(id: string): Promise<Concept | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}`, { next: { revalidate: 0 } });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

export async function generateMetadata({ params }: { params: Promise<{ conceptId: string }> }): Promise<Metadata> {
  const { conceptId } = await params;
  const concept = await fetchConcept(conceptId);
  return {
    title: concept ? `Edit ${concept.name} — The Living Collective` : "Edit Story",
  };
}

export default async function EditStoryPage({ params }: { params: Promise<{ conceptId: string }> }) {
  const { conceptId } = await params;
  const concept = await fetchConcept(conceptId);
  if (!concept) notFound();

  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/vision" className="hover:text-amber-400/80 transition-colors">The Living Collective</Link>
        <span className="text-stone-700">/</span>
        <Link href={`/vision/${conceptId}`} className="hover:text-amber-400/80 transition-colors">{concept.name}</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Edit</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-8">{concept.name}</h1>

      <StoryEditor
        conceptId={conceptId}
        conceptName={concept.name}
        initialContent={concept.story_content || ""}
      />
    </main>
  );
}
