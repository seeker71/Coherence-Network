import type { Metadata } from "next";
import Link from "next/link";

import { TreasuryDepositForm } from "./TreasuryDepositForm";

export const metadata: Metadata = {
  title: "Treasury",
  description: "Deposit ETH or BTC, convert to CC, and stake on ideas.",
};

export default function TreasuryPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Treasury
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Deposit ETH or BTC into the Coherence Network treasury. Your crypto
          converts to CC (Coherence Credits) which get staked on the ideas you
          believe in.
        </p>
      </header>

      {/* How it works */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-4">
        <h2 className="text-lg font-semibold">How it works</h2>
        <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground leading-relaxed">
          <li>
            <span className="text-foreground/80">Send ETH or BTC</span> to the
            treasury wallet address shown below.
          </li>
          <li>
            <span className="text-foreground/80">Record your deposit</span> with
            the blockchain transaction hash so we can verify it.
          </li>
          <li>
            <span className="text-foreground/80">Your CC gets staked</span> on
            ideas you believe in &mdash; directing real compute toward them.
          </li>
          <li>
            <span className="text-foreground/80">When ideas create value</span>,
            your share flows back through value lineage &mdash; proportional to
            your contribution.
          </li>
        </ol>
        <p className="text-xs text-muted-foreground/80">
          Deposits are recorded on an append-only ledger. The actual crypto
          transfer happens on-chain; this system records the transaction hash for
          verification.
        </p>
      </section>

      <TreasuryDepositForm />

      <footer className="text-center text-sm text-muted-foreground/80 pt-4">
        <Link
          href="/invest"
          className="text-primary hover:text-foreground transition-colors underline underline-offset-4"
        >
          View all ideas &amp; stake directly &rarr;
        </Link>
      </footer>
    </main>
  );
}
