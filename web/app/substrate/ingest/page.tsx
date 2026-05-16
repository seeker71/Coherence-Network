// Substrate ingest — let a visiting body place markdown content into
// the lattice without cloning the repo.
//
// The body-reads-itself discipline holds: cells are keyed by frontmatter
// name (or body hash when no name is present); equivalence is structural,
// not lexical. New shapes become new Blueprints; matching shapes converge.
import type { Metadata } from "next";
import Link from "next/link";
import { IngestForm } from "./_components/IngestForm";

export const metadata: Metadata = {
  title: "Ingest into the substrate — Coherence Network",
  description:
    "Place markdown content into the lattice. Memory, spec, idea, concept, presence.",
};

export const dynamic = "force-dynamic";

export default function IngestPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <nav className="mb-6 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/substrate" className="hover:text-amber-400/80 transition-colors">
          Substrate
        </Link>
        <span className="mx-2 text-stone-700">/</span>
        <span className="text-stone-300">Ingest</span>
      </nav>

      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Ingest into the substrate</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Place markdown content into the lattice. Cells are keyed by the
          frontmatter name field for their domain; matching shapes converge to
          the same Blueprint automatically.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Cross-references in your content do not auto-bind to existing cells
          — the body reads itself first. If you mean a specific existing cell,
          name it directly.
        </p>
      </header>

      <IngestForm />
    </main>
  );
}
