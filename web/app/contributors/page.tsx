"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";
import { useT, useLocale } from "@/components/MessagesProvider";
import { LedgerNav } from "@/app/_components/LedgerNav";

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

type ContributorTone = {
  ring: string;
  text: string;
  badge: string;
  glyphBg: string;
  stripe: string;
  glowClass: string;
  hoverTint: string;
};

const HUMAN_TONE: ContributorTone = {
  ring: "ring-amber-500/25",
  text: "text-amber-300",
  badge: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  glyphBg: "bg-amber-500/10",
  stripe: "bg-amber-500/60",
  glowClass: "tone-amber",
  hoverTint: "hover:via-amber-500/5",
};

const AGENT_TONE: ContributorTone = {
  ring: "ring-teal-500/25",
  text: "text-teal-300",
  badge: "bg-teal-500/10 text-teal-300 border-teal-500/30",
  glyphBg: "bg-teal-500/10",
  stripe: "bg-teal-500/60",
  glowClass: "tone-teal",
  hoverTint: "hover:via-teal-500/5",
};

const SYSTEM_TONE: ContributorTone = {
  ring: "ring-sky-500/25",
  text: "text-sky-300",
  badge: "bg-sky-500/10 text-sky-300 border-sky-500/30",
  glyphBg: "bg-sky-500/10",
  stripe: "bg-sky-500/60",
  glowClass: "tone-sky",
  hoverTint: "hover:via-sky-500/5",
};

function toneFor(type: string): ContributorTone {
  const t = (type || "").toUpperCase();
  if (t === "AGENT") return AGENT_TONE;
  if (t === "SYSTEM") return SYSTEM_TONE;
  return HUMAN_TONE;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function ContributorsPageContent() {
  const t = useT();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Contributor[]>([]);
  const [flowRows, setFlowRows] = useState<FlowItem[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<"ALL" | "HUMAN" | "AGENT" | "SYSTEM">("ALL");

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

  const counts = useMemo(() => {
    let human = 0;
    let agent = 0;
    let system = 0;
    let claimed = 0;
    for (const r of rows) {
      const t = (r.type || "HUMAN").toUpperCase();
      if (t === "AGENT") agent += 1;
      else if (t === "SYSTEM") system += 1;
      else human += 1;
      if (r.claimed !== false) claimed += 1;
    }
    return { total: rows.length, human, agent, system, claimed };
  }, [rows]);

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

  const filteredRows = useMemo(() => {
    let r = rows;
    if (typeFilter !== "ALL") {
      r = r.filter((row) => (row.type || "HUMAN").toUpperCase() === typeFilter);
    }
    if (selectedContributorId) {
      r = r.filter((row) => row.id === selectedContributorId);
    }
    // Signal over noise: claimed humans with relations first, unclaimed last.
    const tierOf = (row: Contributor): number => {
      if (row.claimed === false) return 4;
      const type = (row.type || "HUMAN").toUpperCase();
      if (type === "SYSTEM") return 3;
      if (type === "AGENT") return 2;
      const rel = relationsByContributor.get(row.id);
      const hasRelations = !!rel && (
        rel.ideaIds.length > 0 ||
        rel.specIds.length > 0 ||
        rel.processIdeaIds.length > 0 ||
        rel.implementationRefs.length > 0
      );
      return hasRelations ? 0 : 1;
    };
    const tsOf = (row: Contributor): number => {
      const t = row.created_at ? Date.parse(row.created_at) : NaN;
      return Number.isFinite(t) ? t : 0;
    };
    const sorted = [...r].sort((a, b) => {
      const ta = tierOf(a);
      const tb = tierOf(b);
      if (ta !== tb) return ta - tb;
      return tsOf(b) - tsOf(a);
    });
    return sorted;
  }, [rows, typeFilter, selectedContributorId, relationsByContributor]);

  return (
    <main className="bg-stone-950 min-h-screen">
      {/* Hero — the network of cells finding each other */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[40vh] min-h-[300px] max-h-[440px]">
          <div className="absolute inset-0 hero-breath">
            <Image
              src="/visuals/11-the-network.png"
              alt={t("contributors.heroAlt")}
              fill
              priority
              className="object-cover"
              sizes="100vw"
            />
          </div>
          <div
            className="absolute inset-0 hero-pulse pointer-events-none"
            style={{
              background:
                "radial-gradient(ellipse at center, hsl(38 92% 50% / 0.15) 0%, transparent 70%)",
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/40 via-stone-950/55 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-5xl px-4 sm:px-6 pb-8 sm:pb-12 hero-reveal">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                {t("contributors.eyebrow")}
              </p>
              <h1 className="mt-2 text-3xl sm:text-5xl font-light tracking-tight text-stone-50">
                <span className="sr-only">Contributors</span>
                {t("contributors.title")}
              </h1>
              <p className="mt-3 max-w-2xl text-base sm:text-lg text-stone-200/95 leading-relaxed">
                {t("contributors.lede")}
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-10 space-y-6 sm:space-y-8">
        <LedgerNav />

        {/* Stat tiles — the body's count of itself */}
        <section className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          <button
            type="button"
            onClick={() => setTypeFilter("ALL")}
            className={[
              "text-left rounded-2xl border bg-gradient-to-b p-4 transition-all duration-300",
              typeFilter === "ALL"
                ? "border-amber-400/40 from-amber-500/10 to-amber-500/5"
                : "border-border/30 from-card/60 to-card/30 hover:border-amber-400/30",
            ].join(" ")}
          >
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("contributors.statAll")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{counts.total}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributors.statAllHint")}</p>
          </button>
          <button
            type="button"
            onClick={() => setTypeFilter(typeFilter === "HUMAN" ? "ALL" : "HUMAN")}
            className={[
              "text-left rounded-2xl border bg-gradient-to-b p-4 transition-all duration-300",
              typeFilter === "HUMAN"
                ? "border-amber-400/40 from-amber-500/10 to-amber-500/5"
                : "border-border/30 from-card/60 to-card/30 hover:border-amber-400/30",
            ].join(" ")}
          >
            <p className="text-[10px] uppercase tracking-[0.18em] text-amber-400/80">{t("contributors.typeHuman")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{counts.human}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributors.statHumanHint")}</p>
          </button>
          <button
            type="button"
            onClick={() => setTypeFilter(typeFilter === "AGENT" ? "ALL" : "AGENT")}
            className={[
              "text-left rounded-2xl border bg-gradient-to-b p-4 transition-all duration-300",
              typeFilter === "AGENT"
                ? "border-teal-400/40 from-teal-500/10 to-teal-500/5"
                : "border-border/30 from-card/60 to-card/30 hover:border-teal-400/30",
            ].join(" ")}
          >
            <p className="text-[10px] uppercase tracking-[0.18em] text-teal-400/80">{t("contributors.typeAgent")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{counts.agent}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributors.statAgentHint")}</p>
          </button>
          <button
            type="button"
            onClick={() => setTypeFilter(typeFilter === "SYSTEM" ? "ALL" : "SYSTEM")}
            className={[
              "text-left rounded-2xl border bg-gradient-to-b p-4 transition-all duration-300",
              typeFilter === "SYSTEM"
                ? "border-sky-400/40 from-sky-500/10 to-sky-500/5"
                : "border-border/30 from-card/60 to-card/30 hover:border-sky-400/30",
            ].join(" ")}
          >
            <p className="text-[10px] uppercase tracking-[0.18em] text-sky-400/80">{t("contributors.typeSystem")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{counts.system}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributors.statSystemHint")}</p>
          </button>
        </section>

        {/* Filter status */}
        {(selectedContributorId || typeFilter !== "ALL") && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-stone-400">{t("contributors.filterShowing")}</span>
            {typeFilter !== "ALL" && (
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-amber-300">
                {typeFilter === "HUMAN" ? t("contributors.typeHuman") : typeFilter === "AGENT" ? t("contributors.typeAgent") : t("contributors.typeSystem")}
              </span>
            )}
            {selectedContributorId && (
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-amber-300">
                {t("contributors.filterOneCell")}
              </span>
            )}
            <Link
              href="/contributors"
              onClick={() => setTypeFilter("ALL")}
              className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
            >
              {t("contributors.filterClear")}
            </Link>
          </div>
        )}

        <div className="space-y-4">
          {status === "loading" && (
            <p className="text-stone-400 text-sm">{t("common.loading")}</p>
          )}
          {status === "error" && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-300">
              {t("contributors.errorPrefix")} {error}
            </div>
          )}

          {status === "ok" && (
            <>
              <p className="text-sm text-stone-400">
                {filteredRows.length === rows.length
                  ? filteredRows.length === 1
                    ? t("contributors.countOneCell")
                    : t("contributors.countManyCells", { n: filteredRows.length })
                  : t("contributors.countOfTotal", { n: filteredRows.length, total: rows.length })}
              </p>

              <ul className="grid gap-3 sm:grid-cols-2">
                {filteredRows.slice(0, 100).map((c) => {
                  const tone = toneFor(c.type);
                  const rel = relationsByContributor.get(c.id);
                  const hasRelations = rel && (
                    rel.ideaIds.length > 0 ||
                    rel.specIds.length > 0 ||
                    rel.processIdeaIds.length > 0 ||
                    rel.implementationRefs.length > 0
                  );
                  const isUnclaimed = c.claimed === false;
                  return (
                    <li
                      key={c.id}
                      className={[
                        "group relative overflow-hidden tone-card rounded-2xl border bg-gradient-to-br p-4 sm:p-5 pl-5 sm:pl-6",
                        isUnclaimed
                          ? "tone-stone border-border/15 from-card/30 to-card/10"
                          : `${tone.glowClass} border-border/30 from-card/60 to-card/30 hover:border-amber-400/30 hover:from-card/80 ${tone.hoverTint} hover:to-card/40`,
                      ].join(" ")}
                    >
                      <span
                        aria-hidden="true"
                        className={[
                          "absolute left-0 top-0 bottom-0 w-[3px]",
                          isUnclaimed ? "bg-stone-700/40" : tone.stripe,
                        ].join(" ")}
                      />
                      <div className="flex items-start gap-3 sm:gap-4">
                        <div
                          className={[
                            "flex-shrink-0 inline-flex items-center justify-center w-12 h-12 rounded-xl font-light text-lg ring-1",
                            tone.glyphBg,
                            tone.text,
                            tone.ring,
                          ].join(" ")}
                          aria-hidden="true"
                        >
                          {initials(c.name)}
                        </div>
                        <div className="flex-1 min-w-0 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Link
                              href={`/contributors/${encodeURIComponent(c.id)}/portfolio`}
                              className="font-medium text-stone-100 hover:text-amber-200 transition-colors truncate"
                            >
                              {c.name}
                            </Link>
                            <span
                              className={[
                                "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] font-medium",
                                tone.badge,
                              ].join(" ")}
                            >
                              {(c.type || "").toUpperCase() === "SYSTEM"
                                ? t("contributors.typeSystem")
                                : (c.type || "").toUpperCase() === "AGENT"
                                ? t("contributors.typeAgent")
                                : t("contributors.typeHuman")}
                            </span>
                            {isUnclaimed && (
                              <span
                                className="inline-flex items-center rounded-full border border-stone-600/40 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-stone-400 italic"
                                title={t("contributors.heldOpenTitle")}
                              >
                                {t("contributors.heldOpen")}
                              </span>
                            )}
                          </div>

                          {c.created_at && (
                            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-400">
                              <span>{t("contributors.joined", { date: formatDate(c.created_at, locale) })}</span>
                            </div>
                          )}

                          {hasRelations && (
                            <div className="flex flex-wrap gap-1.5">
                              {rel!.ideaIds.length > 0 && (
                                <Link
                                  href={`/ideas/${encodeURIComponent(rel!.ideaIds[0])}`}
                                  className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-[11px] text-stone-300 hover:text-amber-200 hover:border-amber-400/30 transition-colors"
                                >
                                  {t(rel!.ideaIds.length === 1 ? "contributors.ideaOne" : "contributors.ideaMany", { n: rel!.ideaIds.length })}
                                </Link>
                              )}
                              {rel!.specIds.length > 0 && (
                                <Link
                                  href={`/specs/${encodeURIComponent(rel!.specIds[0])}`}
                                  className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-[11px] text-stone-300 hover:text-amber-200 hover:border-amber-400/30 transition-colors"
                                >
                                  {t(rel!.specIds.length === 1 ? "contributors.specOne" : "contributors.specMany", { n: rel!.specIds.length })}
                                </Link>
                              )}
                              {rel!.processIdeaIds.length > 0 && (
                                <Link
                                  href={`/flow?idea_id=${encodeURIComponent(rel!.processIdeaIds[0])}`}
                                  className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-[11px] text-stone-300 hover:text-amber-200 hover:border-amber-400/30 transition-colors"
                                >
                                  {t("contributors.inProcess", { n: rel!.processIdeaIds.length })}
                                </Link>
                              )}
                            </div>
                          )}

                          <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs">
                            <Link
                              href={`/contributions?contributor_id=${encodeURIComponent(c.id)}`}
                              className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
                            >
                              {t("contributors.viewContributions")}
                            </Link>
                            <Link
                              href={`/contributors/${encodeURIComponent(c.id)}/portfolio`}
                              className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
                            >
                              {t("contributors.linkPortfolio")}
                            </Link>
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>

              {filteredRows.length === 0 && (
                <div className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
                  <p className="text-stone-300">{t("contributors.emptyTitle")}</p>
                  <p className="text-sm text-stone-500">
                    {t("contributors.emptyBodyBefore")}
                    <Link href="/contribute" className="text-amber-400 hover:text-amber-300 underline">
                      {t("contributors.console")}
                    </Link>
                    {t("contributors.emptyBodyAfter")}
                  </p>
                </div>
              )}

              {/* Invitation footer — register hint */}
              <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/5 via-amber-500/10 to-transparent p-5 sm:p-6">
                <p className="text-sm text-stone-300">
                  {t("contributors.registerHintBefore")}
                  <Link href="/contribute" className="text-amber-300 underline-offset-4 hover:underline font-medium">
                    {t("contributors.console")}
                  </Link>
                  {t("contributors.registerHintAfter")}
                </p>
              </section>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function LoadingFallback() {
  const t = useT();
  return (
    <main className="min-h-screen bg-stone-950">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-10">
        <p className="text-stone-400">{t("contributors.loading")}</p>
      </div>
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
