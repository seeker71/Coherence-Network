/**
 * Config loader — reads/writes ~/.coherence-network/config.json
 * Same file as the Python CLI and API use.
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

export const CONFIG_DIR = join(homedir(), ".coherence-network");
const CONFIG_FILE = join(CONFIG_DIR, "config.json");

const DEFAULT_HUB_URL = "https://api.coherencycoin.com";

export function loadConfig() {
  try {
    const raw = readFileSync(CONFIG_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function saveConfig(updates) {
  const config = { ...loadConfig(), ...updates };
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2) + "\n");
  return config;
}

/**
 * R3 precedence (highest first): COHERENCE_CONTRIBUTOR_ID → COHERENCE_CONTRIBUTOR (legacy) → config.json
 */
export function getContributorId() {
  const eid = (process.env.COHERENCE_CONTRIBUTOR_ID || "").trim();
  if (eid) return eid;
  const legacy = (process.env.COHERENCE_CONTRIBUTOR || "").trim();
  if (legacy) return legacy;
  const fromFile = loadConfig().contributor_id;
  if (fromFile && String(fromFile).trim()) return String(fromFile).trim();
  return null;
}

/** Resolution source label for `cc identity` (R4). */
export function getContributorSource() {
  const eid = (process.env.COHERENCE_CONTRIBUTOR_ID || "").trim();
  if (eid) return "env:COHERENCE_CONTRIBUTOR_ID";
  const legacy = (process.env.COHERENCE_CONTRIBUTOR || "").trim();
  if (legacy) return "env:COHERENCE_CONTRIBUTOR (legacy)";
  const fromFile = loadConfig().contributor_id;
  if (fromFile && String(fromFile).trim()) return "config.json";
  return "none";
}

/** R2 — contributor_id for `cc identity set` (letters, digits, underscore, period, hyphen; max 64). */
export const CONTRIBUTOR_ID_PATTERN = /^[\w.\-]{1,64}$/;

export function getHubUrl() {
  // Env vars override config file (allows easy local dev testing)
  return (
    process.env.COHERENCE_HUB_URL ||
    process.env.COHERENCE_API_URL ||
    loadConfig().hub_url ||
    DEFAULT_HUB_URL
  );
}

const KEYS_FILE = join(CONFIG_DIR, "keys.json");

export function loadKeys() {
  try {
    return JSON.parse(readFileSync(KEYS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

export function saveKeys(updates) {
  const keys = { ...loadKeys(), ...updates };
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }
  writeFileSync(KEYS_FILE, JSON.stringify(keys, null, 2) + "\n", { mode: 0o600 });
  return keys;
}

/**
 * Get the personal API key for this contributor from keys.json.
 * Falls back to COHERENCE_API_KEY env var.
 */
export function getApiKey() {
  return (
    process.env.COHERENCE_API_KEY ||
    loadKeys().api_key ||
    null
  );
}
