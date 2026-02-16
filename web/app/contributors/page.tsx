"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

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
      setRows(Array.isArray(contributorsJson) ? contributorsJson : []);
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
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/contribute" className="text-muted-foreground hover:text-foreground">
          Contribute
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Contributors</h1>
      <p className="text-muted-foreground">
        Human interface for `GET /api/contributors`.
        {selectedContributorId ? (
          <>
            {" "}
            Filtered by contributor <code>{selectedContributorId}</code>.
          </>
        ) : null}
      </p>
      <p className="text-sm text-muted-foreground">
        To register a new contributor and submit idea/spec/question changes, use the{" "}
        <Link href="/contribute" className="underline hover:text-foreground">Contribution Console</Link>.
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">
            Total: {filteredRows.length}
            {selectedContributorId ? (
              <>
                {" "}
                | <Link href="/contributors" className="underline hover:text-foreground">Clear filter</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((c) => (
              <li key={c.id} className="rounded border p-2 flex justify-between gap-3">
                <span className="font-medium">
                  <Link href={`/contributors?contributor_id=${encodeURIComponent(c.id)}`} className="hover:underline">
                    {c.name}
                  </Link>
                </span>
                <span className="text-muted-foreground text-right">
                  {c.type} | {c.email} | {c.created_at}
                  <br />
                  <Link
                    href={`/contributions?contributor_id=${encodeURIComponent(c.id)}`}
                    className="underline hover:text-foreground"
                  >
                    contributions
                  </Link>
                </span>
              </li>
            ))}
          </ul>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((c) => {
              const rel = relationsByContributor.get(c.id);
              return (
                <li key={`${c.id}-relations`} className="rounded border p-2 text-muted-foreground">
                  idea{" "}
                  {rel && rel.ideaIds.length > 0
                    ? rel.ideaIds.slice(0, 6).map((ideaId, idx) => (
                        <span key={`${c.id}-idea-${ideaId}`}>
                          {idx > 0 ? ", " : ""}
                          <Link href={`/ideas/${encodeURIComponent(ideaId)}`} className="underline hover:text-foreground">
                            {ideaId}
                          </Link>
                        </span>
                      ))
                    : (
                      <Link href="/ideas" className="underline hover:text-foreground">
                        missing
                      </Link>
                    )}{" "}
                  | spec{" "}
                  {rel && rel.specIds.length > 0
                    ? rel.specIds.slice(0, 6).map((specId, idx) => (
                        <span key={`${c.id}-spec-${specId}`}>
                          {idx > 0 ? ", " : ""}
                          <Link href={`/specs/${encodeURIComponent(specId)}`} className="underline hover:text-foreground">
                            {specId}
                          </Link>
                        </span>
                      ))
                    : (
                      <Link href="/specs" className="underline hover:text-foreground">
                        missing
                      </Link>
                    )}{" "}
                  | process{" "}
                  {rel && rel.processIdeaIds.length > 0
                    ? rel.processIdeaIds.slice(0, 4).map((ideaId, idx) => (
                        <span key={`${c.id}-process-${ideaId}`}>
                          {idx > 0 ? ", " : ""}
                          <Link href={`/flow?idea_id=${encodeURIComponent(ideaId)}`} className="underline hover:text-foreground">
                            {ideaId}
                          </Link>
                        </span>
                      ))
                    : (
                      <Link href="/flow" className="underline hover:text-foreground">
                        missing
                      </Link>
                    )}{" "}
                  | implementation{" "}
                  {rel && rel.implementationRefs.length > 0
                    ? rel.implementationRefs.slice(0, 3).map((ref, idx) => (
                        <span key={`${c.id}-impl-${ref}`}>
                          {idx > 0 ? ", " : ""}
                          <Link href={`/flow?contributor_id=${encodeURIComponent(c.id)}`} className="underline hover:text-foreground">
                            ref-{idx + 1}
                          </Link>
                        </span>
                      ))
                    : (
                      <Link href="/flow" className="underline hover:text-foreground">
                        missing
                      </Link>
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
    <Suspense fallback={<main className="min-h-screen p-8 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading contributors…</p></main>}>
      <ContributorsPageContent />
    </Suspense>
  );
}
