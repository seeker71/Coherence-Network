"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

const STORAGE_KEY = "coherence_contributor_id";

export function TimeCommitmentForm({ ideaId, ideaName }: { ideaId: string; ideaName: string }) {
  const [contributorId, setContributorId] = useState("");
  const [inputName, setInputName] = useState("");
  const [hours, setHours] = useState("2");
  const [commitment, setCommitment] = useState<"review" | "implement">("review");
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    const s = localStorage.getItem(STORAGE_KEY);
    if (s) {
      setContributorId(s);
      setInputName(s);
    }
  }, []);

  function saveName() {
    const t = inputName.trim();
    if (!t) return;
    localStorage.setItem(STORAGE_KEY, t);
    setContributorId(t);
  }

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setMsg("");
      const h = parseFloat(hours);
      if (Number.isNaN(h) || h <= 0) {
        setMsg("Enter positive hours.");
        setStatus("err");
        return;
      }
      if (!contributorId.trim()) {
        setMsg("Set your contributor name in the field above first.");
        setStatus("err");
        return;
      }
      setStatus("loading");
      try {
        const API = getApiBase();
        const res = await fetch(`${API}/api/investments/time/${encodeURIComponent(ideaId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contributor_id: contributorId.trim(),
            hours: h,
            commitment,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setMsg((body as { detail?: string }).detail || "Request failed");
          setStatus("err");
          return;
        }
        setStatus("ok");
        setMsg(`Recorded ${h}h toward ${commitment} on “${ideaName}”.`);
      } catch {
        setMsg("Network error");
        setStatus("err");
      }
    },
    [contributorId, hours, commitment, ideaId, ideaName],
  );

  if (!contributorId) {
    return (
      <div className="space-y-3 rounded-xl border border-amber-200/50 bg-white/50 p-4 dark:border-amber-800/30 dark:bg-stone-900/30">
        <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-200">Invest time</h4>
        <p className="text-xs text-amber-800/70 dark:text-amber-300/70">
          Enter your contributor name to log hours toward review or implementation.
        </p>
        <div className="flex gap-2">
          <input
            value={inputName}
            onChange={(e) => setInputName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveName()}
            placeholder="Contributor name"
            className="flex-1 rounded-lg border border-border/40 bg-background px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={saveName}
            className="rounded-lg bg-primary/10 px-3 py-2 text-sm text-primary"
          >
            Save
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-xl border border-amber-200/50 bg-white/50 p-4 dark:border-amber-800/30 dark:bg-stone-900/30">
      <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-200">Invest time</h4>
      <p className="text-xs text-amber-800/70 dark:text-amber-300/70">
        Commit hours to review or implement — recorded on the contribution ledger (no CC charge).
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground">Hours</label>
          <input
            type="number"
            min={0.25}
            step="any"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Commitment</label>
          <select
            value={commitment}
            onChange={(e) => setCommitment(e.target.value as "review" | "implement")}
            className="mt-1 w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-sm"
          >
            <option value="review">Review</option>
            <option value="implement">Implement</option>
          </select>
        </div>
      </div>
      <button
        type="submit"
        disabled={status === "loading"}
        className="rounded-lg bg-amber-600/90 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50 dark:bg-amber-700/90"
      >
        {status === "loading" ? "Saving…" : "Record time commitment"}
      </button>
      {msg ? (
        <p
          className={`text-xs ${status === "ok" ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}
        >
          {msg}
        </p>
      ) : null}
    </form>
  );
}
