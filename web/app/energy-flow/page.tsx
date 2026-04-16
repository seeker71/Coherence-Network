"use client";

/**
 * /energy-flow — Community energy flow dashboard.
 *
 * The nervous system of the community seeing itself:
 * - Active reward policies and their values
 * - Energy flow visualization (views → referrals → rewards → transactions)
 * - Knobs to adjust formulas
 * - Full traceability of how each policy produces outcomes
 */

import React, { useEffect, useState, useCallback } from "react";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

type PolicyEntry = {
  workspace_id: string;
  key: string;
  value: any;
  source: string;
  version?: number;
  description?: string;
  updated_by?: string;
  updated_at?: string;
};

type FlowStats = {
  total_views: number;
  unique_contributors: number;
  assets_viewed: number;
  top_trending: { asset_id: string; view_count: number; velocity: number }[];
};

export default function EnergyFlowDashboard() {
  const [policies, setPolicies] = useState<PolicyEntry[]>([]);
  const [flowStats, setFlowStats] = useState<FlowStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [policiesRes, flowRes] = await Promise.all([
        fetch(`${API}/api/reward-policies`),
        fetch(`${API}/api/views/summary?days=30`),
      ]);
      if (policiesRes.ok) setPolicies(await policiesRes.json());
      if (flowRes.ok) setFlowStats(await flowRes.json());
    } catch {
      // Dashboard data is supplementary
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  function startEdit(policy: PolicyEntry) {
    setEditing(policy.key);
    const val = typeof policy.value === "object" ? policy.value.value ?? policy.value : policy.value;
    setEditValue(String(val));
  }

  async function saveEdit(key: string) {
    setSaving(true);
    try {
      const existing = policies.find((p) => p.key === key);
      const oldValue = existing?.value;
      let newPayload: any;

      // Preserve the envelope structure if it exists
      if (typeof oldValue === "object" && oldValue !== null && "value" in oldValue) {
        const parsed = isNaN(Number(editValue)) ? editValue : Number(editValue);
        newPayload = { ...oldValue, value: parsed };
      } else {
        newPayload = isNaN(Number(editValue)) ? editValue : Number(editValue);
      }

      const res = await fetch(`${API}/api/reward-policies/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          value: newPayload,
          updated_by: "community_dashboard",
        }),
      });
      if (res.ok) {
        setEditing(null);
        await loadData();
      }
    } catch {
      // Best-effort save
    } finally {
      setSaving(false);
    }
  }

  function displayValue(value: any): string {
    if (typeof value === "object" && value !== null) {
      if ("value" in value) {
        const v = value.value;
        if (typeof v === "number") {
          if (value.unit === "fraction") return `${(v * 100).toFixed(1)}%`;
          if (value.unit === "CC") return `${v} CC`;
          return String(v);
        }
        if (Array.isArray(v)) return `${v.length} tiers`;
        return String(v);
      }
      return JSON.stringify(value);
    }
    return String(value);
  }

  function policyDescription(value: any): string {
    if (typeof value === "object" && value !== null && "description" in value) {
      return value.description;
    }
    return "";
  }

  function sourceLabel(source: string): { label: string; color: string } {
    switch (source) {
      case "community_override":
        return { label: "Community", color: "text-green-600 dark:text-green-400" };
      case "default_workspace":
        return { label: "Inherited", color: "text-blue-600 dark:text-blue-400" };
      default:
        return { label: "Default", color: "text-muted-foreground" };
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      </div>
    );
  }

  // Group policies by category
  const categories = new Map<string, PolicyEntry[]>();
  for (const p of policies) {
    const cat = p.key.split(".")[0];
    const list = categories.get(cat) || [];
    list.push(p);
    categories.set(cat, list);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 sm:px-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Energy Flow</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How energy moves through the community. Every formula is visible,
          traceable, and adjustable by the community.
        </p>
      </header>

      {/* Flow overview */}
      {flowStats && (
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <FlowCard label="Views (30d)" value={flowStats.total_views} />
          <FlowCard label="Contributors" value={flowStats.unique_contributors} />
          <FlowCard label="Assets viewed" value={flowStats.assets_viewed} />
          <FlowCard
            label="Velocity"
            value={
              flowStats.top_trending.length > 0
                ? flowStats.top_trending.reduce((s, t) => s + t.velocity, 0).toFixed(1)
                : "0"
            }
            suffix="/day"
          />
        </section>
      )}

      {/* Energy flow visualization */}
      <section className="rounded-xl border border-border/40 bg-card/50 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Flow Path
        </h2>
        <div className="flex flex-col items-center gap-2 sm:flex-row sm:gap-4">
          <FlowStep label="Views" detail="Assets seen" />
          <FlowArrow />
          <FlowStep label="Referrals" detail="Discovery chain" />
          <FlowArrow />
          <FlowStep label="Rewards" detail="CC earned" />
          <FlowArrow />
          <FlowStep label="Transactions" detail="Stakes, swaps" />
          <FlowArrow />
          <FlowStep label="Growth" detail="Community vitality" />
        </div>
      </section>

      {/* Policy knobs by category */}
      {Array.from(categories.entries()).map(([category, pols]) => (
        <section key={category} className="space-y-3">
          <h2 className="text-lg font-semibold capitalize">{category} formulas</h2>
          <div className="space-y-2">
            {pols.map((p) => {
              const { label: srcLabel, color: srcColor } = sourceLabel(p.source);
              const desc = p.description || policyDescription(p.value);
              const isEditing = editing === p.key;

              return (
                <div
                  key={p.key}
                  className="rounded-xl border border-border/40 bg-card/50 p-4 transition-colors hover:border-border/60"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-medium">
                          {p.key.split(".").slice(1).join(".")}
                        </span>
                        <span className={`text-xs ${srcColor}`}>{srcLabel}</span>
                        {p.version != null && p.version > 1 && (
                          <span className="text-xs text-muted-foreground">v{p.version}</span>
                        )}
                      </div>
                      {desc && (
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">{desc}</p>
                      )}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {isEditing ? (
                        <>
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="w-24 rounded border border-border bg-background px-2 py-1 text-right font-mono text-sm"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveEdit(p.key);
                              if (e.key === "Escape") setEditing(null);
                            }}
                          />
                          <button
                            onClick={() => saveEdit(p.key)}
                            disabled={saving}
                            className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                          >
                            {saving ? "..." : "Save"}
                          </button>
                          <button
                            onClick={() => setEditing(null)}
                            className="rounded bg-muted px-2 py-1 text-xs"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="font-mono text-sm font-bold">
                            {displayValue(p.value)}
                          </span>
                          <button
                            onClick={() => startEdit(p)}
                            className="rounded bg-muted/60 px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                            title="Adjust this formula parameter"
                          >
                            Adjust
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {p.updated_by && p.source === "community_override" && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Set by {p.updated_by}
                      {p.updated_at && ` · ${new Date(p.updated_at).toLocaleDateString()}`}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}

      {/* Transparency */}
      <footer className="rounded-xl border border-border/30 bg-muted/20 p-4">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Every reward event records the exact policy snapshot that produced it.
          The flow is fully transparent — anyone can trace how a reward was
          calculated, which formula was active, and who changed it. Communities
          adjust their own formulas; the system provides starting defaults.
        </p>
      </footer>
    </div>
  );
}

function FlowCard({
  label,
  value,
  suffix,
}: {
  label: string;
  value: number | string;
  suffix?: string;
}) {
  return (
    <div className="rounded-xl border border-border/40 bg-card/50 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-bold">
        {typeof value === "number" ? value.toLocaleString() : value}
        {suffix && <span className="text-sm font-normal text-muted-foreground"> {suffix}</span>}
      </p>
    </div>
  );
}

function FlowStep({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-primary/5 px-4 py-3 text-center">
      <span className="text-sm font-semibold">{label}</span>
      <span className="text-xs text-muted-foreground">{detail}</span>
    </div>
  );
}

function FlowArrow() {
  return (
    <span className="text-lg text-muted-foreground/50">→</span>
  );
}
