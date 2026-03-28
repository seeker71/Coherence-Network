/**
 * Federation commands
 *
 *   cc federation                     — list federation nodes
 *   cc federation nodes               — list nodes
 *   cc federation node <id>           — (alias for nodes detail)
 *   cc federation instances           — list federated instances
 *   cc federation instance <id>       — show a specific instance
 *   cc federation register <url>      — register a new node
 *   cc federation heartbeat <id>      — send heartbeat for a node
 *   cc federation capabilities        — fleet capability summary
 *   cc federation stats               — federation node stats
 *   cc federation sync                — trigger federation sync
 *   cc federation sync history        — sync history
 *   cc federation aggregates          — list federated aggregations
 *   cc federation strategies          — compute strategies
 *   cc federation msg <node_id> <msg> — send message to a node
 *   cc federation msgs <node_id>      — read messages from a node
 *   cc federation broadcast <msg>     — broadcast to all nodes
 */

import { get, post, del as apiDel } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  return str.slice(0, len - 3) + "...";
}

export async function listFederationNodes() {
  const data = await get("/api/federation/nodes");
  const nodes = Array.isArray(data) ? data : data?.nodes || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  FEDERATION NODES${R} (${nodes.length})`);
  console.log(`  ${"─".repeat(74)}`);

  if (!nodes.length) {
    console.log(`  ${D}No nodes registered.${R}`);
    console.log();
    return;
  }

  for (const n of nodes) {
    const id = truncate(n.node_id || n.id || "?", 20).padEnd(22);
    const url = truncate(n.url || n.address || "", 30).padEnd(32);
    const status = (n.status || n.state || "?").toLowerCase();
    const statusColor = status === "active" || status === "online" ? G
      : status === "offline" || status === "dead" ? RED : Y;
    const last = n.last_heartbeat ? n.last_heartbeat.slice(0, 16) : "";
    console.log(`  ${id} ${url} ${statusColor}${status}${R}  ${D}${last}${R}`);
  }
  console.log();
}

export async function listFederationInstances() {
  const data = await get("/api/federation/instances");
  const instances = Array.isArray(data) ? data : data?.instances || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m";

  console.log();
  console.log(`${B}  FEDERATION INSTANCES${R} (${instances.length})`);
  console.log(`  ${"─".repeat(74)}`);

  if (!instances.length) {
    console.log(`  ${D}No instances registered.${R}`);
    console.log();
    return;
  }

  for (const inst of instances) {
    const id = truncate(inst.id || inst.instance_id || "?", 24).padEnd(26);
    const url = truncate(inst.url || inst.base_url || "", 35).padEnd(37);
    const region = inst.region || inst.zone || "";
    console.log(`  ${id} ${url} ${D}${region}${R}`);
  }
  console.log();
}

export async function showFederationInstance(args) {
  const id = args[0];
  if (!id) { console.log("Usage: cc federation instance <id>"); return; }

  const data = await get(`/api/federation/instances/${encodeURIComponent(id)}`);
  if (!data) { console.log(`Instance '${id}' not found.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  INSTANCE: ${data.id || id}${R}`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null) console.log(`  ${k.padEnd(20)} ${JSON.stringify(v)}`);
  }
  console.log();
}

export async function registerFederationNode(args) {
  const url = args[0];
  const capabilities = args.slice(1);
  if (!url) { console.log("Usage: cc federation register <url> [capability...]"); return; }

  const body = { url };
  if (capabilities.length) body.capabilities = capabilities;

  const result = await post("/api/federation/nodes", body);
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Node registered: ${result.node_id || result.id || url}`);
    if (result.token) console.log(`  Token: ${result.token}`);
  } else {
    console.log("Registration failed.");
  }
}

export async function federationHeartbeat(args) {
  const nodeId = args[0];
  if (!nodeId) { console.log("Usage: cc federation heartbeat <node_id>"); return; }

  const result = await post(`/api/federation/nodes/${encodeURIComponent(nodeId)}/heartbeat`, {});
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Heartbeat accepted for ${nodeId}`);
    if (result.next_heartbeat_due) console.log(`  Next due: ${result.next_heartbeat_due}`);
  } else {
    console.log("Heartbeat failed.");
  }
}

export async function showFederationCapabilities() {
  const data = await get("/api/federation/nodes/capabilities");
  if (!data) { console.log("Could not fetch capabilities."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  FLEET CAPABILITIES${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.total_nodes != null) console.log(`  Total nodes:  ${data.total_nodes}`);
  if (data.active_nodes != null) console.log(`  Active:       ${data.active_nodes}`);

  const caps = data.capabilities || data.available_capabilities || {};
  if (typeof caps === "object" && Object.keys(caps).length) {
    console.log();
    console.log(`  ${D}CAPABILITIES${R}`);
    for (const [cap, count] of Object.entries(caps)) {
      console.log(`  ${cap.padEnd(25)} ${D}${count} nodes${R}`);
    }
  }
  console.log();
}

export async function showFederationStats() {
  const data = await get("/api/federation/nodes/stats");
  if (!data) { console.log("Could not fetch federation stats."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  FEDERATION STATS${R}`);
  console.log(`  ${"─".repeat(60)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }
  if (data.by_region) {
    console.log();
    console.log(`  ${D}BY REGION${R}`);
    for (const [region, stats] of Object.entries(data.by_region)) {
      const count = stats.count || stats.nodes || stats;
      console.log(`  ${region.padEnd(20)} ${D}${count}${R}`);
    }
  }
  console.log();
}

export async function triggerFederationSync() {
  const result = await post("/api/federation/sync", {});
  if (!result) { console.log("Sync failed."); return; }

  console.log();
  console.log(`\x1b[1m  FEDERATION SYNC\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (result.synced_nodes != null) console.log(`  Synced nodes: ${result.synced_nodes}`);
  if (result.synced_ideas != null) console.log(`  Synced ideas: ${result.synced_ideas}`);
  if (result.errors?.length) {
    console.log(`  \x1b[31mErrors: ${result.errors.length}\x1b[0m`);
    for (const e of result.errors.slice(0, 5)) {
      console.log(`    \x1b[31m✗\x1b[0m ${truncate(e.message || e, 60)}`);
    }
  } else {
    console.log(`  \x1b[32m✓\x1b[0m Sync complete`);
  }
  console.log();
}

export async function showSyncHistory() {
  const data = await get("/api/federation/sync/history");
  const history = Array.isArray(data) ? data : data?.history || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  SYNC HISTORY${R} (${history.length})`);
  console.log(`  ${"─".repeat(60)}`);

  for (const entry of history.slice(0, 20)) {
    const ts = entry.timestamp || entry.created_at || "";
    const date = ts ? ts.slice(0, 16) : "";
    const nodes = entry.synced_nodes ?? entry.node_count ?? "?";
    const status = (entry.status || "?").toLowerCase();
    const color = status === "success" || status === "completed" ? G : RED;
    console.log(`  ${D}${date}${R}  nodes: ${nodes}  ${color}${status}${R}`);
  }
  console.log();
}

export async function showFederationAggregates() {
  const data = await get("/api/federation/aggregates");
  const aggregates = Array.isArray(data) ? data : data?.aggregates || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  FEDERATION AGGREGATES${R} (${aggregates.length})`);
  console.log(`  ${"─".repeat(60)}`);

  for (const agg of aggregates) {
    const name = truncate(agg.name || agg.aggregate_id || agg.id || "?", 30).padEnd(32);
    const val = agg.value != null ? String(agg.value).padStart(10) : "         —";
    const updated = agg.updated_at ? agg.updated_at.slice(0, 10) : "";
    console.log(`  ${name} ${val}  ${D}${updated}${R}`);
  }
  console.log();
}

export async function sendFederationMessage(args) {
  const nodeId = args[0];
  const message = args.slice(1).join(" ");
  if (!nodeId || !message) {
    console.log("Usage: cc federation msg <node_id> <message>");
    return;
  }
  const result = await post(`/api/federation/nodes/${encodeURIComponent(nodeId)}/messages`, {
    message,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Message sent to ${nodeId}`);
  } else {
    console.log("Failed to send message.");
  }
}

export async function readFederationMessages(args) {
  const nodeId = args[0];
  if (!nodeId) { console.log("Usage: cc federation msgs <node_id>"); return; }

  const data = await get(`/api/federation/nodes/${encodeURIComponent(nodeId)}/messages`);
  const messages = Array.isArray(data) ? data : data?.messages || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  MESSAGES from ${nodeId}${R} (${messages.length})`);
  console.log(`  ${"─".repeat(60)}`);

  if (!messages.length) {
    console.log(`  ${D}No messages.${R}`);
    console.log();
    return;
  }

  for (const m of messages) {
    const ts = (m.created_at || m.timestamp || "").slice(0, 16);
    const from = m.from_node || m.sender || "";
    const body = truncate(m.message || m.content || m.body || "", 60);
    console.log(`  ${D}${ts}${R}  ${from ? `[${from}] ` : ""}${body}`);
  }
  console.log();
}

export async function broadcastFederation(args) {
  const message = args.join(" ");
  if (!message) { console.log("Usage: cc federation broadcast <message>"); return; }

  const result = await post("/api/federation/broadcast", { message });
  if (result) {
    const sent = result.sent_to ?? result.node_count ?? "?";
    console.log(`\x1b[32m✓\x1b[0m Broadcast sent to ${sent} nodes`);
  } else {
    console.log("Broadcast failed.");
  }
}

export function handleFederation(args) {
  const sub = args[0];
  const rest = args.slice(1);

  switch (sub) {
    case "nodes":         return listFederationNodes();
    case "node":          return listFederationNodes();
    case "instances":     return listFederationInstances();
    case "instance":      return showFederationInstance(rest);
    case "register":      return registerFederationNode(rest);
    case "heartbeat":     return federationHeartbeat(rest);
    case "capabilities":  return showFederationCapabilities();
    case "stats":         return showFederationStats();
    case "sync": {
      if (rest[0] === "history") return showSyncHistory();
      return triggerFederationSync();
    }
    case "aggregates":    return showFederationAggregates();
    case "msg":           return sendFederationMessage(rest);
    case "msgs":          return readFederationMessages(rest);
    case "messages":      return readFederationMessages(rest);
    case "broadcast":     return broadcastFederation(rest);
    default:
      return listFederationNodes();
  }
}
