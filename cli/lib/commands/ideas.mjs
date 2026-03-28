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
  const tasks = Array.isArray(data) ? data : data?.tasks || [];
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
