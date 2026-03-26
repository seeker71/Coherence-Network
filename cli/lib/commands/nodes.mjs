/**
 * Federation node commands: nodes, msg, cmd, broadcast
 */

import { get, post } from "../api.mjs";
import { hostname } from "node:os";

/**
 * Resolve a node target to a full node_id.
 * Accepts: full node_id, partial match, hostname, alias (mac/windows/win/gateway).
 */
async function resolveNode(target) {
  if (!target) return null;
  const nodes = await get("/api/federation/nodes");
  if (!Array.isArray(nodes) || nodes.length === 0) return target;

  const t = target.toLowerCase();

  // Built-in aliases
  const aliases = { mac: "macos", macos: "macos", win: "windows", windows: "windows", gateway: "gateway" };
  if (aliases[t]) {
    const match = nodes.find(n => (n.os_type || "").toLowerCase() === aliases[t]
      || (n.hostname || "").toLowerCase().includes(t));
    if (match) return match.node_id;
  }

  // Exact node_id match
  const exact = nodes.find(n => n.node_id === target);
  if (exact) return exact.node_id;

  // Partial node_id prefix
  const prefix = nodes.find(n => (n.node_id || "").startsWith(t));
  if (prefix) return prefix.node_id;

  // Hostname match (case-insensitive, partial)
  const hostMatch = nodes.find(n => (n.hostname || "").toLowerCase().includes(t));
  if (hostMatch) return hostMatch.node_id;

  // Still no match — return original (let API error)
  return target;
}

/** Get our own node ID */
async function getMyNodeId() {
  const myHost = hostname();
  const nodes = await get("/api/federation/nodes");
  if (Array.isArray(nodes)) {
    const mine = nodes.find(n => n.hostname === myHost);
    if (mine) return mine.node_id;
  }
  return myHost;
}

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
    console.log("Usage: cc msg <node|broadcast> <message text>");
    console.log("  cc msg broadcast Hello all nodes!");
    console.log("  cc msg mac Hello Mac node!");
    console.log("  cc msg windows Check status please");
    console.log("  cc msg seeker Hello by hostname match");
    return;
  }

  const myNodeId = await getMyNodeId();

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
    const resolvedTarget = await resolveNode(targetOrBroadcast);
    const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
      from_node: myNodeId,
      to_node: resolvedTarget,
      type: "text",
      text,
      payload: {},
    });
    if (result) {
      const label = resolvedTarget !== targetOrBroadcast
        ? `${targetOrBroadcast} (${resolvedTarget.slice(0, 12)})`
        : resolvedTarget.slice(0, 12);
      console.log(`\x1b[32m✓\x1b[0m Message sent to ${label}: ${text.slice(0, 60)}`);
    } else {
      console.log("\x1b[31m✗\x1b[0m Failed to send message");
    }
  }
}

/**
 * Send a command to a node (not a text message).
 * Usage: cc cmd <node> <command> [args...]
 * Examples:
 *   cc cmd mac update
 *   cc cmd windows status
 *   cc cmd all update
 */
export async function sendCommand(args) {
  const [target, command, ...extra] = args;

  if (!target || !command) {
    console.log("Usage: cc cmd <node|all> <command> [args...]");
    console.log("  cc cmd mac update          Tell Mac node to git pull");
    console.log("  cc cmd windows status      Request status from Windows");
    console.log("  cc cmd all update          Update all nodes");
    console.log("  cc cmd seeker restart      Restart by hostname match");
    console.log();
    console.log("Commands: update, status, restart, pause, resume");
    return;
  }

  const myNodeId = await getMyNodeId();
  const text = `${command} ${extra.join(" ")}`.trim();
  const payload = { command, args: extra };

  if (target === "broadcast" || target === "all") {
    const result = await post("/api/federation/broadcast", {
      from_node: myNodeId,
      to_node: null,
      type: "command",
      text,
      payload,
    });
    if (result) {
      console.log(`\x1b[32m✓\x1b[0m Command '${command}' broadcast to all nodes`);
    } else {
      console.log("\x1b[31m✗\x1b[0m Failed to broadcast command");
    }
  } else {
    const resolvedTarget = await resolveNode(target);
    const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
      from_node: myNodeId,
      to_node: resolvedTarget,
      type: "command",
      text,
      payload,
    });
    if (result) {
      const label = resolvedTarget !== target
        ? `${target} (${resolvedTarget.slice(0, 12)})`
        : resolvedTarget.slice(0, 12);
      console.log(`\x1b[32m✓\x1b[0m Command '${command}' sent to ${label}`);
    } else {
      console.log("\x1b[31m✗\x1b[0m Failed to send command");
    }
  }
}

export async function readMessages(args) {
  const myNodeId = await getMyNodeId();
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
