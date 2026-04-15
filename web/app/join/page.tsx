import Link from "next/link";
import { ContributorSetup } from "./_components/ContributorSetup";

export const metadata = {
  title: "Join — Coherence Network",
  description: "Generate your identity, register as a contributor, and start building your frequency profile.",
};

export default function JoinPage() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/vision" className="hover:text-amber-400/80 transition-colors">The Living Collective</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Join</span>
      </nav>

      <div className="mb-10 space-y-3">
        <h1 className="text-3xl font-extralight text-white">Join the Network</h1>
        <p className="text-stone-400 leading-relaxed">
          Three steps. One minute. You get a cryptographic identity that is yours forever —
          not owned by a platform, not stored in a database you cannot see.
          Your public key is your proof. Your reading builds your frequency profile.
          When you contribute, CC flows.
        </p>
      </div>

      <ContributorSetup />
    </main>
  );
}
