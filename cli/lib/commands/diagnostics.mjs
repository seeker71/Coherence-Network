/**
 * Diagnostics commands: diag, diag health, diag issues, diag runners, diag visibility
 */

import { get } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function showDiag() {
  const [effectiveness, pipeline] = await Promise.all([
    get("/api/agent/effectiveness"),
    get("/api/agent/pipeline-status"),
  ]);

  console.log();
  console.log(`\x1b[1m  DIAGNOSTICS\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);

  if (effectiveness) {
    console.log(`  \x1b[1mEffectiveness:\x1b[0m`);
    for (const [key, val] of Object.entries(effectiveness)) {
      console.log(`    ${key}: ${JSON.stringify(val)}`);
    }
  } else {
    console.log(`  Effectiveness: \x1b[2munavailable\x1b[0m`);
  }

  if (pipeline) {
    console.log(`  \x1b[1mPipeline Status:\x1b[0m`);
    for (const [key, val] of Object.entries(pipeline)) {
      console.log(`    ${key}: ${JSON.stringify(val)}`);
    }
  } else {
    console.log(`  Pipeline Status: \x1b[2munavailable\x1b[0m`);
  }
  console.log();
}

export async function showDiagHealth() {
  const data = await get("/api/agent/collective-health");
  if (!data) {
    console.log("Could not fetch collective health.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  COLLECTIVE HEALTH\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

export async function showDiagIssues() {
  const [fatal, monitor] = await Promise.all([
    get("/api/agent/fatal-issues"),
    get("/api/agent/monitor-issues"),
  ]);

  console.log();
  console.log(`\x1b[1m  ISSUES\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);

  const fatalList = Array.isArray(fatal) ? fatal : fatal?.issues || [];
  const monitorList = Array.isArray(monitor) ? monitor : monitor?.issues || [];

  if (fatalList.length > 0) {
    console.log(`  \x1b[31mFatal (${fatalList.length}):\x1b[0m`);
    for (const i of fatalList) {
      const desc = truncate(i.description || i.message || i.id || JSON.stringify(i), 60);
      console.log(`    \x1b[31m✗\x1b[0m ${desc}`);
    }
  } else {
    console.log(`  \x1b[32mNo fatal issues\x1b[0m`);
  }

  if (monitorList.length > 0) {
    console.log(`  \x1b[33mMonitor (${monitorList.length}):\x1b[0m`);
    for (const i of monitorList) {
      const desc = truncate(i.description || i.message || i.id || JSON.stringify(i), 60);
      console.log(`    \x1b[33m!\x1b[0m ${desc}`);
    }
  } else {
    console.log(`  \x1b[32mNo monitor issues\x1b[0m`);
  }
  console.log();
}

export async function showDiagRunners() {
  const raw = await get("/api/agent/runners");
  const data = Array.isArray(raw) ? raw : raw?.runners;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch runners.");
    return;
  }
  if (data.length === 0) {
    console.log("No runners found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  RUNNERS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(50)}`);
  for (const r of data) {
    const name = truncate(r.name || r.id || "?", 25);
    const status = r.status || "?";
    const dot = status === "active" || status === "running" ? "\x1b[32m●\x1b[0m" : "\x1b[2m○\x1b[0m";
    console.log(`  ${dot} ${name.padEnd(27)} ${status}`);
  }
  console.log();
}

export async function showDiagVisibility() {
  const data = await get("/api/agent/visibility");
  if (!data) {
    console.log("Could not fetch visibility.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  VISIBILITY\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}
