/**
 * Specs commands: specs, spec
 */

import { get } from "../api.mjs";

/** Truncate at word boundary, append "..." if needed */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const trimmed = str.slice(0, len - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > len * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
}

export async function listSpecs(args) {
  const limit = parseInt(args[0]) || 20;
  const data = await get("/api/spec-registry", { limit });
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch specs.");
    return;
  }
  if (data.length === 0) {
    console.log("No specs registered.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  SPECS\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(74)}`);
  console.log(`\x1b[2m  ${"Spec ID".padEnd(22)} ${"Title".padEnd(37)} ${"ROI".padStart(6)} ${"Gap".padStart(5)}\x1b[0m`);
  console.log(`  ${"─".repeat(74)}`);
  for (const s of data) {
    const specId = truncate(s.spec_id || "", 20).padEnd(22);
    const title = truncate(s.title || "", 35).padEnd(37);
    const roi = s.estimated_roi != null ? String(s.estimated_roi.toFixed(1)).padStart(6) : "     -";
    const gap = s.value_gap != null ? String(s.value_gap.toFixed(0)).padStart(5) : "    -";
    console.log(`  ${specId} ${title} ${roi} ${gap}`);
  }
  console.log();
}

export async function showSpec(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc spec <spec-id>");
    return;
  }
  const data = await get(`/api/spec-registry/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Spec '${id}' not found.`);
    return;
  }
  console.log();
  console.log(`\x1b[1m  ${data.title || data.spec_id}\x1b[0m`);
  if (data.summary) console.log(`  ${truncate(data.summary, 72)}`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.estimated_roi != null) console.log(`  Est. ROI:     ${data.estimated_roi.toFixed(2)}`);
  if (data.actual_roi != null) console.log(`  Actual ROI:   ${data.actual_roi.toFixed(2)}`);
  if (data.value_gap != null) console.log(`  Value Gap:    ${data.value_gap.toFixed(0)}`);
  if (data.implementation_summary) {
    console.log();
    console.log("  \x1b[1mImplementation:\x1b[0m");
    console.log(`  ${truncate(data.implementation_summary, 72)}`);
  }
  if (data.pseudocode_summary) {
    console.log();
    console.log("  \x1b[1mPseudocode:\x1b[0m");
    console.log(`  ${truncate(data.pseudocode_summary, 72)}`);
  }
  console.log();
}
