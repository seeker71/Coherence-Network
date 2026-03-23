/**
 * Status commands: status, resonance
 */

import { get } from "../api.mjs";
import { getContributorId, getHubUrl } from "../config.mjs";
import { hostname } from "node:os";

export async function showStatus() {
  // Fetch everything in parallel
  const [health, ideas, nodes, pendingData, runningData, completedData, coherence, ledger, messages] =
    await Promise.all([
      get("/api/health"),
      get("/api/ideas/count"),
      get("/api/federation/nodes"),
      get("/api/agent/tasks", { status: "pending", limit: 100 }),
      get("/api/agent/tasks", { status: "running", limit: 100 }),
      get("/api/agent/tasks", { status: "completed", limit: 5 }),
      get("/api/coherence/score"),
      getContributorId() ? get(`/api/contributions/ledger/${encodeURIComponent(getContributorId())}`) : null,
      getContributorId() ? get(`/api/federation/nodes/${encodeURIComponent(getContributorId())}/messages`, { unread_only: true, limit: 10 }) : null,
    ]);

  const taskList = (d) => {
    if (!d) return [];
    if (Array.isArray(d)) return d;
    return d.tasks || [];
  };

  const pending = taskList(pendingData);
  const running = taskList(runningData);
  const completed = taskList(completedData);

  /** Extract a human-readable name from a task */
  function _taskName(t) {
    const ctx = t.context || {};
    if (ctx.idea_name) return ctx.idea_name.slice(0, 45);
    if (t.direction) {
      // Extract the idea name from "Write a spec for: <name>." pattern
      const match = t.direction.match(/for:\s*(.+?)[\.\n]/);
      if (match) return match[1].slice(0, 45);
      return t.direction.slice(0, 45);
    }
    return t.id?.slice(0, 20) || "?";
  }

  console.log();
  console.log("\x1b[1m  COHERENCE NETWORK STATUS\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);

  // API health
  if (health) {
    const schemaIcon = health.schema_ok === false ? "\x1b[31m✗\x1b[0m" : "\x1b[32m✓\x1b[0m";
    console.log(`  API:         \x1b[32m${health.status}\x1b[0m (${health.version || "?"}) ${schemaIcon} schema`);
    console.log(`  Uptime:      ${health.uptime_human || "?"}`);
  } else {
    console.log(`  API:         \x1b[31moffline\x1b[0m`);
  }

  // Coherence score
  if (coherence && coherence.score != null) {
    const score = coherence.score.toFixed(2);
    const color = coherence.score >= 0.7 ? "\x1b[32m" : coherence.score >= 0.4 ? "\x1b[33m" : "\x1b[31m";
    console.log(`  Coherence:   ${color}${score}\x1b[0m (${coherence.signals_with_data || 0}/${coherence.total_signals || 0} signals)`);
  }

  console.log(`  Hub:         ${getHubUrl()}`);
  console.log(`  Node:        ${hostname()}`);
  console.log(`  Identity:    ${getContributorId() || "\x1b[33m(not set — run: cc identity set <id>)\x1b[0m"}`);

  // Ideas
  if (ideas) {
    const byStatus = ideas.by_status || {};
    console.log(`  Ideas:       ${ideas.total || 0} (${byStatus.validated || 0} validated, ${byStatus.none || 0} open)`);
  }

  // Nodes
  if (Array.isArray(nodes) && nodes.length > 0) {
    const now = Date.now();
    const alive = nodes.filter((n) => {
      const last = n.last_seen_at || n.last_heartbeat || n.registered_at || "";
      if (!last) return false;
      return now - new Date(last).getTime() < 600_000; // 10 min
    });
    console.log(`  Nodes:       ${nodes.length} registered (${alive.length} live)`);
    for (const n of nodes) {
      const last = n.last_seen_at || n.last_heartbeat || n.registered_at || "";
      const ago = last ? Math.round((now - new Date(last).getTime()) / 60000) : 9999;
      const icon = ago < 10 ? "\x1b[32m●\x1b[0m" : ago < 60 ? "\x1b[33m●\x1b[0m" : "\x1b[31m○\x1b[0m";
      const agoStr = ago < 60 ? `${ago}m` : `${Math.round(ago / 60)}h`;
      console.log(`    ${icon} ${(n.hostname || n.node_id || "?").slice(0, 20).padEnd(22)} ${(n.os_type || "?").padEnd(8)} ${agoStr} ago`);
    }
  }

  // Pipeline
  console.log();
  console.log("\x1b[1m  PIPELINE\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Pending:     ${pending.length}`);
  console.log(`  Running:     ${running.length}`);

  if (running.length > 0) {
    for (const t of running.slice(0, 3)) {
      const name = _taskName(t);
      const age = t.created_at ? Math.round((Date.now() - new Date(t.created_at).getTime()) / 60000) : 0;
      const ageColor = age > 15 ? "\x1b[31m" : age > 5 ? "\x1b[33m" : "\x1b[32m";
      console.log(`    \x1b[33m▸\x1b[0m ${(t.task_type || "?").padEnd(6)} ${ageColor}${age}m\x1b[0m  ${name}`);
    }
    if (running.length > 3) console.log(`    ... and ${running.length - 3} more`);
  }

  // Recent completions
  if (completed.length > 0) {
    console.log(`  Recent:      last ${completed.length} completed`);
    for (const t of completed.slice(0, 3)) {
      const name = _taskName(t);
      console.log(`    \x1b[32m✓\x1b[0m ${t.task_type || "?"}  ${name}`);
    }
  }

  // My ledger
  if (ledger && ledger.balance) {
    console.log();
    console.log("\x1b[1m  MY LEDGER\x1b[0m");
    console.log(`  ${"─".repeat(50)}`);
    console.log(`  Total:       ${ledger.balance.grand_total || 0} CC`);
    const types = ledger.balance.totals_by_type || {};
    const sorted = Object.entries(types).sort((a, b) => b[1] - a[1]);
    for (const [type, amount] of sorted) {
      console.log(`    ${type.padEnd(14)} ${amount} CC`);
    }
  }

  // Messages
  if (messages && messages.count > 0) {
    console.log();
    console.log(`\x1b[33m  📬 ${messages.count} unread message(s)\x1b[0m`);
    for (const m of (messages.messages || []).slice(0, 3)) {
      console.log(`    from ${(m.from_node || "?").slice(0, 12)}: ${(m.text || "").slice(0, 60)}`);
    }
  }

  console.log();
}

export async function showResonance() {
  const data = await get("/api/ideas/resonance");
  if (!data) {
    console.log("Could not fetch resonance.");
    return;
  }
  console.log();
  console.log("\x1b[1m  RESONANCE\x1b[0m — what's alive right now");
  console.log(`  ${"─".repeat(40)}`);
  if (Array.isArray(data)) {
    for (const item of data.slice(0, 10)) {
      const name = item.name || item.idea_id || item.id || "?";
      console.log(`  \x1b[33m~\x1b[0m ${name}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}
