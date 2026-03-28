/**
 * Data hygiene commands: db-status, db-status investigate
 */

import { get } from "../api.mjs";

function pad(str, len) {
  return String(str).padEnd(len);
}

function rpad(str, len) {
  return String(str).padStart(len);
}

function formatCount(n) {
  return n.toLocaleString("en-US");
}

export async function showDbStatus(args) {
  const sub = args[0];
  if (sub === "investigate") {
    const target = args[1] || "runtime-events";
    return investigateTable(target);
  }

  const data = await get("/api/db-status");
  if (!data) {
    console.error("  Could not reach /api/db-status — API may be down.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  DATABASE STATUS\x1b[0m  \x1b[2m${data.generated_at}\x1b[0m`);
  console.log(`  ${"─".repeat(62)}`);

  const TABLE_W = 30;
  const COUNT_W = 12;
  const MAX_W  = 12;
  const ALERT_W = 8;

  console.log(
    `  ${pad("Table", TABLE_W)}  ${rpad("Rows", COUNT_W)}  ${rpad("Max/day", MAX_W)}  ${pad("Alert", ALERT_W)}`
  );
  console.log(`  ${"─".repeat(62)}`);

  for (const t of data.tables) {
    if (!t.exists) {
      console.log(
        `  \x1b[2m${pad(t.table, TABLE_W)}\x1b[0m  ${rpad("—", COUNT_W)}  ${rpad("—", MAX_W)}  \x1b[2mmissing\x1b[0m`
      );
      continue;
    }

    const alertStr = t.alert
      ? `\x1b[33m⚠ ALERT\x1b[0m`
      : `\x1b[32m✓ ok\x1b[0m`;

    const countStr = t.alert
      ? `\x1b[33m${rpad(formatCount(t.row_count), COUNT_W)}\x1b[0m`
      : rpad(formatCount(t.row_count), COUNT_W);

    const maxStr = t.expected_max_daily != null
      ? rpad(formatCount(t.expected_max_daily), MAX_W)
      : rpad("—", MAX_W);

    console.log(
      `  ${pad(t.table, TABLE_W)}  ${countStr}  ${maxStr}  ${alertStr}`
    );

    if (t.alert && t.alert_reason) {
      console.log(`    \x1b[33m↳ ${t.alert_reason}\x1b[0m`);
    }
  }

  console.log(`  ${"─".repeat(62)}`);
  console.log(`  Total rows: \x1b[1m${formatCount(data.total_rows)}\x1b[0m`);

  if (data.alert_count > 0) {
    console.log();
    console.log(`  \x1b[33m⚠ ${data.alert_count} alert(s) detected\x1b[0m`);
    console.log(`  Run \x1b[1mcc db-status investigate runtime-events\x1b[0m for detailed breakdown`);
  } else {
    console.log(`  \x1b[32m✓ No anomalies detected\x1b[0m`);
  }
  console.log();
}

async function investigateTable(target) {
  const path = `/api/db-status/investigate/${target}`;
  const data = await get(path);
  if (!data) {
    console.error(`  Could not reach ${path} — API may be down.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  INVESTIGATION: ${data.table || target}\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);

  if (data.row_count !== undefined) {
    console.log(`  Total rows: \x1b[1m${formatCount(data.row_count)}\x1b[0m`);
  }

  if (data.investigation) {
    const inv = data.investigation;

    if (Array.isArray(inv.by_event_type)) {
      console.log();
      console.log(`  \x1b[1mBy event type:\x1b[0m`);
      for (const row of inv.by_event_type) {
        console.log(`    ${pad(row.event_type || "(null)", 35)} ${rpad(formatCount(row.count), 10)}`);
      }
    } else if (typeof inv.by_event_type === "string") {
      console.log(`  by_event_type: \x1b[2m${inv.by_event_type}\x1b[0m`);
    }

    if (inv.by_age && typeof inv.by_age === "object") {
      console.log();
      console.log(`  \x1b[1mBy age:\x1b[0m`);
      for (const [bucket, count] of Object.entries(inv.by_age)) {
        console.log(`    ${pad(bucket, 15)} ${rpad(formatCount(count), 10)}`);
      }
    }
  }

  if (data.error) {
    console.log(`  \x1b[31mError: ${data.error}\x1b[0m`);
  }

  console.log();
}
