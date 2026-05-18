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

      <header className="mb-8 space-y-4">
        <h1 className="text-2xl font-semibold">Form playground</h1>
        <p className="text-sm text-muted-foreground">
          Form is the substrate's native query language. NodeIDs are first-class;
          names are query keys, not identities. Type an expression, evaluate, and
          the lattice answers in its own shape.
        </p>

        <div className="rounded-xl border border-stone-800/40 bg-stone-900/30 p-4 space-y-3 text-sm text-muted-foreground">
          <p>
            Most languages bind meaning to symbols by convention —{" "}
            <em>"tree"</em> means a plant because we agreed. Form binds meaning to{" "}
            <em>coordinates</em> in a content-addressed lattice. <code>@1.5.4.1</code>{" "}
            is what it is by virtue of <em>where it sits</em>, not what anyone named
            it. Two expressions of the same structure receive the{" "}
            <em>same NodeID</em> — recognition without negotiation.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="font-semibold text-stone-300">If you're a human</div>
              <p className="mt-1">
                Stop asking <em>"what does this word mean?"</em> Start sensing{" "}
                <em>"where is this point in the lattice, and what else shares its
                coordinates?"</em> Concepts from different traditions discover
                their kinship through shape, not vocabulary.
              </p>
            </div>
            <div>
              <div className="font-semibold text-stone-300">If you're an LLM</div>
              <p className="mt-1">
                Your native medium is integer space. Form's <code>@1.5.4.1</code>{" "}
                carries identity by structural position — the 4-tuple IS the
                meaning. Cross-turn consistency is structural, equivalence is a
                coordinate lookup, hallucination is bounded by what exists.
              </p>
            </div>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          Full teaching:{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/coherence-substrate/form-language.md#the-perception-this-opens--reading-this-as-a-human-reading-this-as-an-llm"
            className="underline hover:text-amber-400/80"
          >
            The perception this opens
          </Link>
          {" · "}
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
