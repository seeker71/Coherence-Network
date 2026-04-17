"use client";

/**
 * ProposalOrigin — the idea's birth certificate.
 *
 * When an idea was lifted from a resonant proposal, this component
 * shows a small origin line on the idea's surface: the proposal title,
 * its author, the tally that lifted it, and a link back to the
 * proposal. Rendering nothing when the idea was authored directly —
 * graceful absence.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";

interface Props {
  ideaId: string;
}

interface Origin {
  id: string;
  title: string;
  author_name: string;
  resolved_at: string | null;
  tally: {
    counts: { support: number; amplify: number; decline: number };
    weighted: { yes: number; no: number };
    status: string;
  };
}

export function ProposalOrigin({ ideaId }: Props) {
  const t = useT();
  const locale = useLocale();
  const [origin, setOrigin] = useState<Origin | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(
          `${getApiBase()}/api/proposals/by-idea/${encodeURIComponent(ideaId)}`,
          { cache: "no-store" },
        );
        if (!cancelled) {
          if (res.ok) {
            setOrigin(await res.json());
          } else {
            setOrigin(null);
          }
        }
      } catch {
        if (!cancelled) setOrigin(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ideaId]);

  if (loading || !origin) return null;

  const yes = origin.tally.counts.support + origin.tally.counts.amplify;
  const no = origin.tally.counts.decline;
  const resolvedLabel = origin.resolved_at
    ? new Date(origin.resolved_at).toLocaleDateString(locale)
    : "";

  return (
    <section className="rounded-md border border-emerald-700/30 bg-emerald-950/10 px-4 py-3 text-sm">
      <div className="flex items-start gap-3">
        <div className="text-xl leading-none shrink-0">🌱</div>
        <div className="flex-1 min-w-0">
          <p className="text-emerald-200/90 font-medium">
            {t("proposalOrigin.lede")}
          </p>
          <p className="text-stone-300 mt-1">
            <Link
              href={`/meet/proposal/${encodeURIComponent(origin.id)}`}
              className="text-amber-300 hover:text-amber-200 underline underline-offset-2"
            >
              “{origin.title}”
            </Link>
            {" — "}
            <span className="text-stone-400">{origin.author_name}</span>
          </p>
          <p className="text-xs text-stone-500 mt-2">
            {resolvedLabel && <span>{resolvedLabel} · </span>}
            <span>
              {yes} ↑ · {no} ↓
            </span>
            {origin.tally.counts.amplify > 0 && (
              <span> · 🔥 {origin.tally.counts.amplify}</span>
            )}
          </p>
        </div>
      </div>
    </section>
  );
}
