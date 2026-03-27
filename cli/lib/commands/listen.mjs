/**
 * cc listen — real-time event stream from the network
 *
 * Connects to the SSE endpoint and prints events as they arrive.
 * Messages, deploys, task completions, status changes — all pushed in real-time.
 *
 * Usage:
 *   cc listen              # Listen for events for this node (federation SSE)
 *   cc listen --ws         # Cross-service WebSocket pub/sub (/api/events/stream)
 *   cc listen --ws --event-types=runtime_event,test_ping
 */

import { hostname } from "node:os";
import { get } from "../api.mjs";

const API_BASE = process.env.COHERENCE_API_URL || "https://api.coherencycoin.com";

export async function listen(args) {
  if (args.includes("--ws")) {
    return listenEventStreamWebSocket(args.filter((a) => a !== "--ws"));
  }

  // Resolve our node ID
  const nodes = await get("/api/federation/nodes");
  const myNode = nodes?.find((n) => n.hostname === hostname());
  const nodeId = myNode?.node_id || "unknown";

  if (nodeId === "unknown") {
    console.log("\x1b[31m✗\x1b[0m Could not resolve node ID. Is the runner registered?");
    return;
  }

  const url = `${API_BASE}/api/federation/nodes/${nodeId}/stream`;

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

function parseKvArgs(argv) {
  let eventTypes = null;
  let entity = null;
  let entityId = null;
  let token = process.env.COHERENCE_EVENT_STREAM_TOKEN || null;
  for (const a of argv) {
    if (a.startsWith("--event-types=")) {
      eventTypes = a.slice("--event-types=".length);
    } else if (a.startsWith("--entity=")) {
      entity = a.slice("--entity=".length);
    } else if (a.startsWith("--entity-id=")) {
      entityId = a.slice("--entity-id=".length);
    } else if (a.startsWith("--token=")) {
      token = a.slice("--token=".length);
    }
  }
  return { eventTypes, entity, entityId, token };
}

function httpOriginToWs(httpBase) {
  const u = new URL(httpBase);
  const proto = u.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${u.host}`;
}

async function listenEventStreamWebSocket(args) {
  const WS = globalThis.WebSocket;
  if (typeof WS === "undefined") {
    console.log(
      "\x1b[31m✗\x1b[0m Global WebSocket is unavailable (need Node.js 22+ for --ws).",
    );
    return;
  }

  const { eventTypes, entity, entityId, token } = parseKvArgs(args);
  const q = new URLSearchParams();
  if (eventTypes) q.set("event_types", eventTypes);
  if (entity) q.set("entity", entity);
  if (entityId) q.set("entity_id", entityId);
  if (token) q.set("token", token);
  const qs = q.toString();
  const url = `${httpOriginToWs(API_BASE)}/api/events/stream${qs ? `?${qs}` : ""}`;

  console.log("\x1b[1m  EVENT STREAM (WebSocket)\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Stream: ${url}`);
  console.log(`  Press Ctrl+C to stop`);
  console.log();

  await new Promise((resolve) => {
    const ws = new WS(url);
    ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data);
        formatEventStream(event);
      } catch {
        console.log(String(ev.data));
      }
    };
    ws.onerror = () => {
      console.log("\x1b[31m✗\x1b[0m WebSocket error");
    };
    ws.onclose = () => resolve();
  });
}

function formatEventStream(msg) {
  const ts = new Date().toLocaleTimeString();
  const type = msg.event_type || "?";
  if (type === "heartbeat") {
    return;
  }
  if (type === "connected") {
    console.log(`  \x1b[32m●\x1b[0m \x1b[2m${ts}\x1b[0m Connected to event stream`);
    return;
  }
  const id = msg.entity_id ? ` ${msg.entity_id.slice(0, 12)}` : "";
  console.log(
    `  \x1b[2m${ts}\x1b[0m [\x1b[36m${type}\x1b[0m] ${msg.entity || "?"}${id}`,
  );
  if (msg.data && Object.keys(msg.data).length) {
    console.log(`    ${JSON.stringify(msg.data).slice(0, 200)}`);
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
