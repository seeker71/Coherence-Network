/**
 * Config loader — reads/writes ~/.coherence-network/config.json
 * Same file as the Python CLI and API use.
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

export const CONFIG_DIR = join(homedir(), ".coherence-network");
export const CONFIG_FILE = join(CONFIG_DIR, "config.json");

const DEFAULT_HUB_URL = "https://api.coherencycoin.com";

function ensureConfigDir() {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function deepMerge(base, updates) {
  if (!isPlainObject(base) || !isPlainObject(updates)) {
    return updates;
  }
  const merged = { ...base };
  for (const [key, value] of Object.entries(updates)) {
    if (isPlainObject(value) && isPlainObject(merged[key])) {
      merged[key] = deepMerge(merged[key], value);
      continue;
    }
    merged[key] = value;
  }
  return merged;
}

function splitConfigPath(path) {
  return String(path || "")
    .split(".")
    .map((part) => part.trim())
    .filter(Boolean);
}

function cloneConfig(value) {
  return JSON.parse(JSON.stringify(value));
}

export function loadConfig() {
  try {
    const raw = readFileSync(CONFIG_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function saveConfig(updates) {
  const config = deepMerge(loadConfig(), updates);
  ensureConfigDir();
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2) + "\n");
  return config;
}

export function getContributorId() {
  const fromFile = loadConfig().contributor_id;
  if (fromFile && String(fromFile).trim()) return String(fromFile).trim();
  return null;
}

/** Resolution source label for `cc identity` (R4). */
export function getContributorSource() {
  const fromFile = loadConfig().contributor_id;
  if (fromFile && String(fromFile).trim()) return "config.json";
  return "none";
}

/** R2 — contributor_id for `cc identity set` (letters, digits, underscore, period, hyphen; max 64). */
export const CONTRIBUTOR_ID_PATTERN = /^[\w.\-]{1,64}$/;

export function normalizeContributorId(value) {
  return String(value || "").trim();
}

export function parseContributorId(value) {
  const contributorId = normalizeContributorId(value);
  if (!CONTRIBUTOR_ID_PATTERN.test(contributorId)) {
    return null;
  }
  return contributorId;
}

export function getHubUrl() {
  const config = loadConfig();
  return (
    config.hub_url ||
    config.web?.api_base_url ||
    config.agent_providers?.api_base_url ||
    DEFAULT_HUB_URL
  );
}

const KEYS_FILE = join(CONFIG_DIR, "keys.json");
const CONTEXT_FILE = join(CONFIG_DIR, "context.json");

export function loadKeys() {
  try {
    return JSON.parse(readFileSync(KEYS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

export function saveKeys(updates) {
  const keys = { ...loadKeys(), ...updates };
  ensureConfigDir();
  writeFileSync(KEYS_FILE, JSON.stringify(keys, null, 2) + "\n", { mode: 0o600 });
  return keys;
}

export function loadContext() {
  try {
    return JSON.parse(readFileSync(CONTEXT_FILE, "utf-8"));
  } catch {
    return {};
  }
}

export function saveContext(updates) {
  const context = { ...loadContext(), ...updates };
  ensureConfigDir();
  writeFileSync(CONTEXT_FILE, JSON.stringify(context, null, 2) + "\n");
  return context;
}

export function getFocus() {
  const context = loadContext();
  return {
    idea_id: context.focused_idea_id || null,
    task_id: context.focused_task_id || null
  };
}

export function getApiKey() {
  return loadKeys().api_key || loadConfig().auth?.api_key || null;
}

export function getAdminKey() {
  return loadConfig().auth?.admin_key || null;
}

export function getExecuteToken() {
  return loadConfig().agent_executor?.execute_token || null;
}

export function getCliProvider() {
  return loadConfig().cli?.provider || "cli";
}

/**
 * Workspace resolution — persistent default lives in config.json under the
 * top-level `workspace` key (falls back to "coherence-network"). A session
 * override can be set by the `--workspace` flag via setActiveWorkspaceOverride.
 *
 * No environment variables are read or written. All state flows through
 * config.json or an in-process override.
 */
export const DEFAULT_WORKSPACE_ID = "coherence-network";
let _activeWorkspaceOverride = null;

export function setActiveWorkspaceOverride(workspaceId) {
  const id = String(workspaceId || "").trim();
  _activeWorkspaceOverride = id || null;
}

export function getActiveWorkspaceOverride() {
  return _activeWorkspaceOverride;
}

export function getActiveWorkspace() {
  if (_activeWorkspaceOverride) return _activeWorkspaceOverride;
  const fromFile = loadConfig().workspace;
  if (fromFile && String(fromFile).trim()) return String(fromFile).trim();
  return DEFAULT_WORKSPACE_ID;
}

export function getActiveWorkspaceSource() {
  if (_activeWorkspaceOverride) return "--workspace flag";
  const fromFile = loadConfig().workspace;
  if (fromFile && String(fromFile).trim()) return "config.json";
  return "default";
}

export function getCliActiveTaskId() {
  return loadConfig().cli?.active_task_id || null;
}

export function getConfigValue(path) {
  const parts = splitConfigPath(path);
  let current = loadConfig();
  for (const part of parts) {
    if (!isPlainObject(current) || !(part in current)) {
      return undefined;
    }
    current = current[part];
  }
  return current;
}

export function setConfigValue(path, value) {
  const parts = splitConfigPath(path);
  if (!parts.length) {
    throw new Error("Config path is required.");
  }
  const config = cloneConfig(loadConfig());
  let node = config;
  for (const key of parts.slice(0, -1)) {
    if (!isPlainObject(node[key])) {
      node[key] = {};
    }
    node = node[key];
  }
  node[parts.at(-1)] = value;
  ensureConfigDir();
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2) + "\n");
  return config;
}

export function unsetConfigValue(path) {
  const parts = splitConfigPath(path);
  if (!parts.length) {
    throw new Error("Config path is required.");
  }
  const config = cloneConfig(loadConfig());
  let node = config;
  for (const key of parts.slice(0, -1)) {
    if (!isPlainObject(node[key])) {
      return config;
    }
    node = node[key];
  }
  delete node[parts.at(-1)];
  ensureConfigDir();
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2) + "\n");
  return config;
}
