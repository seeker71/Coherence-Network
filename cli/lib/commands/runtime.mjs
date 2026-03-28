/**
 * Runtime commands
 *
 *   cc runtime                      — show change token + events summary
 *   cc runtime events               — list recent runtime events
 *   cc runtime event <type> <data>  — post a runtime event
 *   cc runtime ideas                — runtime ideas summary
 *   cc runtime endpoints            — endpoints summary
 *   cc runtime web                  — web views performance
 *   cc runtime attention            — endpoints needing attention
 *   cc runtime exerciser            — run exerciser
 *   cc runtime usage                — verification usage
 *   cc runtime mvp                  — MVP acceptance summary
 *   cc runtime mvp judge            — MVP acceptance judge result
 *   cc runtime mvp baselines        — local baselines
 */

import { get, post } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  return str.slice(0, len - 3) + "...";
}

export async function showRuntimeToken() {
  const data = await get("/api/runtime/change-token");
  if (!data) { console.log("Could not fetch change token."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  RUNTIME${R}`);
  console.log(`  ${"─".repeat(50)}`);
  const token = data.token || data.change_token || data;
  if (typeof token === "string" || typeof token === "number") {
    console.log(`  Change token: ${token}`);
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) console.log(`  ${k.padEnd(20)} ${v}`);
    }
  }
  console.log();
}

export async function listRuntimeEvents(args) {
  const limit = parseInt(args[0]) || 20;
  const data = await get("/api/runtime/events", { limit });
  const events = Array.isArray(data) ? data : data?.events || [];

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", C = "\x1b[36m";

  console.log();
  console.log(`${B}  RUNTIME EVENTS${R} (${events.length})`);
  console.log(`  ${"─".repeat(74)}`);

  if (!events.length) {
    console.log(`  ${D}No runtime events.${R}`);
    console.log();
    return;
  }

  for (const ev of events) {
    const ts = (ev.timestamp || ev.created_at || "").slice(0, 16);
    const type = (ev.event_type || ev.type || "?").padEnd(20);
    const source = ev.source || ev.node_id || "";
    const detail = truncate(ev.data ? JSON.stringify(ev.data) : (ev.description || ""), 40);
    console.log(`  ${D}${ts}${R}  ${C}${type}${R}  ${D}${source}${R} ${detail}`);
  }
  console.log();
}

export async function postRuntimeEvent(args) {
  const eventType = args[0];
  const rest = args.slice(1).join(" ");
  if (!eventType) {
    console.log("Usage: cc runtime event <type> [data...]");
    return;
  }
  let data = {};
  try { data = rest ? JSON.parse(rest) : {}; } catch { data = { description: rest }; }

  const result = await post("/api/runtime/events", { event_type: eventType, data });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Runtime event posted: ${eventType}`);
    if (result.id) console.log(`  ID: ${result.id}`);
  } else {
    console.log("Failed to post runtime event.");
  }
}

export async function showRuntimeIdeas() {
  const data = await get("/api/runtime/ideas/summary");
  if (!data) { console.log("Could not fetch runtime ideas summary."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  RUNTIME IDEAS SUMMARY${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.total != null) console.log(`  Total ideas:      ${data.total}`);
  if (data.validated != null) console.log(`  Validated:        ${G}${data.validated}${R}`);
  if (data.in_progress != null) console.log(`  In progress:      ${Y}${data.in_progress}${R}`);
  if (data.pending != null) console.log(`  Pending:          ${data.pending}`);
  if (data.avg_coherence != null) console.log(`  Avg coherence:    ${data.avg_coherence.toFixed(3)}`);

  if (Array.isArray(data.top_ideas)) {
    console.log();
    console.log(`  ${D}TOP IDEAS${R}`);
    for (const idea of data.top_ideas.slice(0, 5)) {
      const name = truncate(idea.name || idea.id || "", 50).padEnd(52);
      const score = idea.coherence_score != null ? idea.coherence_score.toFixed(2) : "";
      console.log(`  ${name} ${D}${score}${R}`);
    }
  }
  console.log();
}

export async function showRuntimeEndpoints() {
  const data = await get("/api/runtime/endpoints/summary");
  if (!data) { console.log("Could not fetch endpoints summary."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  RUNTIME ENDPOINTS SUMMARY${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.total != null) console.log(`  Total endpoints:  ${data.total}`);
  if (data.covered != null) {
    const pct = data.total ? (data.covered / data.total * 100).toFixed(1) : "?";
    const color = parseFloat(pct) >= 80 ? G : parseFloat(pct) >= 50 ? Y : RED;
    console.log(`  Covered:          ${color}${data.covered} (${pct}%)${R}`);
  }
  if (data.missing != null) console.log(`  Missing:          ${RED}${data.missing}${R}`);

  if (Array.isArray(data.by_module)) {
    console.log();
    console.log(`  ${D}BY MODULE${R}`);
    for (const mod of data.by_module.slice(0, 15)) {
      const name = truncate(mod.module || mod.name || "", 20).padEnd(22);
      const cov = mod.covered ?? mod.count ?? "?";
      const tot = mod.total ?? "";
      const pct = mod.total ? `${(mod.covered / mod.total * 100).toFixed(0)}%`.padStart(4) : "";
      console.log(`  ${name} ${cov}${tot ? `/${tot}` : ""}  ${D}${pct}${R}`);
    }
  }
  console.log();
}

export async function showWebViewsPerformance() {
  const data = await get("/api/runtime/web/views/summary");
  if (!data) { console.log("Could not fetch web views performance."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  WEB VIEWS PERFORMANCE${R}`);
  console.log(`  ${"─".repeat(74)}`);

  const views = Array.isArray(data) ? data : data?.views || [];
  for (const v of views) {
    const route = truncate(v.route || v.path || v.view || "", 35).padEnd(37);
    const p95 = v.p95_ms != null ? `${v.p95_ms}ms`.padStart(8) : "       —";
    const p50 = v.p50_ms != null ? `${v.p50_ms}ms`.padStart(8) : "";
    const requests = v.request_count != null ? `${v.request_count} req` : "";
    const color = (v.p95_ms || 9999) < 500 ? G : (v.p95_ms || 9999) < 2000 ? Y : RED;
    console.log(`  ${route} ${color}p95:${p95}${R}  ${D}p50:${p50}  ${requests}${R}`);
  }

  if (data.overall) {
    console.log();
    const o = data.overall;
    if (o.avg_p95_ms) console.log(`  Overall p95: ${o.avg_p95_ms}ms`);
    if (o.total_requests) console.log(`  Total requests: ${o.total_requests}`);
  }
  console.log();
}

export async function showEndpointAttention() {
  const data = await get("/api/runtime/endpoints/attention");
  if (!data) { console.log("Could not fetch endpoint attention report."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  ENDPOINTS NEEDING ATTENTION${R}`);
  console.log(`  ${"─".repeat(74)}`);

  const endpoints = data.endpoints || data.items || (Array.isArray(data) ? data : []);
  if (!endpoints.length) {
    console.log(`  ${D}No endpoints flagged.${R}`);
    console.log();
    return;
  }

  for (const ep of endpoints) {
    const path = truncate(ep.path || ep.route || "", 40).padEnd(42);
    const reason = truncate(ep.reason || ep.issue || "", 30);
    const severity = (ep.severity || "low").toLowerCase();
    const color = severity === "high" || severity === "critical" ? RED : Y;
    console.log(`  ${color}▲${R} ${path} ${D}${reason}${R}`);
  }
  console.log();
}

export async function runRuntimeExerciser() {
  const result = await post("/api/runtime/exerciser/run", {});
  if (!result) { console.log("Exerciser failed."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  RUNTIME EXERCISER${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (result.total != null) console.log(`  Total endpoints: ${result.total}`);
  if (result.passed != null) console.log(`  Passed:          ${G}${result.passed}${R}`);
  if (result.failed != null) console.log(`  Failed:          ${RED}${result.failed}${R}`);
  if (result.skipped != null) console.log(`  Skipped:         ${D}${result.skipped}${R}`);

  const failures = Array.isArray(result.failures) ? result.failures : [];
  if (failures.length) {
    console.log();
    console.log(`  ${RED}FAILURES${R}`);
    for (const f of failures.slice(0, 10)) {
      const path = truncate(f.path || f.endpoint || "", 40).padEnd(42);
      const err = truncate(f.error || f.message || "", 30);
      console.log(`  ${RED}✗${R} ${path} ${D}${err}${R}`);
    }
  }
  console.log();
}

export async function showUsageVerification() {
  const data = await get("/api/runtime/usage/verification");
  if (!data) { console.log("Could not fetch usage verification."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  USAGE VERIFICATION${R}`);
  console.log(`  ${"─".repeat(60)}`);

  for (const [k, v] of Object.entries(data)) {
    if (v != null && typeof v !== "object") {
      console.log(`  ${k.padEnd(25)} ${v}`);
    }
  }
  if (data.endpoints) {
    const eps = Array.isArray(data.endpoints) ? data.endpoints : Object.entries(data.endpoints);
    console.log();
    for (const ep of eps.slice(0, 15)) {
      const path = Array.isArray(ep) ? ep[0] : ep.path || ep.route || "";
      const count = Array.isArray(ep) ? ep[1] : ep.count || ep.calls || "?";
      console.log(`  ${truncate(path, 50).padEnd(52)} ${D}${count} calls${R}`);
    }
  }
  console.log();
}

export async function showMvpSummary() {
  const data = await get("/api/runtime/mvp/acceptance-summary");
  if (!data) { console.log("Could not fetch MVP acceptance summary."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  MVP ACCEPTANCE SUMMARY${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const overall = data.overall_status || data.status || "?";
  const color = overall === "passing" || overall === "green" ? G
    : overall === "warning" || overall === "yellow" ? Y : RED;

  console.log(`  Overall: ${color}${overall}${R}`);
  if (data.score != null) console.log(`  Score:   ${data.score}`);
  if (data.criteria_met != null && data.total_criteria != null) {
    console.log(`  Criteria: ${data.criteria_met}/${data.total_criteria}`);
  }

  const criteria = Array.isArray(data.criteria) ? data.criteria : [];
  if (criteria.length) {
    console.log();
    for (const c of criteria) {
      const pass = c.passing || c.met || c.status === "passing";
      const icon = pass ? `${G}✓${R}` : `${RED}✗${R}`;
      const name = truncate(c.name || c.criterion || "", 50);
      console.log(`  ${icon} ${name}`);
    }
  }
  console.log();
}

export async function showMvpJudge() {
  const data = await get("/api/runtime/mvp/acceptance-judge");
  if (!data) { console.log("Could not fetch MVP judge result."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  MVP ACCEPTANCE JUDGE${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const verdict = data.verdict || data.judgment || data.result || "?";
  const color = verdict === "pass" || verdict === "accepted" ? G : RED;
  console.log(`  Verdict:   ${color}${verdict}${R}`);
  if (data.reasoning) console.log(`  Reasoning: ${truncate(data.reasoning, 70)}`);
  if (data.confidence != null) console.log(`  Confidence: ${data.confidence}`);
  console.log();
}

export async function showMvpBaselines() {
  const data = await get("/api/runtime/mvp/local-baselines");
  if (!data) { console.log("Could not fetch MVP baselines."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  MVP LOCAL BASELINES${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const baselines = Array.isArray(data) ? data : data?.baselines || [];
  if (baselines.length) {
    for (const b of baselines) {
      const name = truncate(b.name || b.metric || "", 30).padEnd(32);
      const val = b.value != null ? String(b.value).padStart(10) : "         —";
      const baseline = b.baseline != null ? ` (baseline: ${b.baseline})` : "";
      console.log(`  ${name} ${val}${D}${baseline}${R}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (v != null) console.log(`  ${k.padEnd(30)} ${v}`);
    }
  }
  console.log();
}

export function handleRuntime(args) {
  const sub = args[0];
  const rest = args.slice(1);

  switch (sub) {
    case "events":        return listRuntimeEvents(rest);
    case "event":         return postRuntimeEvent(rest);
    case "ideas":         return showRuntimeIdeas();
    case "endpoints":     return showRuntimeEndpoints();
    case "web":           return showWebViewsPerformance();
    case "attention":     return showEndpointAttention();
    case "exerciser":     return runRuntimeExerciser();
    case "usage":         return showUsageVerification();
    case "mvp": {
      const msub = rest[0];
      if (msub === "judge")     return showMvpJudge();
      if (msub === "baselines") return showMvpBaselines();
      return showMvpSummary();
    }
    case "token":
    default:
      return showRuntimeToken();
  }
}
