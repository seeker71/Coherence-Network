/**
 * Assets commands: assets, asset
 */

import { get, post } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function listAssets(args) {
  const limit = parseInt(args[0]) || 20;
  const raw = await get("/api/assets", { limit });
  const data = Array.isArray(raw) ? raw : raw?.assets;
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
  console.log(`  ${"─".repeat(60)}`);
  for (const a of data) {
    const name = truncate(a.name || a.description || a.id, 35);
    const type = (a.type || a.asset_type || "").padEnd(12);
    console.log(`  ${type} ${name}`);
  }
  console.log();
}

export async function showAsset(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc asset <id>");
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
    console.log("Usage: cc asset create <type> <description>");
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
