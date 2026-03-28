/**
 * Lineage commands: lineage, lineage valuation, lineage payout
 */

import { get, post } from "../api.mjs";

/** Truncate at word boundary, append "..." if needed */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const trimmed = str.slice(0, len - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > len * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
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

/**
 * Create a new lineage link between an idea and a spec.
 * Usage: cc lineage create <idea-id> <spec-id> [contributor] [weight]
 */
export async function createLink(args) {
  const [ideaId, specId, contributor, weightStr] = args;
  if (!ideaId || !specId) {
    console.log("Usage: cc lineage create <idea-id> <spec-id> [contributor] [weight]");
    return;
  }
  const payload = { idea_id: ideaId, spec_id: specId };
  if (contributor) payload.contributor = contributor;
  if (weightStr) payload.weight = parseFloat(weightStr);

  const result = await post("/api/value-lineage/links", payload);
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Lineage link created: ${result.id || `${ideaId} → ${specId}`}`);
  } else {
    console.log("Failed to create lineage link.");
  }
}

/**
 * Record a usage event on a lineage link.
 * Usage: cc lineage usage <link-id> <event-type> [amount]
 */
export async function addUsageEvent(args) {
  const [linkId, eventType, amountStr] = args;
  if (!linkId || !eventType) {
    console.log("Usage: cc lineage usage <link-id> <event-type> [amount]");
    return;
  }
  const payload = { event_type: eventType };
  if (amountStr) payload.amount = parseFloat(amountStr);

  const result = await post(`/api/value-lineage/links/${encodeURIComponent(linkId)}/usage`, payload);
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Usage event recorded: ${result.id || eventType}`);
  } else {
    console.log("Failed to record usage event.");
  }
}

/**
 * Run the minimum end-to-end value flow.
 * Verifies the full lineage pipeline is operational.
 * Usage: cc lineage e2e
 */
export async function runMinimumE2EFlow() {
  console.log("Running minimum E2E value flow...");
  const result = await post("/api/value-lineage/minimum-e2e-flow", {});
  if (!result) {
    console.log("\x1b[31m✗\x1b[0m E2E flow failed.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", RED = "\x1b[31m";
  console.log();
  console.log(`${B}  E2E FLOW RESULT${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const ok = result.success ?? result.passed ?? true;
  console.log(`  Status:  ${ok ? G + "✓ passed" + R : RED + "✗ failed" + R}`);
  for (const [k, v] of Object.entries(result)) {
    if (k === "success" || k === "passed") continue;
    if (v != null) {
      const display = typeof v === "object" ? JSON.stringify(v).slice(0, 70) : String(v);
      console.log(`  ${k.padEnd(20)} ${display}`);
    }
  }
  console.log();
}
