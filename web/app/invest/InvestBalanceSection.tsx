"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type LedgerBalance = {
  total: number;
  by_type?: Record<string, number>;
};

type LedgerResponse = {
  balance: LedgerBalance;
};

const STORAGE_KEY = "coherence_contributor_id";

export function InvestBalanceSection() {
  const [contributorId, setContributorId] = useState("");
  const [inputValue, setInputValue] = useState("");
  const [balance, setBalance] = useState<LedgerBalance | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setContributorId(stored);
      setInputValue(stored);
    }
  }, []);

  const loadBalance = useCallback(async (id: string) => {
    if (!id) return;
    setLoading(true);
    try {
      const API = getApiBase();
      const res = await fetch(
        `${API}/api/contributions/ledger/${encodeURIComponent(id)}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setBalance(null);
        return;
      }
      const data: LedgerResponse = await res.json();
      setBalance(data.balance ?? null);
    } catch {
      setBalance(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (contributorId) {
      void loadBalance(contributorId);
    }
  }, [contributorId, loadBalance]);

  function handleSave() {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    localStorage.setItem(STORAGE_KEY, trimmed);
    setContributorId(trimmed);
  }

  if (!contributorId) {
    return (
      <section className="mb-8 rounded-2xl border border-primary/20 bg-primary/5 p-5 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">💧</span>
          <p className="text-sm font-medium text-primary">Your watering can</p>
        </div>
        <p className="text-sm text-muted-foreground">
          Enter your contributor name to see how much CC you have available to water ideas with.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            placeholder="Your contributor name"
            className="flex-1 rounded-xl border border-border/40 bg-card/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="button"
            onClick={handleSave}
            className="rounded-xl bg-primary/10 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/20 transition-colors"
          >
            Save
          </button>
        </div>
      </section>
    );
  }

  const total = balance?.total ?? 0;
  const dropCount = Math.min(5, Math.floor(total / 50));

  return (
    <section className="mb-8 rounded-2xl border border-primary/20 bg-primary/5 p-5">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">💧</span>
        <p className="text-sm font-medium text-primary">Your watering can</p>
      </div>
      <p className="text-2xl font-light text-foreground mt-1">
        {loading ? "Filling up…" : balance ? `${balance.total.toFixed(1)} CC` : "Unavailable"}
      </p>
      {balance && !loading && (
        <p className="text-xs text-muted-foreground/70 mt-1">
          {dropCount > 0
            ? `${"💧".repeat(dropCount)} enough to water ${dropCount} idea${dropCount !== 1 ? "s" : ""} generously`
            : "Keep contributing to fill your can"}
        </p>
      )}
      <p className="mt-2 text-xs text-muted-foreground flex items-center gap-2">
        Gardener: {contributorId}
        <button
          type="button"
          onClick={() => {
            localStorage.removeItem(STORAGE_KEY);
            setContributorId("");
            setBalance(null);
            setInputValue("");
          }}
          className="text-primary/60 hover:text-primary underline text-xs"
        >
          change
        </button>
      </p>
    </section>
  );
}
