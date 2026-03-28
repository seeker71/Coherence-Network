/**
 * cc db-status — database row counts and growth (data hygiene API).
 */

import { get } from "../api.mjs";

function fmt(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return String(n);
}

export async function showDbStatus(args) {
  const jsonMode = args.includes("--json");
  const record = args.includes("--record");
  const params = { record: record ? "true" : "false" };
  const data = await get("/api/data-hygiene/status", params);
  if (!data) {
    console.error("Could not fetch /api/data-hygiene/status (check API URL and auth).");
    process.exitCode = 1;
    return;
  }

  if (jsonMode) {
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  const B = "\x1b[1m";
  const R = "\x1b[0m";
  const D = "\x1b[2m";
  const Y = "\x1b[33m";
  const G = "\x1b[32m";
  const M = "\x1b[31m";

  console.log();
  console.log(`${B}  DATABASE STATUS (row counts & growth)${R}`);
  console.log(`  ${"─".repeat(58)}`);
  console.log(`  ${D}captured_at:${R} ${data.captured_at || "?"}`);
  const health = data.meta?.health ?? "?";
  const hColor = health === "ok" ? G : health === "degraded" ? Y : M;
  console.log(`  ${D}health:${R}       ${hColor}${health}${R}`);
  if (data.meta?.insufficient_history) {
    console.log(`  ${D}note:${R}         first samples not yet recorded — run ${B}cc db-status --record${R} twice.`);
  }
  console.log();

  const tables = Array.isArray(data.tables) ? data.tables : [];
  for (const t of tables) {
    const k = t.key || t.sql_table;
    console.log(`  ${B}${k}${R}`);
    console.log(`    rows:     ${fmt(t.row_count)}`);
    if (t.previous_count != null) {
      console.log(`    previous: ${fmt(t.previous_count)} @ ${t.previous_captured_at || "?"}`);
      console.log(`    delta:    ${fmt(t.delta_rows)}  (${fmt(t.growth_pct_vs_previous)}% vs sample)`);
      console.log(`    rate:     ${fmt(t.growth_rows_per_hour)} rows/h over ${fmt(t.hours_since_previous)} h`);
    }
    if (t.description) console.log(`    ${D}${t.description}${R}`);
    console.log();
  }

  const alerts = Array.isArray(data.alerts) ? data.alerts : [];
  if (alerts.length > 0) {
    console.log(`  ${B}Alerts${R}`);
    for (const a of alerts) {
      const sev = a.severity || "warning";
      const col = sev === "critical" ? M : Y;
      console.log(`    ${col}[${sev}]${R} ${a.message || JSON.stringify(a)}`);
    }
    console.log();
  }

  console.log(`  ${D}Tip: cc db-status --json   ${R}|   ${D}cc db-status --record${R} (persist sample)`);
  console.log();
}
