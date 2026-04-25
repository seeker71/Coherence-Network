/**
 * Friction commands: friction, friction events, friction categories
 */

import { get } from "../api.mjs";
import { truncateWords as truncate } from "../ui/ansi.mjs";

/** Truncate at word boundary, append "..." if needed */

export async function showFrictionReport() {
  const data = await get("/api/friction/report");
  if (!data) {
    console.log("Could not fetch friction report.");
    return;
  }

  const total = data.total_friction ?? data.total_events ?? data.event_count ?? 0;
  const days = data.period_days ?? data.days ?? 7;

  console.log();
  console.log(`\x1b[1m  FRICTION REPORT\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  \x1b[1m${total}\x1b[0m events in \x1b[1m${days}\x1b[0m days`);
  console.log();

  // Top block types as bar chart
  const blockTypes = data.top_block_types || data.top_types || [];
  if (Array.isArray(blockTypes) && blockTypes.length > 0) {
    console.log(`  \x1b[1mTop Block Types\x1b[0m`);
    const maxCount = Math.max(...blockTypes.map(b => b.count || 0), 1);
    for (const b of blockTypes.slice(0, 8)) {
      const name = (b.name || b.type || "?").padEnd(20);
      const count = b.count || 0;
      const barLen = Math.round((count / maxCount) * 20);
      const bar = "\x1b[33m" + "\u2593".repeat(barLen) + "\u2591".repeat(20 - barLen) + "\x1b[0m";
      console.log(`  ${name} ${bar} ${String(count).padStart(5)}`);
    }
    console.log();
  }

  // Top categories/stages as colored list
  const categories = data.top_categories || data.top_stages || [];
  if (Array.isArray(categories) && categories.length > 0) {
    console.log(`  \x1b[1mTop Stages\x1b[0m`);
    const stageColors = ["\x1b[31m", "\x1b[33m", "\x1b[36m", "\x1b[32m", "\x1b[35m"];
    categories.forEach((c, i) => {
      const name = c.name || c.category || c.stage || "?";
      const count = c.count != null ? c.count : "?";
      const color = stageColors[i % stageColors.length];
      console.log(`  ${color}●\x1b[0m ${name.padEnd(25)} ${String(count).padStart(5)}`);
    });
    console.log();
  }

  // Remaining keys (excluding already shown)
  const shown = new Set(["total_friction", "total_events", "event_count", "period_days", "days", "top_categories", "top_stages", "top_block_types", "top_types"]);
  for (const [key, val] of Object.entries(data)) {
    if (!shown.has(key) && val != null) {
      if (typeof val === "object") {
        console.log(`  \x1b[2m${key}:\x1b[0m ${JSON.stringify(val)}`);
      } else {
        console.log(`  \x1b[2m${key}:\x1b[0m ${val}`);
      }
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
