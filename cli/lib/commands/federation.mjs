/**
 * Federation commands: instances, sync, strategies, capabilities.
 *
 * Covers /api/federation/* endpoints beyond the basic node messaging
 * that lives in nodes.mjs.
 *
 * Usage:
 *   cc federation                         — list federation instances
 *   cc federation instances               — list instances
 *   cc federation instance <id>           — show instance detail
 *   cc federation register <id> <url>     — register a new instance
 *   cc federation sync                    — show sync history
 *   cc federation capabilities            — fleet capability summary
 *   cc federation stats [days]            — aggregated node stats
 *   cc federation strategies              — list routing strategies
 *   cc federation strategies compute      — compute strategies
 *   cc federation measurements <node-id>  — node measurement summaries
 */

import { get, post, del } from "../api.mjs";

function timeSince(iso) {
  if (!iso) return "?";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "now";
  if (min < 60) return `${min}m`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

/** List federated instances */
export async function listInstances() {
  const data = await get("/api/federation/instances");
  if (!data) {
    console.log("Could not fetch federation instances.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";

  const items = Array.isArray(data) ? data : data.instances || data.items || [];
  console.log();
  console.log(`${B}  FEDERATION INSTANCES${R} (${items.length})`);
  console.log(`  ${"─".repeat(65)}`);

  if (!items.length) {
    console.log(`  ${D}No federation instances registered.${R}`);
    console.log();
    return;
  }

  for (const inst of items) {
    const name = (inst.name || inst.id || "?").padEnd(25);
    const url = (inst.url || inst.base_url || "").slice(0, 35);
    const status = inst.status || "?";
    const color = status === "active" ? G : status === "offline" ? "\x1b[31m" : Y;
    console.log(`  ${color}●${R} ${name} ${D}${url}${R}`);
  }
  console.log();
}

/** Show instance detail */
export async function showInstance(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc federation instance <id>");
    return;
  }
  const data = await get(`/api/federation/instances/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Instance '${id}' not found.`);
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  INSTANCE: ${data.name || data.id}${R}`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [k, v] of Object.entries(data)) {
    if (v != null) {
      const display = typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
      console.log(`  ${k.padEnd(20)} ${display}`);
    }
  }
  console.log();
}

/** Register a new federated instance */
export async function registerInstance(args) {
  const [id, url, name] = args;
  if (!id || !url) {
    console.log("Usage: cc federation register <id> <url> [name]");
    return;
  }
  const payload = { id, url, name: name || id };
  const result = await post("/api/federation/instances", payload);
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Instance registered: ${result.id || id}`);
  } else {
    console.log("\x1b[31m✗\x1b[0m Registration failed.");
  }
}

/** Show sync history */
export async function showSyncHistory(args) {
  const limit = parseInt(args[0]) || 20;
  const data = await get("/api/federation/sync/history", { limit });
  if (!data) {
    console.log("Could not fetch sync history.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", RED = "\x1b[31m";

  const items = Array.isArray(data) ? data : data.history || data.items || [];
  console.log();
  console.log(`${B}  SYNC HISTORY${R} (${items.length})`);
  console.log(`  ${"─".repeat(65)}`);

  if (!items.length) {
    console.log(`  ${D}No sync history.${R}`);
    console.log();
    return;
  }

  for (const s of items) {
    const age = timeSince(s.synced_at || s.created_at);
    const source = (s.source_instance || s.instance_id || "?").padEnd(20);
    const count = s.items_synced ?? s.count ?? "?";
    const ok = s.success ?? s.status === "ok";
    const icon = ok ? `${G}✓${R}` : `${RED}✗${R}`;
    console.log(`  ${icon} ${D}${age.padEnd(5)}${R} ${source} ${D}${count} items${R}`);
  }
  console.log();
}

/** Fleet capability summary */
export async function showFleetCapabilities() {
  const data = await get("/api/federation/nodes/capabilities");
  if (!data) {
    console.log("Could not fetch fleet capabilities.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";

  console.log();
  console.log(`${B}  FLEET CAPABILITIES${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const caps = data.capabilities || data.providers || (Array.isArray(data) ? data : null);
  if (caps && Array.isArray(caps)) {
    for (const c of caps) {
      const name = (c.provider || c.name || "?").padEnd(20);
      const models = (c.models || []).join(", ").slice(0, 40);
      const count = c.node_count ?? c.count ?? "";
      console.log(`  ${G}◈${R} ${name} ${D}${models}${R} ${count ? `(${count} nodes)` : ""}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) {
        const display = typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
        console.log(`  ${k.padEnd(25)} ${display}`);
      }
    }
  }
  console.log();
}

/** Aggregated node stats */
export async function showNodeStats(args) {
  const days = parseInt(args[0]) || null;
  const params = days ? { window_days: days } : {};
  const data = await get("/api/federation/nodes/stats", params);
  if (!data) {
    console.log("Could not fetch node stats.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";

  console.log();
  console.log(`${B}  NODE STATS${R}${days ? ` (last ${days}d)` : ""}`);
  console.log(`  ${"─".repeat(60)}`);

  for (const [k, v] of Object.entries(data)) {
    if (v != null) {
      const display = typeof v === "object" ? JSON.stringify(v).slice(0, 70) : String(v);
      console.log(`  ${k.padEnd(30)} ${display}`);
    }
  }
  console.log();
}

/** Routing strategies */
export async function listStrategies() {
  const data = await get("/api/federation/strategies");
  if (!data) {
    console.log("Could not fetch strategies.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m";

  const strategies = data.strategies || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  ROUTING STRATEGIES${R} (${strategies.length})`);
  console.log(`  ${"─".repeat(65)}`);

  for (const s of strategies) {
    const name = (s.name || s.strategy || s.id || "?").padEnd(25);
    const desc = (s.description || "").slice(0, 40);
    const active = s.active ? `${G}active${R}` : `${D}inactive${R}`;
    console.log(`  ${name} ${active} ${D}${desc}${R}`);
  }
  console.log();
}

/** Compute routing strategies */
export async function computeStrategies() {
  console.log("Computing routing strategies...");
  const data = await post("/api/federation/strategies/compute", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Failed to compute strategies.");
    return;
  }
  console.log(`\x1b[32m✓\x1b[0m Strategies computed`);
  const count = data.updated || data.strategies_updated || data.count;
  if (count != null) console.log(`  Updated: ${count}`);
}

/** Node measurement summaries */
export async function showMeasurements(args) {
  const nodeId = args[0];
  if (!nodeId) {
    console.log("Usage: cc federation measurements <node-id> [window_hours]");
    return;
  }
  const hours = parseInt(args[1]) || null;
  const params = hours ? { window_hours: hours } : {};
  const data = await get(`/api/federation/nodes/${encodeURIComponent(nodeId)}/measurements`, params);
  if (!data) {
    console.log(`Could not fetch measurements for node '${nodeId}'.`);
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";

  const measurements = data.measurements || data.summaries || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  MEASUREMENTS: ${nodeId}${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (measurements.length) {
    for (const m of measurements) {
      const metric = (m.metric || m.name || "?").padEnd(25);
      const val = m.value ?? m.avg ?? "?";
      const unit = m.unit || "";
      console.log(`  ${metric} ${val} ${D}${unit}${R}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (typeof v !== "object") console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }
  console.log();
}

/** Federation overview */
export async function showFederationOverview() {
  await listInstances();
  await showFleetCapabilities();
}
