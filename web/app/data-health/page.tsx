import Link from "next/link";
import { DataHealthDashboard } from "@/components/data-health/DataHealthDashboard";

export const metadata = {
  title: "Data health — Coherence Network",
  description: "Relational store row counts, growth, and hygiene signals",
};

export default function DataHealthPage() {
  return (
    <main className="mx-auto min-h-screen max-w-5xl p-8">
      <div className="mb-6 flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/friction" className="text-muted-foreground hover:text-foreground">
          Friction
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
      </div>
      <h1 className="mb-2 text-3xl font-bold tracking-tight">Data health</h1>
      <p className="mb-8 max-w-2xl text-muted-foreground">
        Live view of table cardinality and growth versus stored snapshots. Threshold breaches surface as friction events with{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">data_growth_anomaly</code>.
      </p>
      <DataHealthDashboard />
    </main>
  );
}
