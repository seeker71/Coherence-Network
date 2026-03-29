"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface ContributionDetail {
  id: string; type: string; date: string | null;
  asset_id: string | null; cc_attributed: number;
  coherence_score: number; lineage_chain_id: string | null;
}
interface ValueLineageSummary {
  lineage_id: string | null; total_value: number;
  roi_ratio: number | null; stage_events: number;
}
interface DrilldownData {
  contributor_id: string; idea_id: string; idea_title: string;
  contributions: ContributionDetail[];
  value_lineage_summary: ValueLineageSummary;
}

export default function IdeaDrilldownPage() {
  const params = useParams<{ id: string; idea_id: string }>();
  const { id, idea_id } = params ?? {};
  const [data, setData] = useState<DrilldownData | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id || !idea_id) return;
    setStatus("loading");
    try {
      const res = await fetch(`${API}/api/contributors/${id}/idea-contributions/${idea_id}`);
      if (!res.ok) {
        const j = await res.json();
        throw new Error(j.detail ?? "Failed to load");
      }
      setData(await res.json());
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [id, idea_id]);

  useEffect(() => { void load(); }, [load]);

  const back = `/contributors/${id}/portfolio`;

  if (status === "loading") return <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading…</p></main>;
  if (status === "error" || !data) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-4">
        <Link href={back} className="text-sm text-primary underline">← Portfolio</Link>
        <p className="text-destructive">{error}</p>
      </main>
    );
  }

  const lineage = data.value_lineage_summary;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link href={back} className="text-sm text-muted-foreground hover:text-foreground transition-colors">← Portfolio</Link>
      </div>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-2">
        <p className="text-sm text-muted-foreground">Idea drill-down</p>
        <h1 className="text-2xl md:text-3xl font-light">{data.idea_title}</h1>
        <p className="text-sm text-muted-foreground">{data.contributions.length} contribution{data.contributions.length !== 1 ? "s" : ""}</p>
      </section>

      {/* Value lineage summary */}
      <section className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-muted-foreground">Total CC attributed</p>
          <p className="text-2xl font-light text-primary">{lineage.total_value.toFixed(2)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-muted-foreground">ROI ratio</p>
          <p className="text-2xl font-light text-primary">{lineage.roi_ratio != null ? `${lineage.roi_ratio.toFixed(2)}×` : "—"}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-muted-foreground">Stage events</p>
          <p className="text-2xl font-light text-primary">{lineage.stage_events}</p>
        </div>
      </section>

      {/* Contributions table */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <h2 className="text-xl font-medium">My Contributions</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b border-border/20">
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">Date</th>
                <th className="pb-2 pr-4">CC attributed</th>
                <th className="pb-2 pr-4">Coherence score</th>
                <th className="pb-2 pr-4">Lineage</th>
                <th className="pb-2">ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/10">
              {data.contributions.map((c) => (
                <tr key={c.id} className="hover:bg-accent/20 transition-colors">
                  <td className="py-3 pr-4">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/30 text-zinc-300">{c.type}</span>
                  </td>
                  <td className="py-3 pr-4 text-muted-foreground">
                    {c.date ? new Date(c.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—"}
                  </td>
                  <td className="py-3 pr-4 font-mono">{c.cc_attributed.toFixed(2)}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 bg-zinc-700/40 rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${c.coherence_score * 100}%` }} />
                      </div>
                      <span className="text-muted-foreground text-xs">{(c.coherence_score * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-xs text-muted-foreground font-mono truncate max-w-[7rem]">
                    {c.lineage_chain_id ?? "—"}
                  </td>
                  <td className="py-3 text-muted-foreground font-mono text-xs truncate max-w-24">
                    {c.id && id ? (
                      <Link
                        href={`/contributors/${encodeURIComponent(id)}/portfolio/contributions/${encodeURIComponent(c.id)}`}
                        className="text-primary hover:underline"
                      >
                        {c.id}
                      </Link>
                    ) : (
                      c.id
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
