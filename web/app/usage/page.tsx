import Link from "next/link";

import { getApiBase } from "@/lib/api";

type RuntimeIdeaRow = {
  idea_id: string;
  event_count: number;
  total_runtime_ms: number;
  average_runtime_ms: number;
  runtime_cost_estimate: number;
  by_source: Record<string, number>;
};

type RuntimeSummaryResponse = {
  window_seconds: number;
  ideas: RuntimeIdeaRow[];
};

type FrictionReportRow = {
  key: string;
  count: number;
  energy_loss: number;
  cost_of_delay?: number;
};

type FrictionReport = {
  window_days: number;
  total_events: number;
  open_events: number;
  total_energy_loss: number;
  total_cost_of_delay: number;
  top_block_types: FrictionReportRow[];
  top_stages: FrictionReportRow[];
};

type SubscriptionPlanEstimate = {
  provider: string;
  detected: boolean;
  current_tier: string;
  next_tier: string;
  current_monthly_cost_usd: number;
  next_monthly_cost_usd: number;
  monthly_upgrade_delta_usd: number;
  estimated_benefit_score: number;
  estimated_roi: number;
  confidence: number;
  assumptions: string[];
  expected_benefits: string[];
};

type SubscriptionEstimatorResponse = {
  detected_subscriptions: number;
  estimated_current_monthly_cost_usd: number;
  estimated_next_monthly_cost_usd: number;
  estimated_monthly_upgrade_delta_usd: number;
  plans: SubscriptionPlanEstimate[];
};

const FETCH_TIMEOUT_MS = 8000;

const DEFAULT_RUNTIME: RuntimeSummaryResponse = {
  window_seconds: 86400,
  ideas: [],
};

const DEFAULT_FRICTION: FrictionReport = {
  window_days: 7,
  total_events: 0,
  open_events: 0,
  total_energy_loss: 0,
  total_cost_of_delay: 0,
  top_block_types: [],
  top_stages: [],
};

const DEFAULT_SUBSCRIPTIONS: SubscriptionEstimatorResponse = {
  detected_subscriptions: 0,
  estimated_current_monthly_cost_usd: 0,
  estimated_next_monthly_cost_usd: 0,
  estimated_monthly_upgrade_delta_usd: 0,
  plans: [],
};

async function fetchJsonOrNull<T>(url: string): Promise<T | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(new DOMException("Request timed out", "TimeoutError")),
    FETCH_TIMEOUT_MS,
  );
  try {
    const res = await fetch(url, { cache: "no-store", signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function loadUsage(): Promise<{
  runtime: RuntimeSummaryResponse;
  friction: FrictionReport;
  subscriptions: SubscriptionEstimatorResponse;
  warnings: string[];
}> {
  const API = getApiBase();
  const [runtime, friction, subscriptions] = await Promise.all([
    fetchJsonOrNull<RuntimeSummaryResponse>(`${API}/api/runtime/ideas/summary?seconds=86400`),
    fetchJsonOrNull<FrictionReport>(`${API}/api/friction/report?window_days=7`),
    fetchJsonOrNull<SubscriptionEstimatorResponse>(`${API}/api/automation/usage/subscription-estimator`),
  ]);

  const warnings: string[] = [];
  if (!runtime) warnings.push("runtime telemetry");
  if (!friction) warnings.push("friction report");
  if (!subscriptions) warnings.push("subscription estimator");

  return {
    runtime: runtime ?? DEFAULT_RUNTIME,
    friction: friction ?? DEFAULT_FRICTION,
    subscriptions: subscriptions ?? DEFAULT_SUBSCRIPTIONS,
    warnings,
  };
}

export default async function UsagePage() {
  const { runtime, friction, subscriptions, warnings } = await loadUsage();
  const ideas = [...runtime.ideas].sort((a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate).slice(0, 20);
  const plans = [...subscriptions.plans]
    .sort((a, b) => b.estimated_roi - a.estimated_roi)
    .slice(0, 10);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Usage</h1>
      <p className="text-muted-foreground">Runtime telemetry + friction summary (machine data rendered for humans).</p>
      {warnings.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          Partial data mode: unavailable {warnings.join(", ")}.
        </p>
      ) : null}

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Friction (7d)</h2>
        <p className="text-muted-foreground">
          total_events {friction.total_events} | open {friction.open_events} | energy_loss {friction.total_energy_loss}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top block types</p>
            <ul className="space-y-1">
              {friction.top_block_types.slice(0, 8).map((r) => (
                <li key={r.key} className="flex justify-between">
                  <Link href="/friction" className="underline hover:text-foreground">
                    {r.key}
                  </Link>
                  <span className="text-muted-foreground">{r.count}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top stages</p>
            <ul className="space-y-1">
              {friction.top_stages.slice(0, 8).map((r) => (
                <li key={r.key} className="flex justify-between">
                  <span>{r.key}</span>
                  <span className="text-muted-foreground">{r.count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Subscription Upgrade Estimator</h2>
        <p className="text-muted-foreground">
          detected {subscriptions.detected_subscriptions} | current $
          {subscriptions.estimated_current_monthly_cost_usd.toFixed(2)} | next $
          {subscriptions.estimated_next_monthly_cost_usd.toFixed(2)} | delta $
          {subscriptions.estimated_monthly_upgrade_delta_usd.toFixed(2)}
        </p>
        <ul className="space-y-2">
          {plans.map((plan) => (
            <li key={plan.provider} className="rounded border p-2">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">
                  {plan.provider} {plan.detected ? "(detected)" : "(not detected)"}
                </span>
                <span className="text-muted-foreground">
                  {plan.current_tier} → {plan.next_tier} | +${plan.monthly_upgrade_delta_usd.toFixed(2)} | ROI{" "}
                  {plan.estimated_roi.toFixed(2)} | confidence {(plan.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-muted-foreground">
                benefit score {plan.estimated_benefit_score.toFixed(2)} |{" "}
                {plan.expected_benefits[0] ?? "No benefit summary"}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Runtime Cost by Idea (24h)</h2>
        <p className="text-muted-foreground">window_seconds {runtime.window_seconds}</p>
        <ul className="space-y-2">
              {ideas.map((row) => (
                <li key={row.idea_id} className="flex justify-between rounded border p-2">
              <Link href={`/ideas/${encodeURIComponent(row.idea_id)}`} className="underline hover:text-foreground">
                {row.idea_id}
              </Link>
              <span className="text-muted-foreground">
                events {row.event_count} | runtime {row.total_runtime_ms.toFixed(2)}ms | cost ${row.runtime_cost_estimate.toFixed(6)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
