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

export function getContributorId() {
  return (
    loadConfig().contributor_id ||
    process.env.COHERENCE_CONTRIBUTOR ||
    null
  );
}

export function getHubUrl() {
  // Env vars override config file (allows easy local dev testing)
  return (
    process.env.COHERENCE_HUB_URL ||
    process.env.COHERENCE_API_URL ||
    loadConfig().hub_url ||
    DEFAULT_HUB_URL
  );
}
