import type { Metadata } from "next";
import Link from "next/link";
import ResonanceSearch from "./_components/ResonanceSearch";

export const metadata: Metadata = {
  title: "Resonance Discovery",
  description:
    "Enter any concept or contributor ID and discover what resonates most with it across the Coherence Network.",
};

export default function ResonanceDiscoveryPage() {
  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <header className="space-y-2">
        <nav className="text-sm text-muted-foreground flex items-center gap-2" aria-label="breadcrumb">
          <Link href="/discover" className="hover:text-foreground transition-colors">
            Discover
          </Link>
          <span className="text-muted-foreground/40">/</span>
          <span>Resonance</span>
        </nav>
        <h1 className="text-3xl font-bold tracking-tight">
          Resonance Discovery
        </h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Enter a concept or contributor ID and see what resonates most with it.
          Resonance is computed from multi-dimensional frequency profiles across
          the entire graph — revealing connections that go deeper than keywords.
        </p>
      </header>

      {/* Search (client component) */}
      <ResonanceSearch />

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/discover" className="text-blue-400 hover:underline">
            Discovery Feed
          </Link>
          <Link href="/resonance" className="text-purple-400 hover:underline">
            Resonance
          </Link>
          <Link href="/constellation" className="text-emerald-400 hover:underline">
            Constellation
          </Link>
          <Link href="/vision" className="text-amber-400 hover:underline">
            Living Collective
          </Link>
        </div>
      </nav>
    </main>
  );
}
