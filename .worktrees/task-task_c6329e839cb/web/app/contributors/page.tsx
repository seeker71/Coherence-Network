"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";
import { useT, useLocale } from "@/components/MessagesProvider";

const API_URL = getApiBase();

function formatDate(iso: string, locale: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" });
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
  claimed?: boolean;
  canonical_url?: string | null;
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
  const t = useT();
  const locale = useLocale();
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
      // Check res.ok BEFORE .json() — FastAPI returns plain-text on
      // 5xx, which would crash JSON.parse with a cryptic SyntaxError.
      if (!contributorsRes.ok) {
        const body = await contributorsRes.text();
        throw new Error(`contributors HTTP ${contributorsRes.status}: ${body.slice(0, 200)}`);
      }
      if (!flowRes.ok) {
        const body = await flowRes.text();
        throw new Error(`flow HTTP ${flowRes.status}: ${body.slice(0, 200)}`);
      }
      const contributorsJson = await contributorsRes.json();
      const flowJson = (await flowRes.json()) as FlowResponse;
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
        <p className="text-sm text-muted-foreground">{t("contributors.eyebrow")}</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">{t("contributors.title")}</h1>
        <p className="max-w-3xl text-muted-foreground">
          {t("contributors.lede")}
          {selectedContributorId ? (
            <>
              {" "}
              {t("contributors.filteredOne")}
            </>
          ) : null}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("contributors.registerHintBefore")}
          <Link href="/contribute" className="underline hover:text-foreground transition-colors duration-300">{t("contributors.console")}</Link>
          {t("contributors.registerHintAfter")}
        </p>
      </section>

      {status === "loading" && <p className="text-muted-foreground">{t("common.loading")}</p>}
      {status === "error" && <p className="text-destructive">{t("contributors.errorPrefix")}{error}</p>}

      {status === "ok" && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
          <p className="text-sm text-muted-foreground">
            {t("contributors.countLabel", { n: filteredRows.length })}
            {selectedContributorId ? (
              <>
                {" "}
                | <Link href="/contributors" className="underline hover:text-foreground transition-colors duration-300">{t("contributors.clearFilter")}</Link>
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
              <li key={c.id} className={`rounded-xl border p-4 space-y-2 ${
                c.claimed === false
                  ? "border-border/10 bg-background/20 opacity-70"
                  : "border-border/20 bg-background/40"
              }`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link href={`/contributors?contributor_id=${encodeURIComponent(c.id)}`} className="font-medium hover:underline">
                      {c.name}
                    </Link>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      c.type === "SYSTEM" || c.type === "system"
                        ? "bg-blue-500/10 text-blue-500"
                        : "bg-green-500/10 text-green-500"
                    }`}>
                      {c.type === "SYSTEM" || c.type === "system" ? t("contributors.typeSystem") :
                        c.type === "AGENT" || c.type === "agent" ? t("contributors.typeAgent") :
                          t("contributors.typeHuman")}
                    </span>
                    {c.claimed === false && (
                      <span
                        className="inline-flex items-center rounded-full border border-border/40 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-muted-foreground italic"
                        title="Placeholder held open for the real person to claim"
                      >
                        unclaimed
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/contributions?contributor_id=${encodeURIComponent(c.id)}`}
                    className="text-xs underline text-muted-foreground hover:text-foreground"
                  >
                    {t("contributors.viewContributions")}
                  </Link>
                </div>
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                  {c.email && <span>{c.email}</span>}
                  {c.created_at && <span>{t("contributors.joined", { date: formatDate(c.created_at, locale) })}</span>}
                </div>
                {hasRelations && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {rel!.ideaIds.length > 0 && (
                      <Link href={`/ideas/${encodeURIComponent(rel!.ideaIds[0])}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {t(rel!.ideaIds.length === 1 ? "contributors.ideaOne" : "contributors.ideaMany", { n: rel!.ideaIds.length })}
                      </Link>
                    )}
                    {rel!.specIds.length > 0 && (
                      <Link href={`/specs/${encodeURIComponent(rel!.specIds[0])}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {t(rel!.specIds.length === 1 ? "contributors.specOne" : "contributors.specMany", { n: rel!.specIds.length })}
                      </Link>
                    )}
                    {rel!.processIdeaIds.length > 0 && (
                      <Link href={`/flow?idea_id=${encodeURIComponent(rel!.processIdeaIds[0])}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {t("contributors.inProcess", { n: rel!.processIdeaIds.length })}
                      </Link>
                    )}
                    {rel!.implementationRefs.length > 0 && (
                      <Link href={`/flow?contributor_id=${encodeURIComponent(c.id)}`} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                        {t(rel!.implementationRefs.length === 1 ? "contributors.implementationOne" : "contributors.implementationMany", { n: rel!.implementationRefs.length })}
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

function LoadingFallback() {
  const t = useT();
  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto">
      <p className="text-muted-foreground">{t("contributors.loading")}</p>
    </main>
  );
}

export default function ContributorsPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ContributorsPageContent />
    </Suspense>
  );
}
