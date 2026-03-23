"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

const STORAGE_KEY = "coherence_contributor_id";

type TreasuryInfo = {
  eth_address: string;
  btc_address: string;
  cc_per_eth: number;
  cc_per_btc: number;
  total_cc_converted: number;
  deposit_count: number;
};

export function TreasuryDepositForm() {
  const [info, setInfo] = useState<TreasuryInfo | null>(null);
  const [contributorId, setContributorId] = useState("");
  const [asset, setAsset] = useState("eth");
  const [amount, setAmount] = useState("");
  const [txHash, setTxHash] = useState("");
  const [strategy, setStrategy] = useState("highest_roi");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setContributorId(stored);
  }, []);

  useEffect(() => {
    const API = getApiBase();
    fetch(`${API}/api/treasury`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setInfo(d); })
      .catch(() => {});
  }, []);

  const copyAddress = useCallback((addr: string, label: string) => {
    navigator.clipboard.writeText(addr).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    });
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError("");
      setResult(null);
      if (!contributorId.trim() || !amount.trim() || !txHash.trim()) {
        setError("All fields are required.");
        return;
      }
      const numAmount = parseFloat(amount);
      if (isNaN(numAmount) || numAmount <= 0) {
        setError("Amount must be a positive number.");
        return;
      }
      setSubmitting(true);
      localStorage.setItem(STORAGE_KEY, contributorId.trim());
      try {
        const API = getApiBase();
        const res = await fetch(`${API}/api/treasury/deposit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contributor_id: contributorId.trim(),
            asset,
            amount: numAmount,
            tx_hash: txHash.trim(),
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError(body.detail || `Error ${res.status}`);
          return;
        }
        const deposit = await res.json();
        setResult(deposit);

        // Auto-stake if strategy is set
        if (strategy && deposit.cc_converted > 0) {
          try {
            await fetch(`${API}/api/treasury/deposit/${deposit.deposit_id}/stake`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                contributor_id: contributorId.trim(),
                cc_amount: deposit.cc_converted,
                strategy,
              }),
            });
          } catch {
            // staking is optional, deposit already recorded
          }
        }
      } catch {
        setError("Network error. Please try again.");
      } finally {
        setSubmitting(false);
      }
    },
    [contributorId, asset, amount, txHash, strategy],
  );

  const rate = info ? (asset === "eth" ? info.cc_per_eth : info.cc_per_btc) : 0;
  const preview = amount && !isNaN(parseFloat(amount)) ? (parseFloat(amount) * rate).toFixed(2) : null;

  return (
    <div className="space-y-6">
      {/* Wallet addresses */}
      {info && (
        <div className="grid gap-4 sm:grid-cols-2">
          {info.eth_address && (
            <div className="rounded-xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/80">ETH Treasury Wallet</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate text-sm text-foreground/80">{info.eth_address}</code>
                <button
                  onClick={() => copyAddress(info.eth_address, "eth")}
                  className="shrink-0 rounded-lg border border-border/40 px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:border-border transition-all duration-200"
                >
                  {copied === "eth" ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          )}
          {info.btc_address && (
            <div className="rounded-xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/80">BTC Treasury Wallet</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate text-sm text-foreground/80">{info.btc_address}</code>
                <button
                  onClick={() => copyAddress(info.btc_address, "btc")}
                  className="shrink-0 rounded-lg border border-border/40 px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:border-border transition-all duration-200"
                >
                  {copied === "btc" ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Conversion rates */}
      {info && (
        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>1 ETH = {info.cc_per_eth.toLocaleString()} CC</span>
          <span>1 BTC = {info.cc_per_btc.toLocaleString()} CC</span>
          {info.deposit_count > 0 && (
            <span>{info.total_cc_converted.toLocaleString()} CC converted from {info.deposit_count} deposit{info.deposit_count !== 1 ? "s" : ""}</span>
          )}
        </div>
      )}

      {/* Deposit form */}
      <form onSubmit={handleSubmit} className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-4">
        <h2 className="text-lg font-semibold">Record a Deposit</h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-sm text-muted-foreground">Your Name / ID</span>
            <input
              type="text"
              value={contributorId}
              onChange={(e) => setContributorId(e.target.value)}
              placeholder="e.g. alice"
              className="w-full rounded-lg border border-border/50 bg-background/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-muted-foreground">Asset</span>
            <select
              value={asset}
              onChange={(e) => setAsset(e.target.value)}
              className="w-full rounded-lg border border-border/50 bg-background/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="eth">ETH (Ethereum)</option>
              <option value="btc">BTC (Bitcoin)</option>
            </select>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-sm text-muted-foreground">Amount ({asset.toUpperCase()})</span>
            <input
              type="number"
              step="any"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.1"
              className="w-full rounded-lg border border-border/50 bg-background/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {preview && (
              <p className="text-xs text-primary/80 mt-1">= {preview} CC</p>
            )}
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-muted-foreground">Transaction Hash</span>
            <input
              type="text"
              value={txHash}
              onChange={(e) => setTxHash(e.target.value)}
              placeholder="0x..."
              className="w-full rounded-lg border border-border/50 bg-background/50 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
        </div>

        <label className="block space-y-1">
          <span className="text-sm text-muted-foreground">Staking Strategy</span>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full rounded-lg border border-border/50 bg-background/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="highest_roi">Highest ROI idea</option>
            <option value="spread">Spread across top 3 ideas</option>
            <option value="">Do not auto-stake</option>
          </select>
        </label>

        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}

        {result && (
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm space-y-1">
            <p className="font-medium text-primary">Deposit recorded</p>
            <p className="text-muted-foreground">
              {result.amount as number} {(result.asset as string || "").toUpperCase()} converted to {result.cc_converted as number} CC
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-primary/10 px-6 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-50"
        >
          {submitting ? "Recording..." : "Record Deposit"}
        </button>
      </form>
    </div>
  );
}
