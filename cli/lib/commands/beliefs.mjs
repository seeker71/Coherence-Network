/**
 * Contributor belief profile: GET / PATCH / resonance
 */

import { get, patch } from "../api.mjs";

const AXES = ["empirical", "collaborative", "strategic", "technical", "ethical"];
const WORLDVIEWS = ["scientific", "spiritual", "pragmatic", "holistic", "artistic", "systems"];

export async function showBeliefs(contributorId) {
  if (!contributorId) {
    console.log("Usage: cc beliefs <contributor-id>");
    console.log("       cc beliefs <contributor-id> resonance <idea-id>");
    console.log(`       cc beliefs patch <contributor-id> '<json>'`);
    console.log(`  Worldviews: ${WORLDVIEWS.join(", ")}`);
    return;
  }
  const data = await get(`/api/contributors/${encodeURIComponent(contributorId)}/beliefs`);
  if (!data) {
    console.log(`Beliefs for '${contributorId}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  BELIEFS\x1b[0m — ${contributorId}`);
  console.log(`  ${"─".repeat(56)}`);
  console.log(`  Worldview:  ${data.worldview}`);
  console.log(`  Updated:    ${data.updated_at || "—"}`);
  console.log();
  console.log("  Axis weights:");
  for (const a of AXES) {
    const v = data.axis_weights?.[a];
    const bar = "█".repeat(Math.round((v ?? 0.5) * 20));
    console.log(`    ${a.padEnd(14)} ${(v ?? 0.5).toFixed(2)}  ${bar}`);
  }
  console.log();
  const cw = data.concept_weights || {};
  const keys = Object.keys(cw);
  if (keys.length === 0) {
    console.log("  Concepts:   (none — add via PATCH)");
  } else {
    console.log("  Concepts:");
    for (const k of keys.sort()) {
      console.log(`    ${k.padEnd(20)} ${cw[k].toFixed(2)}`);
    }
  }
  console.log();
}

export async function showBeliefResonance(contributorId, ideaId) {
  if (!contributorId || !ideaId) {
    console.log("Usage: cc beliefs <contributor-id> resonance <idea-id>");
    return;
  }
  const data = await get(`/api/contributors/${encodeURIComponent(contributorId)}/beliefs/resonance`, {
    idea_id: ideaId,
  });
  if (!data) {
    console.log("Resonance not available (check contributor and idea ids).");
    return;
  }
  console.log();
  console.log(`\x1b[1m  RESONANCE\x1b[0m ${contributorId} ↔ ${ideaId}`);
  console.log(`  ${"─".repeat(56)}`);
  console.log(`  Score:              ${data.resonance_score}`);
  console.log(`  Concept overlap:    ${data.concept_overlap}`);
  console.log(`  Axis alignment:     ${data.axis_alignment}`);
  console.log(`  Worldview alignment: ${data.worldview_alignment}`);
  console.log(`  Idea worldview sig: ${data.idea_worldview_signal}`);
  if (data.matching_concepts?.length) {
    console.log(`  Matching concepts: ${data.matching_concepts.join(", ")}`);
  }
  console.log();
}

export async function patchBeliefsJson(contributorId, jsonStr) {
  if (!contributorId || !jsonStr) {
    console.log(`Usage: cc beliefs patch <contributor-id> '<json>'`);
    return;
  }
  let body;
  try {
    body = JSON.parse(jsonStr);
  } catch (e) {
    console.log("Invalid JSON:", e.message);
    return;
  }
  const data = await patch(`/api/contributors/${encodeURIComponent(contributorId)}/beliefs`, body);
  if (!data) {
    console.log("PATCH failed (need X-API-Key in ~/.coherence-network/keys.json or env).");
    return;
  }
  await showBeliefs(contributorId);
}
