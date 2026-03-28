/**
 * Edge navigation — browse typed graph relationships (Living Codex + operational edges).
 */

import { get } from "../api.mjs";

function printEdgeRow(e) {
  const dir = e.edge_direction || "?";
  const peer = e.peer?.name || e.peer_id;
  const ptype = e.peer?.type || "?";
  console.log(
    `  \x1b[36m${(e.type || "").padEnd(22)}\x1b[0m ${dir.padEnd(10)} → \x1b[1m${peer}\x1b[0m (\x1b[2m${ptype}\x1b[0m) \x1b[2m${e.peer_id}\x1b[0m`,
  );
}

/** @param {string[]} args */
export async function showEdges(args) {
  const sub = args[0];

  if (!sub || sub === "help" || sub === "-h" || sub === "--help") {
    console.log(`
\x1b[1mcc edg\x1b[0m — browse graph edges by entity or list types

  \x1b[1mcc edg types\x1b[0m              List 46 Living Codex relationship types
  \x1b[1mcc edg list [limit]\x1b[0m       Recent edges (default limit 20)
  \x1b[1mcc edg <entity_id> [type]\x1b[0m  Edges for an entity; optional type filter (e.g. resonates-with)
`);
    return;
  }

  if (sub === "types") {
    const data = await get("/api/edges/types");
    if (!data?.items) {
      console.log("Could not load relationship types.");
      return;
    }
    console.log();
    console.log("\x1b[1m  RELATIONSHIP TYPES\x1b[0m (" + (data.total || data.items.length) + ")");
    console.log(`  ${"─".repeat(60)}`);
    for (const t of data.items) {
      const line = `  \x1b[36m${t.id}\x1b[0m — ${t.name || ""}`;
      console.log(line);
      if (t.description) console.log(`      \x1b[2m${t.description.slice(0, 120)}${t.description.length > 120 ? "…" : ""}\x1b[0m`);
    }
    console.log();
    return;
  }

  if (sub === "list") {
    const limit = Math.min(parseInt(args[1], 10) || 20, 500);
    const data = await get(`/api/edges?limit=${limit}`);
    if (!data?.items) {
      console.log("Could not list edges.");
      return;
    }
    console.log();
    console.log(`\x1b[1m  EDGES\x1b[0m (showing ${data.items.length} of ${data.total})`);
    console.log(`  ${"─".repeat(60)}`);
    for (const e of data.items) {
      console.log(
        `  \x1b[33m${e.id}\x1b[0m  ${e.from_id} \x1b[2m—${e.type}→\x1b[0m ${e.to_id}`,
      );
    }
    console.log();
    return;
  }

  const entityId = sub;
  const typeFilter = args[1] || "";
  let path = `/api/entities/${encodeURIComponent(entityId)}/edges`;
  if (typeFilter) path += `?type=${encodeURIComponent(typeFilter)}`;

  const edges = await get(path);
  if (edges == null) {
    console.log("Could not load entity edges (not found or network error).");
    return;
  }
  if (!Array.isArray(edges)) {
    console.log("Unexpected response.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  ENTITY EDGES\x1b[0m  \x1b[2m${entityId}${typeFilter ? `  [type=${typeFilter}]` : ""}\x1b[0m`);
  console.log(`  ${"─".repeat(60)}`);
  if (edges.length === 0) {
    console.log("  (no edges)");
  } else {
    for (const e of edges) printEdgeRow(e);
  }
  console.log();
}
