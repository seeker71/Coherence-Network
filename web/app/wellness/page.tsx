// Wellness — the body sensing itself, breathing outward.
//
// `make wellness` was repo-only; this surface lets a visiting body read
// the same gentle text. Proprioception in the open.
import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { WellnessRefresh } from "./_components/WellnessRefresh";

export const metadata: Metadata = {
  title: "Wellness — Coherence Network",
  description:
    "The body sensing itself. Drift between maps and body, source-symbol parity, locale parity, chain health, cell breath, contract patterns, witness budget.",
};

export const dynamic = "force-dynamic";

type WellnessReading = {
  output: string;
  captured_at: number;
  duration_ms: number;
  cached: boolean;
};

async function fetchWellness(): Promise<WellnessReading | { error: string }> {
  const base = process.env.NODE_ENV !== "production"
    ? (process.env.API_URL || "http://localhost:8000")
    : (getApiBase() || "");
  try {
    const res = await fetch(`${base}/api/wellness`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) {
      return { error: `Wellness sensing returned ${res.status}` };
    }
    return res.json();
  } catch (e: unknown) {
    return { error: e instanceof Error ? e.message : "Wellness sensing failed" };
  }
}

function relativeTime(epochSeconds: number): string {
  const ageSeconds = Date.now() / 1000 - epochSeconds;
  if (ageSeconds < 60) return "just now";
  if (ageSeconds < 3600) return `${Math.floor(ageSeconds / 60)} min ago`;
  return `${Math.floor(ageSeconds / 3600)} hours ago`;
}

export default async function WellnessPage() {
  const reading = await fetchWellness();

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Wellness</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The body sensing itself. Drift between maps and body, source-symbol
          parity, locale parity, the chain idea→spec→code→test, cell breath,
          contract patterns, witness budget.
        </p>
        <p className="mt-2 text-xs italic text-muted-foreground">
          Feedback is the blood. Run this anytime the body feels slightly off.
        </p>
      </header>

      {"error" in reading ? (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-4 text-sm text-red-300">
          <p className="font-medium">Could not sense the body just now.</p>
          <p className="mt-1 text-red-400/70">{reading.error}</p>
          <p className="mt-3 text-xs text-stone-500">
            The wellness check runs inside the API container. Make sure{" "}
            <code className="font-mono">scripts/wellness_check.py</code> is
            present on the server.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-4 flex items-baseline justify-between text-xs text-stone-500">
            <span>
              captured {relativeTime(reading.captured_at)}
              {reading.cached ? " (cached)" : ` — sensed in ${reading.duration_ms}ms`}
            </span>
            <WellnessRefresh />
          </div>

          <pre className="overflow-auto rounded-xl border border-stone-800/30 bg-stone-900/30 p-4 font-mono text-xs leading-relaxed text-stone-300 whitespace-pre-wrap">
            {reading.output}
          </pre>
        </>
      )}

      <footer className="mt-8 border-t border-stone-800/30 pt-6 text-xs text-stone-500">
        <p>
          The same sensing runs inside the repo via{" "}
          <code className="font-mono">make wellness</code>. The inside body and
          the outside body now share the same proprioception. For deeper
          sensing, see also{" "}
          <Link href="/substrate" className="hover:text-amber-400/80 transition-colors">
            the substrate
          </Link>
          .
        </p>
      </footer>
    </main>
  );
}
