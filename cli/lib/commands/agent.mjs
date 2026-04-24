/**
 * Agent pipeline commands
 *
 *   coh agent                          — show pipeline status
 *   coh agent status                   — full status report
 *   coh agent pipeline                 — pipeline-status
 *   coh agent runners                  — list runners
 *   coh agent lifecycle                — lifecycle summary
 *   coh agent usage                    — agent usage stats
 *   coh agent visibility               — agent visibility
 *   coh agent guidance                 — orchestration guidance
 *   coh agent integration              — integration report
 *   coh agent issues                   — fatal and monitor issues
 *   coh agent metrics                  — task metrics
 *   coh agent effectiveness            — agent effectiveness report
 *   coh agent health                   — collective health
 *   coh agent diagnostics              — diagnostics completeness
 *   coh agent reap-history             — reap history
 *   coh agent attention                — tasks needing attention
 *   coh agent run-state <task_id>      — run state for a task
 *   coh agent execute <task_id>        — execute a task (agent use)
 */

import { get, post, patch, request } from "../api.mjs";
import { getExecuteToken } from "../config.mjs";
import { truncate } from "../ui/ansi.mjs";


function timeSince(isoStr) {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export async function showAgentStatusReport() {
  const data = await get("/api/agent/status-report");
  if (!data) { console.log("Could not fetch agent status report."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  AGENT STATUS REPORT${R}`);
  console.log(`  ${"─".repeat(74)}`);

  if (data.overall_health) {
    const h = data.overall_health.toLowerCase();
    const color = h === "healthy" ? G : h === "degraded" ? Y : RED;
    console.log(`  Health:     ${color}${data.overall_health}${R}`);
  }

  if (data.running_count != null) console.log(`  Running:    ${Y}${data.running_count}${R}`);
  if (data.pending_count != null) console.log(`  Pending:    ${data.pending_count}`);
  if (data.failed_count != null)  console.log(`  Failed:     ${RED}${data.failed_count}${R}`);

  const issues = Array.isArray(data.issues) ? data.issues : [];
  if (issues.length) {
    console.log();
    console.log(`  ${RED}ISSUES (${issues.length})${R}`);
    for (const issue of issues.slice(0, 5)) {
      console.log(`  ${RED}!${R} ${truncate(issue.message || issue.description || issue, 70)}`);
    }
  }

  const runners = Array.isArray(data.runners) ? data.runners : [];
  if (runners.length) {
    console.log();
    console.log(`  ${D}RUNNERS${R}`);
    for (const r of runners) {
      const name = truncate(r.name || r.runner_id || r.id || "", 25).padEnd(27);
      const status = (r.status || r.state || "?").toLowerCase();
      const color = status === "active" || status === "running" ? G : RED;
      console.log(`  ${name} ${color}${status}${R}`);
    }
  }
  console.log();
}

export async function showPipelineStatus() {
  const data = await get("/api/agent/pipeline-status");
  if (!data) { console.log("Could not fetch pipeline status."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  PIPELINE STATUS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const status = (data.status || data.health || "?").toLowerCase();
  const color = status === "healthy" || status === "running" ? G
    : status === "degraded" || status === "warning" ? Y : RED;
  console.log(`  Status:  ${color}${status}${R}`);

  if (data.tasks_running != null) console.log(`  Running: ${Y}${data.tasks_running}${R}`);
  if (data.tasks_queued != null)  console.log(`  Queued:  ${data.tasks_queued}`);
  if (data.throughput != null)    console.log(`  Throughput: ${data.throughput}/min`);

  const stages = data.stages || {};
  if (Object.keys(stages).length) {
    console.log();
    console.log(`  ${D}STAGES${R}`);
    for (const [stage, val] of Object.entries(stages)) {
      const count = typeof val === "object" ? (val.count ?? JSON.stringify(val)) : val;
      console.log(`  ${stage.padEnd(25)} ${count}`);
    }
  }
  console.log();
}

export async function listRunners() {
  const data = await get("/api/agent/runners");
  if (!data) { console.log("Could not fetch runners."); return; }

  const runners = Array.isArray(data) ? data : data?.runners || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  RUNNERS${R} (${runners.length})`);
  console.log(`  ${"─".repeat(74)}`);

  if (!runners.length) {
    console.log(`  ${D}No runners registered.${R}`);
    console.log();
    return;
  }

  for (const r of runners) {
    const id = truncate(r.runner_id || r.node_id || r.id || "?", 20).padEnd(22);
    const provider = (r.provider || r.executor || "").padEnd(10);
    const model = truncate(r.model || "", 20).padEnd(22);
    const status = (r.status || r.state || "?").toLowerCase();
    const color = status === "active" || status === "running" ? G
      : status === "idle" ? D : RED;
    const last = r.last_heartbeat ? timeSince(r.last_heartbeat) : "";
    console.log(`  ${id} ${provider} ${model} ${color}${status}${R}  ${D}${last}${R}`);
  }
  console.log();
}

export async function showLifecycleSummary() {
  const data = await get("/api/agent/lifecycle/summary");
  if (!data) { console.log("Could not fetch lifecycle summary."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  AGENT LIFECYCLE SUMMARY${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.total_tasks != null) console.log(`  Total tasks:    ${data.total_tasks}`);
  if (data.completed != null)   console.log(`  Completed:      ${G}${data.completed}${R}`);
  if (data.failed != null)      console.log(`  Failed:         ${RED}${data.failed}${R}`);
  if (data.running != null)     console.log(`  Running:        ${Y}${data.running}${R}`);
  if (data.avg_duration_s != null) console.log(`  Avg duration:   ${data.avg_duration_s.toFixed(1)}s`);

  const byType = data.by_type || data.by_task_type || {};
  if (Object.keys(byType).length) {
    console.log();
    console.log(`  ${D}BY TYPE${R}`);
    for (const [type, stats] of Object.entries(byType)) {
      const count = typeof stats === "object" ? (stats.count ?? JSON.stringify(stats)) : stats;
      console.log(`  ${type.padEnd(20)} ${count}`);
    }
  }
  console.log();
}

export async function showAgentUsage() {
  const data = await get("/api/agent/usage");
  if (!data) { console.log("Could not fetch agent usage."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  AGENT USAGE${R}`);
  console.log(`  ${"─".repeat(60)}`);

  for (const [k, v] of Object.entries(data)) {
    if (v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }

  const byModel = data.by_model || data.model_usage;
  if (byModel && typeof byModel === "object") {
    console.log();
    console.log(`  ${D}BY MODEL${R}`);
    for (const [model, stats] of Object.entries(byModel)) {
      const count = typeof stats === "object" ? (stats.calls ?? stats.count ?? JSON.stringify(stats)) : stats;
      console.log(`  ${truncate(model, 30).padEnd(32)} ${count}`);
    }
  }
  console.log();
}

export async function showAgentVisibility() {
  const data = await get("/api/agent/visibility");
  if (!data) { console.log("Could not fetch agent visibility."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  AGENT VISIBILITY${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const overall = data.visibility_score ?? data.overall_score ?? data.score;
  if (overall != null) {
    const pct = typeof overall === "number" && overall <= 1 ? (overall * 100).toFixed(1) + "%" : overall;
    const numPct = parseFloat(String(pct));
    const color = numPct >= 70 ? G : RED;
    console.log(`  Score: ${color}${pct}${R}`);
  }

  for (const [k, v] of Object.entries(data)) {
    if (!["visibility_score", "overall_score", "score"].includes(k) && v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }
  console.log();
}

export async function showOrchestrationGuidance() {
  const data = await get("/api/agent/orchestration/guidance");
  if (!data) { console.log("Could not fetch orchestration guidance."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", Y = "\x1b[33m";
  console.log();
  console.log(`${B}  ORCHESTRATION GUIDANCE${R}`);
  console.log(`  ${"─".repeat(70)}`);

  const items = Array.isArray(data) ? data : data?.guidance || data?.recommendations || [];
  if (items.length) {
    for (const item of items) {
      const priority = (item.priority || "").toLowerCase();
      const icon = priority === "high" ? `\x1b[31m▲${R}` : priority === "medium" ? `${Y}▲${R}` : `${D}○${R}`;
      const text = truncate(item.message || item.recommendation || item.text || String(item), 70);
      console.log(`  ${icon} ${text}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) console.log(`  ${k.padEnd(25)} ${typeof v === "object" ? JSON.stringify(v) : v}`);
    }
  }
  console.log();
}

export async function showAgentIntegration() {
  const data = await get("/api/agent/integration");
  if (!data) { console.log("Could not fetch integration report."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  AGENT INTEGRATION${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const integrations = Array.isArray(data) ? data : data?.integrations || [];
  if (integrations.length) {
    for (const intg of integrations) {
      const name = truncate(intg.name || intg.integration || "", 25).padEnd(27);
      const status = (intg.status || "?").toLowerCase();
      const color = status === "connected" || status === "active" ? G : RED;
      console.log(`  ${name} ${color}${status}${R}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null && typeof v !== "object") {
        console.log(`  ${k.padEnd(25)} ${v}`);
      }
    }
  }
  console.log();
}

export async function showFatalIssues() {
  const data = await get("/api/agent/fatal-issues");
  if (!data) { console.log("Could not fetch fatal issues."); return; }

  const issues = Array.isArray(data) ? data : data?.issues || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  FATAL ISSUES${R} (${issues.length})`);
  console.log(`  ${"─".repeat(70)}`);

  if (!issues.length) {
    console.log(`  \x1b[32m✓\x1b[0m No fatal issues.`);
    console.log();
    return;
  }

  for (const issue of issues) {
    const ts = (issue.timestamp || issue.created_at || "").slice(0, 16);
    const msg = truncate(issue.message || issue.description || issue.error || String(issue), 65);
    console.log(`  ${RED}✗${R} ${msg}`);
    if (ts) console.log(`    ${D}${ts}${R}`);
  }
  console.log();
}

export async function showMonitorIssues() {
  const data = await get("/api/agent/monitor-issues");
  if (!data) { console.log("Could not fetch monitor issues."); return; }

  const issues = Array.isArray(data) ? data : data?.issues || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  MONITOR ISSUES${R} (${issues.length})`);
  console.log(`  ${"─".repeat(70)}`);

  if (!issues.length) {
    console.log(`  \x1b[32m✓\x1b[0m No monitor issues.`);
    console.log();
    return;
  }

  for (const issue of issues) {
    const severity = (issue.severity || "low").toLowerCase();
    const icon = severity === "high" || severity === "critical" ? "\x1b[31m▲\x1b[0m"
      : severity === "medium" ? `${Y}▲\x1b[0m` : `${D}○\x1b[0m`;
    const msg = truncate(issue.message || issue.description || String(issue), 65);
    console.log(`  ${icon} ${msg}`);
  }
  console.log();
}

export async function showAgentMetrics() {
  const data = await get("/api/agent/metrics");
  if (!data) { console.log("Could not fetch agent metrics."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  AGENT METRICS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.success_rate != null) {
    const pct = (data.success_rate * 100).toFixed(1);
    const color = data.success_rate >= 0.8 ? G : data.success_rate >= 0.5 ? Y : RED;
    console.log(`  Success rate:   ${color}${pct}%${R}`);
  }
  if (data.total_tasks != null)    console.log(`  Total tasks:    ${data.total_tasks}`);
  if (data.avg_duration_s != null) console.log(`  Avg duration:   ${data.avg_duration_s.toFixed(1)}s`);
  if (data.p95_duration_s != null) console.log(`  P95 duration:   ${data.p95_duration_s.toFixed(1)}s`);

  const byType = data.by_task_type || data.by_type;
  if (byType && typeof byType === "object") {
    console.log();
    console.log(`  ${D}BY TASK TYPE${R}`);
    for (const [type, stats] of Object.entries(byType)) {
      const s = typeof stats === "object" ? stats : {};
      const sr = s.success_rate != null ? `${(s.success_rate * 100).toFixed(0)}%`.padStart(5) : "    —";
      const count = s.count != null ? `${s.count}`.padStart(4) : "   —";
      console.log(`  ${type.padEnd(20)} ${count} tasks  ${sr} success`);
    }
  }

  const byModel = data.by_model;
  if (byModel && typeof byModel === "object") {
    console.log();
    console.log(`  ${D}BY MODEL${R}`);
    for (const [model, stats] of Object.entries(byModel)) {
      const s = typeof stats === "object" ? stats : {};
      const sr = s.success_rate != null ? `${(s.success_rate * 100).toFixed(0)}%`.padStart(5) : "    —";
      console.log(`  ${truncate(model, 30).padEnd(32)} ${sr} success`);
    }
  }
  console.log();
}

export async function showAgentEffectiveness() {
  const data = await get("/api/agent/effectiveness");
  if (!data) { console.log("Could not fetch effectiveness data."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  AGENT EFFECTIVENESS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const score = data.effectiveness_score ?? data.score ?? data.overall;
  if (score != null) {
    const pct = (score * 100).toFixed(1);
    const color = score >= 0.7 ? G : score >= 0.4 ? Y : RED;
    console.log(`  Score: ${color}${pct}%${R}`);
  }

  const dims = data.dimensions || data.breakdown;
  if (dims && typeof dims === "object") {
    console.log();
    for (const [dim, val] of Object.entries(dims)) {
      const numVal = typeof val === "object" ? (val.score ?? val.value ?? "?") : val;
      const pct = typeof numVal === "number" && numVal <= 1
        ? `${(numVal * 100).toFixed(0)}%` : numVal;
      console.log(`  ${dim.padEnd(25)} ${pct}`);
    }
  }
  console.log();
}

export async function showCollectiveHealth() {
  const data = await get("/api/agent/collective-health");
  if (!data) { console.log("Could not fetch collective health."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  COLLECTIVE HEALTH${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const status = (data.status || data.health || "?").toLowerCase();
  const color = status === "healthy" ? G : status === "degraded" ? Y : RED;
  console.log(`  Health: ${color}${status}${R}`);

  if (data.active_agents != null)  console.log(`  Active agents:  ${data.active_agents}`);
  if (data.tasks_running != null)  console.log(`  Tasks running:  ${Y}${data.tasks_running}${R}`);
  if (data.success_rate != null)   console.log(`  Success rate:   ${(data.success_rate * 100).toFixed(1)}%`);

  const agents = Array.isArray(data.agents) ? data.agents : [];
  if (agents.length) {
    console.log();
    console.log(`  ${D}AGENTS${R}`);
    for (const a of agents.slice(0, 10)) {
      const name = truncate(a.name || a.node_id || a.id || "", 25).padEnd(27);
      const aStatus = (a.status || "?").toLowerCase();
      const aColor = aStatus === "active" ? G : RED;
      console.log(`  ${name} ${aColor}${aStatus}${R}`);
    }
  }
  console.log();
}

export async function showDiagnosticsCompleteness() {
  const data = await get("/api/agent/diagnostics-completeness");
  if (!data) { console.log("Could not fetch diagnostics completeness."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  DIAGNOSTICS COMPLETENESS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const score = data.completeness_score ?? data.score;
  if (score != null) {
    const pct = (score * 100).toFixed(1);
    const color = score >= 0.8 ? G : Y;
    console.log(`  Completeness: ${color}${pct}%${R}`);
  }

  const items = Array.isArray(data.items) ? data.items : [];
  for (const item of items.slice(0, 20)) {
    const present = item.present || item.complete || item.has_data;
    const icon = present ? `${G}✓${R}` : `\x1b[31m✗${R}`;
    const name = truncate(item.name || item.check || "", 50);
    console.log(`  ${icon} ${name}`);
  }
  console.log();
}

export async function showReapHistory(args) {
  const limit = parseInt(args[0]) || 20;
  const data = await get("/api/agent/reap-history", { limit });
  if (!data) { console.log("Could not fetch reap history."); return; }

  const entries = Array.isArray(data) ? data : data?.history || data?.entries || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  REAP HISTORY${R} (${entries.length})`);
  console.log(`  ${"─".repeat(74)}`);

  for (const entry of entries.slice(0, 20)) {
    const ts = (entry.reaped_at || entry.timestamp || entry.created_at || "").slice(0, 16);
    const taskId = truncate(entry.task_id || entry.id || "", 20).padEnd(22);
    const reason = truncate(entry.reason || entry.cause || "", 35).padEnd(37);
    const status = (entry.final_status || entry.status || "?").toLowerCase();
    const color = status === "done" ? G : RED;
    console.log(`  ${D}${ts}${R}  ${taskId} ${color}${status}${R}  ${D}${reason}${R}`);
  }
  console.log();
}

export async function showAttentionTasks() {
  const data = await get("/api/agent/tasks/attention");
  if (!data) { console.log("Could not fetch attention tasks."); return; }

  const tasks = Array.isArray(data) ? data : data?.tasks || data?.attention || [];
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  TASKS NEEDING ATTENTION${R} (${tasks.length})`);
  console.log(`  ${"─".repeat(74)}`);

  if (!tasks.length) {
    console.log(`  ${D}No tasks need attention.${R}`);
    console.log();
    return;
  }

  for (const t of tasks) {
    const type = (t.task_type || t.type || "?").padEnd(10);
    const issue = truncate(t.issue || t.reason || t.direction || "", 45);
    const age = t.created_at ? timeSince(t.created_at) : "";
    console.log(`  ${Y}▲${R} ${type} ${issue}  ${D}${age}${R}`);
    if (t.task_id || t.id) console.log(`    ${D}${t.task_id || t.id}${R}`);
  }
  console.log();
}

export async function showRunState(args) {
  const taskId = args[0];
  if (!taskId) { console.log("Usage: coh agent run-state <task_id>"); return; }

  const data = await get(`/api/agent/run-state/${encodeURIComponent(taskId)}`);
  if (!data) { console.log(`No run state for task '${taskId}'.`); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  RUN STATE: ${taskId}${R}`);
  console.log(`  ${"─".repeat(50)}`);

  const status = (data.status || data.state || "?").toLowerCase();
  const color = status === "running" ? Y : status === "done" || status === "completed" ? G : "\x1b[31m";
  console.log(`  Status:   ${color}${status}${R}`);

  if (data.claimed_by) console.log(`  Claimed:  ${data.claimed_by}`);
  if (data.claimed_at) console.log(`  At:       ${data.claimed_at}`);
  if (data.model) console.log(`  Model:    ${data.model}`);

  const checkpoints = Array.isArray(data.checkpoints) ? data.checkpoints : [];
  if (checkpoints.length) {
    console.log();
    console.log(`  ${D}CHECKPOINTS${R}`);
    for (const cp of checkpoints.slice(-5)) {
      const ts = (cp.timestamp || "").slice(0, 16);
      const msg = truncate(cp.message || cp.step || "", 55);
      console.log(`  ${D}${ts}${R} ${msg}`);
    }
  }
  console.log();
}

export async function showAgentRoute(args) {
  const taskType = args[0] || "impl";
  const data = await get("/api/agent/route", { task_type: taskType });
  if (!data) {
    console.log("Could not fetch /api/agent/route (check task_type and API availability).");
    return;
  }
  console.log(JSON.stringify(data, null, 2));
}

export async function executeAgentTask(args) {
  const taskId = args[0];
  if (!taskId) {
    console.log("Usage: coh agent execute <task_id>");
    console.log("  Requires agent_executor.execute_token in ~/.coherence-network/config.json for server-side execute.");
    return;
  }
  const token = String(getExecuteToken() || "").trim();
  const headers = {};
  if (token) headers["X-Agent-Execute-Token"] = token;
  const res = await request("POST", `/api/agent/tasks/${encodeURIComponent(taskId)}/execute`, {
    headers,
    body: {},
  });
  if (res.json != null) console.log(JSON.stringify(res.json, null, 2));
  else console.log(res.text || "");
  if (!res.ok) process.exitCode = 1;
}

export async function pickupExecute(args) {
  const token = String(getExecuteToken() || "").trim();
  const headers = {};
  if (token) headers["X-Agent-Execute-Token"] = token;
  const q = {};
  if (args[0] && args[0].startsWith("task_")) q.task_id = args[0];
  const res = await request("POST", "/api/agent/tasks/pickup-and-execute", {
    headers,
    body: {},
    params: Object.keys(q).length ? q : undefined,
  });
  if (res.json != null) console.log(JSON.stringify(res.json, null, 2));
  else console.log(res.text || "");
  if (!res.ok) process.exitCode = 1;
}

export async function smartReapAgent(args) {
  const sub = args[0] || "preview";
  if (sub === "run") {
    const res = await request("POST", "/api/agent/smart-reap/run", { body: {} });
    if (res.json != null) console.log(JSON.stringify(res.json, null, 2));
    else console.log(res.text || "");
    if (!res.ok) process.exitCode = 1;
    return;
  }
  const data = await get("/api/agent/smart-reap/preview");
  if (!data) {
    console.log("Could not fetch smart-reap preview.");
    return;
  }
  console.log(JSON.stringify(data, null, 2));
}

export function handleAgent(args) {
  const sub = args[0];
  const rest = args.slice(1);

  switch (sub) {
    case "status":        return showAgentStatusReport();
    case "pipeline":      return showPipelineStatus();
    case "runners":       return listRunners();
    case "lifecycle":     return showLifecycleSummary();
    case "usage":         return showAgentUsage();
    case "visibility":    return showAgentVisibility();
    case "guidance":      return showOrchestrationGuidance();
    case "integration":   return showAgentIntegration();
    case "issues":        return showFatalIssues().then(() => showMonitorIssues());
    case "fatal":         return showFatalIssues();
    case "monitor":       return showMonitorIssues();
    case "metrics":       return showAgentMetrics();
    case "effectiveness": return showAgentEffectiveness();
    case "health":        return showCollectiveHealth();
    case "diagnostics":   return showDiagnosticsCompleteness();
    case "reap-history":  return showReapHistory(rest);
    case "attention":     return showAttentionTasks();
    case "run-state":     return showRunState(rest);
    case "route":         return showAgentRoute(rest);
    case "execute":       return executeAgentTask(rest);
    case "pickup":        return pickupExecute(rest);
    case "smart-reap":    return smartReapAgent(rest);
    default:
      return showAgentStatusReport();
  }
}
