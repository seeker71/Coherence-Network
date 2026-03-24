/**
 * Lineage commands: lineage, lineage valuation, lineage payout
 */

import { get, post } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function listLinks(args) {
  const limit = parseInt(args[0]) || 20;
  const raw = await get("/api/value-lineage/links", { limit });
  const data = Array.isArray(raw) ? raw : raw?.links;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch lineage links.");
    return;
  }
  if (data.length === 0) {
    console.log("No lineage links found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  VALUE LINEAGE\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const link of data) {
    const from = truncate(link.from_id || link.source || "?", 20);
    const to = truncate(link.to_id || link.target || "?", 20);
    const weight = link.weight != null ? `w=${link.weight.toFixed(2)}` : "";
    console.log(`  ${from.padEnd(22)} \x1b[2m→\x1b[0m ${to.padEnd(22)} ${weight}`);
  }
  console.log();
}

export async function showLink(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc lineage <id>");
    return;
  }
  const data = await get(`/api/value-lineage/links/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Link '${id}' not found.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  LINEAGE LINK\x1b[0m ${data.id || id}`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.from_id || data.source) console.log(`  From:        ${data.from_id || data.source}`);
  if (data.to_id || data.target) console.log(`  To:          ${data.to_id || data.target}`);
  if (data.weight != null) console.log(`  Weight:      ${data.weight}`);
  if (data.type) console.log(`  Type:        ${data.type}`);
  if (data.created_at) console.log(`  Created:     ${data.created_at}`);
  console.log();
}

export async function showValuation(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc lineage <id> valuation");
    return;
  }
  const data = await get(`/api/value-lineage/links/${encodeURIComponent(id)}/valuation`);
  if (!data) {
    console.log(`No valuation for link '${id}'.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  VALUATION\x1b[0m for ${id}`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

export async function payoutPreview(args) {
  const id = args[0];
  const amount = parseFloat(args[1]);
  if (!id || isNaN(amount)) {
    console.log("Usage: cc lineage <id> payout <amount>");
    return;
  }
  const data = await post(`/api/value-lineage/links/${encodeURIComponent(id)}/payout-preview`, { amount });
  if (!data) {
    console.log("Payout preview failed.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  PAYOUT PREVIEW\x1b[0m for ${id}`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}
