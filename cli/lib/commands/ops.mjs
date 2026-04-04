import { createInterface } from "node:readline/promises";
import { hostname } from "node:os";
import { stdin, stdout } from "node:process";

import { get, getApiBase, post, request } from "../api.mjs";
import { getAdminKey } from "../config.mjs";

function taskCounts(payload) {
  return payload?.tasks?.counts?.by_status || {};
}

function truncate(value, length = 96) {
  const text = String(value || "").trim();
  if (text.length <= length) return text;
  return `${text.slice(0, Math.max(0, length - 1))}\u2026`;
}

function formatNumber(value, fallback = "n/a") {
  return Number.isFinite(Number(value)) ? String(value) : fallback;
}

function asTaskList(payload) {
  return Array.isArray(payload) ? payload : payload?.tasks || [];
}

function formatTimestamp(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString();
}

function printEvents(events, { jsonMode = false } = {}) {
  if (jsonMode) {
    console.log(JSON.stringify(events, null, 2));
    return;
  }
  console.log();
  console.log(`\x1b[1m  TASK EVENTS\x1b[0m`);
  console.log(`  ${"─".repeat(64)}`);
  if (!events.length) {
    console.log("  No task events recorded yet.");
    console.log();
    return;
  }
  for (const event of events) {
    const type = String(event.event_type || "?").padEnd(14);
    const ts = formatTimestamp(event.timestamp);
    const node = truncate(event.node_name || event.node_id || "?", 18);
    const detail = truncate(
      event.data?.message
      || event.data?.preview
      || event.data?.label
      || event.data?.error
      || JSON.stringify(event.data || {}),
      92,
    );
    console.log(`  ${type} ${ts}  ${node}  ${detail}`);
  }
  console.log();
}

function printSnapshot(payload) {
  const counts = taskCounts(payload);
  const health = payload?.health || {};
  const persistence = payload?.persistence || {};
  const config = payload?.config || {};
  const runners = payload?.runners || {};
  const friction = payload?.friction?.summary || {};
  const endpointAttention = payload?.runtime?.endpoint_attention?.items || [];
  const attention = payload?.tasks?.attention || [];
  const contextBudget = payload?.tasks?.context_budget || {};

  console.log();
  console.log(`\x1b[1m  OPS SNAPSHOT\x1b[0m`);
  console.log(`  ${"─".repeat(64)}`);
  console.log(`  API:         ${getApiBase()}`);
  console.log(`  Generated:   ${payload?.generated_at || "n/a"}`);
  console.log(`  Health:      ${health.status || "unknown"}  uptime=${health.uptime_human || "n/a"}  sha=${health.deployed_sha || "n/a"}`);
  console.log(`  Persistence: ${persistence.pass_contract ? "passing" : "attention"}`);
  console.log(`  Config:      env=${config.environment || "unknown"}  db=${config.database?.backend || "unknown"}  api=${config.provider_surfaces?.api_base_url || "n/a"}`);
  console.log(
    `  Tasks:       total=${formatNumber(payload?.tasks?.counts?.total, "0")} running=${formatNumber(counts.running, "0")} pending=${formatNumber(counts.pending, "0")} decision=${formatNumber(counts.needs_decision, "0")}`,
  );
  console.log(
    `  Runners:     total=${formatNumber(runners.total, "0")} running=${formatNumber(runners.running, "0")} stale=${formatNumber(runners.stale, "0")}`,
  );
  console.log(
    `  Friction:    open=${formatNumber(friction.open_events, "0")} total=${formatNumber(friction.total_events, "0")} energy=${formatNumber(friction.total_energy_loss, "0")}`,
  );
  console.log(
    `  Context:     score=${formatNumber(contextBudget.score)} flagged=${formatNumber(contextBudget.flagged_tasks, "0")}/${formatNumber(contextBudget.task_count, "0")} avg_scope=${formatNumber(contextBudget.average_file_scope_count)} avg_cmds=${formatNumber(contextBudget.average_command_count)}`,
  );

  if (attention.length) {
    console.log();
    console.log(`  \x1b[1mAttention Tasks\x1b[0m`);
    for (const row of attention.slice(0, 5)) {
      console.log(`    ! ${row.id}  ${truncate(row.direction, 80)}`);
    }
  }

  if (endpointAttention.length) {
    console.log();
    console.log(`  \x1b[1mRuntime Attention\x1b[0m`);
    for (const item of endpointAttention.slice(0, 5)) {
      console.log(
        `    • ${item.endpoint}  score=${formatNumber(item.attention_score)}  p95=${formatNumber(item.p95_runtime_ms)}ms  count=${formatNumber(item.event_count, "0")}`,
      );
    }
  }

  if ((contextBudget.priority_actions || []).length) {
    console.log();
    console.log(`  \x1b[1mContext Actions\x1b[0m`);
    for (const item of contextBudget.priority_actions.slice(0, 4)) {
      console.log(`    • ${item.summary}`);
    }
  }

  console.log();
}

async function fetchOverview() {
  const adminKey = String(getAdminKey() || "").trim();
  const primary = await request("GET", "/api/agent/diagnostics/overview", {
    headers: adminKey ? { "X-Admin-Key": adminKey } : {},
  });
  if (primary.ok && primary.json) {
    return primary.json;
  }

  const [health, counts, runningRaw, attentionRaw, runnersRaw, friction] = await Promise.all([
    get("/api/health"),
    get("/api/agent/tasks/count"),
    get("/api/agent/tasks", { status: "running", limit: 8 }),
    get("/api/agent/tasks/attention", { limit: 8 }),
    get("/api/agent/runners", { include_stale: true, limit: 20 }),
    get("/api/friction/report"),
  ]);

  if (!health && !counts && !runningRaw && !attentionRaw && !runnersRaw && !friction) {
    return null;
  }

  const running = asTaskList(runningRaw);
  const attention = asTaskList(attentionRaw);
  const runners = Array.isArray(runnersRaw) ? runnersRaw : runnersRaw?.runners || [];
  const byStatus = counts?.by_status || {};

  return {
    generated_at: new Date().toISOString(),
    config: {
      environment: "unknown",
      database: { backend: "unknown" },
      provider_surfaces: {
        api_base_url: getApiBase(),
        web_ui_base_url: null,
      },
    },
    health: health || {},
    persistence: {
      pass_contract: Boolean(health?.database_ok ?? health?.schema_ok ?? false),
    },
    tasks: {
      counts: counts || {
        total: running.length + attention.length,
        by_status: byStatus,
      },
      recent: running.slice(0, 5),
      active: running,
      attention_total: attention.length,
      attention,
    },
    runners: {
      total: runners.length,
      stale: runners.filter((row) => Boolean(row.is_stale)).length,
      running: runners.filter((row) => String(row.status || "").toLowerCase() === "running").length,
      items: runners,
    },
    runtime: {
      endpoint_attention: { items: [] },
      recent_events: [],
    },
    friction: {
      summary: friction || {
        total_events: 0,
        open_events: 0,
        total_energy_loss: 0,
      },
      events: friction?.events || [],
    },
  };
}

async function fetchTaskLog(taskId) {
  const result = await request("GET", `/api/agent/tasks/${encodeURIComponent(taskId)}/log`);
  if (!result.ok) {
    return { error: `Task log request failed with HTTP ${result.status}` };
  }
  const payload = result.json || {};
  return {
    content: payload.content || payload.log || result.text || "",
    path: payload.path || null,
  };
}

async function fetchTaskEvents(taskId) {
  const result = await request("GET", `/api/agent/tasks/${encodeURIComponent(taskId)}/stream`);
  if (!result.ok) {
    return { error: `Task event request failed with HTTP ${result.status}` };
  }
  const events = Array.isArray(result.json) ? result.json : [];
  return { events };
}

async function fetchRunners() {
  const payload = await get("/api/agent/runners", { include_stale: true, limit: 100 });
  return Array.isArray(payload) ? payload : payload?.runners || [];
}

async function fetchNodes() {
  const payload = await get("/api/federation/nodes");
  return Array.isArray(payload) ? payload : [];
}

function normalizeTarget(value) {
  return String(value || "").trim().toLowerCase();
}

function resolveNodeByTarget(nodes, target) {
  const normalized = normalizeTarget(target);
  if (!normalized) return null;
  return (
    nodes.find((node) => String(node.node_id || "").toLowerCase() === normalized)
    || nodes.find((node) => String(node.node_id || "").toLowerCase().startsWith(normalized))
    || nodes.find((node) => normalizeTarget(node.hostname).includes(normalized))
    || null
  );
}

async function resolveRunnerCommandTarget(target) {
  const [runners, nodes] = await Promise.all([fetchRunners(), fetchNodes()]);
  const normalized = normalizeTarget(target);
  const runner = runners.find((row) => {
    const runnerId = normalizeTarget(row.runner_id);
    const host = normalizeTarget(row.host);
    return runnerId === normalized
      || runnerId.startsWith(normalized)
      || host === normalized
      || host.includes(normalized);
  }) || null;

  if (runner) {
    const node = resolveNodeByTarget(nodes, runner.host || runner.runner_id);
    if (node) {
      return {
        node,
        runner,
      };
    }
  }

  const node = resolveNodeByTarget(nodes, target);
  if (!node) return null;
  return { node, runner };
}

async function getSenderNodeId(nodes) {
  const localHost = hostname();
  const node = nodes.find((row) => normalizeTarget(row.hostname) === normalizeTarget(localHost));
  if (node?.node_id) return node.node_id;
  return `ops-${localHost}`.slice(0, 32);
}

function printRunnerResolution(resolution, command) {
  const label = resolution.runner
    ? `${resolution.runner.runner_id}${resolution.runner.host ? ` (${resolution.runner.host})` : ""}`
    : `${resolution.node.hostname || resolution.node.node_id}`;
  console.log(`\x1b[32m✓\x1b[0m Command '${command}' sent to ${label}`);
}

export async function showOpsSnapshot(args = []) {
  const jsonMode = args.includes("--json");
  const payload = await fetchOverview();
  if (!payload) {
    console.log("Could not fetch diagnostics overview.");
    process.exitCode = 1;
    return;
  }
  if (jsonMode) {
    console.log(JSON.stringify(payload, null, 2));
    return;
  }
  printSnapshot(payload);
}

export async function showOpsEvents(args = []) {
  const taskId = args.find((value) => !value.startsWith("--")) || "";
  if (!taskId) {
    console.log("Usage: cc ops events <task_id> [--json] [--follow]");
    return;
  }
  if (args.includes("--follow")) {
    await followTaskEvents(taskId, { verbose: args.includes("--verbose") });
    return;
  }
  const jsonMode = args.includes("--json");
  const payload = await fetchTaskEvents(taskId);
  if (payload.error) {
    console.log(payload.error);
    process.exitCode = 1;
    return;
  }
  printEvents(payload.events, { jsonMode });
}

async function followTaskEvents(taskId, { verbose = false } = {}) {
  console.log(`\x1b[36m◉\x1b[0m Streaming task events for ${taskId}`);
  console.log(`\x1b[2m  Ctrl+C to stop\x1b[0m`);
  console.log();

  const url = `${getApiBase()}/api/agent/tasks/${encodeURIComponent(taskId)}/events`;
  try {
    const response = await fetch(url, {
      headers: { Accept: "text/event-stream", "Cache-Control": "no-cache" },
    });
    if (!response.ok) {
      console.log(`\x1b[31m✗\x1b[0m Stream error: HTTP ${response.status}`);
      process.exitCode = 1;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      while (buffer.includes("\n\n")) {
        const index = buffer.indexOf("\n\n");
        const block = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.event_type === "end") {
              console.log(`\x1b[2m--- stream ended ---\x1b[0m`);
              return;
            }
            printEvents([event], { jsonMode: false });
          } catch (error) {
            if (verbose) {
              console.log(`Failed to decode event: ${error.message}`);
            }
          }
        }
      }
    }
  } catch (error) {
    console.log(`\x1b[31m✗\x1b[0m Stream error: ${error.message}`);
    process.exitCode = 1;
  }
}

export async function sendOpsRunnerCommand(args = []) {
  const [target, command, ...extra] = args;
  if (!target || !command) {
    console.log("Usage: cc ops runner <runner|host|node> <status|pause|resume|restart> [args...]");
    return;
  }
  const resolution = await resolveRunnerCommandTarget(target);
  if (!resolution) {
    console.log(`Could not resolve runner or node target: ${target}`);
    process.exitCode = 1;
    return;
  }
  const nodes = await fetchNodes();
  const senderNodeId = await getSenderNodeId(nodes);
  const text = `${command} ${extra.join(" ")}`.trim();
  const payload = {
    from_node: senderNodeId,
    to_node: resolution.node.node_id,
    type: "command",
    text,
    payload: { command, args: extra },
  };
  const result = await post(`/api/federation/nodes/${senderNodeId}/messages`, payload);
  if (!result) {
    console.log(`\x1b[31m✗\x1b[0m Failed to send runner command '${command}'`);
    process.exitCode = 1;
    return;
  }
  printRunnerResolution(resolution, command);
}

async function watchSnapshot(seconds) {
  while (true) {
    console.clear();
    const payload = await fetchOverview();
    if (!payload) {
      console.log("Could not fetch diagnostics overview.");
    } else {
      printSnapshot(payload);
      console.log(`  Refreshing every ${seconds}s. Press Ctrl+C to stop.`);
    }
    await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
  }
}

export async function startOpsMode() {
  const rl = createInterface({ input: stdin, output: stdout });
  let selectedTaskId = "";
  let selectedEventsTaskId = "";

  try {
    while (true) {
      console.clear();
      const payload = await fetchOverview();
      if (!payload) {
        console.log("Could not fetch diagnostics overview.");
      } else {
        printSnapshot(payload);
      }

      if (selectedTaskId) {
        const logPayload = await fetchTaskLog(selectedTaskId);
        console.log(`\x1b[1m  Task Log: ${selectedTaskId}\x1b[0m`);
        console.log(`  ${"─".repeat(64)}`);
        if (logPayload.error) {
          console.log(`  ${logPayload.error}`);
        } else {
          if (logPayload.path) console.log(`  Path: ${logPayload.path}`);
          console.log();
          console.log(truncate(logPayload.content, 2400) || "No task log content yet.");
        }
        console.log();
      }

      if (selectedEventsTaskId) {
        const eventsPayload = await fetchTaskEvents(selectedEventsTaskId);
        console.log(`\x1b[1m  Task Events: ${selectedEventsTaskId}\x1b[0m`);
        console.log(`  ${"─".repeat(64)}`);
        if (eventsPayload.error) {
          console.log(`  ${eventsPayload.error}`);
          console.log();
        } else {
          printEvents(eventsPayload.events.slice(-12), { jsonMode: false });
        }
      }

      const raw = (await rl.question(
        "ops> [r]efresh [l]og [e]vents [s]tream [w]atch [d]ebug [m]odels [p]roviders [u]sage [q]uit: ",
      )).trim();
      if (!raw || raw === "r" || raw === "refresh") continue;
      if (raw === "q" || raw === "quit") break;
      if (raw === "c" || raw === "clear") {
        selectedTaskId = "";
        selectedEventsTaskId = "";
        continue;
      }
      if (raw.startsWith("l ")) {
        selectedTaskId = raw.slice(2).trim();
        continue;
      }
      if (raw.startsWith("e ")) {
        selectedEventsTaskId = raw.slice(2).trim();
        continue;
      }
      if (raw.startsWith("s ")) {
        await followTaskEvents(raw.slice(2).trim(), { verbose: false });
        continue;
      }
      if (raw.startsWith("w ")) {
        // Launch live watch panel for a task
        const { watchTask } = await import("./tasks.mjs");
        await watchTask([raw.slice(2).trim()]);
        continue;
      }
      if (raw === "d" || raw === "debug") {
        const { debugCommand } = await import("./debug.mjs");
        await debugCommand([]);
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      if (raw === "d on") {
        const { debugCommand } = await import("./debug.mjs");
        await debugCommand(["on"]);
        await new Promise((resolve) => setTimeout(resolve, 1500));
        continue;
      }
      if (raw === "d off") {
        const { debugCommand } = await import("./debug.mjs");
        await debugCommand(["off"]);
        await new Promise((resolve) => setTimeout(resolve, 1500));
        continue;
      }
      if (raw === "m" || raw === "models") {
        const { modelsCommand } = await import("./models.mjs");
        await modelsCommand([]);
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      if (raw === "p" || raw === "providers") {
        const { showProviderStats } = await import("./providers.mjs");
        await showProviderStats([]);
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      if (raw === "u" || raw === "usage") {
        const { usageCommand } = await import("./models.mjs");
        await usageCommand([]);
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      if (raw.startsWith("runner ")) {
        await sendOpsRunnerCommand(raw.slice("runner ".length).trim().split(/\s+/));
        continue;
      }
      console.log(`Unknown command: ${raw}`);
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
  } finally {
    rl.close();
  }
}

export async function handleOps(args = []) {
  const sub = args[0] || "";
  if (sub === "events") {
    await showOpsEvents(args.slice(1));
    return;
  }
  if (sub === "runner") {
    await sendOpsRunnerCommand(args.slice(1));
    return;
  }
  const snapshotMode = args.includes("--snapshot") || args.includes("--json") || !stdout.isTTY;
  const watchIndex = args.findIndex((value) => value === "--watch");
  if (watchIndex >= 0) {
    const seconds = Math.max(2, Number.parseInt(args[watchIndex + 1] || "5", 10) || 5);
    await watchSnapshot(seconds);
    return;
  }
  if (snapshotMode) {
    await showOpsSnapshot(args);
    return;
  }
  await startOpsMode();
}
