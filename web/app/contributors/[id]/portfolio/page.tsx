"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

// ── Types ────────────────────────────────────────────────────────────

interface LinkedIdentity {
  type: string;
  handle: string;
  verified: boolean;
}

interface ContributorSummary {
  id: string;
  display_name: string;
  identities: LinkedIdentity[];
}

interface PortfolioSummary {
  contributor: ContributorSummary;
  cc_balance: number | null;
  cc_network_pct: number | null;
  idea_contribution_count: number;
  stake_count: number;
  task_completion_count: number;
  recent_activity: string | null;
}

interface CCHistoryBucket {
  period_start: string;
  period_end: string;
  cc_earned: number;
  running_total: number;
  network_pct_at_period_end: number | null;
}

interface CCHistory {
  contributor_id: string;
  window: string;
  bucket: string;
  series: CCHistoryBucket[];
}

interface HealthSignal {
  activity_signal: string;
  value_delta_pct: number | null;
  evidence_count: number;
}

interface IdeaContributionSummary {
  idea_id: string;
  idea_title: string;
  idea_status: string;
  contribution_types: string[];
  cc_attributed: number;
  contribution_count: number;
  last_contributed_at: string | null;
  health: HealthSignal;
}

interface IdeaContributionsList {
  contributor_id: string;
  total: number;
  items: IdeaContributionSummary[];
}

interface StakeSummary {
  stake_id: string;
  idea_id: string;
  idea_title: string;
  cc_staked: number;
  cc_valuation: number | null;
  roi_pct: number | null;
  staked_at: string | null;
  health: HealthSignal;
}

interface StakesList {
  contributor_id: string;
  total: number;
  items: StakeSummary[];
}

interface TaskSummary {
  task_id: string;
  description: string;
  idea_id: string | null;
  idea_title: string | null;
  provider: string | null;
  outcome: string | null;
  cc_earned: number;
  completed_at: string | null;
}

interface TasksList {
  contributor_id: string;
  total: number;
  items: TaskSummary[];
}

// ── Helpers ──────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

function fmtCC(val: number | null): string {
  if (val === null || val === undefined) return "—";
  return val.toFixed(2);
}

function activityColor(signal: string): string {
  if (signal === "active") return "text-green-400";
  if (signal === "slow") return "text-yellow-400";
  if (signal === "dormant") return "text-muted-foreground";
  return "text-muted-foreground";
}

function outcomeColor(outcome: string | null): string {
  if (outcome === "passed") return "text-green-400";
  if (outcome === "failed") return "text-red-400";
  if (outcome === "partial") return "text-yellow-400";
  return "text-muted-foreground";
}

// ── Mini bar chart ───────────────────────────────────────────────────

function CCChart({ series }: { series: CCHistoryBucket[] }) {
  if (!series.length) return <p className="text-sm text-muted-foreground">No earning history yet.</p>;

  const maxEarned = Math.max(...series.map((b) => b.cc_earned), 0.001);

  return (
    <div className="flex items-end gap-0.5 h-16 w-full overflow-hidden" title="CC earned per period">
      {series.map((b, i) => {
        const pct = (b.cc_earned / maxEarned) * 100;
        return (
          <div
            key={i}
            className="flex-1 bg-primary/60 rounded-sm transition-all"
            style={{ height: `${Math.max(pct, 2)}%` }}
            title={`${fmtDate(b.period_start)}: ${b.cc_earned.toFixed(2)} CC`}
          />
        );
      })}
    </div>
  );
}

// ── Identity badges ──────────────────────────────────────────────────

function IdentityBadge({ identity }: { identity: LinkedIdentity }) {
  const icons: Record<string, string> = { github: "GH", telegram: "TG", wallet: "💳" };
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/40 bg-background/50 px-3 py-1 text-xs">
      <span className="font-mono text-muted-foreground">{icons[identity.type] ?? identity.type}</span>
      <span>{identity.handle}</span>
      {identity.verified && <span className="text-green-400">✓</span>}
    </span>
  );
}

// ── Main page ────────────────────────────────────────────────────────

export default function ContributorPortfolioPage() {
  const params = useParams<{ id: string }>();
  const contributorId = decodeURIComponent(params.id ?? "");

  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [history, setHistory] = useState<CCHistory | null>(null);
  const [ideas, setIdeas] = useState<IdeaContributionsList | null>(null);
  const [stakes, setStakes] = useState<StakesList | null>(null);
  const [tasks, setTasks] = useState<TasksList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  const load = useCallback(async () => {
    if (!contributorId) return;
    setLoading(true);
    setError(null);

    try {
      const base = `${API}/api/contributors/${encodeURIComponent(contributorId)}`;
      const [sumRes, histRes, ideasRes, stakesRes, tasksRes] = await Promise.all([
        fetch(`${base}/portfolio`),
        fetch(`${base}/cc-history?window=90d&bucket=7d`),
        fetch(`${base}/idea-contributions?sort=cc_attributed_desc&limit=20`),
        fetch(`${base}/stakes?sort=roi_desc&limit=20`),
        fetch(`${base}/tasks?status=completed&limit=20`),
      ]);

      if (!sumRes.ok) {
        const j = await sumRes.json().catch(() => ({}));
        throw new Error(j.detail ?? `Portfolio not found (${sumRes.status})`);
      }

      const [sumData, histData, ideasData, stakesData, tasksData] = await Promise.all([
        sumRes.json(),
        histRes.ok ? histRes.json() : null,
        ideasRes.ok ? ideasRes.json() : null,
        stakesRes.ok ? stakesRes.json() : null,
        tasksRes.ok ? tasksRes.json() : null,
      ]);

      if (!isMounted.current) return;
      setSummary(sumData);
      setHistory(histData);
      setIdeas(ideasData);
      setStakes(stakesData);
      setTasks(tasksData);
    } catch (e) {
      if (isMounted.current) setError(String(e));
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, [contributorId]);

  useEffect(() => { void load(); }, [load]);

  if (loading) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-4xl mx-auto">
        <p className="text-muted-foreground">Loading portfolio for {contributorId}…</p>
      </main>
    );
  }

  if (error || !summary) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-4xl mx-auto space-y-4">
        <p className="text-destructive">{error ?? "Contributor not found."}</p>
        <Link href="/my-portfolio" className="text-sm text-muted-foreground underline hover:text-foreground">
          ← Back to My Portfolio
        </Link>
      </main>
    );
  }

  const { contributor } = summary;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-4xl mx-auto space-y-6">

      {/* ── Header ── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <p className="text-xs text-muted-foreground uppercase tracking-widest">My Portfolio</p>
        <h1 className="text-3xl font-light tracking-tight">{contributor.display_name}</h1>

        {/* Linked identities */}
        {contributor.identities.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {contributor.identities.map((id, i) => (
              <IdentityBadge key={i} identity={id} />
            ))}
          </div>
        )}

        {/* Quick stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
            <p className="text-xs text-muted-foreground">CC Balance</p>
            <p className="text-xl font-light text-primary">{fmtCC(summary.cc_balance)}</p>
            {summary.cc_network_pct !== null && (
              <p className="text-xs text-muted-foreground">{summary.cc_network_pct.toFixed(4)}% of network</p>
            )}
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
            <p className="text-xs text-muted-foreground">Ideas</p>
            <p className="text-xl font-light text-primary">{summary.idea_contribution_count}</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
            <p className="text-xs text-muted-foreground">Stakes</p>
            <p className="text-xl font-light text-primary">{summary.stake_count}</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
            <p className="text-xs text-muted-foreground">Tasks Done</p>
            <p className="text-xl font-light text-primary">{summary.task_completion_count}</p>
          </div>
        </div>
      </section>

      {/* ── CC History Chart ── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-medium">CC Earning History</h2>
          <span className="text-xs text-muted-foreground">90 days · 7d buckets</span>
        </div>
        {history ? (
          <>
            <CCChart series={history.series} />
            <p className="text-xs text-muted-foreground">
              Hover bar for CC earned per period. Running total: {fmtCC(history.series.at(-1)?.running_total ?? null)} CC
            </p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No history data.</p>
        )}
      </section>

      {/* ── Ideas I Contributed To ── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-lg font-medium">Ideas I Contributed To</h2>
        {ideas && ideas.items.length > 0 ? (
          <ul className="space-y-2">
            {ideas.items.map((idea) => (
              <li key={idea.idea_id}>
                <Link
                  href={`/contributors/${encodeURIComponent(contributorId)}/portfolio/ideas/${encodeURIComponent(idea.idea_id)}`}
                  className="block rounded-xl border border-border/20 bg-background/40 p-4 hover:border-primary/40 hover:bg-background/60 transition-all group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1 min-w-0">
                      <p className="font-medium truncate group-hover:text-primary transition-colors">{idea.idea_title}</p>
                      <div className="flex flex-wrap gap-1.5 text-xs">
                        <span className="rounded-full border border-border/30 px-2 py-0.5 text-muted-foreground">{idea.idea_status}</span>
                        {idea.contribution_types.map((t) => (
                          <span key={t} className="rounded-full border border-primary/30 px-2 py-0.5 text-primary/80">{t}</span>
                        ))}
                      </div>
                    </div>
                    <div className="text-right shrink-0 space-y-1">
                      <p className="text-sm font-mono text-primary">{fmtCC(idea.cc_attributed)} CC</p>
                      <p className={`text-xs ${activityColor(idea.health.activity_signal)}`}>
                        {idea.health.activity_signal}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {idea.contribution_count} contribution{idea.contribution_count !== 1 ? "s" : ""} · last {fmtDate(idea.last_contributed_at)}
                    {idea.health.value_delta_pct !== null && (
                      <span className={idea.health.value_delta_pct >= 0 ? " text-green-400" : " text-red-400"}>
                        {" "}· {idea.health.value_delta_pct >= 0 ? "+" : ""}{idea.health.value_delta_pct.toFixed(1)}% value
                      </span>
                    )}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No idea contributions found.</p>
        )}
        {ideas && ideas.total > ideas.items.length && (
          <p className="text-xs text-muted-foreground">Showing {ideas.items.length} of {ideas.total}</p>
        )}
      </section>

      {/* ── Stakes ── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-lg font-medium">Ideas I Staked On</h2>
        {stakes && stakes.items.length > 0 ? (
          <ul className="space-y-2">
            {stakes.items.map((stake) => (
              <li key={stake.stake_id}>
                <Link
                  href={`/contributors/${encodeURIComponent(contributorId)}/portfolio/stakes/${encodeURIComponent(stake.stake_id)}`}
                  className="block rounded-xl border border-border/20 bg-background/40 p-4 hover:border-primary/40 hover:bg-background/60 transition-all group"
                >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 min-w-0">
                    <p className="font-medium hover:text-primary transition-colors truncate group-hover:text-primary">
                      {stake.idea_title}
                    </p>
                    <p className="text-xs text-muted-foreground">Staked {fmtDate(stake.staked_at)}</p>
                  </div>
                  <div className="text-right shrink-0 space-y-1">
                    <p className="text-sm font-mono">{fmtCC(stake.cc_staked)} CC staked</p>
                    {stake.roi_pct !== null && (
                      <p className={`text-sm font-mono font-medium ${stake.roi_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {stake.roi_pct >= 0 ? "+" : ""}{stake.roi_pct.toFixed(2)}% ROI
                      </p>
                    )}
                    {stake.cc_valuation !== null && (
                      <p className="text-xs text-muted-foreground">Now: {fmtCC(stake.cc_valuation)} CC</p>
                    )}
                  </div>
                </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No stakes recorded yet.</p>
        )}
      </section>

      {/* ── Tasks ── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-lg font-medium">Tasks I Completed</h2>
        {tasks && tasks.items.length > 0 ? (
          <ul className="space-y-2">
            {tasks.items.map((task) => (
              <li key={task.task_id} className="rounded-xl border border-border/20 bg-background/40 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 min-w-0 flex-1">
                    <p className="text-sm truncate">{task.description || task.task_id}</p>
                    <div className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
                      {task.provider && <span className="rounded-full border border-border/30 px-2 py-0.5">{task.provider}</span>}
                      {task.idea_title && (
                        <Link
                          href={`/ideas/${encodeURIComponent(task.idea_id ?? "")}`}
                          className="hover:text-foreground underline"
                        >
                          {task.idea_title}
                        </Link>
                      )}
                      <span>{fmtDate(task.completed_at)}</span>
                    </div>
                  </div>
                  <div className="text-right shrink-0 space-y-1">
                    {task.outcome && (
                      <p className={`text-xs font-medium ${outcomeColor(task.outcome)}`}>{task.outcome}</p>
                    )}
                    {task.cc_earned > 0 && (
                      <p className="text-xs font-mono text-primary">+{fmtCC(task.cc_earned)} CC</p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No completed tasks found.</p>
        )}
        {tasks && tasks.total > tasks.items.length && (
          <p className="text-xs text-muted-foreground">Showing {tasks.items.length} of {tasks.total}</p>
        )}
      </section>

      {/* ── Footer nav ── */}
      <div className="flex gap-4 text-sm text-muted-foreground pt-2">
        <Link href="/my-portfolio" className="hover:text-foreground transition-colors">← Change Contributor</Link>
        <Link href={`/contributors/${encodeURIComponent(contributorId)}`} className="hover:text-foreground transition-colors">
          Full Profile →
        </Link>
      </div>
    </main>
  );
}
