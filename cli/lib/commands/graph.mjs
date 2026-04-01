/**
 * Graph commands: graph nodes, graph edges, graph neighbors
 */

import { get, post } from "../api.mjs";

/** List graph nodes with optional filtering */
export async function listGraphNodes(args) {
  const params = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--type" && args[i + 1]) params.type = args[++i];
    else if (args[i] === "--filter" && args[i + 1]) params.filter = args[++i];
    else if (args[i] === "--limit" && args[i + 1]) params.limit = parseInt(args[++i]) || 50;
  }

  const nodes = await get("/api/graph/nodes", params);
  if (!nodes) return;

  const data = Array.isArray(nodes) ? nodes : (nodes?.items || nodes?.nodes);
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch graph nodes.");
    return;
  }
  if (data.length === 0) {
    console.log("No graph nodes found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  GRAPH NODES\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const n of data) {
    const name = (n.name || n.id || "").slice(0, 40).padEnd(42);
    const type = (n.type || "?").padEnd(16);
    console.log(`  ${name} ${type}`);
  }
  console.log();
}

/** Create a graph node */
export async function createGraphNode(args) {
  let type = "idea";
  let name = `node-${Date.now()}`;
  let description = "";
  let properties = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--type" && args[i + 1]) type = args[++i];
    else if (args[i] === "--name" && args[i + 1]) name = args[++i];
    else if (args[i] === "--desc" && args[i + 1]) description = args[++i];
    else if (args[i] === "--payload" && args[i + 1]) {
      try { properties = JSON.parse(args[++i]); }
      catch { console.error("Invalid JSON payload"); return; }
    }
  }

  const body = {
    id: `${crypto.randomUUID()}`,
    type,
    name,
    description,
    properties,
    phase: "water",
  };

  const result = await post("/api/graph/nodes", body);
  if (!result) return;

  console.log(`\x1b[1m  CREATED NODE\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  ID:    ${result.id}`);
  console.log(`  Type:  ${result.type}`);
  console.log(`  Name:  ${result.name}`);
  console.log(`  Phase: ${result.phase}`);
  console.log();
}

/** List graph edges with optional filtering */
export async function listGraphEdges(args) {
  const params = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--type" && args[i + 1]) params.type = args[++i];
    else if (args[i] === "--from-id" && args[i + 1]) params.from_id = args[++i];
    else if (args[i] === "--to-id" && args[i + 1]) params.to_id = args[++i];
    else if (args[i] === "--limit" && args[i + 1]) params.limit = parseInt(args[++i]) || 50;
  }

  const edges = await get("/api/graph/edges", params);
  if (!edges) return;

  const data = Array.isArray(edges) ? edges : (edges?.items || edges?.edges);
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch graph edges.");
    return;
  }
  if (data.length === 0) {
    console.log("No graph edges found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  GRAPH EDGES\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const e of data) {
    const from = (e.from_id || "").slice(0, 12).padEnd(14);
    const type = (e.type || "?").padEnd(16);
    const to = (e.to_id || "").slice(0, 12);
    console.log(`  ${from} ${type} → ${to}`);
  }
  console.log();
}

/** Create a graph edge */
export async function createGraphEdge(args) {
  let fromId = null;
  let toId = null;
  let type = "depends-on";
  let strength = 1.0;
  let properties = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--from-id" && args[i + 1]) fromId = args[++i];
    else if (args[i] === "--to-id" && args[i + 1]) toId = args[++i];
    else if (args[i] === "--type" && args[i + 1]) type = args[++i];
    else if (args[i] === "--strength" && args[i + 1]) strength = parseFloat(args[++i]) || 1.0;
    else if (args[i] === "--payload" && args[i + 1]) {
      try { properties = JSON.parse(args[++i]); }
      catch { console.error("Invalid JSON payload"); return; }
    }
  }

  if (!fromId || !toId) {
    console.log("Usage: cc graph edges create --from-id <id> --to-id <id> [--type <type>]");
    return;
  }

  const body = {
    id: `${crypto.randomUUID()}`,
    from_id: fromId,
    to_id: toId,
    type,
    strength,
    properties,
    created_by: "cli",
  };

  const result = await post("/api/graph/edges", body);
  if (!result) return;

  console.log(`\x1b[1m  CREATED EDGE\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  ID:       ${result.id}`);
  console.log(`  Type:     ${result.type}`);
  console.log(`  From:     ${result.from_id}`);
  console.log(`  To:       ${result.to_id}`);
  console.log(`  Strength: ${result.strength}`);
  console.log();
}

/** Get neighbors of a node */
export async function getGraphNeighbors(args) {
  let nodeId = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--node-id" && args[i + 1]) nodeId = args[++i];
  }
  if (!nodeId) {
    console.log("Usage: cc graph neighbors --node-id <id>");
    return;
  }

  const data = await get(`/api/graph/nodes/${nodeId}/neighbors`);
  if (!data) return;

  const neighbors = Array.isArray(data) ? data : (data?.neighbors || []);
  if (neighbors.length === 0) {
    console.log(`No neighbors found for node ${nodeId}.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  NEIGHBORS OF ${nodeId}\x1b[0m (${neighbors.length})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const n of neighbors) {
    const name = (n.name || n.node?.name || "").slice(0, 30).padEnd(32);
    const type = (n.type || n.node?.type || "?").padEnd(12);
    const rel = (n.via_edge_type || n.edge?.type || "?").padEnd(16);
    const dir = n.via_direction || n.edge?.direction || "";
    console.log(`  ${name} ${type} ${rel} ${dir}`);
  }
  console.log();
}
