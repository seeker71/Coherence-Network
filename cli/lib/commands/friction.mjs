/**
 * Friction commands: friction, friction events, friction categories
 */

import { get } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function showFrictionReport() {
  const data = await get("/api/friction/report");
  if (!data) {
    console.log("Could not fetch friction report.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  FRICTION REPORT\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.total_friction != null) console.log(`  Total:       ${data.total_friction}`);
  if (data.top_categories && Array.isArray(data.top_categories)) {
    console.log(`  Top categories:`);
    for (const c of data.top_categories) {
      const name = c.name || c.category || "?";
      const count = c.count != null ? c.count : "?";
      console.log(`    ${name.padEnd(25)} ${count}`);
    }
  }
  // Fallback: print all keys
  const shown = new Set(["total_friction", "top_categories"]);
  for (const [key, val] of Object.entries(data)) {
    if (!shown.has(key) && val != null) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}

export async function listFrictionEvents(args) {
  const limit = parseInt(args[0]) || 20;
  const raw = await get("/api/friction/events", { limit });
  const data = Array.isArray(raw) ? raw : raw?.events;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch friction events.");
    return;
  }
  if (data.length === 0) {
    console.log("No friction events found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  FRICTION EVENTS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const e of data) {
    const desc = truncate(e.description || e.type || e.id || "?", 45);
    const category = (e.category || "").padEnd(15);
    console.log(`  ${category} ${desc}`);
  }
  console.log();
}

export async function showFrictionCategories() {
  const raw = await get("/api/friction/categories");
  const data = Array.isArray(raw) ? raw : raw?.categories;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch friction categories.");
    return;
  }
  if (data.length === 0) {
    console.log("No friction categories found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  FRICTION CATEGORIES\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(50)}`);
  for (const c of data) {
    const name = typeof c === "string" ? c : c.name || c.category || "?";
    const count = typeof c === "object" && c.count != null ? `(${c.count})` : "";
    console.log(`  ${name} ${count}`);
  }
  console.log();
}
