"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ContributionRow = {
  lineage_id: string;
  idea_id: string;
  spec_id: string;
  role: string;
  contributor: string;
  perspective: string;
  estimated_cost: number;
  measured_value_total: number;
  roi_ratio: number;
};

export default function ContributionsPage() {
  const [rows, setRows] = useState<ContributionRow[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/inventory/system-lineage`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(json));
        if (cancelled) return;
        const attrs = json?.contributors?.attributions;
        setRows(Array.isArray(attrs) ? attrs : []);
        setStatus("ok");
      } catch (e) {
        if (cancelled) return;
        setError(String(e));
        setStatus("error");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-4">
      <Link href="/" className="text-muted-foreground hover:text-foreground">
        ← Coherence Network
      </Link>
      <h1 className="text-2xl font-bold">Contributions</h1>
      <p className="text-sm text-muted-foreground">
        Human interface for contribution attribution from `/api/inventory/system-lineage`.
      </p>
      {status === "loading" && <p className="text-muted-foreground">Loading contributions…</p>}
      {status === "error" && <p className="text-destructive">{error}</p>}
      {status === "ok" && (
        <ul className="space-y-2 text-sm">
          {rows.map((row) => (
            <li key={`${row.lineage_id}:${row.role}:${row.contributor}`} className="rounded border p-3">
              <p className="font-medium">
                {row.role}: {row.contributor} ({row.perspective})
              </p>
              <p className="text-muted-foreground">
                idea {row.idea_id} | spec {row.spec_id}
              </p>
              <p className="text-muted-foreground">
                est cost {row.estimated_cost} | measured value {row.measured_value_total} | ROI {row.roi_ratio}
              </p>
            </li>
          ))}
          {rows.length === 0 && <li className="text-muted-foreground">No contributions found.</li>}
        </ul>
      )}
    </main>
  );
}
