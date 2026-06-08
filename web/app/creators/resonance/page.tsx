import Link from "next/link";

import { LensesNav } from "@/components/LensesNav";
import { CreatorResonanceBuilder } from "./_components/CreatorResonanceBuilder";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Creator Resonance Report - Coherence Network",
  description:
    "Build an evidence-backed report from creator platform snapshots.",
};

export default function CreatorResonancePage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <nav
        className="mb-8 flex items-center gap-2 text-sm text-stone-500"
        aria-label="breadcrumb"
      >
        <Link href="/" className="transition-colors hover:text-amber-400/80">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <Link href="/creators" className="transition-colors hover:text-amber-400/80">
          Creators
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Resonance report</span>
      </nav>

      <div className="mb-8 max-w-3xl">
        <h1 className="mb-4 text-4xl font-extralight text-white">
          Creator resonance report
        </h1>
        <p className="text-lg leading-relaxed text-stone-300">
          Turn Spotify, Instagram, and other platform snapshots into a clear
          signal of attention, conversion, income, and the next move worth testing.
        </p>
      </div>

      <div className="mb-10">
        <LensesNav current="creators" />
      </div>

      <CreatorResonanceBuilder />
    </main>
  );
}
