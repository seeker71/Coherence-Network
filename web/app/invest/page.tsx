import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { formatUsd, humanizeManifestationStatus } from "@/lib/humanize";

export const metadata: Metadata = {
  title: "Invest",
  description: "Direct compute toward ideas you believe in.",
};

export const revalidate = 90;

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  manifestation_status: string;
  free_energy_score: number;
  value_gap: number;
};

type IdeaPortfolioResponse = {
  ideas: IdeaWithScore[];
};

type LedgerBalance = {
  total: number;
  by_type?: Record<string, number>;
};

type LedgerResponse = {
  balance: LedgerBalance;
};

function stageIcon(status: string): string {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "\u2705";
  if (s === "partial") return "\uD83D\uDD28";
  return "\uD83D\uDCCB";
}

async function loadIdeas(): Promise<IdeaWithScore[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas?limit=60`, { cache: "no-store" });
    if (!res.ok) return [];
    const data: IdeaPortfolioResponse = await res.json();
    return data.ideas ?? [];
  } catch {
    return [];
  }
}

async function loadBalance(contributorId: string): Promise<LedgerBalance | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/contributions/ledger/${encodeURIComponent(contributorId)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data: LedgerResponse = await res.json();
    return data.balance ?? null;
  } catch {
    return null;
  }
}

function computeRoi(idea: IdeaWithScore): number {
  const cost = idea.estimated_cost > 0 ? idea.estimated_cost : 1;
  return idea.value_gap / cost;
}

export default async function InvestPage() {
  const CONTRIBUTOR_ID = "urs-muff";
  const [ideas, balance] = await Promise.all([loadIdeas(), loadBalance(CONTRIBUTOR_ID)]);

  const sorted = [...ideas].sort((a, b) => computeRoi(b) - computeRoi(a));

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">
          Invest
        </h1>
        <p className="mt-2 text-lg text-stone-500 dark:text-stone-400">
          Direct compute toward ideas you believe in.
        </p>
      </header>

      <section className="mb-8 rounded-xl border border-amber-200 bg-amber-50/50 p-5 dark:border-amber-800/50 dark:bg-amber-950/20">
        <p className="text-sm font-medium text-amber-800 dark:text-amber-300">Your CC Balance</p>
        <p className="mt-1 text-2xl font-semibold text-amber-900 dark:text-amber-100">
          {balance ? `${balance.total.toFixed(1)} CC` : "Unavailable"}
        </p>
        <p className="mt-1 text-xs text-amber-700/70 dark:text-amber-400/70">
          Contributor: {CONTRIBUTOR_ID}
        </p>
      </section>

      {sorted.length === 0 ? (
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-8 text-center dark:border-stone-700 dark:bg-stone-800/50">
          <p className="text-stone-500 dark:text-stone-400">
            No ideas available right now.
          </p>
          <Link
            href="/ideas"
            className="mt-3 inline-block text-amber-600 hover:text-amber-500"
          >
            Browse ideas &rarr;
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-3 px-4 text-xs font-medium uppercase tracking-wider text-stone-400 dark:text-stone-500">
            <span>Idea</span>
            <span className="text-right">Value Gap</span>
            <span className="text-right">Est. Cost</span>
            <span className="text-right">ROI</span>
            <span />
          </div>
          {sorted.map((idea) => {
            const roi = computeRoi(idea);
            return (
              <div
                key={idea.id}
                className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 shadow-sm transition-shadow hover:shadow-md dark:border-stone-700 dark:bg-stone-800/60"
              >
                <div className="min-w-0">
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="font-medium text-stone-900 hover:text-amber-600 dark:text-stone-100 dark:hover:text-amber-400"
                  >
                    {stageIcon(idea.manifestation_status)} {idea.name}
                  </Link>
                  <p className="mt-0.5 truncate text-xs text-stone-500 dark:text-stone-400">
                    {humanizeManifestationStatus(idea.manifestation_status)}
                  </p>
                </div>
                <span className="whitespace-nowrap text-sm font-medium text-stone-700 dark:text-stone-300">
                  {formatUsd(idea.value_gap)}
                </span>
                <span className="whitespace-nowrap text-sm text-stone-500 dark:text-stone-400">
                  {formatUsd(idea.estimated_cost)}
                </span>
                <span className="whitespace-nowrap text-sm font-semibold text-amber-700 dark:text-amber-400">
                  {roi.toFixed(1)}x
                </span>
                <Link
                  href={`/ideas/${encodeURIComponent(idea.id)}`}
                  className="shrink-0 rounded-lg bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100 dark:bg-amber-900/30 dark:text-amber-300 dark:hover:bg-amber-900/50"
                >
                  Stake
                </Link>
              </div>
            );
          })}
        </div>
      )}

      <footer className="mt-12 text-center text-sm text-stone-400 dark:text-stone-500">
        <p>
          Staking directs compute and attention toward an idea. The Stake button links to the idea detail page for now.
        </p>
        <div className="mt-4 flex justify-center gap-4">
          <Link href="/ideas" className="hover:text-amber-500">
            All ideas
          </Link>
          <Link href="/contribute" className="hover:text-amber-500">
            Contribute
          </Link>
          <Link href="/resonance" className="hover:text-amber-500">
            Resonance
          </Link>
        </div>
      </footer>
    </main>
  );
}
