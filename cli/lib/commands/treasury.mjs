/**
 * Treasury commands: treasury, treasury deposits, treasury deposit
 */

import { get, post } from "../api.mjs";

export async function showTreasury() {
  const data = await get("/api/treasury");
  if (!data) {
    console.log("Could not fetch treasury.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  TREASURY\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.total != null) console.log(`  Total:       ${data.total}`);
  if (data.balance != null) console.log(`  Balance:     ${data.balance}`);
  if (data.deposits_count != null) console.log(`  Deposits:    ${data.deposits_count}`);
  if (data.last_updated) console.log(`  Updated:     ${data.last_updated}`);
  // Fallback: print all keys
  const shown = new Set(["total", "balance", "deposits_count", "last_updated"]);
  for (const [key, val] of Object.entries(data)) {
    if (!shown.has(key) && val != null) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}

export async function showDeposits(args) {
  const contributor = args[0];
  if (!contributor) {
    console.log("Usage: cc treasury deposits <contributor-id>");
    return;
  }
  const data = await get(`/api/treasury/deposits/${encodeURIComponent(contributor)}`);
  const deposits = Array.isArray(data) ? data : data?.deposits;
  if (!deposits || !Array.isArray(deposits)) {
    console.log(`No deposits found for '${contributor}'.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  DEPOSITS\x1b[0m for ${contributor} (${deposits.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const d of deposits) {
    const amount = d.amount != null ? `${d.amount}` : "?";
    const asset = d.asset || d.asset_type || "";
    const date = d.created_at ? d.created_at.slice(0, 10) : "";
    console.log(`  ${amount.padEnd(12)} ${asset.padEnd(15)} ${date}`);
  }
  console.log();
}

export async function makeDeposit(args) {
  const amount = parseFloat(args[0]);
  const asset = args[1];
  if (isNaN(amount) || !asset) {
    console.log("Usage: cc treasury deposit <amount> <asset>");
    return;
  }
  const result = await post("/api/treasury/deposit", { amount, asset });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Deposited ${amount} ${asset}`);
  } else {
    console.log("Deposit failed.");
  }
}
