// Spec creation surface — author a new spec from the visiting body.
import type { Metadata } from "next";
import Link from "next/link";
import { SpecNewForm } from "./_components/SpecNewForm";

export const metadata: Metadata = {
  title: "New spec — Coherence Network",
  description: "Author a new spec. Title, summary, parent idea, value, cost.",
};

export default function NewSpecPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <nav className="mb-8 flex items-center gap-2 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/specs" className="hover:text-amber-400/80 transition-colors">
          Specs
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">New</span>
      </nav>

      <header className="mb-8">
        <h1 className="text-3xl font-extralight text-white">New spec</h1>
        <p className="mt-2 text-sm text-stone-400">
          A spec is the executable form of an idea — what gets built, how it's
          tested, what done looks like. Start with title and summary; link to a
          parent idea if one exists.
        </p>
      </header>

      <SpecNewForm />
    </main>
  );
}
