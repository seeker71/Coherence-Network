/**
 * Task commands: list, claim, report, next
 *
 * This is the agent-to-agent work protocol. An AI agent (Claude, Codex,
 * Cursor, Gemini) can:
 *   cc tasks              — see what's pending/running
 *   cc task next          — claim the highest-priority pending task
 *   cc task <id>          — view task detail
 *   cc task claim <id>    — claim a specific task
 *   cc task report <id> <status> [output] — report result
 *   cc task seed <idea>   — create a task from an idea
 */

import { get, post, patch } from "../api.mjs";
import { hostname } from "node:os";
import { createHash } from "node:crypto";

function nodeId() {
  return createHash("sha256").update(hostname()).digest("hex").slice(0, 16);
}

export async function listTasks(args) {
  const status = args[0] || "pending";
  const limit = parseInt(args[1]) || 10;
  const data = await get("/api/agent/tasks", { status, limit });
  const tasks = data?.tasks || (Array.isArray(data) ? data : []);

  console.log();
  console.log(`\x1b[1m  TASKS\x1b[0m (${status}, ${tasks.length})`)
  console.log(`  ${"─".repeat(60)}`);

  if (!tasks.length) {
    console.log(`  No ${status} tasks.`);
    return;
  }

  for (const t of tasks) {
    const type = (t.type || t.phase || "?").padEnd(7);
    const age = t.created_at ? timeSince(t.created_at) : "?";
    const dir = (t.direction || t.description || "").slice(0, 50);
    const ctx = t.context || {};
    const ideaId = ctx.idea_id || "";
    const statusMark = t.status === "running" ? "\x1b[33m▸\x1b[0m" :
                       t.status === "completed" ? "\x1b[32m✓\x1b[0m" :
                       t.status === "failed" ? "\x1b[31m✗\x1b[0m" : "\x1b[2m○\x1b[0m";

    console.log(`  ${statusMark} ${type} \x1b[2m${age}\x1b[0m  ${dir}`);
    if (ideaId) console.log(`    \x1b[2midea: ${ideaId}\x1b[0m`);
  }
  console.log();
}

export async function showTask(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc task <id>");
    return;
  }
  const t = await get(`/api/agent/tasks/${id}`);
  if (!t) {
    console.log(`Task not found: ${id}`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  TASK ${t.id}\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);
  console.log(`  Status:    ${t.status}`);
  console.log(`  Type:      ${t.type || t.phase || "?"}`);
  console.log(`  Direction: ${(t.direction || t.description || "").slice(0, 200)}`);
  if (t.context?.idea_id) console.log(`  Idea:      ${t.context.idea_id}`);
  if (t.worker_id) console.log(`  Worker:    ${t.worker_id}`);
  if (t.result) console.log(`  Result:    ${String(t.result).slice(0, 200)}`);
  console.log();
}

export async function claimTask(args) {
  const id = args[0];
  if (!id) {
    // Claim next available
    return claimNext();
  }

  const nid = nodeId();
  const result = await patch(`/api/agent/tasks/${id}`, {
    status: "running",
    worker_id: `${hostname()}:cc-cli`,
  });

  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Claimed task ${id}`);
    console.log(`  Type: ${result.type || result.phase || "?"}`);
    console.log(`  Direction: ${(result.direction || result.description || "").slice(0, 150)}`);
  } else {
    console.log(`\x1b[31m✗\x1b[0m Failed to claim task ${id}`);
  }
}

export async function claimNext() {
  const data = await get("/api/agent/tasks", { status: "pending", limit: 1 });
  const tasks = data?.tasks || (Array.isArray(data) ? data : []);

  if (!tasks.length) {
    console.log("No pending tasks available.");
    return null;
  }

  const task = tasks[0];
  const result = await patch(`/api/agent/tasks/${task.id}`, {
    status: "running",
    worker_id: `${hostname()}:cc-cli`,
  });

  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Claimed next task: ${task.id}`);
    console.log(`  Type: ${task.type || task.phase || "?"}`);
    console.log(`  Direction: ${(task.direction || task.description || "").slice(0, 150)}`);
    // Output JSON for machine consumption when piped
    if (!process.stdout.isTTY) {
      console.log(JSON.stringify(task));
    }
    return task;
  } else {
    console.log(`\x1b[31m✗\x1b[0m Failed to claim task ${task.id}`);
    return null;
  }
}

export async function reportTask(args) {
  const [id, status, ...outputParts] = args;
  const output = outputParts.join(" ");

  if (!id || !status) {
    console.log("Usage: cc task report <id> <completed|failed> [output text]");
    return;
  }

  if (!["completed", "failed"].includes(status)) {
    console.log(`Status must be 'completed' or 'failed', got: ${status}`);
    return;
  }

  const result = await patch(`/api/agent/tasks/${id}`, {
    status,
    result: output || `Task ${status} by ${hostname()}`,
  });

  if (result) {
    const mark = status === "completed" ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m";
    console.log(`${mark} Reported task ${id} as ${status}`);
  } else {
    console.log(`\x1b[31m✗\x1b[0m Failed to report task ${id}`);
  }
}

export async function seedTask(args) {
  const [ideaId, type] = args;
  const taskType = type || "spec";

  if (!ideaId) {
    console.log("Usage: cc task seed <idea_id> [spec|test|impl|review]");
    return;
  }

  // Fetch idea for context
  const idea = await get(`/api/ideas/${ideaId}`);
  if (!idea) {
    console.log(`Idea not found: ${ideaId}`);
    return;
  }

  const result = await post("/api/agent/tasks", {
    task_type: taskType,
    direction: `${taskType} for '${idea.name}' (${ideaId})`,
    context: {
      idea_id: ideaId,
      idea_name: idea.name,
      seeded_by: `${hostname()}:cc-cli`,
    },
  });

  if (result?.id) {
    console.log(`\x1b[32m✓\x1b[0m Seeded ${taskType} task: ${result.id}`);
    console.log(`  Idea: ${idea.name}`);
  } else {
    console.log(`\x1b[31m✗\x1b[0m Failed to seed task`);
  }
}

function timeSince(iso) {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "now";
  if (min < 60) return `${min}m`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}
