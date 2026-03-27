/**
 * Investment UX: invest with ROI preview, portfolio, history, time commitment.
 */

import { get, post } from "../api.mjs";
import { ensureIdentity } from "../identity.mjs";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  return str.slice(0, len - 2) + "..";
}

export async function investCommand(args) {
  const sub = args[0];
  if (sub === "portfolio") return showPortfolio();
  if (sub === "history") return showHistory();
  if (sub === "time") return timeInvest(args.slice(1));

  const ideaId = args[0];
  const amount = parseFloat(args[1]);
  const autoYes = args.includes("--yes");

  if (!ideaId || Number.isNaN(amount) || amount <= 0) {
    console.log("Usage: cc invest <idea-id> <amount-cc> [--yes]");
    console.log("       cc invest portfolio");
    console.log("       cc invest history");
    console.log("       cc invest time <idea-id> <hours> --commit <review|implement>");
    return;
  }

  const preview = await get("/api/investments/preview", {
    idea_id: ideaId,
    amount_cc: amount,
  });
  if (!preview) {
    console.log("Could not load investment preview (idea missing or network error).");
    return;
  }

  console.log();
  console.log(`  \x1b[1mConfirm investment\x1b[0m`);
  console.log(`  ${"─".repeat(56)}`);
  console.log(`  Idea:     ${truncate(preview.idea_name || ideaId, 48)}`);
  console.log(`  Stake:    ${amount} CC`);
  console.log(`  ROI (×):  ${preview.roi_cc != null ? preview.roi_cc.toFixed(4) : "?"}`);
  console.log(`  Projected return:  ${preview.projected_return_cc} CC`);
  console.log(`  Projected value:   ${preview.projected_value_cc} CC`);
  console.log(`  ${"─".repeat(56)}`);

  if (!autoYes) {
    const rl = createInterface({ input: stdin, output: stdout });
    const ans = (await rl.question("  Proceed with stake? [y/N] > ")).trim().toLowerCase();
    rl.close();
    if (ans !== "y" && ans !== "yes") {
      console.log("  Cancelled.");
      return;
    }
  }

  const contributor = await ensureIdentity();
  const result = await post(`/api/ideas/${encodeURIComponent(ideaId)}/stake`, {
    contributor_id: contributor,
    amount_cc: amount,
    rationale: `Invest CLI — projected ${preview.projected_return_cc} CC return`,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Invested ${amount} CC on '${ideaId}'`);
  } else {
    console.log("Investment (stake) failed.");
  }
}

async function showPortfolio() {
  const contributor = await ensureIdentity();
  const data = await get("/api/investments/portfolio", { contributor_id: contributor });
  if (!data?.positions) {
    console.log("Could not load portfolio.");
    return;
  }
  console.log();
  console.log(`\x1b[1m  PORTFOLIO\x1b[0m  (${contributor})`);
  console.log(`  ${"─".repeat(72)}`);
  if (data.positions.length === 0) {
    console.log("  No staked positions yet.");
  } else {
    for (const p of data.positions) {
      const name = truncate(p.idea_name || p.idea_id, 40).padEnd(42);
      const st = String(p.staked_cc ?? 0).padStart(8);
      const mark = String(p.current_value_cc ?? 0).padStart(10);
      const th = p.time_hours_committed > 0 ? `  time:${p.time_hours_committed}h` : "";
      console.log(`  ${name}  staked ${st} CC  value≈${mark} CC${th}`);
    }
  }
  if (data.totals) {
    console.log(`  ${"─".repeat(72)}`);
    console.log(
      `  Total staked: ${data.totals.staked_cc} CC   Est. mark: ${data.totals.estimated_mark_value_cc} CC`,
    );
  }
  console.log();
}

async function showHistory() {
  const contributor = await ensureIdentity();
  const data = await get("/api/investments/flow", { contributor_id: contributor });
  if (!data?.edges) {
    console.log("Could not load flow history.");
    return;
  }
  console.log();
  console.log(`\x1b[1m  INVESTMENT FLOW\x1b[0m  (${contributor})`);
  console.log(`  ${"─".repeat(72)}`);
  const edges = [...data.edges].slice(-24);
  for (const e of edges) {
    const tgt = e.target === "_network" ? "·network·" : truncate(e.target, 28);
    const k = (e.kind || "?").padEnd(14);
    const amt = e.amount_cc != null ? `${e.amount_cc} CC` : "";
    const h = e.hours != null ? `  ${e.hours}h ${e.commitment || ""}` : "";
    console.log(`  ${k}  → ${tgt.padEnd(30)}  ${amt}${h}`);
  }
  console.log();
}

async function timeInvest(args) {
  const ideaId = args[0];
  const hours = parseFloat(args[1]);
  let commitment = "review";
  const ci = args.indexOf("--commit");
  if (ci >= 0 && args[ci + 1]) commitment = args[ci + 1];
  if (!ideaId || Number.isNaN(hours) || hours <= 0) {
    console.log("Usage: cc invest time <idea-id> <hours> --commit <review|implement>");
    return;
  }
  if (commitment !== "review" && commitment !== "implement") {
    console.log("--commit must be review or implement");
    return;
  }
  const contributor = await ensureIdentity();
  const result = await post(`/api/investments/time/${encodeURIComponent(ideaId)}`, {
    contributor_id: contributor,
    hours,
    commitment,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Logged ${hours}h (${commitment}) on '${ideaId}'`);
  } else {
    console.log("Time commitment failed.");
  }
}
