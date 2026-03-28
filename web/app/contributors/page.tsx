"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

type Contributor = {
  id: string;
  name: string;
  type: string;
  email: string;
  created_at: string;
};

type FlowItem = {
  idea_id: string;
  spec: { spec_ids: string[] };
  implementation: { implementation_refs: string[] };
  contributors: { all: string[]; by_role: Record<string, string[]> };
};

type FlowResponse = {
  items: FlowItem[];
};

type ContributorRelations = {
  ideaIds: string[];
  specIds: string[];
  processIdeaIds: string[];
  implementationRefs: string[];
};

function ContributorsPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Contributor[]>([]);
  const [flowRows, setFlowRows] = useState<FlowItem[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const selectedContributorId = useMemo(
    () => (searchParams.get("contributor_id") || "").trim(),
    [searchParams]
  );

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const [contributorsRes, flowRes] = await Promise.all([
        fetch(`${API_URL}/api/contributors`, { cache: "no-store" }),
        fetch(`${API_URL}/api/inventory/flow?runtime_window_seconds=86400`, { cache: "no-store" }),
      ]);
      const contributorsJson = await contributorsRes.json();
      const flowJson = (await flowRes.json()) as FlowResponse;
      if (!contributorsRes.ok) throw new Error(JSON.stringify(contributorsJson));
      if (!flowRes.ok) throw new Error(JSON.stringify(flowJson));
      const contributorData = contributorsJson?.items ?? (Array.isArray(contributorsJson) ? contributorsJson : []);
      setRows(contributorData);
      setFlowRows(Array.isArray(flowJson?.items) ? flowJson.items : []);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(loadRows);

  const filteredRows = useMemo(() => {
    if (!selectedContributorId) return rows;
    return rows.filter((row) => row.id === selectedContributorId);
  }, [rows, selectedContributorId]);

  const relationsByContributor = useMemo(() => {
    const map = new Map<string, ContributorRelations>();
    for (const item of flowRows) {
      const contributorIds = new Set<string>(item.contributors.all);
      for (const ids of Object.values(item.contributors.by_role)) {
        for (const contributorId of ids) contributorIds.add(contributorId);
      }
      for (const contributorId of contributorIds) {
        if (!map.has(contributorId)) {
          map.set(contributorId, {
            ideaIds: [],
            specIds: [],
            processIdeaIds: [],
            implementationRefs: [],
          });
        }
        const rel = map.get(contributorId);
        if (!rel) continue;
        rel.ideaIds.push(item.idea_id);
        rel.processIdeaIds.push(item.idea_id);
        rel.specIds.push(...item.spec.spec_ids);
        rel.implementationRefs.push(...item.implementation.implementation_refs);
      }
    }
    for (const rel of map.values()) {
      rel.ideaIds = [...new Set(rel.ideaIds)].sort();
      rel.specIds = [...new Set(rel.specIds)].sort();
      rel.processIdeaIds = [...new Set(rel.processIdeaIds)].sort();
      rel.implementationRefs = [...new Set(rel.implementationRefs)].sort();
    }
    return map;
  }, [flowRows]);

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Contributors</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">Contributors</h1>
        <p className="max-w-3xl text-muted-foreground">
          People and agents contributing to the network.
          {selectedContributorId ? (
            <>
              {" "}
              Showing results for one contributor.
            </>
          ) : null}
        </p>
        <p className="text-sm text-muted-foreground">
          To register a new contributor and submit changes, use the{" "}
          <Link href="/contribute" className="underline hover:text-foreground transition-colors duration-300">Contribution Console</Link>.
        </p>
      </section>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
          <p className="text-sm text-muted-foreground">
            {filteredRows.length} contributors
            {selectedContributorId ? (
              <>
                {" "}
                | <Link href="/contributors" className="underline hover:text-foreground transition-colors duration-300">Clear filter</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((c) => {
              const rel = relationsByContributor.get(c.id);
              const hasRelations = rel && (
                rel.ideaIds.length > 0 ||
                rel.specIds.length > 0 ||
                rel.processIdeaIds.length > 0 ||
                rel.implementationRefs.length > 0
              );
              return (
              <li key={c.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Link href={`/contributors?contributor_id=${encodeURIComponent(c.id)}`} className="font-medium hover:underline">
                      {c.name}
                    </Link>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      c.type === "SYSTEM" || c.type === "system"
                        ? "bg-blue-500/10 text-blue-500"
                        : "bg-green-500/10 text-green-500"
                    }`}>
                      {(c.type || "Human").charAt(0).toUpperCase() + (c.type || "Human").slice(1).toLowerCase()}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={`/contributors/${encodeURIComponent(c.id)}/beliefs`}
                      className="text-xs underline text-muted-foreground hover:text-foreground"
                    >
                      Beliefs
                    </Link>
                    <Link
                      href={`/contributions?contributor_id=${encodeURIComponent(c.id)}`}
                      className="text-xs underline text-muted-foreground hover:text-foreground"
                    >
                      View contributions
                    </Link>
                  </div>
                </div>
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                  {c.email && <span>{c.email}</span>}
                  {c.created_at && <span>Joined {formatDate(c.created_at)}</span>}
                </div>
                {hasRelations && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {rel!.ideaIds.length > 0 && (
                      <Link href={`/ideas/${encodeURIComponent(rel!.ideaIds[0])}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {rel!.ideaIds.length} {rel!.ideaIds.length === 1 ? "idea" : "ideas"}
                      </Link>
                    )}
                    {rel!.specIds.length > 0 && (
                      <Link href={`/specs/${encodeURIComponent(rel!.specIds[0])}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {rel!.specIds.length} {rel!.specIds.length === 1 ? "spec" : "specs"}
                      </Link>
                    )}
                    {rel!.processIdeaIds.length > 0 && (
                      <Link href={`/flow?idea_id=${encodeURIComponent(rel!.processIdeaIds[0])}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {rel!.processIdeaIds.length} in process
                      </Link>
                    )}
                    {rel!.implementationRefs.length > 0 && (
                      <Link href={`/flow?contributor_id=${encodeURIComponent(c.id)}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {rel!.implementationRefs.length} {rel!.implementationRefs.length === 1 ? "implementation" : "implementations"}
                      </Link>
                    )}
                  </div>
                )}
              </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}

export default function ContributorsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading contributors…</p></main>}>
      <ContributorsPageContent />
    </Suspense>
  );
}
