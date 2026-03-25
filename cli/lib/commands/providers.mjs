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
  const data = await get("/api/providers/stats");
  if (!data) {
    console.log("Could not fetch provider stats.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  PROVIDER STATS\x1b[0m`);
  console.log(`  ${"─".repeat(68)}`);
  if (Array.isArray(data)) {
    for (const p of data) {
      const name = (p.name || p.provider || "?").padEnd(22);
      const successRate = p.success_rate ?? p.rate ?? null;
      const count = p.count ?? p.total ?? null;

      let rateStr = "";
      if (successRate != null) {
        const pct = (successRate * 100).toFixed(0);
        rateStr = `${rateBar(successRate)} ${pct}%`.padEnd(22);
      }

      const countStr = count != null ? `${String(count).padStart(6)} uses` : "";
      console.log(`  ${name} ${rateStr} ${countStr}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      const name = key.padEnd(22);
      if (typeof val === "object" && val != null) {
        const successRate = val.success_rate ?? val.rate ?? null;
        const count = val.count ?? val.total ?? null;
        let rateStr = "";
        if (successRate != null) {
          const pct = (successRate * 100).toFixed(0);
          rateStr = `${rateBar(successRate)} ${pct}%`.padEnd(22);
        }
        const countStr = count != null ? `${String(count).padStart(6)} uses` : "";
        console.log(`  ${name} ${rateStr} ${countStr}`);
      } else {
        console.log(`  ${name} ${val}`);
      }
    }
  }
  console.log();
}
