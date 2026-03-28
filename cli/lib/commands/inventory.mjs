/**
 * Inventory commands: pipeline pulse, ROI, process completeness,
 * proactive questions, spec gaps, traceability gaps.
 *
 * Covers /api/inventory/* and /api/pipeline/* endpoints.
 *
 * Usage:
 *   cc inventory                    — pipeline pulse + completeness overview
 *   cc inventory pulse              — live pipeline health pulse
 *   cc inventory roi                — ROI-ordered task sync
 *   cc inventory questions          — proactive questions queue
 *   cc inventory gaps               — traceability + spec gaps
 *   cc inventory routes             — canonical route manifest
 *   cc inventory completeness       — process completeness report
 *   cc inventory sync-tasks         — sync spec implementation tasks
 *   cc inventory sync-proactive     — sync proactive questions
 *   cc inventory sync-roi           — sync ROI progress
 *   cc inventory fix-hollow         — fix hollow completions in pipeline
 */

import { get, post } from "../api.mjs";

function timeSince(iso) {
  if (!iso) return "?";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "now";
  if (min < 60) return `${min}m`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

/** Display pipeline pulse summary */
export async function showPipelinePulse() {
  const data = await get("/api/pipeline/pulse");
  if (!data) {
    console.log("Could not fetch pipeline pulse.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m", C = "\x1b[36m";

  console.log();
  console.log(`${B}  PIPELINE PULSE${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.status) {
    const statusColor = data.status === "healthy" ? G : data.status === "degraded" ? Y : RED;
    console.log(`  Status:        ${statusColor}${data.status}${R}`);
  }
  if (data.running_tasks != null) console.log(`  Running:       ${Y}${data.running_tasks}${R} tasks`);
  if (data.pending_tasks != null) console.log(`  Pending:       ${D}${data.pending_tasks}${R} tasks`);
  if (data.completed_today != null) console.log(`  Done today:    ${G}${data.completed_today}${R}`);
  if (data.failed_today != null && data.failed_today > 0) {
    console.log(`  Failed today:  ${RED}${data.failed_today}${R}`);
  }
  if (data.hollow_completions != null && data.hollow_completions > 0) {
    console.log(`  Hollow:        ${RED}${data.hollow_completions}${R} (fix with: cc inventory fix-hollow)`);
  }
  if (data.last_activity) console.log(`  Last activity: ${D}${timeSince(data.last_activity)} ago${R}`);

  // Show any additional fields
  const shown = new Set(["status","running_tasks","pending_tasks","completed_today","failed_today","hollow_completions","last_activity"]);
  for (const [k, v] of Object.entries(data)) {
    if (!shown.has(k) && v != null && typeof v !== "object") {
      console.log(`  ${k}: ${v}`);
    }
  }
  console.log();
}

/** Show process completeness */
export async function showProcessCompleteness() {
  const data = await get("/api/inventory/process-completeness");
  if (!data) {
    console.log("Could not fetch process completeness.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  PROCESS COMPLETENESS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const items = data.items || data.phases || data.stages || (Array.isArray(data) ? data : []);
  if (items.length) {
    for (const item of items) {
      const pct = item.completeness_pct ?? item.pct ?? item.coverage ?? 0;
      const bar = makeBar(pct, 20);
      const name = (item.phase || item.stage || item.name || "?").padEnd(20);
      const color = pct >= 80 ? G : pct >= 50 ? Y : RED;
      console.log(`  ${name} ${color}${bar}${R} ${String(pct.toFixed ? pct.toFixed(0) : pct).padStart(3)}%`);
    }
  } else {
    // Flat structure
    for (const [k, v] of Object.entries(data)) {
      if (typeof v === "number") {
        const bar = makeBar(v, 20);
        const color = v >= 80 ? G : v >= 50 ? Y : RED;
        console.log(`  ${k.padEnd(25)} ${color}${bar}${R} ${String(Math.round(v)).padStart(3)}%`);
      }
    }
  }
  console.log();
}

/** Show proactive questions queue */
export async function showProactiveQuestions(args) {
  const limit = parseInt(args[0]) || 10;
  const data = await get("/api/inventory/questions/proactive", { limit });
  if (!data) {
    console.log("Could not fetch proactive questions.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", Y = "\x1b[33m";
  const questions = data.questions || data.items || (Array.isArray(data) ? data : []);

  console.log();
  console.log(`${B}  PROACTIVE QUESTIONS${R} (${questions.length})`);
  console.log(`  ${"─".repeat(60)}`);

  if (!questions.length) {
    console.log(`  ${D}No proactive questions queued.${R}`);
    console.log();
    return;
  }

  for (const q of questions) {
    const text = (q.question || q.text || q.description || "?").slice(0, 80);
    const idea = q.idea_id || "";
    const priority = q.priority != null ? ` [p${q.priority}]` : "";
    console.log(`  ${Y}?${R} ${text}${priority}`);
    if (idea) console.log(`    ${D}idea: ${idea}${R}`);
  }
  console.log();
}

/** Show next highest ROI task */
export async function showNextRoiTask() {
  const data = await post("/api/inventory/questions/next-highest-roi-task", {});
  if (!data) {
    console.log("Could not fetch next ROI task.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  console.log();
  console.log(`${B}  NEXT HIGHEST ROI TASK${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.task) {
    const t = data.task;
    console.log(`  Task:    ${t.id || "?"}`);
    console.log(`  Type:    ${t.task_type || t.type || "?"}`);
    console.log(`  ROI:     ${G}${t.roi_cc || t.roi || "?"}${R} CC`);
    if (t.idea_id) console.log(`  Idea:    ${t.idea_id}`);
    if (t.direction) console.log(`  What:    ${t.direction.slice(0, 100)}`);
  } else if (data.idea) {
    const i = data.idea;
    console.log(`  Idea:    ${i.id || i.name || "?"}`);
    console.log(`  ROI:     ${G}${i.roi_cc || "?"}${R} CC`);
    if (i.next_task) console.log(`  Task:    ${i.next_task}`);
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) console.log(`  ${k}: ${JSON.stringify(v).slice(0, 80)}`);
    }
  }
  console.log();
}

/** Show canonical routes inventory */
export async function showCanonicalRoutes(args) {
  const data = await get("/api/inventory/routes/canonical");
  if (!data) {
    console.log("Could not fetch route manifest.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  const filter = args[0] || "";

  const routes = data.routes || data.endpoints || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  CANONICAL ROUTES${R} (${routes.length}${filter ? ` matching '${filter}'` : ""})`);
  console.log(`  ${"─".repeat(70)}`);

  const filtered = filter
    ? routes.filter(r => (r.path || r.route || "").includes(filter))
    : routes.slice(0, 40);

  for (const r of filtered) {
    const method = (r.method || r.methods?.[0] || "GET").toUpperCase().padEnd(6);
    const path = (r.path || r.route || "?").padEnd(45);
    const covered = r.cli_covered ? `${G}✓${R}` : `${D}○${R}`;
    console.log(`  ${covered} ${method} ${path}`);
  }

  if (!filter && routes.length > 40) {
    console.log(`  ${D}... and ${routes.length - 40} more. Use: cc inventory routes <filter>${R}`);
  }
  console.log();
}

/** Show system lineage inventory */
export async function showSystemLineage() {
  const data = await get("/api/inventory/system-lineage");
  if (!data) {
    console.log("Could not fetch system lineage.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  SYSTEM LINEAGE${R}`);
  console.log(`  ${"─".repeat(60)}`);

  for (const [k, v] of Object.entries(data)) {
    if (v != null) {
      const display = typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
      console.log(`  ${k.padEnd(25)} ${display}`);
    }
  }
  console.log();
}

/** Sync spec implementation tasks */
export async function syncSpecTasks() {
  console.log("Syncing spec implementation tasks...");
  const data = await post("/api/inventory/specs/sync-implementation-tasks", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Sync failed.");
    return;
  }
  const created = data.created || data.tasks_created || 0;
  const skipped = data.skipped || 0;
  console.log(`\x1b[32m✓\x1b[0m Synced: ${created} tasks created, ${skipped} skipped`);
  if (data.details) console.log(`  Details: ${JSON.stringify(data.details).slice(0, 100)}`);
}

/** Sync proactive questions */
export async function syncProactiveQuestions() {
  console.log("Syncing proactive questions...");
  const data = await post("/api/inventory/questions/sync-proactive", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Sync failed.");
    return;
  }
  const created = data.created || data.synced || 0;
  console.log(`\x1b[32m✓\x1b[0m Proactive questions synced: ${created}`);
}

/** Sync ROI progress tasks */
export async function syncRoiProgress() {
  console.log("Syncing ROI progress...");
  const data = await post("/api/inventory/roi/sync-progress", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Sync failed.");
    return;
  }
  console.log(`\x1b[32m✓\x1b[0m ROI progress synced`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null && typeof v !== "object") console.log(`  ${k}: ${v}`);
  }
}

/** Sync traceability gap artifacts */
export async function syncTraceabilityGaps() {
  console.log("Syncing traceability gaps...");
  const data = await post("/api/inventory/gaps/sync-traceability", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Sync failed.");
    return;
  }
  const count = data.created || data.gaps_created || data.synced || 0;
  console.log(`\x1b[32m✓\x1b[0m Traceability gaps synced: ${count}`);
}

/** Bootstrap spec tasks */
export async function bootstrapSpecTasks() {
  console.log("Bootstrapping spec tasks...");
  const data = await post("/api/inventory/gaps/bootstrap-specs", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Bootstrap failed.");
    return;
  }
  const created = data.created || data.tasks_created || 0;
  console.log(`\x1b[32m✓\x1b[0m Bootstrapped: ${created} spec tasks`);
}

/** Fix hollow completions */
export async function fixHollowCompletions() {
  console.log("Fixing hollow completions...");
  const data = await post("/api/pipeline/fix-hollow-completions", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Fix failed.");
    return;
  }
  const fixed = data.fixed || data.count || 0;
  console.log(`\x1b[32m✓\x1b[0m Fixed: ${fixed} hollow completions`);
  if (data.details) console.log(`  ${JSON.stringify(data.details).slice(0, 120)}`);
}

/** Inventory overview: pulse + completeness */
export async function showInventoryOverview() {
  await showPipelinePulse();
  await showProcessCompleteness();
}

/** Helper: render a progress bar */
function makeBar(value, width = 20) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const filled = Math.round((pct / 100) * width);
  return "█".repeat(filled) + "░".repeat(width - filled);
}
