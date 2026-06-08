"use client";

import { BarChart3, RotateCcw, Send } from "lucide-react";
import { useMemo, useState } from "react";

import { getApiBase } from "@/lib/api";

type MetricKey =
  | "followers"
  | "new_followers"
  | "reach"
  | "views"
  | "likes"
  | "saves"
  | "shares"
  | "comments"
  | "profile_visits"
  | "link_clicks"
  | "streams"
  | "listeners"
  | "playlist_adds"
  | "pre_saves"
  | "revenue_usd";

type SnapshotKind = "baseline" | "current";

type SnapshotRow = {
  id: string;
  platform: string;
  kind: SnapshotKind;
  source_label: string;
  metrics: Record<MetricKey, string>;
};

type Dimension = {
  name: string;
  score: number;
  lift: number;
  current_total: number;
};

type Recommendation = {
  priority: string;
  reason: string;
  action: string;
  expected_signal: string;
};

type Report = {
  report_id: string;
  answer: {
    status: string;
    healthiest_next_execution: string;
  };
  proof_quality: string;
  resonance_score: number;
  confidence: number;
  attention_total: number;
  engagement_total: number;
  conversion_total: number;
  income_usd: number;
  cost_usd: number;
  net_income_usd: number;
  engagement_rate: number;
  conversion_rate: number;
  dimensions: Dimension[];
  recommendations: Recommendation[];
  evidence_gaps: string[];
};

const METRICS: Array<{ key: MetricKey; label: string }> = [
  { key: "followers", label: "Followers" },
  { key: "new_followers", label: "New followers" },
  { key: "reach", label: "Reach" },
  { key: "views", label: "Views" },
  { key: "likes", label: "Likes" },
  { key: "saves", label: "Saves" },
  { key: "shares", label: "Shares" },
  { key: "comments", label: "Comments" },
  { key: "profile_visits", label: "Profile visits" },
  { key: "link_clicks", label: "Link clicks" },
  { key: "streams", label: "Streams" },
  { key: "listeners", label: "Listeners" },
  { key: "playlist_adds", label: "Playlist adds" },
  { key: "pre_saves", label: "Pre-saves" },
  { key: "revenue_usd", label: "Revenue USD" },
];

const EMPTY_METRICS = METRICS.reduce(
  (acc, item) => ({ ...acc, [item.key]: "" }),
  {} as Record<MetricKey, string>,
);

function snapshot(id: string, platform: string, kind: SnapshotKind): SnapshotRow {
  return {
    id,
    platform,
    kind,
    source_label: "",
    metrics: { ...EMPTY_METRICS },
  };
}

function parseNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function metricPayload(row: SnapshotRow): Record<MetricKey, number> {
  return METRICS.reduce((acc, item) => {
    acc[item.key] = parseNumber(row.metrics[item.key]);
    return acc;
  }, {} as Record<MetricKey, number>);
}

function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (value >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function CreatorResonanceBuilder() {
  const [artistName, setArtistName] = useState("");
  const [campaignTitle, setCampaignTitle] = useState("");
  const [costUsd, setCostUsd] = useState("");
  const [artifactTitle, setArtifactTitle] = useState("");
  const [rows, setRows] = useState<SnapshotRow[]>([
    snapshot("instagram-baseline", "Instagram", "baseline"),
    snapshot("instagram-current", "Instagram", "current"),
    snapshot("spotify-baseline", "Spotify", "baseline"),
    snapshot("spotify-current", "Spotify", "current"),
  ]);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const hasMetrics = useMemo(
    () => rows.some((row) => METRICS.some((item) => parseNumber(row.metrics[item.key]) > 0)),
    [rows],
  );

  function updateRow(id: string, update: (row: SnapshotRow) => SnapshotRow) {
    setRows((current) => current.map((row) => (row.id === id ? update(row) : row)));
  }

  function reset() {
    setArtistName("");
    setCampaignTitle("");
    setCostUsd("");
    setArtifactTitle("");
    setRows([
      snapshot("instagram-baseline", "Instagram", "baseline"),
      snapshot("instagram-current", "Instagram", "current"),
      snapshot("spotify-baseline", "Spotify", "baseline"),
      snapshot("spotify-current", "Spotify", "current"),
    ]);
    setReport(null);
    setError(null);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const payload = {
        artist_name: artistName,
        campaign_title: campaignTitle,
        snapshots: rows
          .filter((row) => row.platform.trim())
          .map((row) => ({
            platform: row.platform.trim(),
            kind: row.kind,
            source_label: row.source_label.trim() || undefined,
            metrics: metricPayload(row),
          })),
        costs: parseNumber(costUsd) > 0 ? [{ label: "Campaign cost", amount_usd: parseNumber(costUsd) }] : [],
        artifacts: artifactTitle.trim() ? [{ title: artifactTitle.trim(), artifact_type: "campaign" }] : [],
      };
      const response = await fetch(`${getApiBase()}/api/creator-economy/resonance-report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setError(`HTTP ${response.status}: ${await response.text()}`);
        return;
      }
      setReport((await response.json()) as Report);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
      <form onSubmit={submit} className="space-y-6">
        <section className="rounded border border-stone-800 bg-stone-950/40 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm text-stone-300">
              Artist
              <input
                required
                value={artistName}
                onChange={(event) => setArtistName(event.target.value)}
                className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white outline-none focus:border-amber-500/50"
                placeholder="Artist name"
              />
            </label>
            <label className="space-y-2 text-sm text-stone-300">
              Campaign
              <input
                required
                value={campaignTitle}
                onChange={(event) => setCampaignTitle(event.target.value)}
                className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white outline-none focus:border-amber-500/50"
                placeholder="Single, drop, show, reel series"
              />
            </label>
            <label className="space-y-2 text-sm text-stone-300">
              Cost USD
              <input
                inputMode="decimal"
                value={costUsd}
                onChange={(event) => setCostUsd(event.target.value)}
                className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white outline-none focus:border-amber-500/50"
                placeholder="0"
              />
            </label>
            <label className="space-y-2 text-sm text-stone-300">
              Main artifact
              <input
                value={artifactTitle}
                onChange={(event) => setArtifactTitle(event.target.value)}
                className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white outline-none focus:border-amber-500/50"
                placeholder="Track, reel, clip, offer"
              />
            </label>
          </div>
        </section>

        <section className="space-y-4">
          {rows.map((row) => (
            <div key={row.id} className="rounded border border-stone-800 bg-stone-950/40 p-5">
              <div className="mb-4 grid gap-3 md:grid-cols-[1fr_140px_1fr]">
                <input
                  value={row.platform}
                  onChange={(event) =>
                    updateRow(row.id, (current) => ({ ...current, platform: event.target.value }))
                  }
                  className="rounded border border-stone-800 bg-stone-950 px-3 py-2 text-sm text-white outline-none focus:border-amber-500/50"
                  aria-label={`${row.id} platform`}
                />
                <select
                  value={row.kind}
                  onChange={(event) =>
                    updateRow(row.id, (current) => ({
                      ...current,
                      kind: event.target.value as SnapshotKind,
                    }))
                  }
                  className="rounded border border-stone-800 bg-stone-950 px-3 py-2 text-sm text-white outline-none focus:border-amber-500/50"
                  aria-label={`${row.id} snapshot kind`}
                >
                  <option value="baseline">Baseline</option>
                  <option value="current">Current</option>
                </select>
                <input
                  value={row.source_label}
                  onChange={(event) =>
                    updateRow(row.id, (current) => ({ ...current, source_label: event.target.value }))
                  }
                  className="rounded border border-stone-800 bg-stone-950 px-3 py-2 text-sm text-white outline-none focus:border-amber-500/50"
                  placeholder="Source label"
                  aria-label={`${row.id} source`}
                />
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                {METRICS.map((metric) => (
                  <label key={metric.key} className="space-y-1 text-xs text-stone-400">
                    {metric.label}
                    <input
                      inputMode="decimal"
                      value={row.metrics[metric.key]}
                      onChange={(event) =>
                        updateRow(row.id, (current) => ({
                          ...current,
                          metrics: { ...current.metrics, [metric.key]: event.target.value },
                        }))
                      }
                      className="w-full rounded border border-stone-800 bg-stone-950 px-2 py-1.5 text-sm text-white outline-none focus:border-amber-500/50"
                    />
                  </label>
                ))}
              </div>
            </div>
          ))}
        </section>

        {error && (
          <div className="rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={submitting || !hasMetrics}
            className="inline-flex min-h-11 items-center gap-2 rounded border border-amber-500/40 bg-amber-500/10 px-5 py-2 text-sm text-amber-100 transition-colors hover:bg-amber-500/20 disabled:opacity-50"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            {submitting ? "Building" : "Build report"}
          </button>
          <button
            type="button"
            onClick={reset}
            className="inline-flex min-h-11 items-center gap-2 rounded border border-stone-700 bg-stone-950 px-5 py-2 text-sm text-stone-200 transition-colors hover:border-stone-500"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Reset
          </button>
        </div>
      </form>

      <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
        <div className="rounded border border-stone-800 bg-stone-950/50 p-5">
          <div className="mb-4 flex items-center gap-2 text-stone-300">
            <BarChart3 className="h-4 w-4 text-amber-300" aria-hidden="true" />
            <span className="text-sm uppercase tracking-wide">Report</span>
          </div>
          {report ? (
            <div className="space-y-5">
              <div>
                <div className="text-3xl font-light text-white">
                  {(report.resonance_score * 100).toFixed(1)}
                </div>
                <div className="text-xs uppercase tracking-wide text-stone-500">
                  Resonance score
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <Metric label="Proof" value={report.proof_quality} />
                <Metric label="Confidence" value={`${(report.confidence * 100).toFixed(0)}%`} />
                <Metric label="Attention" value={formatNumber(report.attention_total)} />
                <Metric label="Engagement" value={formatNumber(report.engagement_total)} />
                <Metric label="Conversion" value={formatNumber(report.conversion_total)} />
                <Metric label="Income" value={`$${formatNumber(report.income_usd)}`} />
              </div>
              <div className="space-y-2">
                {report.dimensions.map((item) => (
                  <div key={item.name}>
                    <div className="mb-1 flex justify-between text-xs text-stone-400">
                      <span className="capitalize">{item.name}</span>
                      <span>{(item.score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded bg-stone-800">
                      <div
                        className="h-full bg-amber-400"
                        style={{ width: `${Math.min(100, item.score * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="rounded border border-stone-800 bg-stone-950 p-4">
                <div className="mb-1 text-xs uppercase tracking-wide text-stone-500">
                  Next execution
                </div>
                <div className="text-sm text-stone-200">
                  {report.answer.healthiest_next_execution}
                </div>
              </div>
              {report.recommendations.length > 0 && (
                <div className="space-y-3">
                  {report.recommendations.slice(0, 3).map((item) => (
                    <div key={`${item.priority}-${item.action}`} className="border-t border-stone-800 pt-3">
                      <div className="text-xs uppercase tracking-wide text-amber-300">
                        {item.priority}
                      </div>
                      <div className="mt-1 text-sm text-stone-200">{item.action}</div>
                      <div className="mt-1 text-xs text-stone-500">{item.expected_signal}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm leading-6 text-stone-400">
              Add platform snapshots and build a report. The result separates attention,
              engagement, conversion, relationship, income, and proof gaps.
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-stone-800 bg-stone-950 p-3">
      <div className="truncate text-white">{value}</div>
      <div className="mt-1 text-[10px] uppercase tracking-wide text-stone-500">
        {label}
      </div>
    </div>
  );
}
