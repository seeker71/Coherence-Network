/**
 * Providers commands: providers, providers stats
 */

import { get } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
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
  console.log(`  ${"─".repeat(50)}`);
  for (const p of data) {
    const name = truncate(p.name || p.id || "?", 30);
    const type = (p.type || p.category || "").padEnd(15);
    console.log(`  ${type} ${name}`);
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
  console.log(`  ${"─".repeat(50)}`);
  if (Array.isArray(data)) {
    for (const p of data) {
      const name = (p.name || p.provider || "?").padEnd(20);
      const count = p.count != null ? `${p.count} uses` : "";
      console.log(`  ${name} ${count}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}
