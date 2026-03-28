/**
 * Extended ideas commands covering additional API endpoints.
 *
 *   cc idea tags                       — list idea tags catalog
 *   cc idea health                     — governance health
 *   cc idea showcase                   — featured ideas showcase
 *   cc idea resonance                  — ideas resonance overview
 *   cc idea progress                   — pipeline progress dashboard
 *   cc idea count                      — ideas count summary
 *   cc idea <id> activity              — idea activity log
 *   cc idea <id> tasks                 — tasks for an idea
 *   cc idea <id> item-progress         — progress for an idea
 *   cc idea <id> resonance             — concept resonance for an idea
 *   cc idea <id> advance               — advance idea to next stage
 *   cc idea <id> stage <stage>         — set idea stage
 *   cc idea <id> tag <tag1> [tag2...]  — update idea tags
 *   cc idea <id> question <text>       — add question to idea
 *   cc idea <id> answer <text>         — answer open question
 */

import { get, post, patch, put } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  return str.slice(0, len - 3) + "...";
}

export async function showIdeaTags() {
  const data = await get("/api/ideas/tags");
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  IDEA TAGS${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const tags = Array.isArray(data) ? data : data?.tags || [];
  if (!tags.length) {
    console.log(`  ${D}No tags found.${R}`);
  } else {
    for (const t of tags) {
      const name = (t.tag || t.name || String(t)).padEnd(25);
      const count = t.count != null ? `${t.count} ideas` : "";
      console.log(`  ${name} ${D}${count}${R}`);
    }
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

export async function showIdeaResonanceList() {
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

export async function showIdeasProgressDashboard() {
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

export async function showIdeaActivity(id) {
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

export async function showIdeaTasks(id) {
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

export async function showIdeaItemProgress(id) {
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

export async function showIdeaConceptResonance(id) {
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

export async function advanceIdea(id) {
  if (!id) { console.log("Usage: cc idea <id> advance"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/advance`, {});
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea '${id}' advanced`);
    if (result.manifestation_status) console.log(`  New status: ${result.manifestation_status}`);
  } else {
    console.log("Failed to advance idea.");
  }
}

export async function setIdeaStage(id, stage) {
  if (!id || !stage) { console.log("Usage: cc idea <id> stage <stage>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/stage`, { stage });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Idea '${id}' stage set to '${stage}'`);
  } else {
    console.log("Failed to set stage.");
  }
}

export async function updateIdeaTags(id, tags) {
  if (!id || !tags.length) { console.log("Usage: cc idea <id> tag <tag1> [tag2...]"); return; }
  const result = await put(`/api/ideas/${encodeURIComponent(id)}/tags`, { tags });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Tags updated for '${id}': ${tags.join(", ")}`);
  } else {
    console.log("Failed to update tags.");
  }
}

export async function addIdeaQuestion(id, question) {
  if (!id || !question) { console.log("Usage: cc idea <id> question <text>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/questions`, { question });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Question added to '${id}'`);
  } else {
    console.log("Failed to add question.");
  }
}

export async function answerIdeaQuestion(id, answer) {
  if (!id || !answer) { console.log("Usage: cc idea <id> answer <text>"); return; }
  const result = await post(`/api/ideas/${encodeURIComponent(id)}/questions/answer`, { answer });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Answer recorded for '${id}'`);
  } else {
    console.log("Failed to record answer.");
  }
}

export async function showIdeaCards() {
  const data = await get("/api/ideas/cards");
  if (!data) { console.log("Could not fetch idea cards."); return; }
  const cards = Array.isArray(data) ? data : data?.cards || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";
  console.log();
  console.log(`${B}  IDEA CARDS${R} (${cards.length})`);
  console.log(`  ${"─".repeat(74)}`);
  for (const card of cards.slice(0, 20)) {
    const name = truncate(card.name || card.title || card.id || "", 45).padEnd(47);
    const status = (card.status || card.manifestation_status || "").toLowerCase();
    const dot = status.includes("valid") ? `${G}●${R}` : status.includes("partial") ? `${Y}●${R}` : `${D}○${R}`;
    console.log(`  ${dot} ${name}`);
  }
  console.log();
}

export async function showSelectionAbStats() {
  const data = await get("/api/ideas/selection-ab/stats");
  if (!data) { console.log("Could not fetch A/B selection stats."); return; }
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  SELECTION A/B STATS${R}`);
  console.log(`  ${"─".repeat(60)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }
  const variants = data.variants || data.conditions;
  if (variants && typeof variants === "object") {
    console.log();
    console.log(`  ${D}VARIANTS${R}`);
    for (const [variant, stats] of Object.entries(variants)) {
      const s = typeof stats === "object" ? stats : {};
      console.log(`  ${variant.padEnd(20)} ${D}${JSON.stringify(s)}${R}`);
    }
  }
  console.log();
}
