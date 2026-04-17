/**
 * CLI locale resolution + message lookup.
 *
 * Resolution order for the active CLI locale:
 *   1. --lang flag on argv (highest priority, explicit override)
 *   2. COHERENCE_LOCALE environment variable
 *   3. locale field in ~/.coherence-network/config.json
 *   4. LANG / LC_ALL / LC_MESSAGES env vars (parsed for a supported locale)
 *   5. Default locale (en)
 *
 * Messages live as JSON bundles in cli/lib/messages/{lang}.json so the same
 * text file can travel with the npm package. A missing key falls back to the
 * English bundle; a missing bundle falls back to English. Unknown keys
 * render as the key string itself — gaps stay visible rather than silent.
 */

import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SUPPORTED = new Set(["en", "de", "es", "id"]);
const DEFAULT_LOCALE = "en";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MESSAGES_DIR = join(__dirname, "messages");

const _bundleCache = new Map();

function loadBundle(lang) {
  if (_bundleCache.has(lang)) return _bundleCache.get(lang);
  const path = join(MESSAGES_DIR, `${lang}.json`);
  if (!existsSync(path)) {
    _bundleCache.set(lang, null);
    return null;
  }
  try {
    const data = JSON.parse(readFileSync(path, "utf-8"));
    _bundleCache.set(lang, data);
    return data;
  } catch {
    _bundleCache.set(lang, null);
    return null;
  }
}

function parseLocaleLike(value) {
  if (!value) return null;
  const root = String(value).trim().toLowerCase().split(/[._-]/)[0];
  return SUPPORTED.has(root) ? root : null;
}

function readConfigLocale() {
  const path = join(homedir(), ".coherence-network", "config.json");
  if (!existsSync(path)) return null;
  try {
    const cfg = JSON.parse(readFileSync(path, "utf-8"));
    return parseLocaleLike(cfg?.locale ?? cfg?.cli?.locale);
  } catch {
    return null;
  }
}

/** Extract --lang value from argv without mutating it. Returns null if absent. */
function argvLocale(argv) {
  if (!Array.isArray(argv)) return null;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--lang" && i + 1 < argv.length) return parseLocaleLike(argv[i + 1]);
    if (argv[i] && typeof argv[i] === "string" && argv[i].startsWith("--lang=")) {
      return parseLocaleLike(argv[i].slice(7));
    }
  }
  return null;
}

/** Resolve the active CLI locale via the priority chain. */
export function resolveLocale(argv = process.argv) {
  return (
    argvLocale(argv) ||
    parseLocaleLike(process.env.COHERENCE_LOCALE) ||
    readConfigLocale() ||
    parseLocaleLike(process.env.LC_ALL) ||
    parseLocaleLike(process.env.LC_MESSAGES) ||
    parseLocaleLike(process.env.LANG) ||
    DEFAULT_LOCALE
  );
}

/** Strip --lang/--lang=X from argv so downstream parsing doesn't trip on it. */
export function stripLangFlag(argv) {
  const out = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--lang") {
      i += 1; // skip value
      continue;
    }
    if (typeof argv[i] === "string" && argv[i].startsWith("--lang=")) continue;
    out.push(argv[i]);
  }
  return out;
}

function lookup(tree, key) {
  const parts = key.split(".");
  let current = tree;
  for (const p of parts) {
    if (!current || typeof current !== "object") return undefined;
    current = current[p];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(template, params) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) => {
    const v = params[k];
    return v === undefined ? `{${k}}` : String(v);
  });
}

/**
 * Create a translator bound to a locale.
 * Returns t(key, params?) that does message lookup with English fallback.
 */
export function createT(lang) {
  const target = loadBundle(lang);
  const fallback = lang === DEFAULT_LOCALE ? target : loadBundle(DEFAULT_LOCALE);
  return (key, params) => {
    const hit = (target && lookup(target, key)) || (fallback && lookup(fallback, key));
    if (hit === undefined) return key;
    return interpolate(hit, params);
  };
}

export const DEFAULT = DEFAULT_LOCALE;
export { SUPPORTED };
