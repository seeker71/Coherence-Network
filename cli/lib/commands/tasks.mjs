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
import { getCliActiveTaskId, getCliProvider, getHubUrl, getActiveWorkspace, DEFAULT_WORKSPACE_ID } from "../config.mjs";

function workspaceQuery() {
  const active = getActiveWorkspace();
  if (active && active !== DEFAULT_WORKSPACE_ID) {
    return { workspace_id: active };
  }
  return {};
}

function nodeId() {
  return createHash("sha256").update(hostname()).digest("hex").slice(0, 16);
}

export async function listTasks(args) {
  const explicit = args[0];
  const limit = parseInt(args[1]) || 10;

  // Default: show running + pending + needs_decision (the actionable stuff)
  if (!explicit) {
    const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
    const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m", C = "\x1b[36m";

    const wsQ = workspaceQuery();
    const [runRes, pendRes, decRes] = await Promise.all([
      get("/api/agent/tasks", { status: "running", limit: 15, ...wsQ }),
      get("/api/agent/tasks", { status: "pending", limit: 10, ...wsQ }),
      get("/api/agent/tasks", { status: "needs_decision", limit: 5, ...wsQ }),
    ]);
    const running = runRes?.tasks || [];
    const pending = pendRes?.tasks || [];
    const blocked = decRes?.tasks || [];

    console.log();
    console.log(`${B}  TASKS${R}`);
    console.log(`  ${"─".repeat(60)}`);

    // Needs decision first — human attention required
    if (blocked.length) {
      console.log(`  ${RED}${B}${blocked.length} need decision${R}`);
      for (const t of blocked) {
        const ideaId = (t.context || {}).idea_id || "";
        const dir = (t.direction || "").slice(0, 50);
        console.log(`  ${RED}!${R} ${(t.task_type || "?").padEnd(8)} ${dir}`);
        if (ideaId) console.log(`    ${D}idea: ${ideaId}${R}`);
      }
      console.log();
    }

    // Running — what's active now
    if (running.length) {
      console.log(`  ${Y}${running.length} running${R}`);
      for (const t of running) {
        const type = (t.task_type || "?").padEnd(8);
        const ideaId = (t.context || {}).idea_id || "";
        const model = t.model || "";
        const claimed = (t.claimed_by || "").split(":")[0].split(".")[0] || "?";
        const age = t.claimed_at ? timeSince(t.claimed_at) : "";
        console.log(`  ${Y}▸${R} ${type} ${D}on ${claimed}${R} ${D}via ${model.split("/").pop() || "?"}${R} ${D}${age}${R}`);
        if (ideaId) console.log(`    ${D}${ideaId}${R}`);
      }
      console.log();
    }

    // Pending — what's queued
    if (pending.length) {
      console.log(`  ${D}${pending.length} pending${R}`);
      for (const t of pending) {
        const type = (t.task_type || "?").padEnd(8);
        const ideaId = (t.context || {}).idea_id || "";
        const age = t.created_at ? timeSince(t.created_at) : "?";
        console.log(`  ${D}○${R} ${type} ${D}${age}${R}  ${(t.direction || "").slice(0, 50)}`);
        if (ideaId) console.log(`    ${D}idea: ${ideaId}${R}`);
      }
      console.log();
    }

    if (!running.length && !pending.length && !blocked.length) {
      console.log(`  ${D}No active tasks. Pipeline idle.${R}`);
      console.log();
    }

    return;
  }

  // Explicit status filter: cc tasks running, cc tasks failed, etc.
  const data = await get("/api/agent/tasks", { status: explicit, limit, ...workspaceQuery() });
  const tasks = data?.tasks || (Array.isArray(data) ? data : []);

  console.log();
  console.log(`\x1b[1m  TASKS\x1b[0m (${explicit}, ${tasks.length})`)
  console.log(`  ${"─".repeat(60)}`);

  if (!tasks.length) {
    console.log(`  No ${explicit} tasks.`);
    return;
  }

  for (const t of tasks) {
    const type = (t.task_type || t.type || t.phase || "?").padEnd(8);
    const age = t.created_at ? timeSince(t.created_at) : "?";
    const dir = (t.direction || t.description || "").slice(0, 50);
    const ctx = t.context || {};
    const ideaId = ctx.idea_id || "";
    const statusMark = t.status === "running" ? "\x1b[33m▸\x1b[0m" :
                       t.status === "completed" ? "\x1b[32m✓\x1b[0m" :
                       t.status === "failed" ? "\x1b[31m✗\x1b[0m" :
                       t.status === "needs_decision" ? "\x1b[31m!\x1b[0m" : "\x1b[2m○\x1b[0m";

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

export async function showTaskCount() {
  const data = await get("/api/agent/tasks/count");
  if (!data) {
    console.log("Could not fetch /api/agent/tasks/count.");
    return;
  }
  console.log(JSON.stringify(data, null, 2));
}

export async function showTaskEvents(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc task events <task_id>");
    console.log("  Fetches stored event list from GET /api/agent/tasks/<id>/stream (not the SSE /events endpoint).");
    return;
  }
  const data = await get(`/api/agent/tasks/${encodeURIComponent(id)}/stream`);
  if (!data) {
    console.log(`No stream data or task not found: ${id}`);
    return;
  }
  console.log(JSON.stringify(data, null, 2));
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

export async function postProgress(args) {
  const message = args.join(" ").trim();
  if (!message) { console.log("Usage: cc progress \"what you just did\""); return; }
  let taskId = getCliActiveTaskId() || "";
  if (!taskId) {
    try { const { readFileSync } = await import("node:fs"); const ctrl = readFileSync(".task-control", "utf-8").trim(); const m = ctrl.match(/task[_-]([a-f0-9]+)/i); if (m) taskId = `task_${m[1]}`; } catch {}
  }
  if (!taskId) {
    const { get } = await import("../api.mjs");
    const data = await get("/api/agent/tasks", { status: "running", limit: 1 });
    if (data?.tasks?.[0]) taskId = data.tasks[0].id;
  }
  if (!taskId) { console.log("\x1b[33m⚠\x1b[0m No active task found."); return; }
  const { post } = await import("../api.mjs");
  const { hostname } = await import("node:os");
  const result = await post(`/api/agent/tasks/${taskId}/activity`, {
    node_name: hostname(), provider: getCliProvider(),
    event_type: "progress", data: { message, source: "cc_progress_cli" },
  });
  console.log(result ? `\x1b[32m✓\x1b[0m Progress: ${message}` : "\x1b[31m✗\x1b[0m Failed");
}

export async function streamStart(args) {
  const label = args.join(" ").trim() || "Live agent stream";
  
  // Find current task
  let taskId = getCliActiveTaskId() || "";
  if (!taskId) {
    try {
      const { readFileSync } = await import("node:fs");
      const ctrl = readFileSync(".task-control", "utf-8").trim();
      const match = ctrl.match(/task[_-]([a-f0-9]+)/i);
      if (match) taskId = `task_${match[1]}`;
    } catch {}
  }
  if (!taskId) {
    const { get } = await import("../api.mjs");
    const data = await get("/api/agent/tasks", { status: "running", limit: 1 });
    if (data?.tasks?.[0]) taskId = data.tasks[0].id;
  }

  if (!taskId) {
    console.log("\x1b[33m⚠\x1b[0m No active task. Set cli.active_task_id in config or claim a task first.");
    return;
  }

  const { post } = await import("../api.mjs");
  const { hostname } = await import("node:os");

  // Open the stream
  console.log(`\x1b[36m◉\x1b[0m Stream open: ${label}`);
  console.log(`\x1b[2m  Watch: curl -N ${getHubUrl()}/api/agent/tasks/${taskId}/events\x1b[0m`);
  console.log(`\x1b[2m  Type messages, they stream live. Ctrl+C to stop.\x1b[0m`);
  console.log();

  // Post stream-open event
  await post(`/api/agent/tasks/${taskId}/activity`, {
    node_name: hostname(),
    event_type: "stream_open",
    data: { label, source: "cc_stream" },
  });

  // Read stdin line by line and post each as a progress event
  const readline = await import("node:readline");
  const rl = readline.createInterface({ input: process.stdin });

  let seq = 0;
  for await (const line of rl) {
    seq++;
    const trimmed = line.trim();
    if (!trimmed) continue;

    await post(`/api/agent/tasks/${taskId}/activity`, {
      node_name: hostname(),
      event_type: "progress",
      data: {
        message: trimmed,
        seq,
        source: "cc_stream",
        label,
      },
    });
    console.log(`  \x1b[32m→\x1b[0m [${seq}] ${trimmed}`);
  }

  // Post stream-close
  await post(`/api/agent/tasks/${taskId}/activity`, {
    node_name: hostname(),
    event_type: "stream_close",
    data: { label, seq, source: "cc_stream" },
  });
  console.log(`\x1b[36m◉\x1b[0m Stream closed (${seq} messages)`);
}

export async function watchTask(args) {
  const { get, post, buildUrl, getApiBase } = await import("../api.mjs");

  let taskId = args[0] || "";
  const verbose = args.includes("--verbose") || args.includes("-v");
  const plain = args.includes("--plain");

  // If no task ID, find the most recent running task
  if (!taskId || taskId.startsWith("-")) {
    const data = await get("/api/agent/tasks", { status: "running", limit: 1 });
    if (data?.tasks?.[0]) {
      taskId = data.tasks[0].id;
    } else {
      console.log("\x1b[33m⚠\x1b[0m No running tasks to watch.");
      return;
    }
  }

  // Use the live panel for TTY, fall back to plain mode for pipes
  if (!plain && process.stdout.isTTY && !process.env.CI) {
    const { runTaskWatcher } = await import("../ui/task_watcher.mjs");
    await runTaskWatcher(taskId, { verbose, api: { get, post, buildUrl } });
    return;
  }

  // ── Plain/legacy mode (pipe-safe, no ANSI cursor control) ──────
  const task = await get(`/api/agent/tasks/${taskId}`);
  const idea = (task?.context || {}).idea_id || "?";
  const provider = task?.model || "?";
  console.log(`\x1b[36m◉\x1b[0m Watching: ${taskId.slice(0, 16)} [${task?.task_type || "?"}] via ${provider}`);
  console.log(`\x1b[2m  idea: ${idea}\x1b[0m`);
  console.log(`\x1b[2m  Ctrl+C to stop\x1b[0m`);
  console.log();

  const apiBase = getApiBase();
  const url = `${apiBase}/api/agent/tasks/${taskId}/events`;

  try {
    const resp = await fetch(url, {
      headers: { "Accept": "text/event-stream", "Cache-Control": "no-cache" },
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      while (buffer.includes("\n\n")) {
        const idx = buffer.indexOf("\n\n");
        const event = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);

        for (const line of event.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const d = JSON.parse(line.slice(6));
            const et = d.event_type || "?";
            const data = d.data || {};
            const ts = new Date(d.timestamp).toLocaleTimeString();

            if (et === "heartbeat") {
              const files = data.files_changed || 0;
              const summary = data.git_summary || "no changes";
              const elapsed = data.elapsed_s || 0;
              if (verbose || files > 0 || elapsed % 30 < 15) {
                console.log(`  \x1b[2m${ts}\x1b[0m \x1b[33m♥\x1b[0m ${elapsed}s | ${files} files | ${summary}`);
              }
            } else if (et === "progress") {
              const msg = data.message || data.preview || "";
              console.log(`  \x1b[2m${ts}\x1b[0m \x1b[36m→\x1b[0m ${msg}`);
            } else if (et === "provider_done") {
              const dur = data.duration_s || 0;
              const chars = data.output_chars || 0;
              const ok = data.success;
              const icon = ok ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m";
              console.log(`  \x1b[2m${ts}\x1b[0m ${icon} Done in ${dur}s | ${chars} chars`);
            } else if (et === "completed") {
              console.log(`  \x1b[2m${ts}\x1b[0m \x1b[32m🏁 Completed\x1b[0m`);
            } else if (et === "failed" || et === "timeout") {
              console.log(`  \x1b[2m${ts}\x1b[0m \x1b[31m✗ ${et}\x1b[0m`);
            } else if (et === "end") {
              console.log(`  \x1b[2m--- stream ended ---\x1b[0m`);
              return;
            } else if (et === "stream_open") {
              console.log(`  \x1b[2m${ts}\x1b[0m \x1b[36m◉ Stream: ${data.label || "opened"}\x1b[0m`);
            } else {
              if (verbose) {
                console.log(`  \x1b[2m${ts}\x1b[0m [${et}] ${JSON.stringify(data).slice(0, 80)}`);
              } else {
                console.log(`  \x1b[2m${ts}\x1b[0m [${et}]`);
              }
            }
          } catch {}
        }
      }
    }
  } catch (e) {
    if (e.name === "AbortError") return;
    console.log(`\x1b[31m✗\x1b[0m Stream error: ${e.message}`);
  }
}
