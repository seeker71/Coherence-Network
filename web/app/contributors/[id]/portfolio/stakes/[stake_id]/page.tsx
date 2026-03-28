"use client";

import { useParams } from "next/navigation";
import Link from "next/link";

export default function StakeDrilldownPage() {
  const params = useParams<{ id: string; stake_id: string }>();
  const { id } = params ?? {};
  const back = `/contributors/${id}/portfolio`;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <Link href={back} className="text-sm text-muted-foreground hover:text-foreground transition-colors">← Portfolio</Link>
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-2">
        <p className="text-sm text-muted-foreground">Stake detail</p>
        <h1 className="text-2xl font-light">Stake position</h1>
        <p className="text-sm text-muted-foreground">
          Stake detail view coming soon. Track ROI, idea activity since staking, and value lineage.
        </p>
      </section>
    </main>
  );
}
