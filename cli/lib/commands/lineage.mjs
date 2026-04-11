/**
 * Lineage commands: lineage, lineage valuation, lineage payout
 */

import { get, post } from "../api.mjs";
import { truncateWords as truncate } from "../ui/ansi.mjs";

/** Truncate at word boundary, append "..." if needed */

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
  console.log(`  ${"─".repeat(74)}`);
  for (const link of data) {
    const ideaId = truncate(link.idea_id || link.from_id || link.source || "?", 18).padEnd(20);
    const specId = truncate(link.spec_id || link.to_id || link.target || "?", 18).padEnd(20);
    const contributor = truncate(link.contributor || link.contributor_id || "", 14).padEnd(16);
    const cost = link.estimated_cost != null ? String(link.estimated_cost.toFixed ? link.estimated_cost.toFixed(1) : link.estimated_cost).padStart(7)
      : link.weight != null ? String(link.weight.toFixed(2)).padStart(7) : "";
    console.log(`  ${ideaId} \x1b[2m->\x1b[0m ${specId} \x1b[2m${contributor}\x1b[0m ${cost}`);
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
