"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const STORAGE_KEY = "coherence_contributor_id";

type Preview = {
  roi_cc?: number;
  projected_return_cc?: number;
  projected_value_cc?: number;
  idea_name?: string;
};

export function InvestIdeaButton({
  ideaId,
  ideaName,
}: {
  ideaId: string;
  ideaName: string;
}) {
  const [open, setOpen] = useState(false);
  const [contributorId, setContributorId] = useState("");
  const [amount, setAmount] = useState("10");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [status, setStatus] = useState<"idle" | "submitting" | "done" | "err">("idle");
  const [err, setErr] = useState("");

  useEffect(() => {
    const s = localStorage.getItem(STORAGE_KEY);
    if (s) setContributorId(s);
  }, []);

  const loadPreview = useCallback(async () => {
    const n = parseFloat(amount);
    if (Number.isNaN(n) || n <= 0) {
      setPreview(null);
      return;
    }
    setLoadingPreview(true);
    try {
      const API = getApiBase();
      const res = await fetch(
        `${API}/api/investments/preview?idea_id=${encodeURIComponent(ideaId)}&amount_cc=${encodeURIComponent(String(n))}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setPreview(null);
        return;
      }
      const data: Preview = await res.json();
      setPreview(data);
    } catch {
      setPreview(null);
    } finally {
      setLoadingPreview(false);
    }
  }, [amount, ideaId]);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => void loadPreview(), 300);
    return () => clearTimeout(t);
  }, [open, loadPreview]);

  async function submitStake(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const n = parseFloat(amount);
    if (Number.isNaN(n) || n <= 0) {
      setErr("Enter a positive amount.");
      return;
    }
    if (!contributorId.trim()) {
      setErr("Set your contributor name in the balance section above first.");
      return;
    }
    setStatus("submitting");
    try {
      const API = getApiBase();
      const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}/stake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contributor_id: contributorId.trim(),
          amount_cc: n,
          rationale: `Invest UI — projected ${preview?.projected_return_cc ?? "?"} CC return`,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setErr((body as { detail?: string }).detail || `Failed (${res.status})`);
        setStatus("err");
        return;
      }
      setStatus("done");
    } catch {
      setErr("Network error");
      setStatus("err");
    }
  }

  return (
    <div className="shrink-0 flex flex-col items-end gap-2">
      <button
        type="button"
        onClick={() => {
          setOpen(!open);
          setStatus("idle");
          setErr("");
        }}
        className="rounded-full bg-primary/15 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/25"
      >
        {open ? "Close" : "Invest"}
      </button>
      {open && (
        <form
          onSubmit={submitStake}
          className="w-[min(100vw-2rem,22rem)] rounded-2xl border border-border/40 bg-card/95 p-4 shadow-lg backdrop-blur sm:w-72"
        >
          <p className="text-xs text-muted-foreground mb-2">
            Stake CC on <span className="font-medium text-foreground">{ideaName}</span>
          </p>
          <label className="block text-xs text-muted-foreground mb-1">Amount (CC)</label>
          <input
            type="number"
            min={0.1}
            step="any"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full rounded-lg border border-border/40 bg-background/80 px-3 py-2 text-sm"
          />
          <div className="mt-3 rounded-lg bg-muted/30 px-3 py-2 text-xs space-y-1">
            {loadingPreview ? (
              <p className="text-muted-foreground">Estimating ROI…</p>
            ) : preview ? (
              <>
                <p>
                  ROI (expected ×):{" "}
                  <span className="font-medium text-primary">{(preview.roi_cc ?? 0).toFixed(4)}</span>
                </p>
                <p>
                  Projected return:{" "}
                  <span className="font-medium">{preview.projected_return_cc ?? "—"} CC</span>
                </p>
                <p>
                  Projected value:{" "}
                  <span className="font-medium">{preview.projected_value_cc ?? "—"} CC</span>
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">Enter an amount to preview.</p>
            )}
          </div>
          {err ? <p className="mt-2 text-xs text-destructive">{err}</p> : null}
          {status === "done" ? (
            <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">Staked successfully.</p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={status === "submitting"}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {status === "submitting" ? "…" : "Confirm stake"}
            </button>
            <Link
              href={`/ideas/${encodeURIComponent(ideaId)}`}
              className="text-xs text-muted-foreground hover:text-primary underline self-center"
            >
              Time commitment →
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}
