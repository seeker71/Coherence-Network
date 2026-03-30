"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface LineageLinkBrief {
  id: string;
  idea_id: string;
  spec_id: string;
  estimated_cost: number;
}

interface ContributionLineageView {
  contributor_id: string;
  contribution_id: string;
  idea_id: string;
  contribution_type: string;
  cc_attributed: number;
  lineage_chain_id: string | null;
  value_lineage_link: LineageLinkBrief | null;
  lineage_resolution_note: string | null;
}

export default function ContributionLineagePage() {
  const params = useParams<{ id: string; contribution_id: string }>();
  const { id, contribution_id } = params ?? {};
  const [data, setData] = useState<ContributionLineageView | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id || !contribution_id) return;
    setStatus("loading");
    try {
      const res = await fetch(
        `${API}/api/contributors/${encodeURIComponent(id)}/contributions/${encodeURIComponent(contribution_id)}/lineage`,
      );
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error((j as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      setData(await res.json());
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [id, contribution_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const backIdea = id && data?.idea_id
    ? `/contributors/${encodeURIComponent(id)}/portfolio/ideas/${encodeURIComponent(data.idea_id)}`
    : id
      ? `/contributors/${encodeURIComponent(id)}/portfolio`
      : "/my-portfolio";

  if (status === "loading") {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-3xl mx-auto">
        <p className="text-muted-foreground">Loading contribution audit…</p>
      </main>
    );
  }

  if (status === "error" || !data) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-3xl mx-auto space-y-4">
        <Link href={backIdea} className="text-sm text-primary underline">
          ← Back
        </Link>
        <p className="text-destructive">{error}</p>
      </main>
    );
  }

  const link = data.value_lineage_link;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link href={backIdea} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
          ← Idea contributions
        </Link>
      </div>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2">
        <p className="text-sm text-muted-foreground">Ledger — contribution audit</p>
        <h1 className="text-2xl font-light tracking-tight">CC &amp; lineage</h1>
        <p className="text-sm text-muted-foreground font-mono break-all">{data.contribution_id}</p>
      </section>

      <section className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-muted-foreground">CC attributed</p>
          <p className="text-2xl font-light text-primary">{data.cc_attributed.toFixed(2)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-muted-foreground">Type</p>
          <p className="text-lg font-light">{data.contribution_type}</p>
        </div>
      </section>

      {data.lineage_chain_id && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2">
          <h2 className="text-lg font-medium">Value lineage chain</h2>
          <p className="text-xs font-mono break-all text-muted-foreground">{data.lineage_chain_id}</p>
          {link && (
            <ul className="text-sm space-y-1 pt-2">
              <li>
                Linked ledger:{" "}
                <a
                  href={`${API}/api/value-lineage/links/${encodeURIComponent(link.id)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline"
                >
                  {link.id}
                </a>{" "}
                (JSON API)
              </li>
              <li>
                idea <span className="font-mono">{link.idea_id}</span> · spec{" "}
                <span className="font-mono">{link.spec_id}</span>
              </li>
              <li>estimated cost (lineage): {link.estimated_cost.toFixed(2)}</li>
            </ul>
          )}
          {data.lineage_resolution_note && (
            <p className="text-xs text-amber-500/90 pt-2">{data.lineage_resolution_note}</p>
          )}
        </section>
      )}

      {!data.lineage_chain_id && (
        <p className="text-sm text-muted-foreground">
          No <code className="text-xs">lineage_chain_id</code> on this contribution yet — garden view only; ledger link
          appears when the graph node is tied to a value-lineage record.
        </p>
      )}
    </main>
  );
}
