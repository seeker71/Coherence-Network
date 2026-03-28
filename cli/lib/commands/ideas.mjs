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

/** List idea tags catalog */
export async function listIdeaTags() {
  const data = await get("/api/ideas/tags");
  if (!data) { console.log("Could not fetch idea tags."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  const tags = data.tags || data.catalog || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  IDEA TAGS${R} (${tags.length})`);
  console.log(`  ${"─".repeat(50)}`);
  for (const t of tags) {
    const name = (t.tag || t.name || t).padEnd(25);
    const count = t.count != null ? `${D}${t.count} ideas${R}` : "";
    console.log(`  ${G}#${R}${name} ${count}`);
  }
  console.log();
}

/** Set tags on an idea */
export async function setIdeaTags(args) {
  const id = args[0];
  const tags = args.slice(1).filter(a => !a.startsWith("--"));
  if (!id || !tags.length) {
    console.log("Usage: cc idea tags <idea-id> <tag1> [tag2 ...]");
    return;
  }
  const result = await import("../api.mjs").then(m =>
    fetch(`${m.getApiBase?.() || "https://api.coherencycoin.com"}/api/ideas/${encodeURIComponent(id)}/tags`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    }).then(r => r.ok ? r.json() : null).catch(() => null)
  );
  // Fallback using post-like call
  const { patch } = await import("../api.mjs");
  const r = await patch(`/api/ideas/${encodeURIComponent(id)}/tags`, { tags });
  if (r) {
    console.log(`\x1b[32m✓\x1b[0m Tags updated for '${id}': ${tags.join(", ")}`);
  } else {
    console.log("Failed to update tags.");
  }
}

/** Show idea cards (brief display format) */
export async function listIdeaCards(args) {
  const limit = parseInt(args[0]) || 10;
  const data = await get("/api/ideas/cards", { limit });
  if (!data) { console.log("Could not fetch idea cards."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";
  const cards = data.cards || data.items || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  IDEA CARDS${R} (${cards.length})`);
  console.log(`  ${"─".repeat(65)}`);
  for (const c of cards) {
    const title = (c.name || c.title || c.id || "?").slice(0, 42).padEnd(44);
    const stage = (c.stage || c.manifestation_status || "").slice(0, 12).padEnd(13);
    const roi = c.roi_cc != null ? `${G}${c.roi_cc.toFixed(1)}${R}` : D + "?" + R;
    console.log(`  ${title} ${D}${stage}${R} roi:${roi}`);
  }
  console.log();
}

/** Show idea progress */
export async function showIdeaProgress(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea progress <idea-id>"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/progress`);
  if (!data) { console.log(`No progress data for '${id}'.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";
  console.log();
  console.log(`${B}  IDEA PROGRESS: ${id}${R}`);
  console.log(`  ${"─".repeat(55)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v == null) continue;
    const display = typeof v === "number" && k.includes("pct")
      ? `${G}${v}%${R}`
      : typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
    console.log(`  ${k.padEnd(28)} ${display}`);
  }
  console.log();
}

/** Show idea activity feed */
export async function showIdeaActivity(args) {
  const id = args[0];
  const limit = parseInt(args[1]) || 15;
  if (!id) { console.log("Usage: cc idea activity <idea-id> [limit]"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/activity`, { limit });
  if (!data) { console.log(`No activity for '${id}'.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", C = "\x1b[36m";
  const items = data.activity || data.events || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  IDEA ACTIVITY: ${id}${R} (${items.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const ev of items) {
    const ts = ev.created_at ? new Date(ev.created_at).toLocaleString() : "?";
    const type = (ev.event_type || ev.type || "?").padEnd(20);
    const actor = ev.actor || ev.contributor_id || "";
    console.log(`  ${D}${ts}${R} ${C}${type}${R} ${D}${actor}${R}`);
  }
  console.log();
}

/** Show idea tasks */
export async function showIdeaTasks(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea tasks <idea-id>"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/tasks`);
  if (!data) { console.log(`No tasks for '${id}'.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";
  const tasks = data.tasks || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  IDEA TASKS: ${id}${R} (${tasks.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const t of tasks) {
    const type = (t.task_type || t.type || "?").padEnd(8);
    const status = t.status || "?";
    const statusColor = status === "completed" ? G : status === "running" ? Y : status === "failed" ? RED : D;
    const dir = (t.direction || t.description || "").slice(0, 50);
    console.log(`  ${statusColor}${status.padEnd(12)}${R} ${type} ${D}${dir}${R}`);
  }
  console.log();
}

/** Advance idea stage */
export async function advanceIdeaStage(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea advance <idea-id>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/advance`, {});
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea '${id}' advanced to: ${result.manifestation_status || result.stage || "?"}`);
  } else {
    console.log("Stage advance failed.");
  }
}

/** Set idea stage explicitly */
export async function setIdeaStage(args) {
  const id = args[0];
  const stage = args[1];
  if (!id || !stage) {
    console.log("Usage: cc idea stage <idea-id> <stage>");
    return;
  }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/stage`, { stage });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea '${id}' stage set to: ${result.manifestation_status || stage}`);
  } else {
    console.log("Stage set failed.");
  }
}

/** Add a question to an idea */
export async function addIdeaQuestion(args) {
  const id = args[0];
  const question = args.slice(1).join(" ");
  if (!id || !question) {
    console.log("Usage: cc idea question <idea-id> <question text>");
    return;
  }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/questions`, { question });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Question added to '${id}'`);
  } else {
    console.log("Failed to add question.");
  }
}

/** Answer an idea question */
export async function answerIdeaQuestion(args) {
  const id = args[0];
  const questionIdx = args[1];
  const answer = args.slice(2).join(" ");
  if (!id || !answer) {
    console.log("Usage: cc idea answer <idea-id> <question-index> <answer text>");
    return;
  }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/questions/answer`, {
    question_index: parseInt(questionIdx) || 0,
    answer,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Answer recorded for '${id}'`);
  } else {
    console.log("Failed to record answer.");
  }
}

/** Show ideas showcase */
export async function showIdeaShowcase() {
  const data = await get("/api/ideas/showcase");
  if (!data) { console.log("Could not fetch idea showcase."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  const ideas = data.ideas || data.showcase || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  IDEA SHOWCASE${R} (${ideas.length})`);
  console.log(`  ${"─".repeat(65)}`);
  for (const idea of ideas) {
    const name = (idea.name || idea.id || "?").padEnd(40);
    const roi = idea.roi_cc != null ? `${G}${idea.roi_cc.toFixed(1)}${R}` : "";
    console.log(`  ${name} roi:${roi}`);
  }
  console.log();
}

/** Show idea storage info */
export async function showIdeaStorage() {
  const data = await get("/api/ideas/storage");
  if (!data) { console.log("Could not fetch storage info."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  IDEA STORAGE${R}`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null) console.log(`  ${k.padEnd(25)} ${JSON.stringify(v).slice(0, 60)}`);
  }
  console.log();
}

/** Show ideas count */
export async function showIdeaCount() {
  const data = await get("/api/ideas/count");
  if (!data) { console.log("Could not fetch idea count."); return; }
  const count = data.count ?? data.total ?? JSON.stringify(data);
  console.log(`Ideas: ${count}`);
}

/** Select best idea (AI-assisted selection) */
export async function selectIdea(args) {
  const context = args.join(" ");
  const result = await post("/api/ideas/select", { context: context || undefined });
  if (!result) { console.log("Selection failed."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  console.log();
  console.log(`${B}  SELECTED IDEA${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const idea = result.idea || result;
  console.log(`  ${G}${idea.name || idea.id || "?"}${R}`);
  if (idea.id) console.log(`  ID:    ${idea.id}`);
  if (idea.roi_cc != null) console.log(`  ROI:   ${idea.roi_cc.toFixed(2)} CC`);
  if (result.reason) console.log(`  Why:   ${result.reason.slice(0, 80)}`);
  console.log();
}

/** Show progress dashboard */
export async function showProgressDashboard() {
  const data = await get("/api/ideas/progress");
  if (!data) { console.log("Could not fetch progress dashboard."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";
  console.log();
  console.log(`${B}  PROGRESS DASHBOARD${R}`);
  console.log(`  ${"─".repeat(60)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v == null) continue;
    const display = typeof v === "number"
      ? (k.includes("pct") || k.includes("score") ? `${v.toFixed ? v.toFixed(1) : v}%` : String(v))
      : typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
    console.log(`  ${k.padEnd(30)} ${display}`);
  }
  console.log();
}

/** Show concept resonance for an idea */
export async function showIdeaConceptResonance(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc idea resonance <idea-id>"); return; }
  const data = await get(`/api/ideas/${encodeURIComponent(id)}/concept-resonance`);
  if (!data) { console.log(`No concept resonance for '${id}'.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  const concepts = data.concepts || data.resonance || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  CONCEPT RESONANCE: ${id}${R}`);
  console.log(`  ${"─".repeat(55)}`);
  if (Array.isArray(concepts) && concepts.length) {
    for (const c of concepts) {
      const name = (c.concept || c.name || "?").padEnd(30);
      const score = c.score ?? c.resonance ?? 0;
      const bar = "█".repeat(Math.round(score * 10)) + "░".repeat(10 - Math.round(score * 10));
      const color = score > 0.7 ? G : score > 0.4 ? "\x1b[33m" : D;
      console.log(`  ${name} ${color}${bar}${R} ${score.toFixed(2)}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) console.log(`  ${k.padEnd(25)} ${JSON.stringify(v).slice(0, 60)}`);
    }
  }
  console.log();
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
