/**
 * Contributors commands: contributors, contributor
 */

import { get } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
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
  console.log(`  ${"─".repeat(60)}`);
  for (const c of data) {
    const name = truncate(c.name || c.display_name || c.id, 30);
    const cc = c.total_cc != null ? `${c.total_cc} CC` : "";
    console.log(`  ${name.padEnd(32)} ${cc}`);
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
    const desc = truncate(c.description || c.type || "?", 45);
    const cc = c.cc_amount != null ? `${c.cc_amount} CC` : "";
    console.log(`  ${desc.padEnd(47)} ${cc}`);
  }
  console.log();
}
