"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type LedgerBalance = {
  total?: number;
  grand_total?: number;
  totals_by_type?: Record<string, number>;
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
        <p className="text-sm font-medium text-primary">Your CC Balance</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter your contributor name to see your balance.
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

  return (
    <section className="mb-8 rounded-2xl border border-primary/20 bg-primary/5 p-5">
      <p className="text-sm font-medium text-primary">Your CC Balance</p>
      <p className="mt-1 text-2xl font-light text-foreground">
        {loading
          ? "Loading..."
          : balance
            ? `${(balance.grand_total ?? balance.total ?? 0).toFixed(1)} CC`
            : "Unavailable"}
      </p>
      <p className="mt-1 text-xs text-muted-foreground flex items-center gap-2">
        Contributor: {contributorId}
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
