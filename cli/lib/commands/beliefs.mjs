/**
 * Belief profile — contributor worldview, axes, concepts, resonance.
 */

import { get } from "../api.mjs";

/** @param {string[]} args */
export async function showBeliefs(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc beliefs <contributor_id>");
    console.log("       cc beliefs <contributor_id> resonance <idea_id>");
    return;
  }
  if (args[1] === "resonance") {
    const ideaId = args[2];
    if (!ideaId) {
      console.log("Usage: cc beliefs <contributor_id> resonance <idea_id>");
      return;
    }
    const path = `/api/contributors/${encodeURIComponent(id)}/beliefs/resonance`;
    const data = await get(path, { idea_id: ideaId });
    if (!data) {
      console.log("Could not fetch resonance (contributor or idea missing).");
      return;
    }
    console.log();
    console.log(`\x1b[1m  RESONANCE\x1b[0m  ${id}  ↔  ${ideaId}`);
    console.log(`  ${"─".repeat(56)}`);
    const s = data.scores || {};
    console.log(`  Overall:     ${(s.overall ?? "?").toString()}`);
    console.log(`  Concepts:    ${(s.concept_overlap ?? "?").toString()}`);
    console.log(`  Worldview:   ${(s.worldview_fit ?? "?").toString()}`);
    console.log(`  Axes:        ${(s.axis_alignment ?? "?").toString()}`);
    if (Array.isArray(data.matched_concepts) && data.matched_concepts.length) {
      console.log(`  Matched:     ${data.matched_concepts.join(", ")}`);
    }
    console.log();
    return;
  }

  const data = await get(`/api/contributors/${encodeURIComponent(id)}/beliefs`);
  if (!data) {
    console.log(`Beliefs for '${id}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  BELIEFS\x1b[0m  ${data.contributor_id || id}`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Worldview:   ${data.worldview}`);
  if (data.axes && typeof data.axes === "object") {
    console.log("  Axes:");
    for (const [k, v] of Object.entries(data.axes)) {
      console.log(`    ${k.padEnd(14)} ${String(v)}`);
    }
  }
  if (data.concepts && typeof data.concepts === "object" && Object.keys(data.concepts).length) {
    console.log("  Concepts:");
    for (const [k, v] of Object.entries(data.concepts)) {
      console.log(`    ${k.padEnd(14)} ${String(v)}`);
    }
  }
  console.log();
}
