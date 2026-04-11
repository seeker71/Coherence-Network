/**
 * Traceability commands: trace, trace coverage, trace idea, trace spec
 */

import { get } from "../api.mjs";
import { truncate } from "../ui/ansi.mjs";


export async function showTraceability() {
  const data = await get("/api/traceability");
  if (!data) {
    console.log("Could not fetch traceability.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  TRACEABILITY\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  for (const [key, val] of Object.entries(data)) {
    console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

export async function showCoverage() {
  const data = await get("/api/traceability/coverage");
  if (!data) {
    console.log("Could not fetch traceability coverage.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  TRACEABILITY COVERAGE\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.coverage != null) {
    const pct = typeof data.coverage === "number" ? `${(data.coverage * 100).toFixed(1)}%` : data.coverage;
    console.log(`  Coverage:    ${pct}`);
  }
  for (const [key, val] of Object.entries(data)) {
    if (key !== "coverage") console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

export async function traceIdea(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc trace idea <id>");
    return;
  }
  const data = await get(`/api/traceability/idea/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`No traceability data for idea '${id}'.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  TRACE: IDEA\x1b[0m ${id}`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.specs && Array.isArray(data.specs)) {
    console.log(`  Linked specs: ${data.specs.length}`);
    for (const s of data.specs) {
      console.log(`    ${truncate(s.id || s.name || JSON.stringify(s), 50)}`);
    }
  }
  if (data.contributions && Array.isArray(data.contributions)) {
    console.log(`  Contributions: ${data.contributions.length}`);
  }
  // Fallback
  const shown = new Set(["specs", "contributions"]);
  for (const [key, val] of Object.entries(data)) {
    if (!shown.has(key)) console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}

export async function traceSpec(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc trace spec <id>");
    return;
  }
  const data = await get(`/api/traceability/spec/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`No traceability data for spec '${id}'.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  TRACE: SPEC\x1b[0m ${id}`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.ideas && Array.isArray(data.ideas)) {
    console.log(`  Linked ideas: ${data.ideas.length}`);
    for (const i of data.ideas) {
      console.log(`    ${truncate(i.id || i.name || JSON.stringify(i), 50)}`);
    }
  }
  // Fallback
  const shown = new Set(["ideas"]);
  for (const [key, val] of Object.entries(data)) {
    if (!shown.has(key)) console.log(`  ${key}: ${JSON.stringify(val)}`);
  }
  console.log();
}
