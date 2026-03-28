/**
 * Belief system commands — per-contributor worldview, interests, and concept preferences.
 * spec-169
 */

import { get, patch } from "../api.mjs";
import { getContributorId } from "../config.mjs";

const AXIS_ORDER = ["scientific", "systemic", "pragmatic", "holistic", "relational", "spiritual"];

function bar(value) {
  const filled = Math.round(value * 10);
  return "█".repeat(filled) + "░".repeat(10 - filled);
}

function resolveContributor(args) {
  const id = args[0] || getContributorId();
  if (!id) {
    console.log("No contributor specified. Pass an ID or run: cc setup");
  }
  return id;
}

/**
 * cc beliefs [contributor_id]
 * Show the belief profile for a contributor (or yourself).
 */
export async function showBeliefs(args) {
  const id = resolveContributor(args);
  if (!id) return;

  const data = await get(`/api/contributors/${encodeURIComponent(id)}/beliefs`);
  if (!data) {
    console.log(`  No belief profile found for '${id}'.`);
    return;
  }

  const axes = data.worldview_axes || {};
  const tags = data.interest_tags || [];
  const resonances = data.concept_resonances || [];
  const updatedAt = data.updated_at ? new Date(data.updated_at).toLocaleDateString() : "never";

  console.log();
  console.log(`\x1b[1mBelief Profile — @${data.contributor_id || id}\x1b[0m`);
  console.log(`${"─".repeat(44)}`);
  console.log(`\x1b[2mUpdated: ${updatedAt}\x1b[0m`);
  console.log();
  console.log("\x1b[1mWorldview Axes:\x1b[0m");
  for (const axis of AXIS_ORDER) {
    const val = axes[axis] ?? 0;
    const label = axis.padEnd(12);
    console.log(`  ${label} ${bar(val)}  ${val.toFixed(2)}`);
  }

  console.log();
  if (resonances.length > 0) {
    const top5 = resonances.slice(0, 5);
    const list = top5.map((r) => `${r.concept_id} (${r.weight.toFixed(2)})`).join(", ");
    console.log(`\x1b[1mConcept Resonances (top ${top5.length}):\x1b[0m`);
    console.log(`  ${list}`);
    console.log();
  }

  if (tags.length > 0) {
    console.log(`\x1b[1mInterest Tags:\x1b[0m ${tags.map((t) => `#${t}`).join(" ")}`);
    console.log();
  }
}

/**
 * cc beliefs set <axis> <value>
 * Set a single worldview axis value (0.0–1.0).
 */
export async function setBeliefAxis(args) {
  const [idOrAxis, axisOrValue, maybeValue] = args;
  let id, axis, value;

  // Support: cc beliefs set scientific 0.9
  //      or: cc beliefs set <contributor> scientific 0.9
  if (maybeValue !== undefined) {
    id = idOrAxis;
    axis = axisOrValue;
    value = parseFloat(maybeValue);
  } else {
    id = getContributorId();
    axis = idOrAxis;
    value = parseFloat(axisOrValue);
  }

  if (!id) {
    console.log("No contributor identified. Run 'cc setup' or pass a contributor ID.");
    return;
  }
  if (!axis || isNaN(value)) {
    console.log("Usage: cc beliefs set <axis> <0.0-1.0>");
    console.log(`Valid axes: ${AXIS_ORDER.join(", ")}`);
    return;
  }
  if (value < 0 || value > 1) {
    console.log(`Value must be between 0.0 and 1.0 (got ${value})`);
    return;
  }

  const updated = await patch(`/api/contributors/${encodeURIComponent(id)}/beliefs`, {
    worldview_axes: { [axis]: value },
  });

  if (!updated) {
    console.log(`  Failed to set ${axis}. Is the axis name valid?`);
    console.log(`  Valid axes: ${AXIS_ORDER.join(", ")}`);
    return;
  }

  console.log(`\x1b[32m✓\x1b[0m ${axis} → ${value.toFixed(2)}`);
}

/**
 * cc beliefs add-concept <concept_id> <weight>
 * Add or update a concept resonance.
 */
export async function addBeliefConcept(args) {
  const [conceptId, weightStr] = args;
  const id = getContributorId();
  if (!id) {
    console.log("No contributor identified. Run 'cc setup'.");
    return;
  }
  if (!conceptId || !weightStr) {
    console.log("Usage: cc beliefs add-concept <concept_id> <0.0-1.0>");
    return;
  }
  const weight = parseFloat(weightStr);
  if (isNaN(weight) || weight < 0 || weight > 1) {
    console.log("Weight must be between 0.0 and 1.0");
    return;
  }

  const updated = await patch(`/api/contributors/${encodeURIComponent(id)}/beliefs`, {
    concept_resonances: [{ concept_id: conceptId, weight }],
  });

  if (!updated) {
    console.log("  Failed to add concept resonance.");
    return;
  }

  console.log(`\x1b[32m✓\x1b[0m Added concept: ${conceptId} (${weight.toFixed(2)})`);
}

/**
 * cc beliefs match <idea_id> [--verbose]
 * Show resonance score between your beliefs and an idea.
 */
export async function matchBeliefs(args) {
  const ideaId = args[0];
  const verbose = args.includes("--verbose") || args.includes("-v");
  const id = getContributorId();
  if (!id) {
    console.log("No contributor identified. Run 'cc setup'.");
    return;
  }
  if (!ideaId) {
    console.log("Usage: cc beliefs match <idea_id> [--verbose]");
    return;
  }

  const data = await get(
    `/api/contributors/${encodeURIComponent(id)}/beliefs/resonance`,
    { idea_id: ideaId }
  );

  if (!data) {
    console.log("  No resonance data returned. Check the idea ID.");
    return;
  }

  const score = data.resonance_score ?? 0;
  const level = score >= 0.7 ? "\x1b[32mHIGH\x1b[0m" : score >= 0.3 ? "\x1b[33mMODERATE\x1b[0m" : "\x1b[2mLOW\x1b[0m";

  console.log();
  console.log(`\x1b[1mResonance Match: ${ideaId}\x1b[0m`);
  console.log(`${"─".repeat(40)}`);
  console.log(`  Score:  ${score.toFixed(4)}  ${level}`);

  if (verbose && data.breakdown) {
    const b = data.breakdown;
    console.log();
    console.log("\x1b[1mBreakdown:\x1b[0m");
    console.log(`  concept_overlap     ${b.concept_overlap?.toFixed(4) ?? "n/a"}`);
    console.log(`  worldview_alignment ${b.worldview_alignment?.toFixed(4) ?? "n/a"}`);
    console.log(`  tag_match           ${b.tag_match?.toFixed(4) ?? "n/a"}`);
    if (data.matched_concepts?.length) {
      console.log();
      console.log(`  Matched concepts: ${data.matched_concepts.join(", ")}`);
    }
    if (data.matched_axes?.length) {
      console.log(`  Matched axes:     ${data.matched_axes.join(", ")}`);
    }
  }
  console.log();
}
