/**
 * Assets commands: assets, asset
 */

import { get, post } from "../api.mjs";
import { truncateWords as truncate } from "../ui/ansi.mjs";

/** Truncate at word boundary, append "..." if needed */

/** Colored type badge */
function assetBadge(type) {
  if (!type) return "\x1b[2m[?]\x1b[0m".padEnd(16);
  const colors = { spec: "\x1b[36m", code: "\x1b[32m", doc: "\x1b[33m", test: "\x1b[35m", data: "\x1b[34m" };
  const color = colors[type.toLowerCase()] || "\x1b[2m";
  return `${color}[${type}]\x1b[0m`.padEnd(16);
}

export async function listAssets(args) {
  const limit = parseInt(args[0]) || 20;
  const raw = await get("/api/assets", { limit });
  const data = Array.isArray(raw) ? raw : (raw?.items || raw?.assets);
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch assets.");
    return;
  }
  if (data.length === 0) {
    console.log("No assets found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  ASSETS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(72)}`);
  for (const a of data) {
    const badge = assetBadge(a.type || a.asset_type);
    const desc = truncate(a.name || a.description || a.id, 42).padEnd(44);
    const cost = a.value != null ? String(a.value).padStart(8) : a.cost != null ? String(a.cost).padStart(8) : "";
    console.log(`  ${badge} ${desc} ${cost}`);
  }
  console.log();
}

export async function showAsset(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: coh asset <id>");
    return;
  }
  const data = await get(`/api/assets/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Asset '${id}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  ${data.name || data.id}\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.type || data.asset_type) console.log(`  Type:        ${data.type || data.asset_type}`);
  if (data.description) console.log(`  Description: ${truncate(data.description, 60)}`);
  if (data.value != null) console.log(`  Value:       ${data.value}`);
  if (data.created_at) console.log(`  Created:     ${data.created_at}`);
  console.log();
}

export async function createAsset(args) {
  const type = args[0];
  const desc = args.slice(1).join(" ");
  if (!type || !desc) {
    console.log("Usage: coh asset create <type> <description>");
    return;
  }
  const result = await post("/api/assets", {
    type,
    description: desc,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Asset created: ${result.id || "(new)"}`);
  } else {
    console.log("Failed to create asset.");
  }
}
