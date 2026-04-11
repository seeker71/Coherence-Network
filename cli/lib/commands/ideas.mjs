/**
 * Ideas commands: ideas, idea, share, stake, fork, and extended coverage
 *
 * Extended commands:
 *   cc idea tags                       — list idea tags catalog
 *   cc idea health                     — governance health
 *   cc idea showcase                   — featured ideas showcase
 *   cc idea resonance                  — ideas resonance overview
 *   cc idea progress                   — pipeline progress dashboard
 *   cc idea count                      — ideas count summary
 *   cc idea cards                      — idea cards view
 *   cc idea <id> activity              — idea activity log
 *   cc idea <id> tasks                 — tasks for an idea
 *   cc idea <id> progress              — progress for an idea
 *   cc idea <id> resonance             — concept resonance for an idea
 *   cc idea <id> advance               — advance idea to next stage
 *   cc idea <id> stage <stage>         — set idea stage
 *   cc idea <id> tag <tag1> [tag2...]  — update idea tags
 *   cc idea <id> question <text>       — add question to idea
 *   cc idea <id> answer <text>         — answer open question
 */

import { get, post, patch, put } from "../api.mjs";
import { ensureIdentity } from "../identity.mjs";
import { getFocus, getActiveWorkspace, DEFAULT_WORKSPACE_ID } from "../config.mjs";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";
import chalk from "chalk";
import inquirer from "inquirer";
import ora from "ora";
import { truncateWords as truncate } from "../ui/ansi.mjs";
import { hasJsonFlag, printJson, printJsonError } from "../ui/json.mjs";

/** Truncate at word boundary, append "..." if needed */

/** Mini bar: filled vs empty blocks for a score out of max */
function miniBar(value, max, width = 5) {
  const filled = Math.round((value / max) * width);
  return "\u2593".repeat(Math.min(filled, width)) + "\u2591".repeat(width - Math.min(filled, width));
}

export async function listIdeas(args) {
  const jsonMode = hasJsonFlag(args);
  const isTTY = process.stdout.isTTY;

  // Interactive picker only when TTY AND not JSON mode AND no other args.
  // When piping (`cc ideas | jq`) or passing `--json`, we always return
  // structured data instead of opening a picker.
  if (isTTY && !jsonMode && args.length === 0) {
    return runInteractivePicker();
  }

  // Parse flags: --type <work_type>, --status <none|partial|validated>, --parent <id>, --limit N, --all, --pillar X
  const flags = {};
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--type" || args[i] === "-t") && args[i+1]) flags.type = args[++i];
    else if ((args[i] === "--status" || args[i] === "-s") && args[i+1]) flags.status = args[++i];
    else if ((args[i] === "--parent" || args[i] === "-p") && args[i+1]) flags.parent = args[++i];
    else if ((args[i] === "--limit" || args[i] === "-n") && args[i+1]) flags.limit = parseInt(args[++i]);
    else if (args[i] === "--all" || args[i] === "-a") flags.all = true;
    else if (args[i] === "--pillar" && args[i+1]) flags.pillar = args[++i];
    else positional.push(args[i]);
  }
  const limit = flags.limit || parseInt(positional[0]) || 40;

  // Default to curated super-ideas; pass --all to see the full fractal.
  const query = { limit: Math.min(limit, 400) };
  if (!flags.all) query.curated_only = true;
  if (flags.pillar) query.pillar = flags.pillar;
  // Workspace scope: --workspace flag override or config.json default.
  // Only send workspace_id when it differs from default, to keep the wire
  // payload quiet for single-tenant users.
  const activeWorkspace = getActiveWorkspace();
  if (activeWorkspace && activeWorkspace !== DEFAULT_WORKSPACE_ID) {
    query.workspace_id = activeWorkspace;
  }

  const raw = await get("/api/ideas", query);
  let data = Array.isArray(raw) ? raw : raw?.ideas;
  if (!data || !Array.isArray(data)) {
    if (jsonMode) {
      printJsonError("fetch_failed");
    } else {
      console.log("Could not fetch ideas.");
    }
    return;
  }

  // Apply local filters (same in both modes)
  if (flags.type)   data = data.filter(i => i.work_type === flags.type);
  if (flags.status) data = data.filter(i => (i.manifestation_status || "none") === flags.status);
  if (flags.parent) data = data.filter(i => i.parent_idea_id === flags.parent);

  // JSON mode: emit the (possibly empty) array and exit. Pipeline-friendly.
  if (jsonMode) {
    printJson(data);
    return;
  }

  if (data.length === 0) { console.log("No ideas match the filter."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", C = "\x1b[36m", M = "\x1b[35m";
  const filterNote = [
    flags.all ? "all" : "curated",
    flags.pillar ? `pillar=${flags.pillar}` : null,
    flags.type   ? `type=${flags.type}` : null,
    flags.status ? `status=${flags.status}` : null,
    flags.parent ? `parent=${flags.parent}` : null,
  ].filter(Boolean).join(", ");

  console.log();
  console.log(`${B}  IDEAS${R} (${data.length})${filterNote ? `  ${D}[${filterNote}]${R}` : ""}`);
  console.log(`  ${"─".repeat(92)}`);

  // When showing curated, group by pillar; otherwise flat list.
  const pillars = ["realization", "pipeline", "economics", "surfaces", "network", "foundation"];
  const groupsActive = !flags.all && !flags.pillar;

  const renderRow = (idea) => {
    const status = (idea.manifestation_status || "none");
    const dot = status === "validated" ? "\x1b[32m●\x1b[0m"
      : status === "partial" ? "\x1b[33m●\x1b[0m"
      : "\x1b[2m○\x1b[0m";
    const name = truncate(idea.name || idea.id, 40).padEnd(42);
    const wt = (idea.work_type || "—").padEnd(12);
    const fe = idea.free_energy_score != null ? idea.free_energy_score.toFixed(2) : "    —";
    const st = D + status.padEnd(10) + R;
    console.log(`  ${dot}  ${name} ${C}${wt}${R} ${String(fe).padStart(6)}  ${st}`);
  };

  if (groupsActive) {
    const byPillar = {};
    for (const p of pillars) byPillar[p] = [];
    const unknown = [];
    for (const i of data) {
      const p = (i.pillar || "").toLowerCase();
      if (p && byPillar[p]) byPillar[p].push(i);
      else unknown.push(i);
    }
    for (const p of pillars) {
      const rows = byPillar[p].sort((a, b) => (b.free_energy_score || 0) - (a.free_energy_score || 0));
      if (rows.length === 0) continue;
      console.log(`\n  ${M}${p.toUpperCase()}${R}`);
      for (const idea of rows) renderRow(idea);
    }
    if (unknown.length > 0) {
      console.log(`\n  ${D}OTHER${R}`);
      for (const idea of unknown) renderRow(idea);
    }
  } else {
    console.log(`  ${D}${"".padEnd(2)}  ${"Name".padEnd(42)} ${"Type".padEnd(12)} ${"FE".padStart(6)}  ${"Status".padEnd(10)}${R}`);
    for (const idea of data) renderRow(idea);
  }
  console.log(`  ${"─".repeat(92)}`);
  if (!flags.all) console.log(`  ${D}Use 'cc idea list --all' to see the full fractal.${R}`);
  console.log();
}

async function runInteractivePicker() {
  const spinner = ora(chalk.cyan("Loading ideas...")).start();
  const raw = await get("/api/ideas", { limit: 100 });
  spinner.stop();

  let data = Array.isArray(raw) ? raw : raw?.ideas;
  if (!data || !Array.isArray(data)) {
    console.log(chalk.red("✗ Could not fetch ideas."));
    return;
  }

  const choices = data.map(i => {
    const status = i.manifestation_status || "none";
    const statusColor = status === "validated" ? chalk.green : status === "partial" ? chalk.yellow : chalk.dim;
    return {
      name: `${truncate(i.name || i.id, 45).padEnd(47)} ${chalk.cyan(i.work_type || "—").padEnd(12)} ${statusColor(status)}`,
      value: i.id
    };
  });

  const { idea_id } = await inquirer.prompt([
    {
      type: "list",
      name: "idea_id",
      message: "Select an idea to view details:",
      choices,
      pageSize: 15
    }
  ]);

  if (idea_id) {
    return showIdea([idea_id]);
  }
}

export async function showIdea(args) {
  // Route subcommands: cc idea <id> <subcommand>
  let id = args[0];
  const focus = getFocus();

  if (!id && focus.idea_id) {
    id = focus.idea_id;
    console.log(chalk.dim(`(Using focused idea: ${chalk.bold(id)})`));
  }

  if (!id) {
    console.log("Usage: cc idea <id> [tasks|translate|children|...]");
    console.log(chalk.dim("Hint: Use 'cc focus' to pick an idea once and skip the ID."));
    return;
  }

  const sub = args[1];
  // Subcommand routing
  if (sub === "translate") return showIdeaTranslate([id, args[2]]);
  if (sub === "tasks")     return showIdeaTasks([id]);
  if (sub === "deps")      return showIdeaDeps([id, ...args.slice(2)]);
  if (sub === "children")  return showIdeaChildren([id]);
  if (sub === "activity")  return showIdeaActivity([id]);
  if (sub === "progress")  return showIdeaItemProgress([id]);
  if (sub === "resonance") return showIdeaConceptResonance([id]);
  if (sub === "advance")   return advanceIdea([id]);
  if (sub === "stage")     return setIdeaStage([id, args[2]]);
  if (sub === "tag")       return updateIdeaTags([id, ...args.slice(2)]);
  if (sub === "question")  return addIdeaQuestion([id, ...args.slice(2)]);
  if (sub === "answer")    return answerIdeaQuestion([id, ...args.slice(2)]);
  if (sub === "type")      return setIdeaWorkType([id, args[2]]);
  if (sub === "link")      return linkIdea([id, ...args.slice(2)]);
  if (sub === "archive")   return archiveIdea([id, ...args.slice(2)]);
  if (sub === "retire")    return retireIdea([id, ...args.slice(2)]);

  // Default: show detail
  const data = await get(`/api/ideas/${encodeURIComponent(id)}`);
  if (!data) { console.log(`Idea '${id}' not found.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", C = "\x1b[36m", Y = "\x1b[33m";
  const status = data.manifestation_status || "none";
  const dot = status === "validated" ? `${G}●${R}` : status === "partial" ? `${Y}●${R}` : `${D}○${R}`;

  console.log();
  console.log(`${B}  ${data.name || data.id}${R}  ${dot}`);
  console.log(`  ${D}${data.id}${R}`);
  if (data.description) console.log(`\n  ${D}${truncate(data.description, 76)}${R}`);
  console.log(`\n  ${"─".repeat(54)}`);
  if (data.work_type)         console.log(`  Work Type:    ${C}${data.work_type}${R}`);
  if (data.idea_type)         console.log(`  Idea Type:    ${data.idea_type}`);
  if (data.parent_idea_id)    console.log(`  Parent:       ${D}${data.parent_idea_id}${R}`);
  if (data.child_idea_ids?.length) console.log(`  Children:     ${data.child_idea_ids.length} ideas`);
  console.log(`  Status:       ${status}`);
  console.log(`  Stage:        ${data.stage || "none"}`);
  console.log(`  ${"─".repeat(54)}`);
  console.log(`  Potential:    ${data.potential_value ?? "?"} CC`);
  console.log(`  Actual:       ${data.actual_value ?? 0} CC`);
  console.log(`  Est. Cost:    ${data.estimated_cost ?? "?"} CC`);
  console.log(`  Actual Cost:  ${data.actual_cost ?? 0} CC`);
  console.log(`  Confidence:   ${((data.confidence ?? 0) * 100).toFixed(0)}%`);
  if (data.free_energy_score != null) console.log(`  Free Energy:  ${data.free_energy_score.toFixed(3)}`);
  if (data.roi_cc != null)            console.log(`  ROI (CC):     ${data.roi_cc.toFixed(2)}`);
  if (data.open_questions?.length) {
    console.log(`\n  ${B}Open Questions${R} (${data.open_questions.length}):`);
    for (const q of data.open_questions) {
      const qText = typeof q === "string" ? q : q.question || JSON.stringify(q);
      const answered = (typeof q === "object" && q.answer) ? ` ${G}✓${R}` : "";
      console.log(`    ${D}?${R}${answered} ${truncate(qText, 66)}`);
    }
  }

  // Specs linked by frontmatter idea_id
  const specs = await get(`/api/ideas/${encodeURIComponent(id)}/specs`).catch(() => []);
  if (Array.isArray(specs) && specs.length > 0) {
    console.log(`\n  ${B}Specs${R} (${specs.length}):`);
    for (const s of specs.slice(0, 10)) {
      console.log(`    ${C}${s.spec_id}${R}  ${truncate(s.title || "", 60)}`);
    }
    if (specs.length > 10) console.log(`    ${D}… and ${specs.length - 10} more${R}`);
  }

  // Absorbed child ideas
  const children = await get(`/api/ideas/${encodeURIComponent(id)}/children`).catch(() => []);
  if (Array.isArray(children) && children.length > 0) {
    console.log(`\n  ${B}Absorbed${R} (${children.length}):`);
    for (const c of children.slice(0, 12)) {
      const st = c.manifestation_status || "none";
      const dot = st === "validated" ? `${G}●${R}` : st === "partial" ? `${Y}●${R}` : `${D}○${R}`;
      console.log(`    ${dot}  ${truncate(c.name || c.id, 48).padEnd(50)} ${D}${c.id}${R}`);
    }
    if (children.length > 12) console.log(`    ${D}… and ${children.length - 12} more${R}`);
  }

  console.log();
}

/** Point-of-view translation: cc idea <id> translate [lens_id] */
export async function showIdeaTranslate(args) {
  const id = args[0];
  const lens = args[1] || "libertarian";
  if (!id) {
    console.log("Usage: cc idea <id> translate [lens_id]");
    return;
  }
  const data = await get(
    `/api/ideas/${encodeURIComponent(id)}/translations/${encodeURIComponent(lens)}`,
  );
  if (!data || data.detail) {
    console.log(data?.detail || `Translation not found for idea '${id}' lens '${lens}'.`);
    return;
  }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  POV: ${data.lens_id}${R}  (${data.idea_id})`);
  console.log(`  ${D}${data.original_name}${R}`);
  console.log();
  console.log(`  ${data.translated_summary || ""}`);
  console.log();
  if (data.emphasis?.length) console.log(`  Emphasis: ${data.emphasis.join(", ")}`);
  console.log(`  Risk: ${data.risk_framing}`);
  console.log(`  Opportunity: ${data.opportunity_framing}`);
  if (data.resonance_delta != null) console.log(`  Resonance Δ: ${data.resonance_delta}`);
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

export async function triageIdeas(args) {
  const raw = await get("/api/ideas", { limit: 400 });
  let data = Array.isArray(raw) ? raw : raw?.ideas;
  if (!data) { console.log("Could not fetch ideas."); return; }

  // Filter: open ideas, not super, sorted by free_energy_score desc
  data = data
    .filter(i => (i.manifestation_status || "none") !== "validated")
    .filter(i => i.idea_type !== "super")
    .sort((a, b) => (b.free_energy_score || 0) - (a.free_energy_score || 0))
    .slice(0, 20);

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", C = "\x1b[36m", G = "\x1b[32m", Y = "\x1b[33m";
  console.log();
  console.log(`${B}  TRIAGE — Next Ideas to Work On${R}`);
  console.log(`  ${D}Ranked by free-energy score. Top 20 open, non-strategic ideas.${R}`);
  console.log(`  ${"─".repeat(82)}`);
  console.log(`  ${D}#   ${"Name".padEnd(40)} ${"Type".padEnd(12)} ${"FE".padStart(6)}  ${"Status".padEnd(9)} ${"Parent"}${R}`);
  const cutoff30 = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  data.forEach((idea, i) => {
    const rank = String(i + 1).padStart(2);
    const name = truncate(idea.name || idea.id, 38).padEnd(40);
    const wt = (idea.work_type || "—").padEnd(12);
    const fe = idea.free_energy_score != null ? idea.free_energy_score.toFixed(2) : "    —";
    const status = (idea.manifestation_status || "none").padEnd(9);
    const parent = idea.parent_idea_id ? D + truncate(idea.parent_idea_id, 20) + R : "";
    const isStale = !idea.last_activity_at || idea.last_activity_at < cutoff30;
    const staleTag = isStale ? ` ${Y}[stale]${R}` : "";
    console.log(`  ${G}${rank}${R}  ${name} ${C}${wt}${R} ${String(fe).padStart(6)}  ${D}${status}${R} ${parent}${staleTag}`);
  });
  console.log(`  ${"─".repeat(82)}`);
  console.log();
}

export async function setIdeaWorkType(args) {
  const id = args[0];
  const workType = args[1];
  const validTypes = ["exploration", "research", "prototype", "feature", "enhancement", "bug-fix", "mvp"];
  if (!id || !workType) {
    console.log(`Usage: cc idea <id> type <work_type>`);
    console.log(`  Valid types: ${validTypes.join(", ")}`);
    return;
  }
  if (!validTypes.includes(workType)) {
    console.log(`Unknown work_type '${workType}'. Valid: ${validTypes.join(", ")}`);
    return;
  }
  const result = await patch(`/api/ideas/${encodeURIComponent(id)}`, { work_type: workType });
  if (result?.id) {
    console.log(`\x1b[32m✓\x1b[0m ${id} → work_type: ${workType}`);
  } else {
    console.log("Failed to set work_type.");
  }
}

export async function linkIdea(args) {
  // cc idea <id> link <relation> <target-id>
  // relation: blocks, enables, supersedes, depends-on, related-to
  const fromId = args[0];
  const rel = args[1];
  const toId = args[2];
  const validRels = ["blocks", "enables", "supersedes", "depends-on", "related-to"];
  if (!fromId || !rel || !toId) {
    console.log("Usage: cc idea <id> link <relation> <target-id>");
    console.log(`  Relations: ${validRels.join(", ")}`);
    return;
  }
  if (!validRels.includes(rel)) {
    console.log(`Unknown relation '${rel}'. Valid: ${validRels.join(", ")}`);
    return;
  }
  // Use edges API
  const result = await post("/api/graph/edges", {
    from_id: fromId,
    to_id: toId,
    type: rel,
    metadata: { source: "cc-idea-link" },
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m ${fromId} --[${rel}]--> ${toId}`);
    if (result.id) console.log(`  Edge ID: ${result.id}`);
  } else {
    console.log("Failed to create edge.");
  }
}

export async function showIdeaChildren(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> children"); return; }
  const raw = await get("/api/ideas", { limit: 400 });
  const all = Array.isArray(raw) ? raw : raw?.ideas || [];
  const children = all.filter(i => i.parent_idea_id === id);
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", C = "\x1b[36m";
  console.log();
  console.log(`${B}  CHILDREN of ${id}${R} (${children.length})`);
  console.log(`  ${"─".repeat(70)}`);
  if (!children.length) { console.log(`  No child ideas found.`); console.log(); return; }
  for (const child of children.sort((a,b) => (b.free_energy_score||0)-(a.free_energy_score||0))) {
    const status = child.manifestation_status || "none";
    const dot = status === "validated" ? "\x1b[32m●\x1b[0m" : status === "partial" ? "\x1b[33m●\x1b[0m" : "\x1b[2m○\x1b[0m";
    const name = truncate(child.name || child.id, 40).padEnd(42);
    const wt = D + (child.work_type || "—").padEnd(12) + R;
    const fe = child.free_energy_score != null ? child.free_energy_score.toFixed(2) : "   —";
    console.log(`  ${dot}  ${name} ${wt} ${fe}`);
  }
  console.log();
}

export async function showIdeaDeps(args) {
  // cc idea <id> deps [--type blocks|enables|supersedes|depends-on|related-to]
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> deps [--type <relation>]"); return; }

  let edgeType = null;
  for (let i = 1; i < args.length; i++) {
    if ((args[i] === "--type" || args[i] === "-t") && args[i+1]) edgeType = args[++i];
  }

  const params = { direction: "both" };
  if (edgeType) params.type = edgeType;

  const data = await get(`/api/graph/nodes/${encodeURIComponent(id)}/edges`, params);
  const edges = Array.isArray(data) ? data : data?.edges || data?.items || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", C = "\x1b[36m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  // Colour per relation type
  const relColor = {
    "blocks":      RED,
    "enables":     G,
    "supersedes":  Y,
    "depends-on":  Y,
    "related-to":  C,
  };

  console.log();
  console.log(`${B}  DEPENDENCIES: ${id}${R}${edgeType ? `  ${D}[type=${edgeType}]${R}` : ""}`);

  if (!edges.length) {
    console.log(`  ${D}No dependency edges found.${R}`);
    console.log(`  ${D}Add one: cc idea ${id} link blocks|enables|supersedes <target-id>${R}`);
    console.log();
    return;
  }

  // Split into outgoing (this idea → other) and incoming (other → this idea)
  const outgoing = edges.filter(e => e.from_id === id || e.source === id || e.from === id);
  const incoming = edges.filter(e => e.to_id   === id || e.target === id || e.to   === id);

  if (outgoing.length) {
    console.log(`\n  ${B}This idea →${R}  ${D}(outgoing)${R}`);
    console.log(`  ${"─".repeat(60)}`);
    for (const e of outgoing) {
      const rel  = e.type || e.edge_type || e.relation || "?";
      const col  = relColor[rel] || C;
      const peer = e.to_id || e.target || e.to || "?";
      const label = truncate(peer, 40).padEnd(42);
      console.log(`  ${col}──[${rel}]──▶${R}  ${label}`);
    }
  }

  if (incoming.length) {
    console.log(`\n  ${B}→ This idea${R}  ${D}(incoming)${R}`);
    console.log(`  ${"─".repeat(60)}`);
    for (const e of incoming) {
      const rel  = e.type || e.edge_type || e.relation || "?";
      const col  = relColor[rel] || C;
      const peer = e.from_id || e.source || e.from || "?";
      const label = truncate(peer, 40).padEnd(42);
      console.log(`  ${col}◀──[${rel}]──${R}  ${label}`);
    }
  }

  console.log();
  console.log(`  ${D}Total edges: ${edges.length}  |  cc idea <id> link <rel> <target> to add more${R}`);
  console.log();
}

// ─── Extended idea commands ────────────────────────────────────────────────

export async function showIdeaTags() {
  const data = await get("/api/ideas/tags");
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  IDEA TAGS${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const tags = Array.isArray(data) ? data : data?.tags || [];
  for (const t of tags) {
    const name = (t.tag || t.name || String(t)).padEnd(25);
    const count = t.count != null ? `${t.count} ideas` : "";
    console.log(`  ${name} ${D}${count}${R}`);
  }
  console.log();
}

export async function showIdeaHealth() {
  const data = await get("/api/ideas/health");
  if (!data) { console.log("Could not fetch ideas health."); return; }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";
  console.log();
  console.log(`${B}  IDEAS HEALTH${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const score = data.health_score ?? data.score ?? data.overall;
  if (score != null) {
    const pct = typeof score === "number" && score <= 1 ? (score * 100).toFixed(1) + "%" : score;
    const numPct = parseFloat(String(pct));
    const color = numPct >= 70 ? G : numPct >= 40 ? Y : RED;
    console.log(`  Health: ${color}${pct}${R}`);
  }
  for (const [k, v] of Object.entries(data)) {
    if (!["health_score", "score", "overall"].includes(k) && v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(22)} ${v}`);
    }
  }
  console.log();
}

export async function showIdeaShowcase() {
  const data = await get("/api/ideas/showcase");
  if (!data) { console.log("Could not fetch showcase."); return; }
  const ideas = Array.isArray(data) ? data : data?.ideas || data?.showcase || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  console.log();
  console.log(`${B}  IDEAS SHOWCASE${R}`);
  console.log(`  ${"─".repeat(74)}`);
  for (const idea of ideas) {
    const name = truncate(idea.name || idea.id || "", 50).padEnd(52);
    const score = idea.coherence_score ?? idea.free_energy_score;
    const scoreStr = score != null ? score.toFixed(2) : "";
    console.log(`  ${G}★${R} ${name} ${D}${scoreStr}${R}`);
  }
  console.log();
}

export async function showIdeaResonance() {
  const data = await get("/api/ideas/resonance");
  if (!data) { console.log("Could not fetch ideas resonance."); return; }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  IDEAS RESONANCE${R}`);
  console.log(`  ${"─".repeat(60)}`);
  const items = Array.isArray(data) ? data : data?.ideas || data?.resonance || [];
  for (const item of items.slice(0, 20)) {
    const name = truncate(item.name || item.idea_id || item.id || "", 40).padEnd(42);
    const score = item.resonance_score ?? item.score;
    const scoreStr = score != null ? score.toFixed(3) : "";
    const bar = score != null ? "█".repeat(Math.round(score * 10)).padEnd(10, "░") : "";
    console.log(`  ${name} ${D}${scoreStr}${R}  ${D}${bar}${R}`);
  }
  console.log();
}

export async function showIdeasProgress() {
  const data = await get("/api/ideas/progress");
  if (!data) { console.log("Could not fetch ideas progress."); return; }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  IDEAS PROGRESS${R}`);
  console.log(`  ${"─".repeat(60)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }
  const stages = data.stages || data.by_stage;
  if (stages && typeof stages === "object") {
    console.log();
    console.log(`  ${D}BY STAGE${R}`);
    for (const [stage, count] of Object.entries(stages)) {
      console.log(`  ${stage.padEnd(25)} ${count}`);
    }
  }
  console.log();
}

export async function showIdeasCount() {
  const data = await get("/api/ideas/count");
  if (!data) { console.log("Could not fetch ideas count."); return; }
  const total = data.count ?? data.total ?? data;
  console.log();
  console.log(`\x1b[1m  IDEAS COUNT\x1b[0m`);
  console.log(`  ${"─".repeat(30)}`);
  if (typeof total === "number") {
    console.log(`  Total: ${total}`);
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) console.log(`  ${k.padEnd(20)} ${v}`);
    }
  }
  console.log();
}

export async function showIdeaActivity(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> activity"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/activity`);
  if (!data) { console.log(`No activity for idea '${id}'.`); return; }
  const events = Array.isArray(data) ? data : data?.events || data?.activity || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", C = "\x1b[36m";
  console.log();
  console.log(`${B}  IDEA ACTIVITY: ${id}${R}`);
  console.log(`  ${"─".repeat(60)}`);
  for (const ev of events) {
    const ts = (ev.timestamp || ev.created_at || "").slice(0, 16);
    const type = (ev.event_type || ev.type || "?").padEnd(18);
    const actor = ev.actor || ev.contributor_id || "";
    console.log(`  ${D}${ts}${R}  ${C}${type}${R}  ${D}${actor}${R}`);
  }
  console.log();
}

export async function showIdeaTasks(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> tasks"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/tasks`);
  if (!data) { console.log(`No tasks for idea '${id}'.`); return; }
  const groups = Array.isArray(data?.groups) ? data.groups : [];
  const tasks = Array.isArray(data)
    ? data
    : Array.isArray(data?.tasks)
      ? data.tasks
      : groups.flatMap((group) => (Array.isArray(group?.tasks) ? group.tasks : []));
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";
  console.log();
  console.log(`${B}  TASKS for ${id}${R} (${tasks.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const t of tasks) {
    const status = (t.status || "?").toLowerCase();
    const dot = status === "done" || status === "completed" ? `${G}●${R}`
      : status === "running" ? `${Y}▸${R}` : `${D}○${R}`;
    const type = (t.task_type || t.type || "?").padEnd(10);
    const dir = truncate(t.direction || t.summary || "", 45);
    console.log(`  ${dot} ${type} ${dir}`);
  }
  console.log();
}

export async function showIdeaItemProgress(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> progress"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/progress`);
  if (!data) { console.log(`No progress data for idea '${id}'.`); return; }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  console.log();
  console.log(`${B}  PROGRESS: ${id}${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const pct = data.progress_pct ?? data.completion_pct ?? data.percent;
  if (pct != null) {
    const bar = "█".repeat(Math.round(pct / 5)).padEnd(20, "░");
    console.log(`  Progress: ${G}${pct.toFixed(1)}%${R}  ${D}${bar}${R}`);
  }
  for (const [k, v] of Object.entries(data)) {
    if (!["progress_pct", "completion_pct", "percent"].includes(k) && v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(22)} ${v}`);
    }
  }
  console.log();
}

export async function showIdeaConceptResonance(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> resonance"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/concept-resonance`);
  if (!data) { console.log(`No concept resonance data for idea '${id}'.`); return; }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  CONCEPT RESONANCE: ${id}${R}`);
  console.log(`  ${"─".repeat(60)}`);
  const overall = data.overall_score ?? data.resonance_score;
  if (overall != null) console.log(`  Overall: ${overall.toFixed(3)}`);
  const concepts = Array.isArray(data.concepts) ? data.concepts : [];
  for (const c of concepts.slice(0, 15)) {
    const name = truncate(c.concept_id || c.name || c.id || "", 30).padEnd(32);
    const score = c.resonance_score ?? c.score;
    const scoreStr = score != null ? score.toFixed(3) : "";
    const bar = score != null ? "█".repeat(Math.round(score * 10)).padEnd(10, "░") : "";
    console.log(`  ${name} ${D}${scoreStr}${R}  ${D}${bar}${R}`);
  }
  console.log();
}

export async function advanceIdea(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> advance"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/advance`, {});
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea '${id}' advanced`);
    if (result.manifestation_status) console.log(`  New status: ${result.manifestation_status}`);
  } else {
    console.log("Failed to advance idea.");
  }
}

export async function setIdeaStage(args) {
  const id = args[0];
  const stage = args[1];
  if (!id || !stage) { console.log("Usage: cc idea <id> stage <stage>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/stage`, { stage });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea '${id}' stage set to '${stage}'`);
  } else {
    console.log("Failed to set stage.");
  }
}

export async function updateIdeaTags(args) {
  const id = args[0];
  const tags = args.slice(1);
  if (!id || !tags.length) { console.log("Usage: cc idea <id> tag <tag1> [tag2...]"); return; }
  const result = await put(`/api/ideas/${encodeURIComponent(id)}/tags`, { tags });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Tags updated for '${id}': ${tags.join(", ")}`);
  } else {
    console.log("Failed to update tags.");
  }
}

export async function addIdeaQuestion(args) {
  const id = args[0];
  const question = args.slice(1).join(" ");
  if (!id || !question) { console.log("Usage: cc idea <id> question <text>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/questions`, { question });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Question added to '${id}'`);
  } else {
    console.log("Failed to add question.");
  }
}

export async function answerIdeaQuestion(args) {
  const id = args[0];
  const answer = args.slice(1).join(" ");
  if (!id || !answer) { console.log("Usage: cc idea <id> answer <text>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/questions/answer`, { answer });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Answer recorded for '${id}'`);
  } else {
    console.log("Failed to record answer.");
  }
}

export async function archiveIdea(args) {
  // cc idea <id> archive [--reason "..."] [--duplicate-of <id>]
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> archive [--reason \"...\"] [--duplicate-of <id>]"); return; }
  const flags = {};
  for (let i = 1; i < args.length; i++) {
    if ((args[i] === "--reason" || args[i] === "-r") && args[i+1]) flags.reason = args[++i];
    if ((args[i] === "--duplicate-of") && args[i+1]) flags.duplicateOf = args[++i];
  }
  const body = { lifecycle: "archived" };
  if (flags.duplicateOf) body.duplicate_of = flags.duplicateOf;
  if (flags.reason) body.name = undefined; // reason goes in a note, not name
  const result = await patch(`/api/ideas/${encodeURIComponent(id)}`, body);
  if (result?.id) {
    console.log(`\x1b[32m✓\x1b[0m ${id} → archived`);
    if (flags.duplicateOf) console.log(`  Duplicate of: ${flags.duplicateOf}`);
    if (flags.reason) console.log(`  Reason: ${flags.reason}`);
  } else {
    console.log("Failed to archive idea.");
  }
}

export async function retireIdea(args) {
  // cc idea <id> retire [--duplicate-of <id>]
  const id = args[0];
  if (!id) { console.log("Usage: cc idea <id> retire [--duplicate-of <id>]"); return; }
  const flags = {};
  for (let i = 1; i < args.length; i++) {
    if (args[i] === "--duplicate-of" && args[i+1]) flags.duplicateOf = args[++i];
  }
  const body = { lifecycle: "retired" };
  if (flags.duplicateOf) body.duplicate_of = flags.duplicateOf;
  const result = await patch(`/api/ideas/${encodeURIComponent(id)}`, body);
  if (result?.id) {
    console.log(`\x1b[32m✓\x1b[0m ${id} → retired${flags.duplicateOf ? ` (duplicate of: ${flags.duplicateOf})` : ""}`);
  } else {
    console.log("Failed to retire idea.");
  }
}

export async function showStaleIdeas(args) {
  // cc idea stale [--days N]   — ideas with lifecycle=active not touched in N days (default 30)
  let days = 30;
  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--days" || args[i] === "-d") && args[i+1]) days = parseInt(args[++i]);
  }
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const raw = await get("/api/ideas", { limit: 400 });
  let data = Array.isArray(raw) ? raw : raw?.ideas || [];

  // Filter: active, not validated, no activity since cutoff
  const stale = data.filter(i => {
    if ((i.lifecycle || "active") !== "active") return false;
    if (i.manifestation_status === "validated") return false;
    if (i.idea_type === "super") return false;
    const lastActivity = i.last_activity_at;
    if (!lastActivity) return true; // no recorded activity = stale
    return lastActivity < cutoff;
  }).sort((a, b) => {
    const ta = a.last_activity_at || "0";
    const tb = b.last_activity_at || "0";
    return ta < tb ? -1 : 1; // oldest first
  });

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", Y = "\x1b[33m", C = "\x1b[36m";
  console.log();
  console.log(`${B}  STALE IDEAS${R}  ${D}(no activity in ${days}+ days, ${stale.length} found)${R}`);
  if (!stale.length) { console.log(`  All active ideas touched in last ${days} days. ✓`); console.log(); return; }
  console.log(`  ${"─".repeat(76)}`);
  console.log(`  ${D}${"Name".padEnd(42)} ${"Last active".padEnd(14)} ${"Type".padEnd(12)} Status${R}`);
  for (const idea of stale) {
    const name = truncate(idea.name || idea.id, 40).padEnd(42);
    const last = idea.last_activity_at ? idea.last_activity_at.slice(0, 10) : D+"never"+R;
    const wt = (idea.work_type || "—").padEnd(12);
    const status = idea.manifestation_status || "none";
    console.log(`  ${Y}⚠${R}  ${name} ${String(last).padEnd(14)} ${C}${wt}${R} ${D}${status}${R}`);
  }
  console.log(`  ${"─".repeat(76)}`);
  console.log(`  ${D}Archive: cc idea <id> archive | Retire duplicate: cc idea <id> retire --duplicate-of <id>${R}`);
  console.log();
}
