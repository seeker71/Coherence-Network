"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

const STORAGE_KEY = "coherence_contributor_id";

interface IdeaStakeFormProps {
  ideaId: string;
  ideaName: string;
}

type StakeResponse = {
  tasks_created?: Array<{ task_type?: string; task_id?: string }>;
  amount_cc?: number;
  message?: string;
};

export function IdeaStakeForm({ ideaId, ideaName }: IdeaStakeFormProps) {
  const [contributorId, setContributorId] = useState("");
  const [inputName, setInputName] = useState("");
  const [amount, setAmount] = useState("10");
  const [strategy, setStrategy] = useState("highest_roi");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<StakeResponse | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setContributorId(stored);
      setInputName(stored);
    }
  }, []);

  function handleSaveName() {
    const trimmed = inputName.trim();
    if (!trimmed) return;
    localStorage.setItem(STORAGE_KEY, trimmed);
    setContributorId(trimmed);
  }

  const handleStake = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError("");
      setResult(null);

      const numAmount = parseFloat(amount);
      if (isNaN(numAmount) || numAmount <= 0) {
        setError("Enter a positive CC amount.");
        return;
      }
      if (!contributorId.trim()) {
        setError("Enter your contributor name first.");
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
            amount_cc: numAmount,
            rationale: `Staked on "${ideaName}" via UI`,
          }),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError(body.detail || `Something went wrong (${res.status}). Try again?`);
          setStatus("error");
          return;
        }

        const data: StakeResponse = await res.json();
        setResult(data);
        setStatus("success");
      } catch {
        setError("Network error. Please try again.");
        setStatus("error");
      }
    },
    [contributorId, amount, ideaId, ideaName],
  );

  const tasksPreview = amount && !isNaN(parseFloat(amount))
    ? Math.max(1, Math.round(parseFloat(amount) / 5))
    : 0;

  // Name entry gate (same pattern as InvestBalanceSection)
  if (!contributorId) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-amber-800/70 dark:text-amber-300/70">
          Enter your contributor name to stake CC on this idea.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={inputName}
            onChange={(e) => setInputName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSaveName()}
            placeholder="Your contributor name"
            className="w-full sm:flex-1 rounded-lg border border-amber-200/60 bg-white/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 dark:border-amber-800/30 dark:bg-stone-800/40 min-h-[44px]"
          />
          <button
            type="button"
            onClick={handleSaveName}
            className="rounded-lg bg-amber-100 px-4 py-2 text-sm font-medium text-amber-900 hover:bg-amber-200 transition-colors dark:bg-amber-900/30 dark:text-amber-200 dark:hover:bg-amber-900/50 min-h-[44px]"
          >
            Save
          </button>
        </div>
      </div>
    );
  }

  if (status === "success" && result) {
    const tasks = result.tasks_created ?? [];
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-green-600 dark:text-green-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            Staked! {result.amount_cc ?? parseFloat(amount)} CC on this idea.
          </p>
        </div>
        {tasks.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs text-amber-700/70 dark:text-amber-400/70">{tasks.length} task{tasks.length !== 1 ? "s" : ""} queued:</p>
            <ul className="text-xs text-amber-800/60 dark:text-amber-300/60 space-y-0.5">
              {tasks.map((t, i) => (
                <li key={i}>{t.task_type || t.task_id || `Task ${i + 1}`}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          type="button"
          onClick={() => {
            setStatus("idle");
            setResult(null);
            setAmount("10");
          }}
          className="text-xs text-amber-700/60 dark:text-amber-400/60 hover:text-amber-900 dark:hover:text-amber-200 underline underline-offset-4 transition-colors"
        >
          Stake more
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleStake} className="space-y-3">
      <p className="text-xs text-amber-700/60 dark:text-amber-400/60">
        Staking as: {contributorId}
        <button
          type="button"
          onClick={() => {
            localStorage.removeItem(STORAGE_KEY);
            setContributorId("");
            setInputName("");
          }}
          className="ml-2 underline hover:text-amber-900 dark:hover:text-amber-200 transition-colors"
        >
          change
        </button>
      </p>
      <div className="flex flex-col sm:flex-row gap-3">
        <label className="flex-1 space-y-1">
          <span className="text-xs text-amber-700/70 dark:text-amber-400/70">Amount (CC)</span>
          <input
            type="number"
            step="any"
            min="0.1"
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value);
              if (status === "error") { setStatus("idle"); setError(""); }
            }}
            placeholder="10"
            className="w-full rounded-lg border border-amber-200/60 bg-white/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 dark:border-amber-800/30 dark:bg-stone-800/40 min-h-[44px]"
          />
          {tasksPreview > 0 && (
            <p className="text-xs text-amber-700/60 dark:text-amber-400/60">
              {amount} CC ~ {tasksPreview} task{tasksPreview !== 1 ? "s" : ""} created
            </p>
          )}
        </label>
        <label className="flex-1 space-y-1">
          <span className="text-xs text-amber-700/70 dark:text-amber-400/70">Strategy</span>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full rounded-lg border border-amber-200/60 bg-white/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/40 dark:border-amber-800/30 dark:bg-stone-800/40 min-h-[44px]"
          >
            <option value="highest_roi">Highest ROI</option>
            <option value="this_idea">This idea only</option>
          </select>
        </label>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="w-full sm:w-auto rounded-full bg-amber-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700 disabled:opacity-50 dark:bg-amber-500 dark:hover:bg-amber-600 min-h-[44px]"
      >
        {status === "submitting" ? (
          <span className="inline-flex items-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Staking...
          </span>
        ) : "Stake"}
      </button>
    </form>
  );
}
