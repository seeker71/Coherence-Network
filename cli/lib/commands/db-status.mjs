/**
 * cc db-status — row counts and growth from GET /api/data-health
 */

import { get } from "../api.mjs";

function parseArgs(argv) {
  const json = argv.includes("--json");
  return { json };
}

export async function dbStatus(argv) {
  const { json } = parseArgs(argv);
  const data = await get("/api/data-health");
  if (!data) {
    if (json) {
      console.log(JSON.stringify({ error: "data_health_unavailable", message: "API returned no data (check COHERENCE_API_URL / network)" }));
    } else {
      console.error("Could not load /api/data-health. Set COHERENCE_API_URL and ensure the API is reachable.");
    }
    process.exitCode = 1;
    return;
  }
  if (json) {
    console.log(JSON.stringify(data, null, 2));
    return;
  }
  const B = "\x1b[1m", R = "\x1b[0m", D = "\x1b[2m";
  console.log(`\n${B}  DATABASE STATUS${R}  ${D}(from API)${R}`);
  console.log(`  ${"─".repeat(56)}`);
  console.log(`  ${D}kind:${R} ${data.database_kind || "?"}  ${D}health_score:${R} ${data.health_score ?? "?"}`);
  if (data.last_snapshot_at) {
    console.log(`  ${D}last snapshot:${R} ${data.last_snapshot_at}`);
  }
  if (data.snapshot_stale_hours != null && data.snapshot_stale_hours > 48) {
    console.log(`  ${D}stale:${R} snapshot is ${data.snapshot_stale_hours.toFixed(1)}h old`);
  }
  console.log();
  const tables = data.tables || [];
  for (const t of tables) {
    const prev = t.previous_row_count != null ? t.previous_row_count : "—";
    const delta = t.delta_24h != null ? t.delta_24h : "—";
    const pct = t.pct_change_24h != null ? `${t.pct_change_24h}%` : "—";
    const age = t.previous_snapshot_at ? `(ref ${t.previous_snapshot_at})` : "";
    console.log(`  ${B}${t.name}${R}  rows=${t.row_count}  ${D}vs 24h ref:${R} ${prev}  Δ=${delta}  ${pct}  ${age}`);
    console.log(`    status: ${t.status}`);
  }
  if (data.investigation_hints?.length) {
    console.log(`\n  ${B}Hints${R}`);
    for (const h of data.investigation_hints) {
      console.log(`    • ${h}`);
    }
  }
  if (data.open_friction_ids?.length) {
    console.log(`\n  ${B}Open friction (data growth)${R}: ${data.open_friction_ids.join(", ")}`);
  }
  console.log();
}
