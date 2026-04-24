/**
 * Inventory commands: inventory, pipeline
 *
 * Covers the gap analysis, process completeness, flow, and pipeline endpoints.
 *   coh inventory                    — show pipeline pulse / overall flow
 *   coh inventory flow               — full flow details
 *   coh inventory gaps               — list traceability gaps
 *   coh inventory routes             — canonical routes
 *   coh inventory completeness       — process completeness report
 *   coh inventory endpoints          — endpoint traceability
 *   coh inventory evidence           — route evidence
 *   coh inventory assets             — asset modularity report
 *   coh pipeline pulse               — pipeline pulse (alias)
 *   coh pipeline fix-hollow          — fix hollow completions
 */

import { get, post } from "../api.mjs";
import { truncate } from "../ui/ansi.mjs";


function fmt(val, pad = 0) {
  const s = val == null ? "—" : String(val);
  return pad ? s.padEnd(pad) : s;
}

export async function showInventoryFlow(args) {
  const data = await get("/api/inventory/flow");
  if (!data) { console.log("Could not fetch inventory flow."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  INVENTORY FLOW${R}`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.summary) {
    const s = data.summary;
    if (s.total_ideas != null)    console.log(`  Ideas total:     ${s.total_ideas}`);
    if (s.ideas_with_specs != null) console.log(`  With specs:      ${s.ideas_with_specs}`);
    if (s.ideas_with_tests != null) console.log(`  With tests:      ${s.ideas_with_tests}`);
    if (s.ideas_with_impl != null)  console.log(`  Implemented:     ${s.ideas_with_impl}`);
    if (s.ideas_validated != null)  console.log(`  Validated:       ${s.ideas_validated}`);
  }

  if (Array.isArray(data.stages)) {
    console.log();
    console.log(`  ${D}STAGES${R}`);
    for (const stage of data.stages) {
      const name  = fmt(stage.name || stage.stage, 20);
      const count = fmt(stage.count, 6);
      const pct   = stage.pct != null ? `${stage.pct.toFixed(1)}%`.padStart(6) : "";
      const bar   = stage.pct != null
        ? "█".repeat(Math.round(stage.pct / 5)).padEnd(20, "░")
        : "";
      console.log(`  ${name} ${count} ${pct}  ${D}${bar}${R}`);
    }
  }

  if (Array.isArray(data.bottlenecks) && data.bottlenecks.length) {
    console.log();
    console.log(`  ${Y}BOTTLENECKS${R}`);
    for (const b of data.bottlenecks) {
      console.log(`  ${Y}▲${R} ${truncate(b.description || b, 70)}`);
    }
  }

  console.log();
}

export async function showPipelinePulse() {
  const data = await get("/api/pipeline/pulse");
  if (!data) { console.log("Could not fetch pipeline pulse."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log();
  console.log(`${B}  PIPELINE PULSE${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const status = (data.status || "?").toLowerCase();
  const statusColor = status === "healthy" ? G : status === "warning" ? Y : RED;
  console.log(`  Status: ${statusColor}${status}${R}`);

  if (data.throughput != null) console.log(`  Throughput:   ${data.throughput}`);
  if (data.queue_depth != null) console.log(`  Queue depth:  ${data.queue_depth}`);
  if (data.avg_latency_ms != null) console.log(`  Avg latency:  ${data.avg_latency_ms}ms`);
  if (data.error_rate != null) console.log(`  Error rate:   ${(data.error_rate * 100).toFixed(1)}%`);

  if (data.stages) {
    console.log();
    console.log(`  ${D}STAGE BREAKDOWN${R}`);
    for (const [k, v] of Object.entries(data.stages)) {
      console.log(`  ${k.padEnd(20)} ${D}${JSON.stringify(v)}${R}`);
    }
  }

  console.log();
}

export async function showInventoryGaps() {
  const data = await get("/api/inventory/gaps/sync-traceability", null, "POST") ||
               await get("/api/inventory/gaps/bootstrap-specs");
  // Primary: GET traceability gaps
  const gaps = await get("/api/inventory/flow");
  if (!gaps) { console.log("Could not fetch inventory gaps."); return; }

  console.log();
  console.log(`\x1b[1m  INVENTORY GAPS\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);
  if (gaps.gaps && Array.isArray(gaps.gaps)) {
    for (const g of gaps.gaps) {
      console.log(`  \x1b[33m▲\x1b[0m ${truncate(g.description || g.id || String(g), 70)}`);
    }
  } else {
    console.log(`  \x1b[2mNo gap data in flow response. Try: coh inventory endpoints\x1b[0m`);
  }
  console.log();
}

export async function showInventoryRoutes() {
  const data = await get("/api/inventory/routes/canonical");
  if (!data) { console.log("Could not fetch canonical routes."); return; }
  const routes = Array.isArray(data) ? data : data?.routes || [];

  console.log();
  console.log(`\x1b[1m  CANONICAL ROUTES\x1b[0m (${routes.length})`);
  console.log(`  ${"─".repeat(74)}`);
  for (const r of routes) {
    const method = (r.method || "GET").padEnd(6);
    const path = (r.path || r.route || "").padEnd(45);
    const tag = r.tag || r.module || "";
    console.log(`  ${method} ${path} \x1b[2m${tag}\x1b[0m`);
  }
  console.log();
}

export async function showInventoryCompleteness() {
  const data = await get("/api/inventory/process-completeness");
  if (!data) { console.log("Could not fetch process completeness."); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
  const G = "\x1b[32m", Y = "\x1b[33m";

  console.log();
  console.log(`${B}  PROCESS COMPLETENESS${R}`);
  console.log(`  ${"─".repeat(60)}`);

  const score = data.overall_score ?? data.completeness_score;
  if (score != null) {
    const pct = (score * 100).toFixed(1);
    const bar = "█".repeat(Math.round(score * 20)).padEnd(20, "░");
    const color = score >= 0.8 ? G : score >= 0.5 ? Y : "\x1b[31m";
    console.log(`  Overall: ${color}${pct}%${R}  ${D}${bar}${R}`);
    console.log();
  }

  if (Array.isArray(data.dimensions)) {
    for (const dim of data.dimensions) {
      const name = fmt(dim.name || dim.dimension, 25);
      const pct = dim.score != null ? `${(dim.score * 100).toFixed(0)}%`.padStart(5) : "    —";
      console.log(`  ${name} ${pct}`);
    }
  }

  if (data.missing_steps && data.missing_steps.length) {
    console.log();
    console.log(`  ${Y}MISSING STEPS${R}`);
    for (const step of data.missing_steps.slice(0, 10)) {
      console.log(`  ${Y}○${R} ${truncate(step.name || step, 60)}`);
    }
  }

  console.log();
}

export async function showInventoryEndpoints() {
  const data = await get("/api/inventory/endpoint-traceability");
  if (!data) { console.log("Could not fetch endpoint traceability."); return; }
  const endpoints = Array.isArray(data) ? data : data?.endpoints || [];

  const covered = endpoints.filter(e => e.has_spec || e.has_test || e.has_impl);
  const pct = endpoints.length ? (covered.length / endpoints.length * 100).toFixed(1) : "0.0";

  console.log();
  console.log(`\x1b[1m  ENDPOINT TRACEABILITY\x1b[0m (${covered.length}/${endpoints.length} = ${pct}% covered)`);
  console.log(`  ${"─".repeat(74)}`);

  for (const ep of endpoints.slice(0, 30)) {
    const spec = ep.has_spec ? "\x1b[32mS\x1b[0m" : "\x1b[31ms\x1b[0m";
    const test = ep.has_test ? "\x1b[32mT\x1b[0m" : "\x1b[31mt\x1b[0m";
    const impl = ep.has_impl ? "\x1b[32mI\x1b[0m" : "\x1b[31mi\x1b[0m";
    const path = truncate(ep.path || ep.route || "", 50).padEnd(52);
    console.log(`  ${spec}${test}${impl} ${path}`);
  }

  if (endpoints.length > 30) {
    console.log(`  \x1b[2m... and ${endpoints.length - 30} more\x1b[0m`);
  }
  console.log(`  \x1b[2mS=spec T=test I=impl (green=present, red=missing)\x1b[0m`);
  console.log();
}

export async function showInventoryEvidence() {
  const [routeEv, commitEv] = await Promise.all([
    get("/api/inventory/route-evidence"),
    get("/api/inventory/commit-evidence"),
  ]);

  console.log();
  console.log(`\x1b[1m  INVENTORY EVIDENCE\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);

  if (routeEv) {
    const routes = Array.isArray(routeEv) ? routeEv : routeEv?.routes || [];
    console.log(`  Route evidence:  ${routes.length} routes tracked`);
  }
  if (commitEv) {
    const commits = Array.isArray(commitEv) ? commitEv : commitEv?.commits || [];
    console.log(`  Commit evidence: ${commits.length} commits tracked`);
    for (const c of commits.slice(0, 5)) {
      const sha = (c.sha || c.commit || "").slice(0, 7);
      const msg = truncate(c.message || c.summary || "", 55);
      console.log(`    \x1b[2m${sha}\x1b[0m ${msg}`);
    }
  }
  console.log();
}

export async function showInventoryAssets() {
  const data = await get("/api/inventory/asset-modularity");
  if (!data) { console.log("Could not fetch asset modularity."); return; }

  console.log();
  console.log(`\x1b[1m  ASSET MODULARITY\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);

  const score = data.overall_score ?? data.modularity_score;
  if (score != null) {
    console.log(`  Overall score: ${(score * 100).toFixed(1)}%`);
  }

  const assets = Array.isArray(data.assets) ? data.assets : [];
  for (const a of assets.slice(0, 20)) {
    const name = truncate(a.name || a.id || "", 40).padEnd(42);
    const mod = a.modularity_score != null ? `${(a.modularity_score * 100).toFixed(0)}%`.padStart(4) : "   —";
    const deps = a.dependency_count != null ? `${a.dependency_count} deps` : "";
    console.log(`  ${name} ${mod}  \x1b[2m${deps}\x1b[0m`);
  }
  console.log();
}

export async function fixHollowCompletions() {
  const result = await post("/api/pipeline/fix-hollow-completions", {});
  if (!result) { console.log("Request failed."); return; }
  console.log();
  console.log(`\x1b[1m  FIX HOLLOW COMPLETIONS\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  const fixed = result.fixed_count ?? result.count ?? result.updated;
  if (fixed != null) console.log(`  Fixed: ${fixed}`);
  const affected = Array.isArray(result.affected) ? result.affected : [];
  for (const id of affected.slice(0, 10)) {
    console.log(`  \x1b[32m✓\x1b[0m ${id}`);
  }
  if (affected.length > 10) console.log(`  \x1b[2m... and ${affected.length - 10} more\x1b[0m`);
  console.log();
}

export async function showSystemLineage() {
  const data = await get("/api/inventory/system-lineage");
  if (!data) { console.log("Could not fetch system lineage."); return; }

  console.log();
  console.log(`\x1b[1m  SYSTEM LINEAGE\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);

  if (data.total_links != null) console.log(`  Total links:   ${data.total_links}`);
  if (data.linked_ideas != null) console.log(`  Linked ideas:  ${data.linked_ideas}`);
  if (data.depth_avg != null) console.log(`  Avg depth:     ${data.depth_avg.toFixed(2)}`);

  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  if (nodes.length) {
    console.log();
    console.log(`  \x1b[2mTOP NODES\x1b[0m`);
    for (const n of nodes.slice(0, 10)) {
      const name = truncate(n.name || n.id || "", 40).padEnd(42);
      const links = n.link_count != null ? `${n.link_count} links` : "";
      console.log(`  ${name} \x1b[2m${links}\x1b[0m`);
    }
  }
  console.log();
}

export function handleInventory(args) {
  const sub = args[0];
  const rest = args.slice(1);

  switch (sub) {
    case "flow":          return showInventoryFlow(rest);
    case "pulse":         return showPipelinePulse();
    case "gaps":          return showInventoryGaps();
    case "routes":        return showInventoryRoutes();
    case "completeness":  return showInventoryCompleteness();
    case "endpoints":     return showInventoryEndpoints();
    case "evidence":      return showInventoryEvidence();
    case "assets":        return showInventoryAssets();
    case "lineage":       return showSystemLineage();
    case "fix-hollow":    return fixHollowCompletions();
    default:
      // Default: show pipeline pulse + quick flow summary
      return showPipelinePulse().then(() => showInventoryFlow([]));
  }
}

export function handlePipeline(args) {
  const sub = args[0];
  switch (sub) {
    case "pulse":         return showPipelinePulse();
    case "fix-hollow":    return fixHollowCompletions();
    case "flow":          return showInventoryFlow(args.slice(1));
    default:              return showPipelinePulse();
  }
}
