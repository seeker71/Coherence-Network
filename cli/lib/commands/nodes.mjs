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
    const sha = (node.git_sha || "").slice(0, 7);
    const shaAge = node.git_sha_updated_at
      ? relativeTime(Math.floor((now - new Date(node.git_sha_updated_at).getTime()) / 60000))
      : "";

    console.log(`  ${dot} \x1b[1m${hostName.padEnd(26)}\x1b[0m ${ago.padEnd(10)} \x1b[2m${shortId}\x1b[0m  ${os}`);
    if (sha) {
      console.log(`    sha \x1b[36m${sha}\x1b[0m${shaAge ? ` (updated ${shaAge})` : ""}`);
    }
    // Streak
    const streak = node.streak || {};
    const total = streak.total_resolved || 0;
    const attn = streak.attention || "idle";
    if (total > 0 || streak.executing > 0) {
      const icons = (streak.last_10 || []).map(s =>
        s === "ok" ? "\x1b[32m✓\x1b[0m" : s === "fail" ? "\x1b[31m✗\x1b[0m" : "\x1b[33mT\x1b[0m"
      ).join("");
      const rate = streak.success_rate != null ? `${Math.round(streak.success_rate * 100)}%` : "?";
      const attnColor = attn === "healthy" ? "\x1b[32m" : attn === "failing" ? "\x1b[31m" : attn === "slow" ? "\x1b[33m" : "\x1b[2m";
      const running = streak.executing > 0 ? ` \x1b[33m${streak.executing} running\x1b[0m` : "";
      console.log(`    ${icons} ${rate} ${attnColor}${attn}\x1b[0m${running}`);
      if (attn === "failing" || attn === "slow") {
        console.log(`    \x1b[2m→ ${streak.attention_detail}\x1b[0m`);
      }
    } else {
      console.log(`    \x1b[2midle — no recent tasks\x1b[0m`);
    }
    // System metrics
    const caps = node.capabilities || {};
    const sm = caps.system_metrics;
    if (sm) {
      const bar = (val, max, w = 10) => {
        const filled = Math.round((Math.min(val, max) / max) * w);
        const color = filled > w * 0.8 ? "\x1b[31m" : filled > w * 0.6 ? "\x1b[33m" : "\x1b[32m";
        return `${color}${"█".repeat(filled)}${"░".repeat(w - filled)}\x1b[0m`;
      };
      const parts = [];
      if (sm.cpu_percent != null) parts.push(`CPU ${bar(sm.cpu_percent, 100)} ${sm.cpu_percent}%`);
      if (sm.memory_percent != null) parts.push(`RAM ${bar(sm.memory_percent, 100)} ${sm.memory_percent}%`);
      if (sm.disk_percent != null) parts.push(`Disk ${bar(sm.disk_percent, 100)} ${sm.disk_percent}%`);
      if (parts.length) console.log(`    ${parts.join("  ")}`);
      const extra = [];
      if (sm.process_count != null) extra.push(`${sm.process_count} procs`);
      if (sm.net_sent_mb != null) extra.push(`↑${sm.net_sent_mb}MB ↓${sm.net_recv_mb || 0}MB`);
      if (sm.cpu_count != null) extra.push(`${sm.cpu_count} cores`);
      if (sm.memory_total_gb != null) {
        let memDetail = `${sm.memory_total_gb}GB total`;
        if (sm.memory_used_gb != null) memDetail += ` ${sm.memory_used_gb}GB used`;
        if (sm.memory_available_gb != null) memDetail += ` ${sm.memory_available_gb}GB free`;
        if (sm.memory_cached_gb != null) memDetail += ` (${sm.memory_cached_gb}GB cached)`;
        extra.push(memDetail);
      }
      if (sm.swap_percent != null && sm.swap_percent > 0) extra.push(`swap ${sm.swap_percent}%`);
      if (extra.length) console.log(`    \x1b[2m${extra.join(" · ")}\x1b[0m`);
    }
    if (providers.length > 0) {
      const pv = caps.provider_versions || {};
      const ps = caps.provider_streaks || {};
      const badges = providers.map(p => {
        const ver = pv[p];
        const streak = ps[p];
        let badge = providerBadge(p);
        if (ver && ver !== "unknown") badge += `\x1b[2m(${ver.slice(0, 24)})\x1b[0m`;
        if (streak && streak.total > 0) {
          const icons = (streak.last_10 || []).slice(-5).map(s =>
            s === "ok" ? "\x1b[32m·\x1b[0m" : "\x1b[31m·\x1b[0m"
          ).join("");
          const rate = streak.success_rate != null ? `${Math.round(streak.success_rate * 100)}%` : "?";
          badge += ` ${icons} ${rate}`;
        }
        return badge;
      });
      console.log(`    ${badges.join("  ")}`)
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
