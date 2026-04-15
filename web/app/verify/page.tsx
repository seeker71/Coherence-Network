import Link from "next/link";
import { VerificationPanel } from "./_components/VerificationPanel";

export const metadata = {
  title: "Verify — Coherence Network",
  description: "Publicly verify CC flows, hash chains, and weekly snapshots. No login required.",
};

export default function VerifyPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/" className="hover:text-amber-400/80 transition-colors">Home</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Verify</span>
      </nav>

      <div className="mb-10 space-y-3">
        <h1 className="text-3xl font-extralight text-white">Public Verification</h1>
        <p className="text-stone-400 max-w-2xl leading-relaxed">
          Every CC flow in the Coherence Network is publicly verifiable. No login needed.
          Fetch any asset's hash chain, recompute every hash from the data, and verify
          weekly snapshot signatures with the Ed25519 public key. The math is the proof.
        </p>
      </div>

      <VerificationPanel />
    </main>
  );
}
