// Idea creation surface — first-class authoring from outside the repo.
import type { Metadata } from "next";
import Link from "next/link";
import { IdeaNewForm } from "./_components/IdeaNewForm";

export const metadata: Metadata = {
  title: "Propose an idea — Coherence Network",
  description: "Bring a new idea into the network. Name it, describe it, value it.",
};

export default function NewIdeaPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <nav className="mb-8 flex items-center gap-2 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/ideas" className="hover:text-amber-400/80 transition-colors">
          Ideas
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">New</span>
      </nav>

      <header className="mb-8">
        <h1 className="text-3xl font-extralight text-white">Propose an idea</h1>
        <p className="mt-2 text-sm text-stone-400">
          Every idea tracked, funded, built, measured. Name it; describe the
          problem and the shape of the answer; estimate value and cost as
          honestly as you can.
        </p>
      </header>

      <IdeaNewForm />
    </main>
  );
}
