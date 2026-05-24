/**
 * Federation commands
 *
 *   coh federation                     — list federation nodes
 *   coh federation nodes               — list nodes
 *   coh federation node <id>           — (alias for nodes detail)
 *   coh federation instances           — list federated instances
 *   coh federation instance <id>       — show a specific instance
 *   coh federation register <url>      — register a new node
 *   coh federation heartbeat <id>      — send heartbeat for a node
 *   coh federation capabilities        — fleet capability summary
 *   coh federation stats               — federation node stats
 *   coh federation sync                — trigger federation sync
 *   coh federation sync history        — sync history
 *   coh federation aggregates          — list federated aggregations
 *   coh federation strategies          — compute strategies
 *   coh federation msg <node_id> <msg> — send message to a node
 *   coh federation msgs <node_id>      — read messages from a node
 *   coh federation broadcast <msg>     — broadcast to all nodes
 *   coh federation substrate-canonicals       — list local canonical shapes
 *   coh federation substrate-discover <url>   — exchange canonicals with a peer
 */

import { get, post, del as apiDel } from "../api.mjs";
import { truncate } from "../ui/ansi.mjs";


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
  if (!id) { console.log("Usage: coh federation instance <id>"); return; }

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
  if (!url) { console.log("Usage: coh federation register <url> [capability...]"); return; }

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
  if (!nodeId) { console.log("Usage: coh federation heartbeat <node_id>"); return; }

  const result = await post(`/api/federation/nodes/${encodeURIComponent(nodeId)}/heartbeat`, {});
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Heartbeat accepted for ${nodeId}`);
    if (result.next_heartbeat_due) console.log(`  Next due: ${result.next_heartbeat_due}`);
  } else {
    console.log("Heartbeat failed.");
  }
}

function _fmtCapList(items, max = 8) {
  const D = "\x1b[2m", R = "\x1b[0m";
  if (!items || items.length === 0) return `${D}(none declared)${R}`;
  if (items.length <= max) return items.join(", ");
  return `${items.slice(0, max).join(", ")}, ${D}+${items.length - max} more${R}`;
}

export async function showSelfCapabilities() {
  /* Self-sovereign capability manifest: this instance declaring its own
     truth. The fleet emerges from each instance's self-declaration, not
     a coerced aggregate. */
  let manifest;
  try {
    manifest = await get("/api/federation/capabilities/self");
  } catch (e) {
    console.log(`Could not fetch self capabilities: ${e.message}`);
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";
  console.log();
  console.log(`${B}  THIS INSTANCE'S CAPABILITIES${R}`);
  console.log(`  ${"─".repeat(72)}`);
  console.log(`  ${"Instance ID".padEnd(22)} ${manifest.instance_id}`);
  console.log(`  ${"Instance URL".padEnd(22)} ${manifest.instance_url}`);
  console.log(`  ${"Truth source".padEnd(22)} ${G}${manifest.truth_source}${R} ${D}(this instance is the only authority over these claims)${R}`);
  console.log(`  ${"Declared at".padEnd(22)} ${manifest.declared_at}`);
  console.log();
  console.log(`  ${B}Providers${R} ${D}(from model_routing.json)${R}`);
  console.log(`    ${_fmtCapList(manifest.providers)}`);
  console.log();
  console.log(`  ${B}Languages${R} ${D}(from translator SUPPORTED_LOCALES)${R}`);
  console.log(`    ${_fmtCapList(manifest.language_coverage)}`);
  console.log();
  console.log(`  ${B}Substrate canonicals${R} ${D}(from modality_shapes canonical_shape_names)${R}`);
  console.log(`    ${_fmtCapList(manifest.substrate_canonicals, 6)}`);
  console.log();
  console.log(`  ${B}Economics${R}`);
  const econ = manifest.economics || {};
  console.log(`    cc_accepted:     ${econ.cc_accepted ? G + "yes" + R : D + "no" + R}`);
  console.log(`    cc_rate_per_usd: ${econ.cc_rate_per_usd ?? D + "—" + R}`);
  console.log(`    staking:         ${econ.staking_enabled ? G + "on" + R : D + "off" + R}`);

  // Peer alignment hint — show whether any peer secrets are held.
  let peers = [];
  try {
    peers = await get("/api/federation/instances");
  } catch { /* none registered */ }
  const signedPeers = (peers || []).filter((p) => p && p.public_key);
  console.log();
  if (signedPeers.length === 0) {
    console.log(`  ${D}No peers registered with shared secrets — alignment skipped.${R}`);
    console.log(`  ${D}Each instance speaks its own truth; alignment is a comparison, not a requirement.${R}`);
  } else {
    console.log(`  ${B}PEERS WITH SHARED SECRETS${R} ${D}(${signedPeers.length})${R}`);
    for (const p of signedPeers.slice(0, 10)) {
      console.log(`    ${D}•${R} ${p.instance_id}  ${D}${p.endpoint_url || ""}${R}`);
    }
    console.log(`  ${D}Fetch a peer's manifest from their /federation/capabilities/sign,${R}`);
    console.log(`  ${D}then POST to /federation/capabilities/{peer_id}/verify for alignment.${R}`);
  }
  console.log();
}

export async function showFleetCapabilities() {
  /* Aggregated fleet view across registered nodes (legacy aggregate). */
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
    console.log("Usage: coh federation msg <node_id> <message>");
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
  if (!nodeId) { console.log("Usage: coh federation msgs <node_id>"); return; }

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
  if (!message) { console.log("Usage: coh federation broadcast <message>"); return; }

  const result = await post("/api/federation/broadcast", { message });
  if (result) {
    const sent = result.sent_to ?? result.node_count ?? "?";
    console.log(`\x1b[32m✓\x1b[0m Broadcast sent to ${sent} nodes`);
  } else {
    console.log("Broadcast failed.");
  }
}

// ── Substrate canonical exchange — freedom-preserving discovery ──────

export async function listSubstrateCanonicals() {
  const data = await get("/api/federation/substrate/canonicals");
  const canonicals = data?.canonicals || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  LOCAL SUBSTRATE CANONICALS${R} (${canonicals.length})`);
  console.log(`  ${"─".repeat(76)}`);

  if (!canonicals.length) {
    console.log(`  ${D}No canonicals declared.${R}`);
    console.log();
    return;
  }

  for (const c of canonicals) {
    const name = truncate(c.canonical_name, 38).padEnd(40);
    const hash = (c.content_hash || "").slice(0, 12);
    const interned = c.interned ? `${G}interned${R}` : `${Y}declared${R}`;
    const members = c.member_count != null ? ` ${D}members:${c.member_count}${R}` : "";
    console.log(`  ${name} ${D}${hash}${R}  ${interned}${members}`);
  }
  console.log();
}

export async function substrateDiscoverPeer(args) {
  // Two arg forms:
  //   coh federation substrate-discover --peer-url <url> [--peer-id <id>]
  //   coh federation substrate-discover <url>
  let peerUrl = null;
  let peerId = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--peer-url") { peerUrl = args[++i]; continue; }
    if (args[i] === "--peer-id")  { peerId  = args[++i]; continue; }
    if (!peerUrl && !args[i].startsWith("-")) peerUrl = args[i];
  }
  if (!peerUrl) {
    console.log("Usage: coh federation substrate-discover --peer-url <url> [--peer-id <id>]");
    return;
  }
  const trimmed = peerUrl.replace(/\/+$/, "");
  if (!peerId) peerId = trimmed;

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", C = "\x1b[36m";

  let peerData;
  try {
    const res = await fetch(`${trimmed}/api/federation/substrate/canonicals`);
    if (!res.ok) {
      console.log(`Peer canonicals fetch failed: HTTP ${res.status}`);
      return;
    }
    peerData = await res.json();
  } catch (err) {
    console.log(`Could not reach peer ${trimmed}: ${err.message}`);
    return;
  }

  const peerCanonicals = (peerData?.canonicals || []).map((c) => ({
    canonical_name: c.canonical_name,
    role_slots: c.role_slots || [],
    modality_tags: c.modality_tags || [],
    content_hash: c.content_hash,
  }));

  // Send peer's inventory to our local exchange endpoint for attestation.
  const result = await post("/api/federation/substrate/exchange", {
    peer_instance_id: peerId,
    peer_endpoint_url: trimmed,
    canonicals: peerCanonicals,
  });
  if (!result) { console.log("Exchange failed."); return; }

  console.log();
  console.log(`${B}  SUBSTRATE DISCOVERY${R}  peer: ${C}${peerId}${R}`);
  console.log(`  ${"─".repeat(76)}`);
  console.log(`  received:   ${result.received}`);
  console.log(`  ${G}aligned:    ${result.aligned}${R}   ${D}structurally identical${R}`);
  console.log(`  ${Y}diverged:   ${result.diverged}${R}   ${D}same name, different shape${R}`);
  console.log(`  ${C}discovered: ${result.discovered}${R}   ${D}peer carries, we do not${R}`);
  console.log();

  if (result.attestations?.length) {
    const byStatus = { aligned: [], diverged: [], discovered: [] };
    for (const a of result.attestations) {
      (byStatus[a.alignment_status] || []).push(a);
    }
    for (const status of ["diverged", "discovered", "aligned"]) {
      if (!byStatus[status].length) continue;
      console.log(`  ${D}${status.toUpperCase()}${R}`);
      for (const a of byStatus[status].slice(0, 20)) {
        const name = truncate(a.canonical_name, 40).padEnd(42);
        const ph = (a.peer_content_hash || "").slice(0, 10);
        const lh = (a.local_content_hash || "—       ").slice(0, 10);
        console.log(`    ${name} peer:${ph}  local:${lh}`);
      }
      console.log();
    }
  }
  console.log(`  ${D}No local cells were modified — sovereignty preserved.${R}`);
  console.log();
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
    case "capabilities":
    case "caps":          return showSelfCapabilities();
    case "fleet":         return showFleetCapabilities();
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
    case "substrate-canonicals": return listSubstrateCanonicals();
    case "substrate-discover":   return substrateDiscoverPeer(rest);
    default:
      return listFederationNodes();
  }
}
