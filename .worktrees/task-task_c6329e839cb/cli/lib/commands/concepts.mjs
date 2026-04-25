/**
 * Concept commands — browse and extend the Living Codex ontology (184 concepts, 46 rel types, 53 axes).
 *
 * Commands:
 *   coh concepts [--limit N] [--search <query>]
 *   coh concept <id>
 *   coh concept link <from-id> <rel-type> <to-id> [--by <author>]
 */

import { get, post } from "../api.mjs";

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const MAGENTA = "\x1b[35m";
const RED = "\x1b[31m";
const BLUE = "\x1b[34m";

const LEVEL_COLORS = {
  0: MAGENTA,   // Core
  1: BLUE,      // Primary
  2: CYAN,      // Secondary
  3: GREEN,     // Derived
};
const LEVEL_LABELS = { 0: "Core", 1: "Primary", 2: "Secondary", 3: "Derived" };

function levelTag(level) {
  const color = LEVEL_COLORS[level ?? 0] || DIM;
  const label = LEVEL_LABELS[level ?? 0] || `L${level}`;
  return `${color}[${label}]${RESET}`;
}

function parseArgs(args) {
  const opts = { limit: 50, search: null, by: "cli" };
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--limit" || args[i] === "-n") && args[i + 1]) {
      opts.limit = parseInt(args[++i], 10);
    } else if ((args[i] === "--search" || args[i] === "-q") && args[i + 1]) {
      opts.search = args[++i];
    } else if (args[i] === "--by" && args[i + 1]) {
      opts.by = args[++i];
    } else {
      positional.push(args[i]);
    }
  }
  return { opts, positional };
}

/** coh concepts [--limit N] [--search <query>] */
export async function listConcepts(args) {
  const { opts } = parseArgs(args);

  let data;
  if (opts.search) {
    data = await get("/api/concepts/search", { q: opts.search, limit: opts.limit });
    if (!data) {
      console.error(`${RED}Error:${RESET} could not reach API or no results.`);
      process.exit(1);
    }
    // search returns an array directly
    const items = Array.isArray(data) ? data : [];
    console.log(`\n${BOLD}Concept Search: "${opts.search}"${RESET}  (${items.length} result${items.length === 1 ? "" : "s"})\n`);
    for (const c of items) {
      const tag = levelTag(c.level);
      const axes = (c.axes || []).slice(0, 3).map(a => `${DIM}${a}${RESET}`).join(", ");
      console.log(`  ${BOLD}${c.id}${RESET}  ${tag}`);
      console.log(`    ${c.name}  ${axes ? "· " + axes : ""}`);
      if (c.description) {
        const snippet = c.description.length > 80 ? c.description.slice(0, 77) + "…" : c.description;
        console.log(`    ${DIM}${snippet}${RESET}`);
      }
      console.log();
    }
    return;
  }

  // paged list
  data = await get("/api/concepts", { limit: opts.limit, offset: 0 });
  if (!data) {
    console.error(`${RED}Error:${RESET} could not reach API.`);
    process.exit(1);
  }

  const items = data.items || [];
  const total = data.total || items.length;
  const stats = await get("/api/concepts/stats");

  console.log(`\n${BOLD}Concepts${RESET}  ${DIM}(${items.length} of ${total})${RESET}`);
  if (stats) {
    console.log(`${DIM}  ${stats.concepts} concepts · ${stats.relationship_types} rel-types · ${stats.axes} axes · ${stats.user_edges} user-edges${RESET}`);
  }
  console.log();

  for (const c of items) {
    const tag = levelTag(c.level);
    const axes = (c.axes || []).slice(0, 3).map(a => `${DIM}${a}${RESET}`).join(" ");
    console.log(`  ${BOLD}${c.id}${RESET}  ${tag}  ${CYAN}${c.name}${RESET}`);
    if (axes) console.log(`    ${axes}`);
  }

  if (total > opts.limit) {
    console.log(`\n${DIM}  … and ${total - opts.limit} more. Use --limit ${total} to see all.${RESET}`);
  }
  console.log();
}

/** coh concept <id> */
export async function showConcept(args) {
  const { positional } = parseArgs(args);
  const id = positional[0];
  if (!id) {
    console.error("Usage: coh concept <id>");
    process.exit(1);
  }

  const [concept, edges, related] = await Promise.all([
    get(`/api/concepts/${id}`),
    get(`/api/concepts/${id}/edges`),
    get(`/api/concepts/${id}/related`),
  ]);

  if (!concept) {
    console.error(`${RED}Not found:${RESET} concept '${id}'`);
    process.exit(1);
  }

  console.log(`\n${BOLD}${concept.name}${RESET}  ${levelTag(concept.level)}`);
  console.log(`  ${DIM}id: ${concept.id}${RESET}`);
  if (concept.typeId) console.log(`  ${DIM}type: ${concept.typeId}${RESET}`);
  if (concept.userDefined) console.log(`  ${YELLOW}[user-defined]${RESET}`);
  console.log();

  if (concept.description) {
    console.log(`  ${concept.description}`);
    console.log();
  }

  if (concept.keywords && concept.keywords.length > 0) {
    console.log(`  ${BOLD}Keywords:${RESET}  ${concept.keywords.map(k => `${DIM}${k}${RESET}`).join(", ")}`);
  }

  if (concept.axes && concept.axes.length > 0) {
    console.log(`  ${BOLD}Axes:${RESET}     ${concept.axes.map(a => `${CYAN}${a}${RESET}`).join("  ")}`);
  }

  if (concept.parentConcepts && concept.parentConcepts.length > 0) {
    console.log(`  ${BOLD}Parents:${RESET}  ${concept.parentConcepts.join(", ")}`);
  }

  if (concept.childConcepts && concept.childConcepts.length > 0) {
    console.log(`  ${BOLD}Children:${RESET} ${concept.childConcepts.join(", ")}`);
  }

  if (edges && edges.length > 0) {
    console.log(`\n  ${BOLD}Edges (${edges.length}):${RESET}`);
    const outgoing = edges.filter(e => e.from === id);
    const incoming = edges.filter(e => e.to === id);
    for (const e of outgoing) {
      console.log(`    ${GREEN}→${RESET}  ${MAGENTA}${e.type}${RESET}  ${BOLD}${e.to}${RESET}`);
    }
    for (const e of incoming) {
      console.log(`    ${YELLOW}←${RESET}  ${MAGENTA}${e.type}${RESET}  ${BOLD}${e.from}${RESET}`);
    }
  }

  if (related && related.total > 0) {
    console.log(`\n  ${BOLD}Tagged in:${RESET}  ${related.ideas.length} ideas, ${related.specs.length} specs`);
  }

  console.log();
}

/** coh concept link <from-id> <rel-type> <to-id> [--by <author>] */
export async function linkConcepts(args) {
  const { opts, positional } = parseArgs(args);
  const [fromId, relType, toId] = positional;

  if (!fromId || !relType || !toId) {
    console.error("Usage: coh concept link <from-id> <rel-type> <to-id> [--by <author>]");
    console.error("Example: coh concept link activity transforms knowledge");
    process.exit(1);
  }

  const result = await post(`/api/concepts/${fromId}/edges`, {
    from_id: fromId,
    to_id: toId,
    relationship_type: relType,
    created_by: opts.by,
  });

  if (!result) {
    console.error(`${RED}Error:${RESET} failed to create edge. Check that both concepts exist.`);
    process.exit(1);
  }

  console.log(`\n${GREEN}Edge created${RESET}`);
  console.log(`  ${BOLD}${fromId}${RESET}  ${MAGENTA}—[${relType}]→${RESET}  ${BOLD}${toId}${RESET}`);
  console.log(`  ${DIM}id: ${result.id}  by: ${result.created_by || opts.by}${RESET}`);
  console.log();
}
