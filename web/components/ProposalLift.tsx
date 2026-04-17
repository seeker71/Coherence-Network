"use client";

/**
 * ProposalLift — the collective's gesture that raises a resonant proposal
 * into a kinetic idea.
 *
 * Fetches the tally. If the status is `resonant` and the proposal hasn't
 * been resolved yet, renders a gentle call-to-action that any viewer can
 * tap to lift the proposal into an idea. After lifting, renders the new
 * idea link. No gate — the voices already spoke; this is just the
 * ceremony.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT } from "@/components/MessagesProvider";

interface Props {
  proposalId: string;
}

interface Tally {
  status: "quiet" | "warming" | "balanced" | "cooling" | "resonant";
  counts: { support: number; amplify: number; decline: number; expression: number };
  weighted: { yes: number; no: number };
}

interface Proposal {
  id: string;
  title: string;
  resolved_as_idea_id: string | null;
}

export function ProposalLift({ proposalId }: Props) {
  const t = useT();
  const [tally, setTally] = useState<Tally | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [lifting, setLifting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const base = getApiBase();
      const [tallyRes, propRes] = await Promise.all([
        fetch(`${base}/api/proposals/${proposalId}/tally`),
        fetch(`${base}/api/proposals/${proposalId}`),
      ]);
      if (tallyRes.ok) setTally(await tallyRes.json());
      if (propRes.ok) setProposal(await propRes.json());
    } catch {
      /* transient */
    }
  }, [proposalId]);

  useEffect(() => {
    load();
  }, [load]);

  async function lift() {
    setLifting(true);
    setError(null);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/proposals/${proposalId}/resolve`, {
        method: "POST",
      });
      if (!res.ok) {
        const p = await res.json().catch(() => ({}));
        setError(p?.detail || "unable to lift proposal");
        return;
      }
      await load();
    } finally {
      setLifting(false);
    }
  }

  if (!tally || !proposal) return null;

  if (proposal.resolved_as_idea_id) {
    return (
      <div className="rounded-md border border-emerald-700/40 bg-emerald-950/20 p-4 text-sm text-emerald-200 flex items-center gap-3 flex-wrap">
        <span>🌱 {t("proposal.lifted")}</span>
        <Link
          href={`/ideas/${encodeURIComponent(proposal.resolved_as_idea_id)}`}
          className="rounded-md bg-emerald-700/80 hover:bg-emerald-600/90 text-stone-950 px-3 py-1 font-medium"
        >
          {t("proposal.viewIdea")} →
        </Link>
      </div>
    );
  }

  if (tally.status === "resonant") {
    return (
      <div className="rounded-md border border-amber-700/40 bg-amber-950/20 p-4 text-sm text-amber-100 space-y-2">
        <p>{t("proposal.readyToLift")}</p>
        <button
          type="button"
          onClick={lift}
          disabled={lifting}
          className="rounded-md bg-amber-700/80 hover:bg-amber-600/90 disabled:bg-stone-800 disabled:text-stone-600 text-stone-950 px-4 py-2 font-medium"
        >
          {lifting ? t("proposal.lifting") : t("proposal.lift")}
        </button>
        {error && <p className="text-rose-300 text-xs">{error}</p>}
      </div>
    );
  }

  // Quiet/warming/balanced/cooling — just show the current status gently
  const label: Record<Tally["status"], string> = {
    quiet: t("proposal.statusQuiet"),
    warming: t("proposal.statusWarming"),
    balanced: t("proposal.statusBalanced"),
    cooling: t("proposal.statusCooling"),
    resonant: t("proposal.statusResonant"),
  };

  return (
    <div className="rounded-md border border-stone-800/60 bg-stone-900/40 p-3 text-xs text-stone-400">
      {label[tally.status]} · {tally.weighted.yes} ↑ · {tally.weighted.no} ↓
    </div>
  );
}
