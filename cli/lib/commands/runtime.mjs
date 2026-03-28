/**
 * Runtime monitoring commands.
 *
 * Covers /api/runtime/* endpoints for observing live system behavior,
 * endpoint attention, web view performance, and MVP acceptance.
 *
 * Usage:
 *   cc runtime                      — runtime overview (events + attention)
 *   cc runtime events [limit]       — list runtime events
 *   cc runtime events post <type> <data>  — record a new runtime event
 *   cc runtime attention            — endpoints needing attention
 *   cc runtime ideas                — summary by idea
 *   cc runtime endpoints            — summary by endpoint
 *   cc runtime web                  — web view performance
 *   cc runtime mvp                  — MVP acceptance summary
 *   cc runtime mvp judge            — MVP acceptance judge
 *   cc runtime mvp baselines        — local baselines
 *   cc runtime usage                — usage verification report
 *   cc runtime exerciser            — run endpoint exerciser
 *   cc runtime token                — change token (cache busting)
 */

import { get, post } from "../api.mjs";

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

/** List runtime events */
export async function listRuntimeEvents(args) {
  const limitArg = args.find(a => /^\d+$/.test(a));
  const limit = parseInt(limitArg) || 20;
  const typeFilter = args.find(a => a.startsWith("--type="))?.split("=")[1] || "";

  const params = { limit };
  if (typeFilter) params.event_type = typeFilter;

  const data = await get("/api/runtime/events", params);
  if (!data) {
    console.log("Could not fetch runtime events.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", C = "\x1b[36m";

  const events = Array.isArray(data) ? data : data.events || data.items || [];

  console.log();
  console.log(`${B}  RUNTIME EVENTS${R} (${events.length})`);
  console.log(`  ${"─".repeat(70)}`);

  if (!events.length) {
    console.log(`  ${D}No runtime events.${R}`);
    console.log();
    return;
  }

  for (const ev of events) {
    const age = timeSince(ev.created_at || ev.timestamp);
    const type = (ev.event_type || ev.type || "?").padEnd(20);
    const source = (ev.source || ev.endpoint || "").slice(0, 25);
    const val = ev.value != null ? ` val=${ev.value}` : "";
    console.log(`  ${D}${age.padEnd(5)}${R} ${C}${type}${R} ${D}${source}${val}${R}`);
  }
  console.log();
}

/** Record a new runtime event */
export async function createRuntimeEvent(args) {
  // cc runtime events post <event_type> [source] [value]
  const [eventType, source, value] = args;
  if (!eventType) {
    console.log("Usage: cc runtime events post <event_type> [source] [value]");
    return;
  }
  const payload = { event_type: eventType };
  if (source) payload.source = source;
  if (value != null) payload.value = isNaN(value) ? value : parseFloat(value);

  const result = await post("/api/runtime/events", payload);
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Runtime event recorded: ${result.id || eventType}`);
  } else {
    console.log("\x1b[31m✗\x1b[0m Failed to record runtime event.");
  }
}

/** Show endpoint attention report */
export async function showEndpointAttention() {
  const data = await get("/api/runtime/endpoints/attention");
  if (!data) {
    console.log("Could not fetch endpoint attention report.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  ENDPOINT ATTENTION${R}`);
  console.log(`  ${"─".repeat(70)}`);

  const endpoints = data.endpoints || data.items || (Array.isArray(data) ? data : []);

  if (!endpoints.length) {
    console.log(`  ${D}All endpoints healthy.${R}`);
    console.log();
    return;
  }

  for (const ep of endpoints) {
    const path = (ep.path || ep.endpoint || "?").padEnd(45);
    const score = ep.attention_score ?? ep.score;
    const color = score != null ? (score > 0.7 ? RED : score > 0.4 ? Y : G) : D;
    const scoreStr = score != null ? `${color}${score.toFixed(2)}${R}` : D + "?" + R;
    const reason = (ep.reason || ep.issue || "").slice(0, 25);
    console.log(`  ${path} ${scoreStr} ${D}${reason}${R}`);
  }

  if (data.summary) {
    console.log();
    console.log(`  Summary: ${data.summary}`);
  }
  console.log();
}

/** Show runtime summary by idea */
export async function showRuntimeByIdea(args) {
  const limit = parseInt(args[0]) || 10;
  const data = await get("/api/runtime/ideas/summary", { limit });
  if (!data) {
    console.log("Could not fetch runtime summary by idea.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";

  const items = data.ideas || data.items || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  RUNTIME BY IDEA${R} (${items.length})`);
  console.log(`  ${"─".repeat(65)}`);

  for (const item of items) {
    const name = (item.idea_name || item.name || item.idea_id || "?").padEnd(40);
    const calls = item.call_count ?? item.requests ?? item.events ?? 0;
    const latency = item.avg_latency_ms != null ? `${item.avg_latency_ms.toFixed(0)}ms` : "";
    console.log(`  ${name} ${String(calls).padStart(5)} calls ${D}${latency}${R}`);
  }
  console.log();
}

/** Show runtime summary by endpoint */
export async function showRuntimeByEndpoint(args) {
  const limit = parseInt(args[0]) || 15;
  const data = await get("/api/runtime/endpoints/summary", { limit });
  if (!data) {
    console.log("Could not fetch runtime endpoint summary.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";

  const items = data.endpoints || data.items || (Array.isArray(data) ? data : []);
  console.log();
  console.log(`${B}  RUNTIME BY ENDPOINT${R} (${items.length})`);
  console.log(`  ${"─".repeat(70)}`);

  for (const ep of items) {
    const path = (ep.path || ep.endpoint || "?").padEnd(45);
    const calls = ep.call_count ?? ep.requests ?? 0;
    const latency = ep.avg_latency_ms != null ? `${ep.avg_latency_ms.toFixed(0)}ms` : "";
    const errors = ep.error_count > 0 ? ` \x1b[31m${ep.error_count} err\x1b[0m` : "";
    console.log(`  ${path} ${String(calls).padStart(5)} ${D}${latency}${errors}${R}`);
  }
  console.log();
}

/** Show web view performance */
export async function showWebViewPerformance() {
  const data = await get("/api/runtime/web/views/summary");
  if (!data) {
    console.log("Could not fetch web view performance.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  WEB VIEW PERFORMANCE${R}`);
  console.log(`  ${"─".repeat(65)}`);

  const views = data.views || data.pages || (Array.isArray(data) ? data : []);
  if (views.length) {
    for (const v of views) {
      const name = (v.view || v.page || v.path || "?").padEnd(35);
      const lcp = v.lcp_ms != null ? `LCP:${v.lcp_ms.toFixed(0)}ms` : "";
      const fcp = v.fcp_ms != null ? `FCP:${v.fcp_ms.toFixed(0)}ms` : "";
      const score = v.performance_score;
      const color = score != null ? (score >= 90 ? G : score >= 70 ? Y : RED) : D;
      const scoreStr = score != null ? `${color}${score}${R}` : "";
      console.log(`  ${name} ${scoreStr} ${D}${lcp} ${fcp}${R}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (typeof v !== "object") console.log(`  ${k.padEnd(30)} ${v}`);
    }
  }
  console.log();
}

/** Show MVP acceptance summary */
export async function showMvpSummary() {
  const data = await get("/api/runtime/mvp/acceptance-summary");
  if (!data) {
    console.log("Could not fetch MVP acceptance summary.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  MVP ACCEPTANCE SUMMARY${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const criteria = data.criteria || data.items || (Array.isArray(data) ? data : []);
  if (criteria.length) {
    for (const c of criteria) {
      const name = (c.criterion || c.name || c.id || "?").padEnd(35);
      const passed = c.passed ?? c.status === "passed";
      const icon = passed ? `${G}✓${R}` : `${RED}✗${R}`;
      const score = c.score != null ? ` ${D}${c.score.toFixed(2)}${R}` : "";
      console.log(`  ${icon} ${name}${score}`);
    }
  }

  if (data.overall_score != null) {
    const s = data.overall_score;
    const color = s >= 0.8 ? G : s >= 0.5 ? Y : RED;
    console.log();
    console.log(`  Overall: ${color}${(s * 100).toFixed(1)}%${R}`);
  }
  if (data.passed != null) {
    console.log(`  Passed:  ${data.passed}/${data.total || "?"}`);
  }
  console.log();
}

/** Show MVP acceptance judge */
export async function showMvpJudge() {
  const data = await get("/api/runtime/mvp/acceptance-judge");
  if (!data) {
    console.log("Could not fetch MVP judge.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  MVP ACCEPTANCE JUDGE${R}`);
  console.log(`  ${"─".repeat(60)}`);

  for (const [k, v] of Object.entries(data)) {
    if (v != null) {
      const display = typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
      console.log(`  ${k.padEnd(25)} ${display}`);
    }
  }
  console.log();
}

/** Show local baselines */
export async function showMvpBaselines() {
  const data = await get("/api/runtime/mvp/local-baselines");
  if (!data) {
    console.log("Could not fetch local baselines.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  console.log();
  console.log(`${B}  MVP LOCAL BASELINES${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const baselines = data.baselines || data.items || (Array.isArray(data) ? data : []);
  if (baselines.length) {
    for (const b of baselines) {
      const name = (b.name || b.metric || "?").padEnd(30);
      const val = b.value ?? b.baseline ?? "?";
      console.log(`  ${name} ${val}`);
    }
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (typeof v !== "object") console.log(`  ${k.padEnd(30)} ${v}`);
    }
  }
  console.log();
}

/** Show usage verification */
export async function showUsageVerification() {
  const data = await get("/api/runtime/usage/verification");
  if (!data) {
    console.log("Could not fetch usage verification.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  USAGE VERIFICATION${R}`);
  console.log(`  ${"─".repeat(60)}`);

  for (const [k, v] of Object.entries(data)) {
    if (v != null) {
      const display = typeof v === "boolean"
        ? (v ? `${G}✓ yes${R}` : `${RED}✗ no${R}`)
        : typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v);
      console.log(`  ${k.padEnd(30)} ${display}`);
    }
  }
  console.log();
}

/** Run the endpoint exerciser */
export async function runExerciser() {
  console.log("Running endpoint exerciser...");
  const data = await post("/api/runtime/exerciser/run", {});
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Exerciser failed.");
    return;
  }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", RED = "\x1b[31m";
  console.log();
  console.log(`${B}  EXERCISER RESULTS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const results = data.results || data.endpoints || (Array.isArray(data) ? data : []);
  if (results.length) {
    let passed = 0, failed = 0;
    for (const r of results) {
      const ok = r.success ?? r.ok ?? r.passed;
      if (ok) passed++; else failed++;
      const icon = ok ? `${G}✓${R}` : `${RED}✗${R}`;
      const path = (r.path || r.endpoint || "?").padEnd(45);
      const ms = r.latency_ms != null ? `${D}${r.latency_ms}ms${R}` : "";
      console.log(`  ${icon} ${path} ${ms}`);
    }
    console.log();
    console.log(`  ${G}${passed} passed${R}, ${RED}${failed} failed${R}`);
  } else {
    for (const [k, v] of Object.entries(data)) {
      if (typeof v !== "object") console.log(`  ${k}: ${v}`);
    }
  }
  console.log();
}

/** Get change token (for cache busting) */
export async function showChangeToken() {
  const data = await get("/api/runtime/change-token");
  if (!data) {
    console.log("Could not fetch change token.");
    return;
  }
  const token = data.token || data.change_token || JSON.stringify(data);
  console.log(token);
}

/** Runtime overview */
export async function showRuntimeOverview() {
  await showEndpointAttention();
  await showMvpSummary();
}
