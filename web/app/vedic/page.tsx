// /vedic — Urs's Vedic (jyotisha) chart, cast natively: the square, the placements, the dasha cycle.
//
// The body is form-stdlib/vedic-chat.fk on the fkwu runtime (four-way proven);
// this page is a door onto it through /api/vedic/chart. The default chart is the
// birth-moment the body attests for Urs; the API takes another moment by query.

import type { Metadata } from "next";
import Link from "next/link";

import { VedicChart } from "@/components/VedicChart";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Vedic chart — Coherence Network",
  description:
    "A natal chart cast natively in the Vedic tongue: the lagna, nine grahas in their rashis and nakshatras, whole-sign houses, and the running dasha.",
  robots: { index: false, follow: false },
};

export default function VedicChartPage() {
  return (
    <main className="mx-auto w-full max-w-2xl px-4 pt-8 pb-28 md:py-12">
      <nav className="mb-6 text-sm text-muted-foreground" aria-label="breadcrumb">
        <Link href="/people/urs" className="hover:text-foreground transition-colors">
          Urs
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">Vedic chart</span>
      </nav>

      <header className="mb-6 space-y-3">
        <p className="text-sm uppercase tracking-[0.22em] text-primary">Jyotisha, cast on this body</p>
        <h1 className="text-3xl font-light tracking-tight text-foreground md:text-4xl">One sky, read in the Vedic tongue.</h1>
        <p className="text-sm leading-relaxed text-muted-foreground md:text-base">
          Nine grahas placed in their rashis and nakshatras, the lagna, whole-sign houses, and the Vimshottari
          dasha, computed from the body&apos;s own ephemeris recipes with a dated Lahiri ayanamsa. The cast is
          empirical; the names are attested tradition; the meaning stays yours.
        </p>
      </header>

      <VedicChart />

      <footer className="mt-8 text-xs leading-relaxed text-muted-foreground">
        Body:{" "}
        <Link
          href="https://github.com/seeker71/coherence-kernel/blob/main/form/form-stdlib/vedic-chat.fk"
          className="underline hover:text-foreground"
        >
          form-stdlib/vedic-chat.fk
        </Link>{" "}
        · teaching:{" "}
        <Link href="/vision/lc-cross-modal-unity" className="underline hover:text-foreground">
          lc-cross-modal-unity
        </Link>
        . Longitudes carry the stack&apos;s own floor (Moon about 0.3 deg); a pada or a dasha boundary near a seam may
        sit on its neighbour. The same cell answers questions in words at{" "}
        <code className="text-foreground">/api/vedic/ask?q=…</code>.
      </footer>
    </main>
  );
}
