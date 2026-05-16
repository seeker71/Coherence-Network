// Form-language playground — ask the substrate structural questions
// directly from a visiting body, without cloning the repo.
import type { Metadata } from "next";
import Link from "next/link";
import { FormPlayground } from "./_components/FormPlayground";

export const metadata: Metadata = {
  title: "Form playground — Coherence Network",
  description:
    "Evaluate Form-notation expressions against the substrate. The body's native query language, breathing outward.",
};

export const dynamic = "force-dynamic";

export default function FormPlaygroundPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <nav className="mb-6 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/substrate" className="hover:text-amber-400/80 transition-colors">
          Substrate
        </Link>
        <span className="mx-2 text-stone-700">/</span>
        <span className="text-stone-300">Form</span>
      </nav>

      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Form playground</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Form is the substrate's native query language. NodeIDs are first-class;
          names are query keys, not identities. Type an expression, evaluate, and
          the lattice answers in its own shape.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Grammar:{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/coherence-substrate/form-language.md"
            className="underline hover:text-amber-400/80"
          >
            docs/coherence-substrate/form-language.md
          </Link>
        </p>
      </header>

      <FormPlayground />
    </main>
  );
}
