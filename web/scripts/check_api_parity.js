#!/usr/bin/env node
/**
 * Web-side interface parity check.
 *
 * Validates that the API response shapes match the fields the web pages
 * depend on. Runs against a live or local API (set API_BASE env var).
 *
 * Usage:
 *   API_BASE=http://localhost:8000 node web/scripts/check_api_parity.js
 *
 * Exit codes:
 *   0 — all contracts pass
 *   1 — at least one contract violation detected
 */

const API_BASE = process.env.API_BASE || "http://localhost:8000";

let failures = 0;
let passes = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  FAIL: ${message}`);
    failures += 1;
  } else {
    passes += 1;
  }
}

function hasFields(obj, fields, context) {
  for (const f of fields) {
    assert(f in obj, `${context} missing field '${f}'`);
  }
}

function isType(value, types, context) {
  const actual = typeof value;
  assert(types.includes(actual), `${context}: expected ${types.join("|")}, got ${actual}`);
}

async function checkHealth() {
  console.log("\n--- Pair 1: GET /api/health (health/landing) ---");
  let resp;
  try {
    resp = await fetch(`${API_BASE}/api/health`);
  } catch (err) {
    console.error(`  FAIL: Could not reach ${API_BASE}/api/health: ${err.message}`);
    failures += 1;
    return;
  }
  assert(resp.ok, `/api/health returned ${resp.status}`);
  const data = await resp.json();

  const requiredFields = [
    "status", "version", "timestamp", "started_at",
    "uptime_seconds", "uptime_human",
  ];
  hasFields(data, requiredFields, "health");
  assert(data.status === "ok", `health.status should be 'ok', got '${data.status}'`);
  isType(data.version, ["string"], "health.version");
  isType(data.timestamp, ["string"], "health.timestamp");
  isType(data.uptime_seconds, ["number"], "health.uptime_seconds");
}

async function checkIdeasList() {
  console.log("\n--- Pair 2: GET /api/ideas (ideas list) ---");
  let resp;
  try {
    resp = await fetch(`${API_BASE}/api/ideas`);
  } catch (err) {
    console.error(`  FAIL: Could not reach ${API_BASE}/api/ideas: ${err.message}`);
    failures += 1;
    return;
  }
  assert(resp.ok, `/api/ideas returned ${resp.status}`);
  const data = await resp.json();

  assert(Array.isArray(data.ideas), "data.ideas should be an array");
  assert(typeof data.summary === "object" && data.summary !== null, "data.summary should be an object");

  // Summary fields consumed by web/app/ideas/page.tsx and web/app/page.tsx
  const summaryFields = [
    "total_ideas", "total_potential_value", "total_actual_value", "total_value_gap",
  ];
  hasFields(data.summary, summaryFields, "summary");
  isType(data.summary.total_ideas, ["number"], "summary.total_ideas");

  // Per-idea fields consumed by web/app/ideas/page.tsx
  const ideaFields = [
    "id", "name", "description", "potential_value", "actual_value",
    "estimated_cost", "actual_cost", "confidence", "resistance_risk",
    "manifestation_status", "interfaces", "open_questions",
    "free_energy_score", "value_gap",
  ];
  for (const idea of data.ideas) {
    hasFields(idea, ideaFields, `idea[${idea.id || "?"}]`);
  }
}

async function checkIdeaDetail() {
  console.log("\n--- Pair 3: GET /api/ideas/{id} (idea detail) ---");
  // First get any idea ID from the list
  let listResp;
  try {
    listResp = await fetch(`${API_BASE}/api/ideas`);
  } catch (err) {
    console.error(`  FAIL: Could not reach /api/ideas to find an ID: ${err.message}`);
    failures += 1;
    return;
  }
  const listData = await listResp.json();
  if (!listData.ideas || listData.ideas.length === 0) {
    console.log("  SKIP: No ideas in portfolio to test detail endpoint");
    return;
  }

  const ideaId = listData.ideas[0].id;
  let resp;
  try {
    resp = await fetch(`${API_BASE}/api/ideas/${encodeURIComponent(ideaId)}`);
  } catch (err) {
    console.error(`  FAIL: Could not reach detail for '${ideaId}': ${err.message}`);
    failures += 1;
    return;
  }
  assert(resp.ok, `/api/ideas/${ideaId} returned ${resp.status}`);
  const idea = await resp.json();

  // All fields the detail page renders or passes to components
  const coreFields = [
    "id", "name", "description", "potential_value", "actual_value",
    "estimated_cost", "actual_cost", "confidence", "resistance_risk",
    "manifestation_status", "interfaces", "open_questions",
    "free_energy_score", "value_gap",
  ];
  hasFields(idea, coreFields, "detail");

  // Score fields
  const scoreFields = [
    "free_energy_score", "marginal_cc_score", "value_gap", "selection_weight",
  ];
  hasFields(idea, scoreFields, "detail.scores");

  // CC fields
  const ccFields = ["remaining_cost_cc", "value_gap_cc", "roi_cc"];
  hasFields(idea, ccFields, "detail.cc");
  assert("cost_vector" in idea, "detail missing cost_vector key");
  assert("value_vector" in idea, "detail missing value_vector key");

  // manifestation_status must be one of the known enum values
  assert(
    ["none", "partial", "validated"].includes(idea.manifestation_status),
    `manifestation_status '${idea.manifestation_status}' not in expected enum`,
  );

  // open_questions shape
  for (const q of idea.open_questions || []) {
    hasFields(q, ["question", "value_to_whole", "estimated_cost", "answer"], `question`);
  }
}

async function main() {
  console.log(`Interface parity check against ${API_BASE}`);
  await checkHealth();
  await checkIdeasList();
  await checkIdeaDetail();

  console.log(`\n=== Results: ${passes} passed, ${failures} failed ===`);
  process.exit(failures > 0 ? 1 : 0);
}

main();
