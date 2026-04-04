/**
 * TaskWatcher — orchestrates SSE streaming + REST polling + LivePanel.
 *
 * Dual data source:
 *   1. SSE stream (`/tasks/{id}/events`) for real-time events
 *   2. REST poll (`/tasks/{id}`) every 3s for metadata (model, tokens, progress)
 *
 * Handles agent→user "ask" prompts inline via LivePanel.
 */

import { LivePanel } from "./live_panel.mjs";
import { C, color, fmtTime, fmtElapsed, truncate, isTTY } from "./ansi.mjs";

const POLL_INTERVAL_MS = 3000;
const SSE_RECONNECT_DELAY_MS = 2000;
const SSE_TIMEOUT_MS = 3600_000; // 1 hour

/**
 * Run the live task watcher.
 * @param {string} taskId
 * @param {object} opts
 * @param {boolean} [opts.verbose=false]
 * @param {object} api - The API client { get, post, buildUrl }
 */
export async function runTaskWatcher(taskId, { verbose = false, api }) {
  const { get, post, buildUrl } = api;

  // Fetch initial task metadata
  const initialTask = await get(`/api/agent/tasks/${taskId}`);
  if (!initialTask) {
    console.error(`${color("✗", C.red)} Task ${taskId} not found.`);
    return;
  }

  const taskType = initialTask.task_type || "task";
  const panel = new LivePanel({ taskId, taskType });

  // Extract initial metadata
  _updateMetaFromTask(panel, initialTask);

  let done = false;
  let pollTimer = null;
  const startTime = Date.now();

  // ── Cleanup handler ────────────────────────────────────────────

  function cleanup() {
    done = true;
    if (pollTimer) clearInterval(pollTimer);
    panel.destroy();
  }

  process.on("SIGINT", () => {
    panel.appendLog(color("\n  Interrupted.", C.dim));
    cleanup();
    process.exit(0);
  });

  // ── REST poll loop ─────────────────────────────────────────────

  pollTimer = setInterval(async () => {
    if (done) return;
    try {
      const task = await get(`/api/agent/tasks/${taskId}`);
      if (!task) return;
      _updateMetaFromTask(panel, task);
      panel.updateMeta({ elapsed_sec: (Date.now() - startTime) / 1000 });

      if (_isTerminal(task.status)) {
        done = true;
      }
    } catch { /* polling errors are non-fatal */ }
  }, POLL_INTERVAL_MS);

  // ── SSE event stream ───────────────────────────────────────────

  try {
    await _streamEvents(panel, taskId, { verbose, api, isDone: () => done, post, buildUrl });
  } catch (err) {
    if (!done) {
      panel.appendLog(color(`  SSE error: ${err.message}`, C.red));
    }
  }

  // Final metadata refresh
  try {
    const finalTask = await get(`/api/agent/tasks/${taskId}`);
    if (finalTask) _updateMetaFromTask(panel, finalTask);
    panel.updateMeta({ elapsed_sec: (Date.now() - startTime) / 1000 });
  } catch { /* best effort */ }

  // Show final status
  const status = panel.meta.status;
  const icon = status === "completed" ? color("✓", C.green, C.bold) :
               status === "failed" ? color("✗", C.red, C.bold) :
               color("●", C.yellow);
  panel.appendLog(`\n  ${icon} Task ${status} after ${fmtElapsed((Date.now() - startTime) / 1000)}\n`);

  cleanup();
}


// ── SSE stream processor ───────────────────────────────────────────

async function _streamEvents(panel, taskId, { verbose, api, isDone, post, buildUrl }) {
  const url = buildUrl(`/api/agent/tasks/${taskId}/events`);

  let retries = 0;
  const MAX_RETRIES = 3;

  while (!isDone() && retries < MAX_RETRIES) {
    try {
      const response = await fetch(url, {
        headers: { Accept: "text/event-stream" },
        signal: AbortSignal.timeout(SSE_TIMEOUT_MS),
      });

      if (!response.ok) {
        panel.appendLog(color(`  SSE HTTP ${response.status}`, C.red));
        retries++;
        await _sleep(SSE_RECONNECT_DELAY_MS);
        continue;
      }

      retries = 0; // reset on successful connection
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!isDone()) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          if (isDone()) break;
          const event = _parseSSEBlock(block);
          if (!event) continue;

          await _handleEvent(panel, event, { verbose, taskId, post, buildUrl });

          if (event.event_type === "end" || _isTerminal(event.event_type)) {
            return;
          }
        }
      }
    } catch (err) {
      if (isDone()) return;
      if (err.name === "TimeoutError" || err.name === "AbortError") return;
      retries++;
      if (retries < MAX_RETRIES) {
        panel.appendLog(color(`  SSE reconnecting (${retries}/${MAX_RETRIES})...`, C.dim));
        await _sleep(SSE_RECONNECT_DELAY_MS);
      }
    }
  }
}


// ── Event handlers ─────────────────────────────────────────────────

async function _handleEvent(panel, event, { verbose, taskId, post, buildUrl }) {
  const ts = fmtTime(event.timestamp || new Date().toISOString());
  const data = event.data || {};
  const type = event.event_type || "";

  switch (type) {
    case "heartbeat": {
      const files = data.files_changed ?? data.file_count ?? "";
      const summary = data.summary || data.git_summary || "";
      const sha = data.git_sha || "";
      panel.updateMeta({
        heartbeat_ago: 0,
        git_sha: sha || panel.meta.git_sha,
      });
      if (files || summary) {
        panel.appendLog(
          `  ${color(ts, C.dim)}  ${color("♥", C.red)} ${files ? `${files} files` : ""}${summary ? ` | ${truncate(summary, 60)}` : ""}`
        );
      }
      break;
    }

    case "progress": {
      const msg = data.message || data.preview || data.text || JSON.stringify(data);
      if (data.progress_pct != null) {
        panel.updateMeta({ progress_pct: data.progress_pct });
      }
      if (data.current_step) {
        panel.updateMeta({ current_step: data.current_step });
      }
      panel.appendLog(`  ${color(ts, C.dim)}  ${color("→", C.cyan)} ${truncate(msg, 100)}`);
      break;
    }

    case "provider_done": {
      const dur = data.duration_seconds || data.duration_sec || data.duration || "?";
      const chars = data.output_chars || data.chars || "?";
      const ok = data.success !== false;
      const icon = ok ? color("✓", C.green) : color("✗", C.red);
      // Extract token usage if present
      if (data.usage_prompt_tokens || data.prompt_tokens) {
        panel.updateMeta({
          tokens_in: data.usage_prompt_tokens || data.prompt_tokens || panel.meta.tokens_in,
          tokens_out: data.usage_completion_tokens || data.completion_tokens || panel.meta.tokens_out,
          tokens_total: data.usage_total_tokens || data.total_tokens || panel.meta.tokens_total,
        });
      }
      if (data.cost_usd || data.total_cost_usd) {
        panel.updateMeta({ cost_usd: data.cost_usd || data.total_cost_usd });
      }
      panel.appendLog(`  ${color(ts, C.dim)}  ${icon} provider_done in ${dur}s | ${chars} chars`);
      break;
    }

    case "completed":
    case "failed":
    case "timeout": {
      panel.updateMeta({ status: type });
      const icon = type === "completed" ? color("✓", C.green, C.bold) :
                   type === "failed" ? color("✗", C.red, C.bold) :
                   color("⏱", C.yellow);
      panel.appendLog(`  ${color(ts, C.dim)}  ${icon} ${type.toUpperCase()}`);
      break;
    }

    case "ask":
    case "control_ask": {
      const question = data.question || data.text || data.payload?.question || JSON.stringify(data);
      const answer = await panel.startAskPrompt(question);
      if (answer) {
        try {
          await post(`/api/agent/tasks/${taskId}/activity`, {
            node_id: "cli-user",
            node_name: "cli",
            provider: "human",
            event_type: "control_response_ask",
            data: { response: answer, question },
          });
          panel.appendLog(`  ${color(ts, C.dim)}  ${color("↩", C.green)} Answer sent.`);
        } catch (err) {
          panel.appendLog(`  ${color(ts, C.dim)}  ${color("✗", C.red)} Failed to send answer: ${err.message}`);
        }
      }
      break;
    }

    case "stream_open":
    case "stream_close":
      if (verbose) {
        panel.appendLog(`  ${color(ts, C.dim)}  ${color("~", C.dim)} ${type}`);
      }
      break;

    case "claimed":
    case "executing": {
      const node = data.node_name || data.node_id || "";
      const provider = data.provider || "";
      if (provider) panel.updateMeta({ provider });
      if (node) panel.updateMeta({ node_id: node });
      panel.appendLog(`  ${color(ts, C.dim)}  ${color("▸", C.cyan)} ${type}${node ? ` on ${node}` : ""}${provider ? ` (${provider})` : ""}`);
      break;
    }

    default:
      if (verbose) {
        panel.appendLog(`  ${color(ts, C.dim)}  ${color("·", C.dim)} ${type}: ${truncate(JSON.stringify(data), 80)}`);
      }
      break;
  }
}


// ── Metadata extraction from task object ───────────────────────────

function _updateMetaFromTask(panel, task) {
  const ctx = task.context || {};
  const route = ctx.route_decision || {};

  const updates = {};

  // Provider & model
  if (route.provider || route.billing_provider || ctx.executor) {
    updates.provider = route.provider || route.billing_provider || ctx.executor || panel.meta.provider;
  }
  if (task.model) {
    updates.model = task.model;
    // Also extract provider from model string if not set
    if (task.model.includes("/") && !updates.provider) {
      updates.provider = task.model.split("/")[0];
    }
  }

  // Progress
  if (task.progress_pct != null) updates.progress_pct = task.progress_pct;
  if (task.current_step) updates.current_step = task.current_step;

  // Status
  if (task.status) {
    updates.status = typeof task.status === "string" ? task.status : (task.status.value || task.status);
  }

  // Node
  if (task.claimed_by) updates.node_id = task.claimed_by;

  // Token usage from context telemetry
  if (ctx.usage_prompt_tokens) updates.tokens_in = ctx.usage_prompt_tokens;
  if (ctx.usage_completion_tokens) updates.tokens_out = ctx.usage_completion_tokens;
  if (ctx.usage_total_tokens) updates.tokens_total = ctx.usage_total_tokens;
  if (ctx.infrastructure_cost_usd) updates.cost_usd = ctx.infrastructure_cost_usd;

  if (Object.keys(updates).length > 0) {
    panel.updateMeta(updates);
  }
}


// ── Helpers ────────────────────────────────────────────────────────

function _isTerminal(status) {
  return ["completed", "failed", "timeout", "cancelled"].includes(status);
}

function _parseSSEBlock(block) {
  let data = null;
  for (const line of block.split("\n")) {
    if (line.startsWith("data: ")) {
      try {
        data = JSON.parse(line.slice(6));
      } catch {
        data = { raw: line.slice(6) };
      }
    }
  }
  return data;
}

function _sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
