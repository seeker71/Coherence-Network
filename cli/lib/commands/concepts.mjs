/**
 * Concepts commands — Living Codex ontology CRUD and navigation.
 *
 *   cc concepts                         — list all concepts (paginated)
 *   cc concepts search <query>          — search concepts by name/description
 *   cc concepts stats                   — show ontology statistics
 *   cc concepts relationships           — list all 46 relationship types
 *   cc concepts axes                    — list all 53 ontology axes
 *   cc concept <id>                     — get a single concept by ID
 *   cc concept <id> edges               — show edges for a concept
 *   cc concept link <from> <rel> <to>   — create a typed edge between concepts
 */

import { get, post } from "../api.mjs";

const R = "\x1b[31m";
const G = "\x1b[32m";
const Y = "\x1b[33m";
const C = "\x1b[36m";
const B = "\x1b[1m";
const D = "\x1b[2m";
const X = "\x1b[0m";

const levelLabels = { 0: "Root", 1: "Foundational", 2: "Core", 3: "Applied" };

export async function listConcepts(args) {
  const sub = args[0];
  if (sub === "search") return searchConcepts(args.slice(1));
  if (sub === "stats") return showConceptStats();
  if (sub === "relationships") return listRelationshipTypes();
  if (sub === "axes") return listAxes();

  const offset = !isNaN(parseInt(sub, 10)) ? parseInt(sub, 10) : 0;
  const data = await get("/api/concepts", { limit: 50, offset });
  if (!data || !data.items) {
    console.error(`${R}Failed to load concepts${X}`);
    return;
  }

  const { items, total, limit } = data;
  console.log(`\n${B}Concepts Ontology${X} — Living Codex`);
  console.log(`${D}Showing ${items.length} of ${total} concepts (offset: ${offset})${X}\n`);

  if (items.length === 0) {
    console.log(`${D}No concepts found. Check if the ontology data is loaded.${X}`);
    return;
  }

  const byLevel = {};
  for (const c of items) {
    const lvl = c.level ?? 2;
    if (!byLevel[lvl]) byLevel[lvl] = [];
    byLevel[lvl].push(c);
  }

  for (const lvl of Object.keys(byLevel).sort((a, b) => Number(a) - Number(b))) {
    const concepts = byLevel[lvl];
    console.log(`\n${C}${B}${levelLabels[lvl] ?? "Level " + lvl} (${concepts.length}):${X}`);
    for (const c of concepts) {
      const typeTag = c.typeId ? `${D}[${c.typeId}]${X}` : "";
      const desc = c.description
        ? c.description.length > 55
          ? c.description.slice(0, 52) + "..."
          : c.description
        : "";
      console.log(`  ${B}${c.id.padEnd(24)}${X} ${c.name.padEnd(22)} ${typeTag.padEnd(18)} ${D}${desc}${X}`);
    }
  }

  if (total > limit + offset) {
    const next = offset + limit;
    console.log(`\n${D}Load more: cc concepts ${next}${X}`);
  }
  console.log();
}

export async function searchConcepts(args) {
  const query = args.join(" ");
  if (!query) {
    console.error(`${R}Usage: cc concepts search <query>${X}`);
    return;
  }

  const data = await get("/api/concepts/search", { q: query, limit: 20 });
  if (!data) {
    console.error(`${R}Search failed${X}`);
    return;
  }

  const items = Array.isArray(data) ? data : data.items ?? [];
  console.log(`\n${B}Search:${X} "${query}" — ${items.length} result(s)\n`);

  if (items.length === 0) {
    console.log(`${D}No concepts matched.${X}`);
    return;
  }

  for (const c of items) {
    console.log(`  ${B}${C}${c.id}${X} — ${c.name}`);
    if (c.description) {
      console.log(`    ${D}${c.description}${X}`);
    }
    if (c.keywords?.length) {
      console.log(`    ${D}Keywords: ${c.keywords.join(", ")}${X}`);
    }
    console.log();
  }
}

export async function showConcept(args) {
  const id = args[0];
  if (!id) {
    console.error(`${R}Usage: cc concept <id>${X}`);
    return;
  }

  if (args[1] === "edges") return showConceptEdges(args);
  if (args[0] === "link") return createConceptLink(args.slice(1));

  const concept = await get(`/api/concepts/${id}`);
  if (!concept) {
    console.error(`${R}Concept '${id}' not found${X}`);
    return;
  }

  console.log(`\n${B}${C}${concept.name}${X} ${D}(${concept.id})${X}`);
  console.log(`${D}${"─".repeat(60)}${X}`);
  console.log(`\n${concept.description}\n`);

  if (concept.typeId) console.log(`  ${D}Type:${X}     ${concept.typeId}`);
  if (concept.level !== undefined) {
    console.log(`  ${D}Level:${X}    ${levelLabels[concept.level] ?? concept.level}`);
  }
  if (concept.keywords?.length) {
    console.log(`  ${D}Keywords:${X} ${concept.keywords.join(", ")}`);
  }
  if (concept.axes?.length) {
    console.log(`  ${D}Axes:${X}     ${concept.axes.join(", ")}`);
  }

  console.log();
  console.log(`${D}  To see edges: cc concept ${id} edges${X}`);
  console.log(`${D}  To link:      cc concept link ${id} <relationship> <target-id>${X}`);
  console.log();
}

export async function showConceptEdges(args) {
  const id = args[0];
  if (!id) {
    console.error(`${R}Usage: cc concept <id> edges${X}`);
    return;
  }

  const edges = await get(`/api/concepts/${id}/edges`);
  if (!edges) {
    console.error(`${R}Failed to load edges for '${id}'${X}`);
    return;
  }

  const items = Array.isArray(edges) ? edges : edges.edges ?? [];
  console.log(`\n${B}Edges${X} for concept: ${C}${id}${X}`);
  console.log(`${D}${"─".repeat(50)}${X}`);

  if (items.length === 0) {
    console.log(`${D}\n  No edges yet. Create one: cc concept link ${id} <rel> <target>${X}`);
    return;
  }

  const out = items.filter((e) => e.from === id);
  const inc = items.filter((e) => e.to === id);

  if (out.length > 0) {
    console.log(`\n  ${G}→ Outgoing${X} (${out.length}):`);
    for (const e of out) {
      console.log(`    ${B}${e.type.padEnd(22)}${X} → ${C}${e.to}${X}`);
    }
  }

  if (inc.length > 0) {
    console.log(`\n  ${Y}← Incoming${X} (${inc.length}):`);
    for (const e of inc) {
      console.log(`    ${C}${e.from}${X} ${B}${e.type.padEnd(22)}${X}`);
    }
  }

  console.log();
}

export async function createConceptLink(args) {
  const [from, rel, to] = args;
  if (!from || !rel || !to) {
    console.error(`${R}Usage: cc concept link <from-id> <relationship-type> <to-id>${X}`);
    console.error(`${D}  Example: cc concept link breath resonates-with water${X}`);
    return;
  }

  const result = await post(`/api/concepts/${from}/edges`, {
    from_id: from,
    to_id: to,
    relationship_type: rel,
  });

  if (!result) {
    console.error(`${R}Failed to create edge: ${from} → ${rel} → ${to}${X}`);
    return;
  }

  console.log(`\n${G}✓${X} Edge created: ${C}${from}${X} ${B}${rel}${X} → ${C}${to}${X}`);
  console.log(`${D}  ID: ${result.id}${X}`);
  console.log(`${D}  Created: ${result.created_at}${X}`);
  console.log();
}

export async function showConceptStats() {
  const stats = await get("/api/concepts/stats");
  if (!stats) {
    console.error(`${R}Failed to load stats${X}`);
    return;
  }

  console.log(`\n${B}Concepts Ontology Stats${X}`);
  console.log(`${D}${"─".repeat(40)}${X}`);
  console.log(`  ${D}Concepts:${X}           ${B}${stats.concepts}${X}`);
  console.log(`  ${D}Relationship Types:${X}  ${B}${stats.relationship_types}${X}`);
  console.log(`  ${D}Axes:${X}               ${B}${stats.axes}${X}`);
  console.log(`  ${D}User Edges:${X}         ${B}${stats.user_edges}${X}`);
  console.log();
}

export async function listRelationshipTypes() {
  const data = await get("/api/concepts/relationships");
  if (!data) {
    console.error(`${R}Failed to load relationship types${X}`);
    return;
  }

  const items = Array.isArray(data) ? data : data.relationships ?? [];
  console.log(`\n${B}Relationship Types${X} (${items.length})`);
  console.log(`${D}${"─".repeat(70)}${X}`);

  const byCategory = {};
  for (const r of items) {
    const cat = r.category ?? "other";
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(r);
  }

  for (const [cat, catRels] of Object.entries(byCategory)) {
    console.log(`\n  ${C}${B}${cat}${X}:`);
    for (const r of catRels) {
      const desc = r.description?.length > 45 ? r.description.slice(0, 42) + "..." : (r.description ?? "");
      console.log(`    ${B}${r.id.padEnd(26)}${X} ${r.name.padEnd(22)} ${D}${desc}${X}`);
    }
  }

  console.log();
}

export async function listAxes() {
  const data = await get("/api/concepts/axes");
  if (!data) {
    console.error(`${R}Failed to load axes${X}`);
    return;
  }

  const items = Array.isArray(data) ? data : data.axes ?? [];
  console.log(`\n${B}Ontology Axes${X} (${items.length})`);
  console.log(`${D}${"─".repeat(70)}${X}`);

  for (const a of items) {
    const poles = a.pole_a && a.pole_b ? `${D} [${a.pole_a} ↔ ${a.pole_b}]${X}` : "";
    console.log(`  ${B}${a.id.padEnd(22)}${X} ${a.name.padEnd(24)} ${poles}`);
  }

  console.log();
}
