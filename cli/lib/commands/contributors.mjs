/**
 * Contributors commands: contributors, contributor
 */

import { get } from "../api.mjs";
import { truncateWords as truncate } from "../ui/ansi.mjs";

/** Truncate at word boundary, append "..." if needed */

/** Colored type badge */
function typeBadge(type) {
  if (!type) return "\x1b[2m[?]\x1b[0m".padEnd(17);
  const upper = type.toUpperCase();
  if (upper === "HUMAN") return "\x1b[36m[HUMAN]\x1b[0m".padEnd(18);
  if (upper === "AGENT") return "\x1b[33m[AGENT]\x1b[0m".padEnd(18);
  return `\x1b[2m[${upper}]\x1b[0m`.padEnd(18);
}

export async function listContributors(args) {
  const limit = parseInt(args[0]) || 20;
  const raw = await get("/api/contributors", { limit });
  const data = Array.isArray(raw) ? raw : (raw?.items || raw?.contributors);
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch contributors.");
    return;
  }
  if (data.length === 0) {
    console.log("No contributors found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  CONTRIBUTORS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const c of data) {
    const name = truncate(c.name || c.display_name || c.id, 30).padEnd(32);
    const badge = typeBadge(c.type || c.role);
    const cc = c.total_cc != null ? String(c.total_cc.toFixed ? c.total_cc.toFixed(1) : c.total_cc).padStart(8) + " CC" : "";
    console.log(`  ${name} ${badge} ${cc}`);
  }
  console.log();
}

export async function showContributor(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc contributor <id>");
    return;
  }
  const data = await get(`/api/contributors/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Contributor '${id}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  ${data.name || data.display_name || data.id}\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.id) console.log(`  ID:          ${data.id}`);
  if (data.total_cc != null) console.log(`  Total CC:    ${data.total_cc}`);
  if (data.role) console.log(`  Role:        ${data.role}`);
  if (data.joined_at) console.log(`  Joined:      ${data.joined_at}`);
  console.log();
}

export async function showContributions(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc contributor <id> contributions");
    return;
  }
  const data = await get(`/api/contributors/${encodeURIComponent(id)}/contributions`);
  const list = Array.isArray(data) ? data : data?.contributions;
  if (!list || !Array.isArray(list)) {
    console.log(`No contributions found for '${id}'.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  CONTRIBUTIONS\x1b[0m for ${id} (${list.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const c of list) {
    const desc = truncate(
      c.description
        || c.metadata?.description
        || c.metadata?.summary
        || c.metadata?.type
        || c.type
        || "Contribution",
      45,
    );
    const amount = c.cost_amount ?? c.cc_amount ?? null;
    const cc = amount != null ? `${amount} CC` : "";
    console.log(`  ${desc.padEnd(47)} ${cc}`);
  }
  console.log();
}
