/**
 * cc listen — real-time event stream from the network
 *
 * Connects to the SSE endpoint and prints events as they arrive.
 * Messages, deploys, task completions, status changes — all pushed in real-time.
 *
 * Usage:
 *   cc listen              # Listen for events for this node
 *   cc listen --all        # Listen for all events (broadcast)
 */

import { hostname } from "node:os";
import { get, getApiBase } from "../api.mjs";

export async function listen(args) {
  // Resolve our node ID
  const nodes = await get("/api/federation/nodes");
  const myNode = nodes?.find((n) => n.hostname === hostname());
  const nodeId = myNode?.node_id || "unknown";

  if (nodeId === "unknown") {
    console.log("\x1b[31m✗\x1b[0m Could not resolve node ID. Is the runner registered?");
    return;
  }

  const url = `${getApiBase()}/api/federation/nodes/${nodeId}/stream`;

  console.log("\x1b[1m  LISTENING\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Node:   ${myNode.hostname} (${nodeId.slice(0, 12)})`);
  console.log(`  Stream: ${url}`);
  console.log(`  Press Ctrl+C to stop`);
  console.log();

  try {
    const response = await fetch(url, {
      headers: { Accept: "text/event-stream" },
      signal: AbortSignal.timeout(3600000), // 1 hour max
    });

    if (!response.ok) {
      console.log(`\x1b[31m✗\x1b[0m Stream error: HTTP ${response.status}`);
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
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6));
            formatEvent(event);
          } catch {
            // Not JSON — skip
          }
        }
      }
    }
  } catch (e) {
    if (e.name === "AbortError") {
      console.log("\n  Stream timed out after 1 hour.");
    } else {
      console.log(`\n\x1b[31m✗\x1b[0m Stream error: ${e.message}`);
    }
  }
}

function formatEvent(event) {
  const ts = new Date().toLocaleTimeString();
  const type = event.event_type || event.type || "?";

  switch (type) {
    case "connected":
      console.log(`  \x1b[32m●\x1b[0m \x1b[2m${ts}\x1b[0m Connected to stream`);
      break;
    case "text":
    case "command":
    case "command_response":
      console.log(`  \x1b[33m◆\x1b[0m \x1b[2m${ts}\x1b[0m [${type}] from ${(event.from_node || "?").slice(0, 12)}`);
      console.log(`    ${event.text || "(no text)"}`);
      break;
    case "deploy":
      console.log(`  \x1b[36m▲\x1b[0m \x1b[2m${ts}\x1b[0m DEPLOY: ${event.text || "?"}`);
      break;
    case "task_completed":
      console.log(`  \x1b[32m✓\x1b[0m \x1b[2m${ts}\x1b[0m Task completed: ${event.task_type || "?"} — ${event.idea_name || "?"}`);
      break;
    case "task_failed":
      console.log(`  \x1b[31m✗\x1b[0m \x1b[2m${ts}\x1b[0m Task failed: ${event.task_type || "?"} — ${event.error || "?"}`);
      break;
    default:
      console.log(`  \x1b[2m${ts}\x1b[0m [${type}] ${JSON.stringify(event).slice(0, 100)}`);
  }
}
