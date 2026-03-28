/**
 * Concepts commands: concepts, concept <id>, concept link <from> <rel> <to>
 *
 * CLI surface for the Living Codex ontology (184 concepts, 46 rel types, 53 axes).
 */

import { get, post, patch } from "../api.mjs";

/** Truncate string at word boundary */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const t = str.slice(0, len - 3);
  const s = t.lastIndexOf(" ");
  return (s > len * 0.4 ? t.slice(0, s) : t) + "...";
}

/** Colorize an axis name */
function axisColor(axis) {
  const map = {
    temporal: "\x1b[34m",
    causal: "\x1b[33m",
    ucore: "\x1b[35m",
    spatial: "\x1b[36m",
    social: "\x1b[32m",
    epistemic: "\x1b[93m",
    ethical: "\x1b[31m",
    energetic: "\x1b[91m",
    informational: "\x1b[96m",
  };
  return (map[axis] ?? "\x1b[2m") + axis + "\x1b[0m";
}

/**
 * cc concepts [limit] [--axis <axis>]
 * List concepts, optionally filtered by axis.
 */
export async function listConcepts(args) {
  let limit = 50;
  let axis = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--axis" && args[i + 1]) {
      axis = args[++i];
    } else if (!isNaN(parseInt(args[i]))) {
      limit = parseInt(args[i]);
    }
  }

  const params = { limit };
  if (axis) params.axis = axis;

  const data = await get("/api/concepts", params);
  if (!data || !Array.isArray(data.items)) {
    console.log("Could not fetch concepts.");
    return;
  }

  console.log();
  const header = axis ? `  CONCEPTS  [axis: ${axis}]  (${data.total} total, showing ${data.items.length})` : `  CONCEPTS  (${data.total} total, showing ${data.items.length})`;
  console.log(`\x1b[1m${header}\x1b[0m`);
  console.log(`  ${"─".repeat(76)}`);

  for (const c of data.items) {
    const name = truncate(c.name || c.id, 28).padEnd(30);
    const desc = truncate(c.description, 36).padEnd(38);
    const axes = (c.axes || []).slice(0, 2).map(axisColor).join(" ");
    console.log(`  \x1b[33m${(c.id || "").padEnd(22)}\x1b[0m  ${name}  ${axes}`);
  }

  console.log(`  ${"─".repeat(76)}`);
  console.log(`\x1b[2m  Use 'cc concept <id>' for full details. Web: /concepts\x1b[0m`);
  console.log();
}

/**
 * cc concept <id>
 * Show full details for a concept including edges and related entities.
 */
export async function showConcept(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc concept <id>");
    console.log("       cc concept link <from-id> <rel-type> <to-id>");
    return;
  }

  const [concept, edges, related] = await Promise.all([
    get(`/api/concepts/${encodeURIComponent(id)}`),
    get(`/api/concepts/${encodeURIComponent(id)}/edges`).catch(() => null),
    get(`/api/concepts/${encodeURIComponent(id)}/related`).catch(() => null),
  ]);

  if (!concept || concept.detail) {
    console.log(`Concept '${id}' not found.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  ${concept.name || concept.id}\x1b[0m`);
  console.log(`  \x1b[2m${concept.id}  ·  Level ${concept.level}  ·  ${concept.typeId}\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);

  if (concept.description) {
    console.log(`  ${truncate(concept.description, 72)}`);
    console.log();
  }

  if (concept.axes && concept.axes.length > 0) {
    console.log(`  Axes:         ${concept.axes.map(axisColor).join("  ")}`);
  }
  if (concept.keywords && concept.keywords.length > 0) {
    console.log(`  Keywords:     \x1b[2m${concept.keywords.slice(0, 8).join(", ")}\x1b[0m`);
  }
  if (concept.parentConcepts && concept.parentConcepts.length > 0) {
    console.log(`  Parents:      ${concept.parentConcepts.join(", ")}`);
  }
  if (concept.childConcepts && concept.childConcepts.length > 0) {
    console.log(`  Children:     ${concept.childConcepts.slice(0, 6).join(", ")}${concept.childConcepts.length > 6 ? ` +${concept.childConcepts.length - 6} more` : ""}`);
  }

  // Edges
  if (edges) {
    const total = edges.total ?? 0;
    if (total > 0) {
      console.log();
      console.log(`  \x1b[1mEdges\x1b[0m (${total})`);
      const allEdges = [...(edges.seed_edges || []), ...(edges.user_edges || [])];
      for (const e of allEdges.slice(0, 8)) {
        console.log(`    ${e.from.padEnd(22)}  \x1b[33m${(e.type || "").padEnd(16)}\x1b[0m  ${e.to}`);
      }
      if (allEdges.length > 8) {
        console.log(`    \x1b[2m... and ${allEdges.length - 8} more\x1b[0m`);
      }
    }
  }

  // Related entities
  if (related && related.total > 0) {
    console.log();
    console.log(`  \x1b[1mTagged Entities\x1b[0m (${related.total})`);
    for (const [etype, tags] of Object.entries(related.by_type || {})) {
      const ids = tags.slice(0, 5).map(t => t.entity_id).join(", ");
      const more = tags.length > 5 ? ` +${tags.length - 5} more` : "";
      console.log(`    ${etype.padEnd(8)}  \x1b[2m${ids}${more}\x1b[0m`);
    }
  }

  console.log(`  ${"─".repeat(60)}`);
  console.log(`\x1b[2m  Web: /concepts/${concept.id}\x1b[0m`);
  console.log();
}

/**
 * cc concept link <from-id> <rel-type> <to-id> [--by <contributor>]
 * Create a typed edge between two concepts.
 */
export async function linkConcepts(args) {
  const [fromId, relType, toId, ...rest] = args;

  if (!fromId || !relType || !toId) {
    console.log("Usage: cc concept link <from-id> <rel-type> <to-id>");
    console.log();
    console.log("  Relationship types: parent_of, child_of, related_to, contrasts_with,");
    console.log("                      instantiates, transforms_into, requires, enables");
    return;
  }

  let createdBy = "cli-user";
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === "--by" && rest[i + 1]) {
      createdBy = rest[++i];
    }
  }

  const result = await post(`/api/concepts/${encodeURIComponent(fromId)}/edges`, {
    to_id: toId,
    relationship_type: relType,
    created_by: createdBy,
  });

  if (!result || result.detail) {
    console.log(`Failed to create edge: ${result?.detail ?? "unknown error"}`);
    return;
  }

  console.log();
  console.log(`\x1b[32m✓\x1b[0m Edge created`);
  console.log(`  \x1b[33m${fromId}\x1b[0m  —[${relType}]→  \x1b[33m${toId}\x1b[0m`);
  console.log(`  ID: ${result.id}  ·  Created by: ${result.created_by}`);
  console.log();
}

/**
 * cc concept tag <concept-id> <entity-type> <entity-id> [--by <contributor>]
 * Tag an idea, spec, or news item with a concept.
 */
export async function tagEntity(args) {
  const [conceptId, entityType, entityId, ...rest] = args;

  if (!conceptId || !entityType || !entityId) {
    console.log("Usage: cc concept tag <concept-id> <entity-type> <entity-id>");
    console.log("  entity-type: idea | spec | news | task");
    return;
  }

  let taggedBy = "cli-user";
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === "--by" && rest[i + 1]) {
      taggedBy = rest[++i];
    }
  }

  const result = await post(`/api/concepts/${encodeURIComponent(conceptId)}/tags`, {
    entity_type: entityType,
    entity_id: entityId,
    tagged_by: taggedBy,
  });

  if (!result || result.detail) {
    console.log(`Failed to tag entity: ${result?.detail ?? "unknown error"}`);
    return;
  }

  console.log();
  console.log(`\x1b[32m✓\x1b[0m Tagged: \x1b[33m${entityType}/${entityId}\x1b[0m with concept \x1b[35m${conceptId}\x1b[0m`);
  console.log(`  Tag ID: ${result.id}`);
  console.log();
}

/**
 * cc concept stats
 * Show ontology statistics.
 */
export async function conceptStats() {
  const data = await get("/api/concepts/stats");
  if (!data) {
    console.log("Could not fetch concept stats.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  ONTOLOGY STATS\x1b[0m`);
  console.log(`  ${"─".repeat(40)}`);
  console.log(`  Seed concepts:       ${data.seed_concepts ?? data.concepts ?? "?"}`);
  console.log(`  Custom concepts:     ${data.custom_concepts ?? 0}`);
  console.log(`  Relationship types:  ${data.relationship_types ?? "?"}`);
  console.log(`  Axes:                ${data.axes ?? "?"}`);
  console.log(`  User edges:          ${data.user_edges ?? 0}`);
  console.log(`  Entity tags:         ${data.entity_tags ?? 0}`);
  console.log(`  ${"─".repeat(40)}`);
  console.log(`\x1b[2m  Web: /concepts  ·  API: /api/concepts/stats\x1b[0m`);
  console.log();
}

/**
 * Dispatcher for the 'concept' command.
 * cc concept <subcommand> [args...]
 */
export async function handleConcept(args) {
  const [sub, ...rest] = args;

  switch (sub) {
    case "link":
      return linkConcepts(rest);
    case "tag":
      return tagEntity(rest);
    case "stats":
      return conceptStats();
    default:
      // Treat first arg as concept ID
      if (sub) return showConcept([sub, ...rest]);
      console.log("Usage: cc concept <id>");
      console.log("       cc concept link <from> <rel-type> <to>");
      console.log("       cc concept tag <concept-id> <entity-type> <entity-id>");
      console.log("       cc concept stats");
  }
}
