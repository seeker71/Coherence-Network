/**
 * cc workspace — workspace (tenant) CRUD.
 *
 * Workspaces own their own ideas, specs, pillars, and agent personas.
 * Every idea/spec belongs to exactly one workspace.
 * Default workspace: 'coherence-network'.
 */

import { get, post } from "../api.mjs";
import {
  getActiveWorkspace,
  getActiveWorkspaceSource,
  setConfigValue,
  unsetConfigValue,
  DEFAULT_WORKSPACE_ID,
} from "../config.mjs";

function printWorkspace(ws) {
  if (!ws) return;
  console.log(`\x1b[1m${ws.name}\x1b[0m  \x1b[2m(${ws.id})\x1b[0m`);
  if (ws.description) console.log(`  ${ws.description}`);
  if (Array.isArray(ws.pillars) && ws.pillars.length) {
    console.log(`  pillars: ${ws.pillars.join(", ")}`);
  }
  console.log(`  visibility: ${ws.visibility || "public"}`);
  if (ws.owner_contributor_id) console.log(`  owner: ${ws.owner_contributor_id}`);
  if (ws.bundle_path) console.log(`  bundle: ${ws.bundle_path}`);
}

export async function listWorkspaces() {
  const items = await get("/api/workspaces");
  if (!Array.isArray(items) || items.length === 0) {
    console.log("No workspaces.");
    return;
  }
  console.log(`\x1b[1mWorkspaces\x1b[0m  \x1b[2m(${items.length})\x1b[0m`);
  console.log("");
  for (const ws of items) {
    printWorkspace(ws);
    console.log("");
  }
}

export async function showWorkspace(args) {
  const id = args[0];
  if (!id) {
    console.error("Usage: cc workspace show <workspace_id>");
    process.exit(1);
  }
  const ws = await get(`/api/workspaces/${encodeURIComponent(id)}`);
  if (!ws) {
    console.error(`Workspace '${id}' not found.`);
    process.exit(1);
  }
  printWorkspace(ws);
}

export async function createWorkspace(args) {
  // Usage: cc workspace create <id> <name> [--desc "..."] [--pillars "a,b,c"] [--visibility public]
  const id = args[0];
  const name = args[1];
  if (!id || !name) {
    console.error("Usage: cc workspace create <id> <name> [--desc \"...\"] [--pillars \"a,b,c\"] [--visibility public]");
    process.exit(1);
  }
  let description = "";
  let pillars = [];
  let visibility = "public";
  for (let i = 2; i < args.length; i++) {
    if (args[i] === "--desc" && i + 1 < args.length) { description = args[++i]; continue; }
    if (args[i] === "--pillars" && i + 1 < args.length) {
      pillars = args[++i].split(",").map(s => s.trim()).filter(Boolean);
      continue;
    }
    if (args[i] === "--visibility" && i + 1 < args.length) { visibility = args[++i]; continue; }
  }
  const created = await post("/api/workspaces", { id, name, description, pillars, visibility });
  if (!created) {
    console.error(`Failed to create workspace '${id}' (may already exist).`);
    process.exit(1);
  }
  console.log(`\x1b[32m✓\x1b[0m Created workspace:`);
  printWorkspace(created);
}

export async function showWorkspacePillars(args) {
  const id = args[0] || "coherence-network";
  const pillars = await get(`/api/workspaces/${encodeURIComponent(id)}/pillars`);
  if (!Array.isArray(pillars)) {
    console.error(`Workspace '${id}' not found or has no pillars.`);
    process.exit(1);
  }
  console.log(`\x1b[1mPillars for '${id}'\x1b[0m  \x1b[2m(${pillars.length})\x1b[0m`);
  for (const p of pillars) console.log(`  • ${p}`);
}

export function useWorkspace(args) {
  const id = args[0];
  if (!id) {
    console.error("Usage: cc workspace use <workspace_id>");
    console.error("       cc workspace use --clear");
    process.exit(1);
  }
  if (id === "--clear" || id === "default") {
    unsetConfigValue("workspace");
    console.log(`\x1b[32m✓\x1b[0m Cleared workspace pref (now using default '${DEFAULT_WORKSPACE_ID}').`);
    return;
  }
  setConfigValue("workspace", id);
  console.log(`\x1b[32m✓\x1b[0m Active workspace set to '\x1b[1m${id}\x1b[0m' (persisted in config.json).`);
}

export function currentWorkspace() {
  const id = getActiveWorkspace();
  const src = getActiveWorkspaceSource();
  console.log(`\x1b[1m${id}\x1b[0m  \x1b[2m(source: ${src})\x1b[0m`);
}

export async function handleWorkspace(args) {
  const sub = args[0];
  switch (sub) {
    case "list":    return listWorkspaces();
    case "show":    return showWorkspace(args.slice(1));
    case "create":  return createWorkspace(args.slice(1));
    case "pillars": return showWorkspacePillars(args.slice(1));
    case "use":     return useWorkspace(args.slice(1));
    case "current": return currentWorkspace();
    default:
      if (!sub) return listWorkspaces();
      // cc workspace <id> → show
      return showWorkspace(args);
  }
}
