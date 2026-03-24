/**
 * Federation node commands: nodes, msg, cmd, broadcast
 */

import { get, post } from "../api.mjs";
import { hostname } from "node:os";

/**
 * Send a remote command to a node.
 * Usage: cc cmd <node_id_or_name> <command> [...args]
 * Commands: update, status, diagnose, restart, ping
 */
export async function sendCommand(args) {
  if (args.length < 2) {
    console.log("Usage: cc cmd <node_id_or_name> <command>");
    console.log("Commands: update, status, diagnose, restart, ping");
    return;
  }

  const [target, command, ...cmdArgs] = args;

  // Resolve target: could be node_id prefix or hostname
  const nodes = await get("/api/federation/nodes");
  const node = nodes?.find(
    (n) =>
      n.node_id?.startsWith(target) ||
      n.hostname?.toLowerCase().includes(target.toLowerCase()),
  );
  if (!node) {
    console.log(`Node not found: ${target}`);
    console.log("Available nodes:");
    for (const n of nodes || []) {
      console.log(`  ${n.node_id?.slice(0, 12)}  ${n.hostname}`);
    }
    return;
  }

  const myNodeId = nodes?.find(
    (n) => n.hostname === hostname(),
  )?.node_id || "unknown";

  console.log(
    `Sending \x1b[1m${command}\x1b[0m to \x1b[1m${node.hostname}\x1b[0m (${node.node_id?.slice(0, 12)})...`,
  );

  const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
    from_node: myNodeId,
    to_node: node.node_id,
    type: "command",
    text: `Remote command: ${command} ${cmdArgs.join(" ")}`.trim(),
    payload: { command, args: cmdArgs },
  });

  if (result?.id) {
    const msgId = result.id;
    console.log(`\x1b[32m✓\x1b[0m Command sent (msg ${msgId.slice(0, 12)})`);
    console.log("  Waiting for reply (up to 3 min)...");

    // Poll for reply
    const deadline = Date.now() + 180_000;
    const pollInterval = 10_000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, pollInterval));
      process.stdout.write(".");

      const inbox = await get(
        `/api/federation/nodes/${myNodeId}/messages?unread_only=false&limit=20`,
      );
      const reply = inbox?.messages?.find(
        (m) =>
          (m.type === "command_response" || m.type === "ack") &&
          m.payload?.in_reply_to === msgId,
      );
      if (reply) {
        console.log(`\n\x1b[32m✓\x1b[0m Reply from ${node.hostname}:`);
        console.log(`  ${reply.text}`);
        return;
      }
    }
    console.log("\n\x1b[33m⏱\x1b[0m No reply within 3 min. Check later: cc inbox");
  } else {
    console.log("\x1b[31m✗\x1b[0m Failed to send command");
  }
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

  const now = Date.now();
  for (const node of nodes) {
    const lastSeen = node.last_seen_at ? new Date(node.last_seen_at) : null;
    const ageMs = lastSeen ? now - lastSeen.getTime() : Infinity;
    const ageMin = Math.floor(ageMs / 60000);

    // Status dot
    let dot = "\x1b[31m●\x1b[0m"; // red
    if (ageMin < 5) dot = "\x1b[32m●\x1b[0m"; // green
    else if (ageMin < 60) dot = "\x1b[33m●\x1b[0m"; // yellow

    // OS icon
    const os = node.os_type || "?";
    const icon = os === "macos" ? "🍎" : os === "windows" ? "🪟" : os === "linux" ? "🐧" : "🖥️";

    // Providers
    let providers = [];
    try {
      providers = typeof node.providers_json === "string"
        ? JSON.parse(node.providers_json)
        : (node.providers || []);
    } catch { providers = []; }

    const ago = ageMin < 1 ? "now" : ageMin < 60 ? `${ageMin}m ago` : `${Math.floor(ageMin / 60)}h ago`;

    console.log(`  ${dot} ${icon}  \x1b[1m${node.hostname || "?"}\x1b[0m  ${ago}`);
    console.log(`     ${providers.join(", ")}`);
    console.log(`     id: ${node.node_id}`);
    console.log();
  }
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
    // Resolve target name to node_id
    const targetNode = Array.isArray(nodes)
      ? nodes.find(
          (n) =>
            n.node_id?.startsWith(targetOrBroadcast) ||
            n.hostname?.toLowerCase().includes(targetOrBroadcast.toLowerCase()),
        )
      : null;
    const toNodeId = targetNode?.node_id || targetOrBroadcast;
    const toName = targetNode?.hostname || targetOrBroadcast.slice(0, 12);

    const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
      from_node: myNodeId,
      to_node: toNodeId,
      type: "text",
      text,
      payload: {},
    });
    if (result?.id) {
      const msgId = result.id;
      console.log(`\x1b[32m✓\x1b[0m Message sent to ${toName}: ${text.slice(0, 60)}`);
      console.log("  Waiting for ack (up to 3 min)...");

      const deadline = Date.now() + 180_000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 10_000));
        process.stdout.write(".");
        const inbox = await get(
          `/api/federation/nodes/${myNodeId}/messages?unread_only=false&limit=20`,
        );
        const ack = inbox?.messages?.find(
          (m) => m.type === "ack" && m.payload?.in_reply_to === msgId,
        );
        if (ack) {
          console.log(`\n\x1b[32m✓\x1b[0m Acknowledged by ${toName}`);
          return;
        }
      }
      console.log("\n\x1b[33m⏱\x1b[0m No ack within 3 min. Node may be offline. Check: cc inbox");
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
