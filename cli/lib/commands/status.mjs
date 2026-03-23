/**
 * Status commands: status, resonance
 */

import { get } from "../api.mjs";
import { getContributorId, getHubUrl } from "../config.mjs";
import { hostname } from "node:os";

export async function showStatus() {
  const health = await get("/api/health");
  const ideas = await get("/api/ideas/count");
  const nodes = await get("/api/federation/nodes");

  console.log();
  console.log("\x1b[1m  COHERENCE NETWORK STATUS\x1b[0m");
  console.log(`  ${"─".repeat(40)}`);

  if (health) {
    console.log(`  API:        \x1b[32m${health.status}\x1b[0m (${health.version || "?"})`);
    console.log(`  Uptime:     ${health.uptime_human || "?"}`);
  } else {
    console.log(`  API:        \x1b[31moffline\x1b[0m`);
  }

  console.log(`  Hub:        ${getHubUrl()}`);
  console.log(`  Node:       ${hostname()}`);
  console.log(`  Identity:   ${getContributorId() || "(not set — run: cc identity setup)"}`);

  if (ideas?.count != null) {
    console.log(`  Ideas:      ${ideas.count}`);
  }

  if (Array.isArray(nodes) && nodes.length > 0) {
    console.log(`  Fed. Nodes: ${nodes.length}`);
  }

  console.log();
}

export async function showResonance() {
  const data = await get("/api/ideas/resonance");
  if (!data) {
    console.log("Could not fetch resonance.");
    return;
  }
  console.log();
  console.log("\x1b[1m  RESONANCE\x1b[0m — what's alive right now");
  console.log(`  ${"─".repeat(40)}`);
  if (Array.isArray(data)) {
    for (const item of data.slice(0, 10)) {
      const name = item.name || item.idea_id || item.id || "?";
      console.log(`  \x1b[33m~\x1b[0m ${name}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}
