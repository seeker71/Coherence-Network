"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Contribution = {
  id: string;
  contributor_id: string;
  asset_id: string;
  cost_amount: string;
  coherence_score: number;
  timestamp: string;
};

export default function ContributionsPage() {
  const [rows, setRows] = useState<Contribution[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setStatus("loading");
      setError(null);
      try {
        const res = await fetch(`${API_URL}/v1/contributions`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(json));
        setRows(Array.isArray(json) ? json : []);
        setStatus("ok");
      } catch (e) {
        setStatus("error");
        setError(String(e));
      }
    })();
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex gap-3">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Contributions</h1>
      <p className="text-muted-foreground">Human interface for `GET /v1/contributions`.</p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">Total: {rows.length}</p>
          <ul className="space-y-2 text-sm">
            {rows.slice(0, 100).map((c) => (
              <li key={c.id} className="rounded border p-2 space-y-1">
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{c.id}</span>
                  <span className="text-muted-foreground">{c.timestamp}</span>
                </div>
                <div className="text-muted-foreground">
                  contributor {c.contributor_id} | asset {c.asset_id} | cost {c.cost_amount} | coherence {c.coherence_score}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
