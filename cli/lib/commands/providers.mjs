/**
 * Providers commands: providers, providers stats
 */

import { get } from "../api.mjs";

/** Truncate at word boundary, append "..." if needed */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const trimmed = str.slice(0, len - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > len * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
}

/** Mini bar for success rate */
function rateBar(rate, width = 10) {
  const pct = Math.max(0, Math.min(1, rate));
  const filled = Math.round(pct * width);
  const color = pct >= 0.9 ? "\x1b[32m" : pct >= 0.7 ? "\x1b[33m" : "\x1b[31m";
  return `${color}${"\u2593".repeat(filled)}${"\u2591".repeat(width - filled)}\x1b[0m`;
}

export async function listProviders() {
  const raw = await get("/api/providers");
  const data = Array.isArray(raw) ? raw : raw?.providers;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch providers.");
    return;
  }
  if (data.length === 0) {
    console.log("No providers found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  PROVIDERS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const p of data) {
    const name = truncate(p.name || p.id || "?", 22).padEnd(24);
    const successRate = p.success_rate ?? p.rate ?? null;
    const samples = p.sample_count ?? p.count ?? p.total ?? null;

    let rateStr = "";
    if (successRate != null) {
      const pct = (successRate * 100).toFixed(0);
      rateStr = `${rateBar(successRate)} ${pct}%`.padEnd(22);
    } else {
      rateStr = "\x1b[2m-\x1b[0m".padEnd(22);
    }

    const sampleStr = samples != null ? `\x1b[2m${String(samples).padStart(5)} samples\x1b[0m` : "";
    console.log(`  ${name} ${rateStr} ${sampleStr}`);
  }
  console.log();
}

export async function showProviderStats() {
  const data = await get("/api/federation/nodes/stats");
  if (!data) {
    console.log("Could not fetch provider stats.");
    return;
  }

  const providers = data.providers || {};
  const alerts = data.alerts || [];
  const native = ["claude", "codex", "cursor", "gemini", "ollama-local", "ollama-cloud", "openrouter"];

  console.log();
  console.log(`\x1b[1m  PROVIDER STATS\x1b[0m (${data.window_days || 7}d window)`);
  console.log(`  ${"─".repeat(72)}`);
  console.log(`  ${"Provider".padEnd(28)} ${"Rate".padEnd(18)} ${"Samples".padStart(8)} ${"Avg".padStart(6)}`);
  console.log(`  ${"─".repeat(72)}`);

  for (const name of native) {
    const stats = providers[name];
    if (!stats) continue;
    const rate = stats.overall_success_rate ?? 0;
    const pct = (rate * 100).toFixed(0);
    const bar = rateBar(rate, 8);
    const samples = String(stats.total_samples || 0).padStart(8);
    const avg = stats.avg_duration_s ? `${stats.avg_duration_s.toFixed(0)}s`.padStart(6) : "    -";
    console.log(`  ${name.padEnd(28)} ${bar} ${pct.padStart(3)}%    ${samples} ${avg}`);

    for (const [mName, mStats] of Object.entries(providers)) {
      if (mName.startsWith(name + "/") || (name === "cursor" && mName.startsWith("claude-4.6")) || (name === "codex" && mName.startsWith("gpt-5."))) {
        const mRate = mStats.overall_success_rate ?? 0;
        const mPct = (mRate * 100).toFixed(0);
        const mBar = rateBar(mRate, 8);
        const mSamples = String(mStats.total_samples || 0).padStart(8);
        const mAvg = mStats.avg_duration_s ? `${mStats.avg_duration_s.toFixed(0)}s`.padStart(6) : "    -";
        console.log(`    \x1b[2m\u2514 ${mName.padEnd(26)}\x1b[0m ${mBar} ${mPct.padStart(3)}%    ${mSamples} ${mAvg}`);
      }
    }
  }

  if (alerts.length > 0) {
    console.log();
    console.log(`  \x1b[1mAlerts\x1b[0m`);
    for (const a of alerts) {
      console.log(`  \x1b[31m!\x1b[0m ${a.message || a.provider}`);
    }
  }
  console.log();
}
