/**
 * Belief profile — worldview, concepts, axes, optional resonance vs an idea.
 */

import { get } from "../api.mjs";

function fmtNum(n) {
  if (n == null || Number.isNaN(n)) return "?";
  return (Math.round(n * 1000) / 1000).toString();
}

export async function showBeliefs(args) {
  const sub = args[0];
  const subArgs = args.slice(1);
  if (sub === "resonance") {
    const cid = subArgs[0];
    const ideaId = subArgs[1];
    if (!cid || !ideaId) {
      console.log("Usage: cc beliefs resonance <contributor_id> <idea_id>");
      return;
    }
    const path = `/api/contributors/${encodeURIComponent(cid)}/beliefs/resonance`;
    const data = await get(path, { idea_id: ideaId });
    if (!data) {
      console.log("Could not load resonance (contributor or idea missing).");
      return;
    }
    console.log();
    console.log(`\x1b[1m  BELIEF RESONANCE\x1b[0m`);
    console.log(`  ${"─".repeat(52)}`);
    console.log(`  Contributor:  ${data.contributor_id}`);
    console.log(`  Idea:         ${data.idea_id}`);
    console.log(`  Score:        ${fmtNum(data.resonance_score)}`);
    if (data.breakdown) {
      console.log(`  Concepts:     ${fmtNum(data.breakdown.concept_alignment)}`);
      console.log(`  Worldview:    ${fmtNum(data.breakdown.worldview_alignment)}`);
      console.log(`  Axes:         ${fmtNum(data.breakdown.axis_alignment)}`);
    }
    if (data.matched_concepts?.length) {
      console.log(`  Matched:      ${data.matched_concepts.join(", ")}`);
    }
    console.log();
    return;
  }

  const cid = sub;
  if (!cid) {
    console.log("Usage: cc beliefs <contributor_id>");
    console.log("       cc beliefs resonance <contributor_id> <idea_id>");
    return;
  }
  const data = await get(`/api/contributors/${encodeURIComponent(cid)}/beliefs`);
  if (!data) {
    console.log(`Beliefs for '${cid}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  BELIEF PROFILE\x1b[0m (${data.contributor_id})`);
  console.log(`  ${"─".repeat(52)}`);
  console.log(`  Worldview:    ${data.worldview}`);
  const axes = data.axis_values || {};
  const keys = Object.keys(axes).sort();
  if (keys.length) {
    console.log(`  Axes:`);
    for (const k of keys) {
      console.log(`    ${k.padEnd(14)} ${fmtNum(axes[k])}`);
    }
  }
  const cw = data.concept_weights || {};
  const ckeys = Object.keys(cw);
  if (ckeys.length) {
    console.log(`  Concepts:`);
    for (const k of ckeys.sort()) {
      console.log(`    ${k.padEnd(22)} ${fmtNum(cw[k])}`);
    }
  } else {
    console.log(`  Concepts:     (none — set via API or web)`);
  }
  console.log();
}
