/**
 * Edge navigation commands — browse the graph through 46 typed relationships.
 *
 * Commands:
 *   cc edges <entity-id> [--type <type>] [--direction both|outgoing|incoming]
 *   cc edge create <from-id> <type> <to-id> [--strength 0.9]
 *   cc edge delete <edge-id>
 *   cc edge types
 */

import { get, post, del } from "../api.mjs";

// Family colour codes (ANSI 256-colour approximations)
const FAMILY_COLORS = {
  ontological: "\x1b[35m",   // magenta
  process:     "\x1b[33m",   // yellow
  knowledge:   "\x1b[34m",   // blue
  scale:       "\x1b[36m",   // cyan
  temporal:    "\x1b[32m",   // green
  tension:     "\x1b[31m",   // red
  attribution: "\x1b[37m",   // white
};
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";

function colorForFamily(familySlug) {
  return FAMILY_COLORS[familySlug] || "\x1b[0m";
}

function parseArgs(args) {
  const opts = { type: null, direction: "both", strength: null };
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--type" && args[i + 1]) {
      opts.type = args[++i];
    } else if (args[i] === "--direction" && args[i + 1]) {
      opts.direction = args[++i];
    } else if (args[i] === "--strength" && args[i + 1]) {
      opts.strength = parseFloat(args[++i]);
    } else {
      positional.push(args[i]);
    }
  }
  return { opts, positional };
}

/** cc edges <entity-id> [--type X] [--direction both|outgoing|incoming] */
export async function listEntityEdges(args) {
  const { opts, positional } = parseArgs(args);
  const entityId = positional[0];
  if (!entityId) {
    console.error("Usage: cc edges <entity-id> [--type <type>] [--direction both|outgoing|incoming]");
    process.exit(1);
  }

  const params = { direction: opts.direction };
  if (opts.type) params.type = opts.type;

  let data;
  try {
    data = await get(`/api/entities/${encodeURIComponent(entityId)}/edges`, params);
  } catch (err) {
    if (err.status === 404) {
      console.error(`Entity not found: ${entityId}`);
      process.exit(1);
    }
    throw err;
  }

  const items = data?.items ?? [];
  if (items.length === 0) {
    console.log(`\n  No edges found for entity: ${entityId}\n`);
    return;
  }

  // Group by type
  const grouped = {};
  for (const edge of items) {
    if (!grouped[edge.type]) grouped[edge.type] = [];
    grouped[edge.type].push(edge);
  }

  console.log(`\n${BOLD}  EDGES for ${entityId}${RESET} (${items.length} total)\n`);

  for (const [type, typeEdges] of Object.entries(grouped)) {
    const isCanonical = typeEdges[0]?.canonical;
    const label = isCanonical ? type : `${type} ${DIM}(custom)${RESET}`;
    console.log(`  ${BOLD}${label}${RESET}`);
    for (const edge of typeEdges) {
      const fromName = edge.from_node?.name ?? edge.from_id;
      const toName = edge.to_node?.name ?? edge.to_id;
      const dir = edge.from_id === entityId ? "→" : "←";
      const peer = edge.from_id === entityId
        ? `${DIM}${edge.to_id}${RESET} (${toName})`
        : `${DIM}${edge.from_id}${RESET} (${fromName})`;
      const strength = edge.strength != null ? ` [${edge.strength.toFixed(2)}]` : "";
      console.log(`    ${dir} ${peer}${DIM}${strength}${RESET}`);
    }
    console.log();
  }
}

/** cc edge types */
export async function listEdgeTypes() {
  const data = await get("/api/edges/types");
  const families = data?.families ?? [];

  console.log(`\n${BOLD}  EDGE TYPES${RESET} (${data.total ?? 0} canonical)\n`);

  for (const family of families) {
    const color = colorForFamily(family.slug);
    console.log(`  ${color}${BOLD}${family.name}${RESET}`);
    for (const t of family.types) {
      const slug = t.slug.padEnd(24);
      console.log(`    ${color}${slug}${RESET}  ${DIM}${t.description}${RESET}`);
    }
    console.log();
  }
}

/** cc edge create <from-id> <type> <to-id> [--strength 0.9] */
export async function createEdge(args) {
  const { opts, positional } = parseArgs(args);
  const [fromId, type, toId] = positional;

  if (!fromId || !type || !toId) {
    console.error("Usage: cc edge create <from-id> <type> <to-id> [--strength 0.9]");
    process.exit(1);
  }

  const body = { from_id: fromId, to_id: toId, type };
  if (opts.strength !== null) body.strength = opts.strength;

  let result;
  try {
    result = await post("/api/edges", body);
  } catch (err) {
    if (err.status === 409) {
      console.error(`Edge already exists: ${fromId} --[${type}]--> ${toId}`);
      process.exit(1);
    }
    if (err.status === 404) {
      console.error(`Node not found — check that both entities exist.`);
      process.exit(1);
    }
    if (err.status === 400) {
      console.error(`Unknown edge type '${type}'. Run 'cc edge types' to see valid types.`);
      process.exit(1);
    }
    throw err;
  }

  if (!result.canonical) {
    console.warn(`\x1b[33mWarning: '${type}' is not a canonical edge type.\x1b[0m`);
  }

  console.log(JSON.stringify(result, null, 2));
}

/** cc edge delete <edge-id> */
export async function deleteEdge(args) {
  const edgeId = args[0];
  if (!edgeId) {
    console.error("Usage: cc edge delete <edge-id>");
    process.exit(1);
  }

  let result;
  try {
    result = await del(`/api/edges/${encodeURIComponent(edgeId)}`);
  } catch (err) {
    if (err.status === 404) {
      console.error(`Edge not found: ${edgeId}`);
      process.exit(1);
    }
    throw err;
  }

  console.log(`Deleted edge: ${result.deleted}`);
}
