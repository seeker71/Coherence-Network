"use client";

// InvestModal — opens from an "Invest" button, fetches the ROI preview for
// an idea, and posts a stake on confirmation. Reuses the i18n hook (useT)
// so all chrome strings live in web/messages/<locale>.json.

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT } from "@/components/MessagesProvider";

const CONTRIBUTOR_KEY = "cc-contributor-id";

type InvestPreview = {
  idea_id: string;
  idea_name: string;
  stage: string;
  coherence_score: number;
  total_cc_staked: number;
  prior_investments_count: number;
  prior_roi_avg: number;
  projections: {
    low_multiplier: number;
    high_multiplier: number;
    basis: string;
  };
  stage_unlock_pct: number;
  pipeline_velocity_days: number[];
};

type Props = {
  ideaId: string;
  ideaName: string;
  open: boolean;
  onClose: () => void;
  onStaked?: (newTotalCc: number) => void;
};

export function InvestModal({ ideaId, ideaName, open, onClose, onStaked }: Props) {
  const t = useT();
  const [preview, setPreview] = useState<InvestPreview | null>(null);
  const [amount, setAmount] = useState<string>("10");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successCc, setSuccessCc] = useState<number | null>(null);

  // Fetch preview on open.
  useEffect(() => {
    if (!open) {
      setPreview(null);
      setError(null);
      setSuccessCc(null);
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/api/ideas/${encodeURIComponent(ideaId)}/invest-preview`,
          { cache: "no-store" },
        );
        if (!res.ok) {
          if (!cancelled) setError(t("investModal.errorPreview"));
          return;
        }
        const data: InvestPreview = await res.json();
        if (!cancelled) setPreview(data);
      } catch {
        if (!cancelled) setError(t("investModal.errorNetwork"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [open, ideaId, t]);

  const numericAmount = Number(amount);
  const validAmount = Number.isFinite(numericAmount) && numericAmount > 0;

  async function handleStake() {
    if (!validAmount) return;
    setSubmitting(true);
    setError(null);
    let contributorId: string | null = null;
    try {
      contributorId = typeof window !== "undefined"
        ? localStorage.getItem(CONTRIBUTOR_KEY)
        : null;
    } catch {
      /* ignore */
    }
    if (!contributorId) {
      setError(t("investModal.errorNoContributor"));
      setSubmitting(false);
      return;
    }
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/ideas/${encodeURIComponent(ideaId)}/stake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contributor_id: contributorId,
          amount_cc: numericAmount,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || t("investModal.errorStake"));
        return;
      }
      const newTotal = (preview?.total_cc_staked ?? 0) + numericAmount;
      setSuccessCc(numericAmount);
      onStaked?.(newTotal);
    } catch {
      setError(t("investModal.errorNetwork"));
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="invest-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl border border-border/30 bg-background p-6 shadow-2xl space-y-4">
        <header className="space-y-1">
          <h2 id="invest-modal-title" className="text-lg font-medium">
            {t("investModal.title", { name: ideaName })}
          </h2>
          {preview && (
            <p className="text-xs text-muted-foreground">
              {t("investModal.stageLabel")}: <span className="font-mono">{preview.stage}</span>
              {" · "}
              {t("investModal.coherence")}: {(preview.coherence_score * 100).toFixed(0)}%
            </p>
          )}
        </header>

        {loading && (
          <p className="text-sm text-muted-foreground">{t("investModal.loading")}</p>
        )}

        {preview && !successCc && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg border border-border/30 bg-muted/20 p-3">
                <p className="text-xs text-muted-foreground/80">
                  {t("investModal.totalStaked")}
                </p>
                <p className="font-medium">{preview.total_cc_staked.toFixed(1)} CC</p>
              </div>
              <div className="rounded-lg border border-border/30 bg-muted/20 p-3">
                <p className="text-xs text-muted-foreground/80">
                  {t("investModal.priorInvestors")}
                </p>
                <p className="font-medium">{preview.prior_investments_count}</p>
              </div>
              <div className="rounded-lg border border-border/30 bg-muted/20 p-3">
                <p className="text-xs text-muted-foreground/80">
                  {t("investModal.projectedReturn")}
                </p>
                <p className="font-medium text-primary">
                  {preview.projections.low_multiplier.toFixed(2)}×
                  {" – "}
                  {preview.projections.high_multiplier.toFixed(2)}×
                </p>
              </div>
              <div className="rounded-lg border border-border/30 bg-muted/20 p-3">
                <p className="text-xs text-muted-foreground/80">
                  {t("investModal.stageUnlock")}
                </p>
                <p className="font-medium">{preview.stage_unlock_pct}%</p>
              </div>
            </div>

            <label className="block text-sm space-y-1">
              <span className="text-muted-foreground">{t("investModal.amountLabel")}</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-base"
                aria-invalid={!validAmount}
              />
              {!validAmount && amount !== "" && (
                <span className="text-xs text-destructive">
                  {t("investModal.amountInvalid")}
                </span>
              )}
            </label>

            {validAmount && (
              <p className="text-xs text-muted-foreground">
                {t("investModal.projectedValue", {
                  low: (numericAmount * preview.projections.low_multiplier).toFixed(1),
                  high: (numericAmount * preview.projections.high_multiplier).toFixed(1),
                })}
              </p>
            )}
          </div>
        )}

        {successCc !== null && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
            {t("investModal.success", { amount: successCc.toFixed(1) })}
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full px-4 py-1.5 text-sm border border-border/40 hover:bg-muted/30"
          >
            {successCc !== null ? t("investModal.close") : t("investModal.cancel")}
          </button>
          {successCc === null && (
            <button
              type="button"
              onClick={handleStake}
              disabled={!validAmount || submitting || !preview}
              className="rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting ? t("investModal.staking") : t("investModal.confirm")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Convenience wrapper: a button + the modal it opens.
export function InvestButton({
  ideaId,
  ideaName,
  className,
  onStaked,
}: {
  ideaId: string;
  ideaName: string;
  className?: string;
  onStaked?: (newTotalCc: number) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={
          className ??
          "rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary hover:bg-primary/20"
        }
        aria-label={t("investModal.openFor", { name: ideaName })}
      >
        {t("investModal.button")}
      </button>
      <InvestModal
        ideaId={ideaId}
        ideaName={ideaName}
        open={open}
        onClose={() => setOpen(false)}
        onStaked={onStaked}
      />
    </>
  );
}
