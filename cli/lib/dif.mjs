/**
 * DIF (Deep Inspection Framework) integration — config-file driven.
 *
 * Config:  ~/.coherence-network/config.json  → dif.base_url, dif.response_mode, etc.
 * Secrets: ~/.coherence-network/keys.json    → dif.api_key, dif.key_id
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const CONFIG_DIR = join(homedir(), ".coherence-network");
const CONFIG_PATH = join(CONFIG_DIR, "config.json");
const KEYS_PATH = join(CONFIG_DIR, "keys.json");

const DIF_DEFAULTS = {
  base_url: "https://coherency-network.merly-mentor.ai",
  response_mode: "script",
  sensitivity: 0,
  selected_key_id: "",
  selected_key_preview: "",
};

// ── Config helpers ──────────────────────────────────────────────────

function _readJson(path) {
  try { return JSON.parse(readFileSync(path, "utf-8")); }
  catch { return {}; }
}

function _writeJson(path, data) {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(path, JSON.stringify(data, null, 2) + "\n", { mode: 0o600 });
}

export function getDifConfig() {
  const cfg = _readJson(CONFIG_PATH);
  return { ...DIF_DEFAULTS, ...(cfg.dif || {}) };
}

export function setDifConfig(patch) {
  const cfg = _readJson(CONFIG_PATH);
  cfg.dif = { ...(cfg.dif || {}), ...patch };
  _writeJson(CONFIG_PATH, cfg);
  return cfg.dif;
}

export function getDifKey() {
  const keys = _readJson(KEYS_PATH);
  return keys.dif || {};
}

export function setDifKey(patch) {
  const keys = _readJson(KEYS_PATH);
  keys.dif = { ...(keys.dif || {}), ...patch };
  _writeJson(KEYS_PATH, keys);
  return keys.dif;
}

// ── HTTP helper ─────────────────────────────────────────────────────

const TIMEOUT_MS = 30_000;

export async function difFetch(method, path, body, opts = {}) {
  const cfg = getDifConfig();
  const key = getDifKey();
  const url = `${cfg.base_url}${path}`;

  const headers = { "Content-Type": "application/json" };
  if (opts.apiKey) {
    headers["X-API-Key"] = opts.apiKey;
  } else if (key.api_key) {
    headers["X-API-Key"] = key.api_key;
  }

  const fetchOpts = { method, headers, signal: AbortSignal.timeout(TIMEOUT_MS) };
  if (body && method !== "GET") fetchOpts.body = JSON.stringify(body);

  const start = Date.now();
  const resp = await fetch(url, fetchOpts);
  const latency = Date.now() - start;

  let data;
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("json")) {
    data = await resp.json();
  } else {
    data = await resp.text();
  }

  return { status: resp.status, data, latency, headers: resp.headers };
}

// ── Verify helper ───────────────────────────────────────────────────

export async function difVerify(language, code, opts = {}) {
  const cfg = getDifConfig();
  const payload = {
    language,
    response_mode: opts.responseMode || cfg.response_mode || "script",
    sensitivity: opts.sensitivity ?? cfg.sensitivity ?? 0,
    code,
  };
  return difFetch("POST", "/api/v2/dif/verify", payload);
}
