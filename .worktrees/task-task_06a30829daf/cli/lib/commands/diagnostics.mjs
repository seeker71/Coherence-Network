/**
 * Diagnostics commands: diag, diag health, diag issues, diag runners, diag visibility
 */

import { get } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function showDiag() {
  const [effectiveness, pipeline] = await Promise.all([
    get("/api/agent/effectiveness"),
    get("/api/agent/pipeline-status"),
  ]);

  console.log();
  console.log(`\x1b[1m  DIAGNOSTICS\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);

  if (effectiveness) {
    console.log(`  \x1b[1mEffectiveness:\x1b[0m`);
    for (const [key, val] of Object.entries(effectiveness)) {
      console.log(`    ${key}: ${JSON.stringify(val)}`);
    }
  } else {
    console.log(`  Effectiveness: \x1b[2munavailable\x1b[0m`);
  }

  if (pipeline) {
    console.log(`  \x1b[1mPipeline Status:\x1b[0m`);
    for (const [key, val] of Object.entries(pipeline)) {
      console.log(`    ${key}: ${JSON.stringify(val)}`);
    }
  } else {
    console.log(`  Pipeline Status: \x1b[2munavailable\x1b[0m`);
  }
  console.log();
}

export async function showDiagHealth() {
  const data = await get("/api/agent/collective-health");
  if (!data) {
    console.log("Could not fetch collective health.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  COLLECTIVE HEALTH\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

export async function showDiagIssues() {
  const [fatal, monitor] = await Promise.all([
    get("/api/agent/fatal-issues"),
    get("/api/agent/monitor-issues"),
  ]);

  console.log();
  console.log(`\x1b[1m  ISSUES\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);

  const fatalList = Array.isArray(fatal) ? fatal : fatal?.issues || [];
  const monitorList = Array.isArray(monitor) ? monitor : monitor?.issues || [];

  if (fatalList.length > 0) {
    console.log(`  \x1b[31mFatal (${fatalList.length}):\x1b[0m`);
    for (const i of fatalList) {
      const desc = truncate(i.description || i.message || i.id || JSON.stringify(i), 60);
      console.log(`    \x1b[31m✗\x1b[0m ${desc}`);
    }
  } else {
    console.log(`  \x1b[32mNo fatal issues\x1b[0m`);
  }

  if (monitorList.length > 0) {
    console.log(`  \x1b[33mMonitor (${monitorList.length}):\x1b[0m`);
    for (const i of monitorList) {
      const desc = truncate(i.description || i.message || i.id || JSON.stringify(i), 60);
      console.log(`    \x1b[33m!\x1b[0m ${desc}`);
    }
  } else {
    console.log(`  \x1b[32mNo monitor issues\x1b[0m`);
  }
  console.log();
}

export async function showDiagRunners() {
  const raw = await get("/api/agent/runners");
  const data = Array.isArray(raw) ? raw : raw?.runners;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch runners.");
    return;
  }
  if (data.length === 0) {
    console.log("No runners found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  RUNNERS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(50)}`);
  for (const r of data) {
    const name = truncate(r.name || r.id || "?", 25);
    const status = r.status || "?";
    const dot = status === "active" || status === "running" ? "\x1b[32m●\x1b[0m" : "\x1b[2m○\x1b[0m";
    console.log(`  ${dot} ${name.padEnd(27)} ${status}`);
  }
  console.log();
}

export async function showDiagVisibility() {
  const data = await get("/api/agent/visibility");
  if (!data) {
    console.log("Could not fetch visibility.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  VISIBILITY\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

/**
 * cc diag live [node_id] — subscribe to real-time diagnostic events from agents.
 *
 * Shows: heartbeat, tool usage, reasoning steps, cc ingress/egress, messages.
 * Use node_id='*' or omit to see all nodes.
 */
export async function showDiagLive(args) {
  const API_BASE = process.env.COHERENCE_API_URL || "https://api.coherencycoin.com";
  const nodeId = args[0] || "*";

  console.log(`\x1b[1m  DIAGNOSTIC STREAM\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Subscribing to: ${nodeId === "*" ? "all nodes" : nodeId}`);
  console.log(`  Press Ctrl+C to stop`);
  console.log();

  const url = `${API_BASE}/api/federation/nodes/${encodeURIComponent(nodeId)}/diag/stream`;

  try {
    const response = await fetch(url, {
      headers: { Accept: "text/event-stream" },
      signal: AbortSignal.timeout(3600000),
    });

    if (!response.ok) {
      console.log(`\x1b[31m✗\x1b[0m HTTP ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          formatDiagEvent(event);
        } catch {}
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") {
      console.log(`\x1b[31m✗\x1b[0m ${e.message}`);
    }
  }
}

function formatDiagEvent(e) {
  const ts = new Date(e.timestamp || Date.now()).toLocaleTimeString();
  const node = (e.node_id || "?").slice(0, 8);
  const type = e.event || e.type || e.event_type || "?";

  const colors = {
    heartbeat: "\x1b[32m",    // green
    tool_call: "\x1b[36m",    // cyan
    tool_result: "\x1b[36m",
    reasoning: "\x1b[33m",    // yellow
    cc_cmd: "\x1b[35m",       // magenta
    cc_msg: "\x1b[35m",
    msg_received: "\x1b[34m", // blue
    msg_sent: "\x1b[34m",
    started: "\x1b[1m",       // bold
    finished: "\x1b[1m",
    error: "\x1b[31m",        // red
    checkpoint: "\x1b[32m",
    subscribed: "\x1b[2m",    // dim
  };
  const color = colors[type] || "\x1b[2m";
  const reset = "\x1b[0m";

  let detail = "";
  if (e.tool) detail = ` ${e.tool}`;
  if (e.text) detail = ` ${e.text.slice(0, 80)}`;
  if (e.message) detail = ` ${e.message.slice(0, 80)}`;
  if (e.step) detail = ` step ${e.step}`;
  if (e.command) detail = ` ${e.command}`;
  if (e.direction) detail = ` → ${e.direction.slice(0, 60)}`;
  if (e.output_lines) detail += ` (${e.output_lines} lines)`;

  console.log(`  ${color}${type.padEnd(14)}${reset} \x1b[2m${ts}\x1b[0m \x1b[2m[${node}]\x1b[0m${detail}`);
}
