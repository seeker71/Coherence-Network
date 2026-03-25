/**
 * cc diag publish <event> [message] — emit a diagnostic event from this node
 *
 * Used by agents in diagnostic mode to broadcast activity:
 *   cc diag publish heartbeat
 *   cc diag publish tool_call "running git status"
 *   cc diag publish reasoning "analyzing the API response schema"
 *   cc diag publish cc_cmd "cc ideas 5"
 *   cc diag publish error "failed to connect to API"
 *   cc diag publish checkpoint "saving progress"
 */

import { post, get } from "../api.mjs";
import { hostname } from "node:os";

export async function publishDiag(args) {
  if (args.length < 1) {
    console.log("Usage: cc diag publish <event> [message]");
    console.log("Events: heartbeat, tool_call, tool_result, reasoning, cc_cmd, cc_msg, error, checkpoint, started, finished");
    return;
  }

  const event = args[0];
  const message = args.slice(1).join(" ") || undefined;

  // Resolve node ID
  const nodes = await get("/api/federation/nodes");
  const myNode = nodes?.find((n) => n.hostname === hostname());
  const nodeId = myNode?.node_id || "unknown";

  const payload = {
    event,
    type: event,
    ...(message ? { text: message, message } : {}),
  };

  const result = await post(`/api/federation/nodes/${nodeId}/diag`, payload);
  if (result?.ok) {
    // Silent success — diagnostic mode shouldn't be noisy in the agent's own output
  }
}

/**
 * Start diagnostic mode — emit heartbeats and wrap cc commands with diagnostic events.
 *
 * cc diag mode — starts emitting heartbeat every 10s + wraps future cc calls
 */
export async function startDiagMode(args) {
  const nodes = await get("/api/federation/nodes");
  const myNode = nodes?.find((n) => n.hostname === hostname());
  const nodeId = myNode?.node_id || "unknown";

  console.log(`\x1b[1m  DIAGNOSTIC MODE\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Node: ${myNode?.hostname || "?"} (${nodeId.slice(0, 12)})`);
  console.log(`  Publishing to: /api/federation/nodes/${nodeId}/diag`);
  console.log(`  Subscribe with: cc diag live ${nodeId.slice(0, 12)}`);
  console.log(`  Press Ctrl+C to stop`);
  console.log();

  // Emit started event
  await post(`/api/federation/nodes/${nodeId}/diag`, {
    event: "started",
    type: "started",
    text: `Diagnostic mode started on ${myNode?.hostname || "?"}`,
  });

  // Heartbeat loop
  let count = 0;
  const interval = parseInt(args[0]) || 10;

  try {
    while (true) {
      count++;
      await post(`/api/federation/nodes/${nodeId}/diag`, {
        event: "heartbeat",
        type: "heartbeat",
        count,
        uptime_s: count * interval,
      });
      process.stdout.write(`\r  \x1b[32m●\x1b[0m heartbeat #${count} (every ${interval}s)`);
      await new Promise((r) => setTimeout(r, interval * 1000));
    }
  } catch {
    // Ctrl+C
  }

  console.log();
  await post(`/api/federation/nodes/${nodeId}/diag`, {
    event: "finished",
    type: "finished",
    text: `Diagnostic mode stopped after ${count} heartbeats`,
  });
  console.log(`  Stopped after ${count} heartbeats.`);
}
