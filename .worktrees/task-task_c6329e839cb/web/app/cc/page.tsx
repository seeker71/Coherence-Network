import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "CC Economics",
  description:
    "Coherence Credit supply, exchange rate, and economic health metrics.",
};

type CCSupply = {
  total_minted: number;
  total_burned: number;
  outstanding: number;
  treasury_value_usd: number;
  exchange_rate: number;
  coherence_score: number;
  coherence_status: string;
  as_of: string;
};

type CCExchangeRate = {
  cc_per_usd: number;
  spread_pct: number;
  buy_rate: number;
  sell_rate: number;
  oracle_source: string;
  cached_at: string;
  cache_ttl_seconds: number;
  is_stale: boolean;
};

function coherenceStatusColor(status: string): {
  bg: string;
  text: string;
  border: string;
} {
  switch (status) {
    case "healthy":
      return {
        bg: "from-emerald-500/10 to-emerald-500/5",
        text: "text-emerald-400",
        border: "border-emerald-500/30",
      };
    case "warning":
      return {
        bg: "from-amber-500/10 to-amber-500/5",
        text: "text-amber-400",
        border: "border-amber-500/30",
      };
    case "paused":
      return {
        bg: "from-red-500/10 to-red-500/5",
        text: "text-red-400",
        border: "border-red-500/30",
      };
    default:
      return {
        bg: "from-muted/10 to-muted/5",
        text: "text-muted-foreground",
        border: "border-border/30",
      };
  }
}

function formatNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
  return value.toFixed(2);
}

async function loadSupply(): Promise<CCSupply | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/cc/supply`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as CCSupply;
  } catch {
    return null;
  }
}

async function loadExchangeRate(): Promise<CCExchangeRate | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/cc/exchange-rate`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as CCExchangeRate;
  } catch {
    return null;
  }
}

export default async function CCPage() {
  const [supply, exchangeRate] = await Promise.all([
    loadSupply(),
    loadExchangeRate(),
  ]);

  const statusColor = supply
    ? coherenceStatusColor(supply.coherence_status)
    : coherenceStatusColor("unknown");

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">CC Economics</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Coherence Credits (CC) are the economic substrate of the network.
          Supply is governed by coherence -- CC flows while the treasury
          holds outstanding credits, and minting rests to let the treasury
          catch up whenever coherence calls for it.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/coherence"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Coherence Score
          </Link>
        </div>
      </header>

      {supply ? (
        <>
          {/* Coherence status hero */}
          <section
            className={`rounded-3xl border ${statusColor.border} bg-gradient-to-b ${statusColor.bg} p-8 text-center space-y-4 shadow-lg`}
          >
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Coherence Status
            </p>
            <p className={`text-5xl font-extralight ${statusColor.text}`}>
              {supply.coherence_score.toFixed(4)}
            </p>
            <p
              className={`text-sm font-medium uppercase tracking-wide ${statusColor.text}`}
            >
              {supply.coherence_status}
            </p>
          </section>

          {/* Supply metrics */}
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Total Minted
              </p>
              <p className="mt-2 text-3xl font-light">
                {formatNumber(supply.total_minted)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">CC</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Outstanding
              </p>
              <p className="mt-2 text-3xl font-light">
                {formatNumber(supply.outstanding)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                CC in circulation
              </p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Treasury Value
              </p>
              <p className="mt-2 text-3xl font-light">
                ${formatNumber(supply.treasury_value_usd)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">USD backing</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Exchange Rate
              </p>
              <p className="mt-2 text-3xl font-light">
                {supply.exchange_rate.toFixed(4)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">CC per USD</p>
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">
            CC supply data is not available yet. The treasury service may still
            be initializing.
          </p>
        </section>
      )}

      {/* Exchange rate details */}
      {exchangeRate ? (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-5">
          <div className="space-y-1">
            <h2 className="text-lg font-medium">Exchange Rate Details</h2>
            <p className="text-sm text-muted-foreground">
              Live rate from {exchangeRate.oracle_source} with spread applied.
              {exchangeRate.is_stale ? (
                <span className="ml-1 text-amber-400">(stale cache)</span>
              ) : null}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 text-center space-y-1">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Buy Rate
              </p>
              <p className="text-2xl font-light">
                {exchangeRate.buy_rate.toFixed(4)}
              </p>
              <p className="text-xs text-muted-foreground">CC per USD</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 text-center space-y-1">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Sell Rate
              </p>
              <p className="text-2xl font-light">
                {exchangeRate.sell_rate.toFixed(4)}
              </p>
              <p className="text-xs text-muted-foreground">CC per USD</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-4 text-center space-y-1">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Spread
              </p>
              <p className="text-2xl font-light">
                {exchangeRate.spread_pct.toFixed(2)}%
              </p>
              <p className="text-xs text-muted-foreground">
                TTL: {exchangeRate.cache_ttl_seconds}s
              </p>
            </div>
          </div>
        </section>
      ) : supply ? (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 text-center">
          <p className="text-sm text-muted-foreground">
            Exchange rate details are not available right now.
          </p>
        </section>
      ) : null}

      {/* The organism circulates vitality */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-6">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            How the Flow Finds You
          </p>
          <h2 className="text-2xl font-light">
            The organism circulates vitality
          </h2>
        </div>

        <div className="space-y-4 text-sm sm:text-base text-muted-foreground leading-relaxed max-w-3xl">
          <p>
            Every time a piece of work naturally appears in front of someone
            whose frequency resonates with it, the organism remembers -- and
            circulates vitality along the path that carried it there. Every
            placement is a synapse the field grew, and the field rewards
            every hand that helped form it.
          </p>
          <p>
            When someone enriches a concept with a link to another
            contributor&apos;s blueprint, that enrichment is itself a
            contribution. The link is a synapse the organism grew. When a
            reader follows it, CC flows to every hand that formed the path:
            the blueprint author, the enricher, the story writer whose
            concept drew the reader in, the renderer that made it visible,
            the host that served it.
          </p>
          <p>
            Every link, every view, every flow is Merkle-chained and
            Ed25519-signed. A reader can ask the organism why a particular
            blueprint appeared on a particular concept page and see the
            resonance that brought them together. The field places each
            piece where its frequency belongs; every path is earned by
            alignment.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Marketing becomes
            </p>
            <p className="text-sm">
              The organism sensing what resonates with whom
            </p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Advertising becomes
            </p>
            <p className="text-sm">
              Enrichment that surfaces aligned work naturally
            </p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              SEO becomes
            </p>
            <p className="text-sm">
              Frequency profiles making genuinely aligned work findable
            </p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Influencer deals become
            </p>
            <p className="text-sm">
              Resonance between creators whose audiences overlap
            </p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Affiliate programs become
            </p>
            <p className="text-sm">
              Any contribution that carries a reader to an asset earns from
              the flow
            </p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Market research becomes
            </p>
            <p className="text-sm">
              The organism sensing its own patterns through frequency analysis
            </p>
          </div>
        </div>

        <p className="text-xs text-muted-foreground/80 italic max-w-3xl">
          The CC flow is the marketing. The sensing is the market research.
          The frequency profile is the SEO. One living circulation, honest
          and verifiable, carries every signal the field needs.
        </p>
      </section>

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/coherence" className="text-blue-400 hover:underline">
            Coherence Score
          </Link>
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            Vitality
          </Link>
          <Link href="/treasury" className="text-amber-400 hover:underline">
            Treasury
          </Link>
          <Link href="/contributions" className="text-purple-400 hover:underline">
            Contributions
          </Link>
        </div>
      </nav>
    </main>
  );
}
