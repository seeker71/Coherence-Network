// Spec edit surface — close the asymmetry with ideas/concepts.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { SpecEditor, type SpecRegistryEntry } from "./_components/SpecEditor";

export const dynamic = "force-dynamic";

async function fetchSpec(id: string): Promise<SpecRegistryEntry | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/spec-registry/${encodeURIComponent(id)}`, {
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
  params: Promise<{ spec_id: string }>;
}): Promise<Metadata> {
  const { spec_id } = await params;
  const spec = await fetchSpec(decodeURIComponent(spec_id));
  return {
    title: spec ? `Edit ${spec.title} — Coherence Network` : "Edit Spec",
  };
}

export default async function EditSpecPage({
  params,
}: {
  params: Promise<{ spec_id: string }>;
}) {
  const { spec_id } = await params;
  const specId = decodeURIComponent(spec_id);
  const spec = await fetchSpec(specId);
  if (!spec) notFound();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <nav className="mb-8 flex items-center gap-2 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/specs" className="hover:text-amber-400/80 transition-colors">
          Specs
        </Link>
        <span className="text-stone-700">/</span>
        <Link
          href={`/specs/${encodeURIComponent(specId)}`}
          className="hover:text-amber-400/80 transition-colors"
        >
          {spec.title}
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Edit</span>
      </nav>

      <h1 className="mb-8 text-3xl font-extralight text-white">{spec.title}</h1>

      <SpecEditor spec={spec} />
    </main>
  );
}
