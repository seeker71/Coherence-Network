/**
 * Ideas commands: ideas, idea, share, stake, fork
 */

import { get, post } from "../api.mjs";
import { ensureIdentity } from "../identity.mjs";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

/** Truncate at word boundary, append "..." if needed */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const trimmed = str.slice(0, len - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > len * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
}

/** Mini bar: filled vs empty blocks for a score out of max */
function miniBar(value, max, width = 5) {
  const filled = Math.round((value / max) * width);
  return "\u2593".repeat(Math.min(filled, width)) + "\u2591".repeat(width - Math.min(filled, width));
}

export async function listIdeas(args) {
  const limit = parseInt(args[0]) || 20;
  const raw = await get("/api/ideas", { limit });
  // API may return { ideas: [...] } or a raw array
  const data = Array.isArray(raw) ? raw : raw?.ideas;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch ideas.");
    return;
  }
  if (data.length === 0) {
    console.log("No ideas in the portfolio yet.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  IDEAS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(74)}`);
  for (const idea of data) {
    const status = (idea.manifestation_status || "NONE").toUpperCase();
    const dot = status === "VALIDATED" ? "\x1b[32m●\x1b[0m"
      : status === "PARTIAL" ? "\x1b[33m●\x1b[0m"
      : "\x1b[2m○\x1b[0m";
    const name = truncate(idea.name || idea.id, 45).padEnd(47);
    const roi = idea.roi_cc != null ? String(idea.roi_cc.toFixed(1)).padStart(6) : "     -";
    const fe = idea.free_energy_score != null ? idea.free_energy_score.toFixed(2) : null;
    const feStr = fe != null ? `${String(fe).padStart(5)} ${miniBar(idea.free_energy_score, 20)}` : "";
    console.log(`  ${dot} ${name} ${roi}  ${feStr}`);
  }
  console.log(`  ${"─".repeat(74)}`);
  console.log(`\x1b[2m  ${"Name".padEnd(49)} ${"ROI".padStart(6)}  ${"FE".padStart(5)}\x1b[0m`);
  console.log();
}

export async function showIdea(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc idea <id>");
    return;
  }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Idea '${id}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  ${data.name || data.id}\x1b[0m`);
  if (data.description) console.log(`  \x1b[2m${truncate(data.description, 72)}\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Status:      ${data.manifestation_status || "NONE"}`);
  console.log(`  Potential:    ${data.potential_value ?? "?"}`);
  console.log(`  Actual:       ${data.actual_value ?? 0}`);
  console.log(`  Est. Cost:    ${data.estimated_cost ?? "?"}`);
  console.log(`  Confidence:   ${data.confidence ?? "?"}`);
  if (data.free_energy_score != null) console.log(`  Free Energy:  ${data.free_energy_score.toFixed(3)}`);
  if (data.roi_cc != null) console.log(`  ROI (CC):     ${data.roi_cc.toFixed(2)}`);
  if (data.open_questions?.length) {
    console.log();
    console.log("  \x1b[1mOpen Questions:\x1b[0m");
    for (const q of data.open_questions) {
      const qText = typeof q === "string" ? q : q.question || q.text || JSON.stringify(q);
      console.log(`    ? ${truncate(qText, 68)}`);
    }
  }
  console.log();
}

export async function shareIdea() {
  const contributor = await ensureIdentity();
  const rl = createInterface({ input: stdin, output: stdout });

  console.log();
  const name = (await rl.question("Idea name: > ")).trim();
  if (!name) { rl.close(); return; }
  const description = (await rl.question("Description: > ")).trim();
  const potentialValue = parseFloat((await rl.question("Potential value (CC): > ")).trim()) || 100;
  const estimatedCost = parseFloat((await rl.question("Estimated cost (CC): > ")).trim()) || 50;

  rl.close();

  const result = await post("/api/ideas", {
    name,
    description,
    potential_value: potentialValue,
    estimated_cost: estimatedCost,
    metadata: { shared_by: contributor },
  });

  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea shared: ${result.id || result.name || name}`);
  } else {
    console.log("Failed to share idea.");
  }
}

export async function stakeOnIdea(args) {
  const ideaId = args[0];
  const amount = parseFloat(args[1]);
  if (!ideaId || isNaN(amount)) {
    console.log("Usage: cc stake <idea-id> <amount-cc>");
    return;
  }
  const contributor = await ensureIdentity();
  const result = await post(`/api/ideas/${encodeURIComponent(ideaId)}/stake`, {
    contributor_id: contributor,
    amount_cc: amount,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Staked ${amount} CC on '${ideaId}'`);
  } else {
    console.log("Stake failed.");
  }
}

export async function forkIdea(args) {
  const ideaId = args[0];
  if (!ideaId) {
    console.log("Usage: cc fork <idea-id>");
    return;
  }
  const contributor = await ensureIdentity();
  const result = await post(
    `/api/ideas/${encodeURIComponent(ideaId)}/fork?forker_id=${encodeURIComponent(contributor)}`,
    {},
  );
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Forked idea '${ideaId}' → ${result.id || "(new)"}`);
  } else {
    console.log("Fork failed.");
  }
}

/**
 * Non-interactive idea creation for agents and scripts.
 *
 * Usage: cc idea create <id> <name> [--desc "..."] [--value N] [--cost N] [--parent <id>]
 */
export async function createIdea(args) {
  if (args.length < 2) {
    console.log("Usage: cc idea create <id> <name> [--desc \"...\"] [--value N] [--cost N] [--parent <id>]");
    return;
  }

  const id = args[0];
  const name = args[1];
  const flags = {};
  for (let i = 2; i < args.length; i++) {
    if (args[i] === "--desc" && args[i + 1]) flags.desc = args[++i];
    else if (args[i] === "--value" && args[i + 1]) flags.value = parseFloat(args[++i]);
    else if (args[i] === "--cost" && args[i + 1]) flags.cost = parseFloat(args[++i]);
    else if (args[i] === "--parent" && args[i + 1]) flags.parent = args[++i];
    else if (args[i] === "--confidence" && args[i + 1]) flags.confidence = parseFloat(args[++i]);
  }

  const body = {
    id,
    name,
    description: flags.desc || name,
    potential_value: flags.value || 50,
    estimated_cost: flags.cost || 5,
    confidence: flags.confidence || 0.5,
  };
  if (flags.parent) body.parent_idea_id = flags.parent;

  const result = await post("/api/ideas", body);
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea created: ${result.id || id}`);
  } else {
    console.log("Failed to create idea.");
    process.exit(1);
  }
}
