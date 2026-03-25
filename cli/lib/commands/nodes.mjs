/**
 * Federation node commands: nodes, msg, broadcast
 */

import { get, post } from "../api.mjs";
import { hostname } from "node:os";

export async function listNodes() {
  const nodes = await get("/api/federation/nodes");
  if (!nodes || !Array.isArray(nodes)) {
    console.log("Could not fetch federation nodes.");
    return;
  }

  console.log();
  console.log("\x1b[1m  FEDERATION NODES\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);

  /** Format relative time */
  function relativeTime(min) {
    if (min < 1) return "just now";
    if (min < 60) return `${min}m ago`;
    if (min < 1440) return `${Math.floor(min / 60)}h ago`;
    return `${Math.floor(min / 1440)}d ago`;
  }

  /** Colored provider badge */
  function providerBadge(name) {
    const colors = { openrouter: "\x1b[36m", ollama: "\x1b[32m", anthropic: "\x1b[33m" };
    const color = colors[name.toLowerCase()] || "\x1b[2m";
    return `${color}[${name}]\x1b[0m`;
  }

  const now = Date.now();
  for (const node of nodes) {
    const lastSeen = node.last_seen_at ? new Date(node.last_seen_at) : null;
    const ageMs = lastSeen ? now - lastSeen.getTime() : Infinity;
    const ageMin = Math.floor(ageMs / 60000);

    // Status dot
    let dot = "\x1b[31m●\x1b[0m"; // red
    if (ageMin < 5) dot = "\x1b[32m●\x1b[0m"; // green
    else if (ageMin < 60) dot = "\x1b[33m●\x1b[0m"; // yellow

    // Providers
    let providers = [];
    try {
      providers = typeof node.providers_json === "string"
        ? JSON.parse(node.providers_json)
        : (node.providers || []);
    } catch { providers = []; }

    const shortId = (node.node_id || "").slice(0, 7);
    const ago = relativeTime(ageMin);
    const hostName = (node.hostname || "?").slice(0, 24);
    const os = node.os_type || "?";

    console.log(`  ${dot} \x1b[1m${hostName.padEnd(26)}\x1b[0m ${ago.padEnd(10)} \x1b[2m${shortId}\x1b[0m  ${os}`);
    if (providers.length > 0) {
      console.log(`    ${providers.map(providerBadge).join(" ")}`);
    }
  }
  console.log();
}

export async function sendMessage(args) {
  const [targetOrBroadcast, ...textParts] = args;
  const text = textParts.join(" ");

  if (!targetOrBroadcast || !text) {
    console.log("Usage: cc msg <node_id|broadcast> <message text>");
    console.log("  cc msg broadcast Hello all nodes!");
    console.log("  cc msg e66ff3d35dd4ccb1 Hello Mac node!");
    return;
  }

  // Determine our node ID from hostname
  const myHost = hostname();
  const nodes = await get("/api/federation/nodes");
  let myNodeId = null;
  if (Array.isArray(nodes)) {
    const mine = nodes.find(n => n.hostname === myHost);
    if (mine) myNodeId = mine.node_id;
  }
  if (!myNodeId) {
    // Fallback: use first 16 chars of hostname hash
    myNodeId = myHost;
  }

  if (targetOrBroadcast === "broadcast" || targetOrBroadcast === "all") {
    const result = await post("/api/federation/broadcast", {
      from_node: myNodeId,
      to_node: null,
      type: "text",
      text,
      payload: {},
    });
    if (result) {
      console.log(`\x1b[32m✓\x1b[0m Broadcast sent: ${text.slice(0, 60)}`);
    } else {
      console.log("\x1b[31m✗\x1b[0m Failed to broadcast");
    }
  } else {
    const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
      from_node: myNodeId,
      to_node: targetOrBroadcast,
      type: "text",
      text,
      payload: {},
    });
    if (result) {
      console.log(`\x1b[32m✓\x1b[0m Message sent to ${targetOrBroadcast.slice(0, 12)}: ${text.slice(0, 60)}`);
    } else {
      console.log("\x1b[31m✗\x1b[0m Failed to send message");
    }
  }
}

export async function readMessages(args) {
  const myHost = hostname();
  const nodes = await get("/api/federation/nodes");
  let myNodeId = null;
  if (Array.isArray(nodes)) {
    const mine = nodes.find(n => n.hostname === myHost);
    if (mine) myNodeId = mine.node_id;
  }
  if (!myNodeId) {
    console.log("Could not determine your node ID. Register first.");
    return;
  }

  const data = await get(`/api/federation/nodes/${myNodeId}/messages?unread_only=false&limit=20`);
  if (!data || !data.messages) {
    console.log("No messages.");
    return;
  }

  console.log();
  console.log("\x1b[1m  MESSAGES\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);

  if (data.messages.length === 0) {
    console.log("  No messages yet.");
  }

  for (const msg of data.messages) {
    const ts = msg.timestamp ? new Date(msg.timestamp).toLocaleString() : "?";
    const from = msg.from_node ? msg.from_node.slice(0, 12) : "?";
    const type = msg.type || "text";
    const unread = !msg.read_by?.includes(myNodeId) ? " \x1b[33m(new)\x1b[0m" : "";

    console.log(`  \x1b[2m${ts}\x1b[0m  [${type}] from ${from}${unread}`);
    console.log(`  ${msg.text || "(no text)"}`);
    console.log();
  }
}
